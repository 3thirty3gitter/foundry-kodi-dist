"""Small anonymous HTTPS client; cache and backoff stay on the user's device."""
import hashlib
import json
import math
import os
import tempfile
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, build_opener

HOST = 'api.weather.gc.ca'
BASE = 'https://' + HOST
COLLECTION = '/collections/citypageweather-realtime'
CATALOGUE = COLLECTION + '/items?f=json&limit=1000&properties=identifier%2Cname.en%2Cname.fr'
MAX_BYTES = 4 * 1024 * 1024
SCHEMA = 1


class WeatherError(Exception):
    pass


class PayloadError(WeatherError):
    pass


class AllowedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != 'https' or parsed.hostname != HOST or parsed.port not in (None, 443):
            raise WeatherError('Unexpected redirect refused')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def transport(path, headers):
    if not path.startswith(COLLECTION + '/') or '\\' in path or '..' in path:
        raise WeatherError('Invalid endpoint')
    request = Request(BASE + path, headers=headers)
    # Default urllib HTTPS handler verifies certificates. No secrets or cookies.
    with build_opener(AllowedRedirect()).open(request, timeout=12) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise PayloadError('Response exceeded size limit')
        return response.status, dict(response.headers.items()), body


def atomic_json(path, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.weather-', dir=os.path.dirname(path))
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(document, handle, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def retry_delay(value, now):
    try:
        return min(86400, max(60, int(value)))
    except (TypeError, ValueError):
        try:
            from email.utils import parsedate_to_datetime
            return min(86400, max(60, int(parsedate_to_datetime(value).timestamp() - now)))
        except (TypeError, ValueError, OverflowError):
            return None


class Client:
    def __init__(self, cache_directory, fetch=transport, clock=time.time):
        self.directory = cache_directory
        self.fetch = fetch
        self.clock = clock

    def _file(self, path):
        return os.path.join(self.directory, hashlib.sha256(path.encode('utf-8')).hexdigest() + '.json')

    def get(self, path, validate, ttl=900, max_stale=21600):
        """Return (payload, fetch timestamp, stale, reason); never fake fresh data."""
        now = self.clock()
        filename = self._file(path)
        cached = {}
        try:
            with open(filename, encoding='utf-8') as handle:
                cached = json.load(handle)
            if not isinstance(cached, dict):
                raise ValueError('Invalid cache envelope')
            if cached.get('schema') != SCHEMA:
                cached = {}
            for key in ('fetched_at', 'retry_at'):
                value = cached.get(key, 0)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError('Invalid cache timestamp')
            failures = cached.get('failures', 0)
            if isinstance(failures, bool) or not isinstance(failures, int) or not 0 <= failures <= 6:
                raise ValueError('Invalid cache failure count')
            if cached.get('fetched_at', 0) > now + 300:
                raise ValueError('Cache timestamp is in the future')
            for key in ('etag', 'last_modified'):
                if not isinstance(cached.get(key, ''), str):
                    raise ValueError('Invalid cache header')
            if 'payload' in cached:
                validate(cached['payload'])
        except (OSError, ValueError, TypeError, WeatherError):
            cached = {}
        age = max(0, now - cached.get('fetched_at', 0))
        usable = 'payload' in cached and age <= max_stale
        if usable and age < ttl:
            return cached['payload'], cached['fetched_at'], False, 'cached'
        if cached.get('retry_at', 0) > now:
            if usable:
                return cached['payload'], cached['fetched_at'], True, 'backoff'
            raise WeatherError('Temporarily unavailable; retry is deferred')
        headers = {'User-Agent': 'FoundryCanadaWeather/0.1 (Kodi 21; personal weather display)',
                   'Accept': 'application/geo+json, application/json'}
        if cached.get('etag'):
            headers['If-None-Match'] = cached['etag']
        if cached.get('last_modified'):
            headers['If-Modified-Since'] = cached['last_modified']
        delay = None
        response_headers = {}
        try:
            try:
                status, response_headers, body = self.fetch(path, headers)
            except HTTPError as error:
                if error.code == 304 and usable:
                    status, body = 304, b''
                    response_headers = dict(error.headers.items())
                else:
                    if error.code in (429, 503):
                        delay = retry_delay(error.headers.get('Retry-After'), now)
                    raise
            response_headers = {k.lower(): v for k, v in response_headers.items()}
            if status == 304 and usable:
                payload = cached['payload']
            elif status == 200:
                if len(body) > MAX_BYTES:
                    raise PayloadError('Response exceeded size limit')
                payload = json.loads(body.decode('utf-8'))
                validate(payload)
            else:
                raise WeatherError('Unexpected HTTP status')
            entry = {'schema': SCHEMA, 'payload': payload, 'fetched_at': now,
                     'etag': response_headers.get('etag', cached.get('etag', '')),
                     'last_modified': response_headers.get('last-modified', cached.get('last_modified', '')),
                     'failures': 0, 'retry_at': 0}
            atomic_json(filename, entry)
            return payload, now, False, 'fresh'
        except (OSError, ValueError, TypeError, WeatherError, URLError):
            failures = min(6, cached.get('failures', 0) + 1)
            cached.update(schema=SCHEMA, failures=failures,
                          retry_at=now + (delay or min(3600, 60 * 2 ** (failures - 1))))
            try:
                atomic_json(filename, cached)
            except OSError:
                pass
            if usable:
                return cached['payload'], cached['fetched_at'], True, 'offline'
            raise WeatherError('Weather is unavailable and no recent cache exists')
