"""Debounced OMDb enrichment for the currently focused Kodi media item."""
import re
import time
from threading import Thread, RLock

import xbmc
import xbmcaddon
import xbmcvfs

from ..apis.omdb import FIELDS, OmdbCache, OmdbClient, clean, lookup_key


class OmdbMonitor:
    def __init__(self, home_window, cache=None, clock=time.monotonic, client_factory=OmdbClient):
        self.window, self.clock, self.client_factory = home_window, clock, client_factory
        self.addon = xbmcaddon.Addon("script.foundry.slate.helper")
        self.cache = cache or OmdbCache(xbmcvfs.translatePath("special://profile/addon_data/script.foundry.slate.helper/omdb.sqlite"))
        self.config = None
        self.generation = 0
        self.current = ""
        self.changed_at = 0
        self.retry_after = {}
        self.worker = None
        self.stopped = False
        self.displayed = None
        self.state_lock = RLock()
        self.current_owner = ("", "", "")

    def _set(self, name, value):
        self.window.setProperty("foundry.slate.omdb." + name, str(value))

    def _clear(self, status="disabled"):
        self.displayed = None
        for name in FIELDS:
            self.window.clearProperty("foundry.slate.omdb." + name)
        for name in ("owner_label", "owner_year", "owner_type"):
            self.window.clearProperty("foundry.slate.omdb." + name)
        self._set("status", status)

    def _read_config(self):
        enabled = self.addon.getSettingBool("omdb_enabled")
        key = self.addon.getSetting("omdb_api_key").strip() if enabled else ""
        current = (enabled, key)
        self._set("show_rotten_tomatoes", str(self.addon.getSettingBool("omdb_show_rotten_tomatoes")).lower())
        self._set("show_metacritic", str(self.addon.getSettingBool("omdb_show_metacritic")).lower())
        if current != self.config:
            self.generation += 1
            self.config = current
            self.cache.configure(enabled, key)
            self.client = self.client_factory(key)
            self.current = ""
            self.retry_after.clear()
            self._clear("missing_key" if enabled else "disabled")
        return enabled and bool(key)

    def _meta(self):
        info = xbmc.getInfoLabel
        kind = info("ListItem.DBTYPE").lower()
        if kind not in {"movie", "tvshow", "season", "episode"}:
            return {}
        title = info("ListItem.Title") or info("ListItem.Label")
        if kind == "season":
            title = info("ListItem.TVShowTitle") or title
        year = info("ListItem.Year")
        return {"imdb_id": info("ListItem.IMDBNumber") or info("ListItem.Property(imdb)"), "title": title,
                "year": year if re.fullmatch(r"\d{4}", year) else "",
                "type": "movie" if kind == "movie" else "episode" if kind == "episode" else "series"}

    def _publish(self, payload, status):
        identity = (self.current, self.current_owner, status, tuple((name, clean(payload.get(name))) for name in FIELDS))
        if self.displayed == identity:
            return
        self._clear(status)
        for name, value in zip(("owner_label", "owner_year", "owner_type"), self.current_owner):
            self._set(name, value)
        for name in FIELDS:
            value = clean(payload.get(name))
            if value:
                self._set(name, value)
        self.displayed = identity

    def process_current_item(self):
        with self.state_lock:
            self._process_current_item()

    def refresh_config(self):
        with self.state_lock:
            if not self.stopped:
                self._read_config()

    def _process_current_item(self):
        if self.stopped:
            return
        if not self._read_config():
            return
        owner = tuple(xbmc.getInfoLabel(label) for label in ("ListItem.Label", "ListItem.Year", "ListItem.DBTYPE"))
        meta = self._meta()
        if owner != tuple(xbmc.getInfoLabel(label) for label in ("ListItem.Label", "ListItem.Year", "ListItem.DBTYPE")):
            return  # Focus moved while collecting native metadata.
        item = lookup_key(meta)
        self.current_owner = owner
        if item != self.current:
            self.current, self.changed_at = item, self.clock()
            self._clear("loading" if item else "unavailable")
        if not item:
            return
        cached = self.cache.get(item)
        if cached is not None:
            self._publish(cached, "ready" if cached else "not_found")
            return
        if self.clock() - self.changed_at < .2 or self.clock() < self.retry_after.get(item, 0):
            return
        if self.cache.blocked_until() > self.cache.clock():
            self._publish(self.cache.get(item, stale=True) or {}, self.cache.blocked_status())
            return
        if self.worker and self.worker.is_alive():
            return
        self.worker = Thread(target=self._fetch, args=(item, meta, self.generation, self.client), daemon=True)
        self.worker.start()

    def _fetch(self, item, meta, generation, client):
        payload, status, backoff = client.fetch(meta)
        with self.state_lock:
            self._complete_fetch(item, generation, payload, status, backoff)

    def _complete_fetch(self, item, generation, payload, status, backoff):
        if self.stopped or generation != self.generation:
            return
        if status == "ready":
            self.cache.put(item, payload)
        elif status == "not_found":
            self.cache.put(item, {}, ttl=15 * 60)
        else:
            self.retry_after[item] = self.clock() + max(30, backoff)
            if status in {"rate_limited", "invalid_key", "offline"}:
                self.cache.block(max(30, backoff), status)
            payload = self.cache.get(item, stale=True) or {}
        if item == self.current and generation == self.generation and not self.stopped:
            self._publish(payload, status)

    def stop(self):
        with self.state_lock:
            self.stopped = True
            self.generation += 1
