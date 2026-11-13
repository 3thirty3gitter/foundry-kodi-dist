"""Optional, user-keyed OMDb enrichment. No direct IMDb API or scraping."""
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from threading import Lock
from contextlib import contextmanager

import requests


FIELDS = ("imdb_rating", "imdb_votes", "rotten_tomatoes", "metacritic", "title",
          "plot", "released", "certification", "genres", "language", "studio", "imdb_id")


def clean(value):
    text = str(value or "").strip()
    return "" if text.lower() in {"n/a", "none", "null"} else text


def lookup_key(meta):
    imdb = clean(meta.get("imdb_id"))
    if re.fullmatch(r"tt\d{5,12}", imdb):
        return "imdb:" + imdb
    title = " ".join(clean(meta.get("title")).casefold().split())
    if not title:
        return ""
    return json.dumps([meta.get("type", "movie"), title, clean(meta.get("year"))], ensure_ascii=True)


class OmdbCache:
    """Profile-local cache. Key changes/removal invalidate all provider data."""
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS omdb (item TEXT PRIMARY KEY, payload TEXT, expires REAL, stale_until REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS omdb_state (name TEXT PRIMARY KEY, value TEXT)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def configure(self, enabled, key):
        # Fingerprint is used only for local cache ownership; never store the key.
        owner = hashlib.sha256(key.encode()).hexdigest() if enabled and key else ""
        with self.lock, self._connect() as db:
            old = db.execute("SELECT value FROM omdb_state WHERE name='owner'").fetchone()
            if not old or old[0] != owner or not owner:
                db.execute("DELETE FROM omdb")
                db.execute("DELETE FROM omdb_state")
                db.execute("INSERT INTO omdb_state VALUES ('owner', ?)", (owner,))

    def get(self, item, stale=False):
        with self.lock, self._connect() as db:
            row = db.execute("SELECT payload, expires, stale_until FROM omdb WHERE item=?", (item,)).fetchone()
        if row and self.clock() < row[2 if stale else 1]:
            try:
                return json.loads(row[0])
            except (ValueError, TypeError):
                pass
        return None

    def put(self, item, payload, ttl=7 * 86400):
        now = self.clock()
        with self.lock, self._connect() as db:
            db.execute("INSERT OR REPLACE INTO omdb VALUES (?,?,?,?)", (item, json.dumps(payload), now + ttl, now + (30 * 86400 if payload else ttl)))
            db.execute("DELETE FROM omdb WHERE stale_until < ?", (now,))
            # Bound disk growth even when browsing very large catalogs.
            db.execute("DELETE FROM omdb WHERE item IN (SELECT item FROM omdb ORDER BY expires DESC LIMIT -1 OFFSET 2000)")

    def blocked_until(self):
        with self.lock, self._connect() as db:
            row = db.execute("SELECT value FROM omdb_state WHERE name='blocked_until'").fetchone()
        return float(row[0]) if row else 0

    def blocked_status(self):
        with self.lock, self._connect() as db:
            row = db.execute("SELECT value FROM omdb_state WHERE name='blocked_status'").fetchone()
        return row[0] if row else "rate_limited"

    def block(self, seconds, status="rate_limited"):
        with self.lock, self._connect() as db:
            db.execute("INSERT OR REPLACE INTO omdb_state VALUES ('blocked_until', ?)", (str(self.clock() + seconds),))
            db.execute("INSERT OR REPLACE INTO omdb_state VALUES ('blocked_status', ?)", (status,))


class OmdbClient:
    URL = "https://www.omdbapi.com/"

    def __init__(self, key, session=None):
        self.key = key
        self.session = session or requests.Session()

    def fetch(self, meta):
        """Return (payload, status, global_backoff_seconds), with sanitized errors."""
        if not self.key:
            return {}, "missing_key", 0
        params = {"apikey": self.key, "r": "json", "plot": "short"}
        imdb = clean(meta.get("imdb_id"))
        if re.fullmatch(r"tt\d{5,12}", imdb):
            params["i"] = imdb
        else:
            if not clean(meta.get("title")):
                return {}, "not_found", 0
            params.update(t=clean(meta["title"]), type=meta.get("type", "movie"))
            year = clean(meta.get("year"))
            if re.fullmatch(r"\d{4}", year):
                params["y"] = year
        for field in ('season', 'episode'):
            value = meta.get(field)
            if value is not None and re.fullmatch(r'\d+', str(value)):
                params[field.title()] = int(value)
        try:
            response = self.session.get(self.URL, params=params, timeout=(8, 15))
            if response.status_code == 429:
                try:
                    wait = max(30, min(86400, int(response.headers.get("Retry-After", "3600"))))
                except (TypeError, ValueError):
                    wait = 3600
                return {}, "rate_limited", wait
            if response.status_code in (401, 403):
                return {}, "invalid_key", 86400
            if response.status_code != 200:
                return {}, "offline", 30
            data = response.json()
            if not isinstance(data, dict) or not data:
                return {}, "offline", 30
            if str(data.get("Response", "True")).lower() == "false":
                error = str(data.get("Error", "")).lower()
                if "limit" in error:
                    return {}, "rate_limited", 86400
                if "api key" in error or "apikey" in error:
                    return {}, "invalid_key", 86400
                return {}, "not_found", 0
            result = {"imdb_id": clean(data.get("imdbID"))}
            mapping = {"Title": "title", "Plot": "plot", "Released": "released", "Rated": "certification", "Genre": "genres", "Language": "language", "Production": "studio", "imdbVotes": "imdb_votes"}
            result.update({target: clean(data.get(source)) for source, target in mapping.items()})
            result.update({target: clean(data.get(source)) for source,target in
                           [('Year','year'),('Type','media_type'),('Season','season'),('Episode','episode'),('Country','country')]})
            for source,target in [('Actors','cast'),('Director','director'),('Writer','writer')]:
                result[target] = [name.strip() for name in clean(data.get(source)).split(',') if name.strip()]
            runtime = re.fullmatch(r'(\d+) min', clean(data.get('Runtime')))
            if runtime:
                result['runtime'] = int(runtime[1]) * 60
            rating = clean(data.get("imdbRating"))
            try:
                number = float(rating)
                if 0 < number <= 10:
                    result["imdb_rating"] = rating + "/10"
            except (ValueError, TypeError):
                pass
            for rating in data.get("Ratings", []) if isinstance(data.get("Ratings"), list) else []:
                if not isinstance(rating, dict):
                    continue
                source, value = rating.get("Source"), clean(rating.get("Value"))
                if source == "Rotten Tomatoes" and re.fullmatch(r"\d{1,3}%", value) and int(value[:-1]) <= 100:
                    result["rotten_tomatoes"] = value
                elif source == "Metacritic" and re.fullmatch(r"\d{1,3}/100", value) and int(value.split("/")[0]) <= 100:
                    result["metacritic"] = value
            score = clean(data.get('Metascore'))
            if 'metacritic' not in result and score.isdigit() and 0 <= int(score) <= 100:
                result['metacritic'] = score + '/100'
            return result, "ready", 0
        except (requests.RequestException, ValueError, TypeError):
            # Exception strings may contain the request URL and API key.
            return {}, "offline", 30
