"""Offline tests: optional OMDb ratings, cache ownership and stale requests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import requests
import test_release as kodi

from modules.apis.omdb import OmdbClient, OmdbCache, lookup_key
from modules.monitors.omdb import OmdbMonitor


class Clock:
    value = 1000.0
    def __call__(self): return self.value


def reply(data=None, status=200, headers=None):
    response = Mock(status_code=status, headers=headers or {})
    response.json.return_value = data or {}
    return response


class OmdbApi(unittest.TestCase):
    def test_missing_key_is_disabled_without_network(self):
        session = Mock()
        self.assertEqual(OmdbClient("", session).fetch({"title": "Example"})[1], "missing_key")
        session.get.assert_not_called()

    def test_https_keyed_id_lookup_and_bounded_timeout(self):
        session = Mock(); session.get.return_value = reply({"Response": "True", "imdbID": "tt1234567", "imdbRating": "8.2", "imdbVotes": "12,345", "Plot": "Example plot"})
        payload, status, _ = OmdbClient("test-key", session).fetch({"imdb_id": "tt1234567"})
        self.assertEqual((status, payload["imdb_rating"]), ("ready", "8.2/10"))
        self.assertEqual(payload["imdb_votes"], "12,345")
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], "https://www.omdbapi.com/")
        self.assertEqual(kwargs["timeout"], (8, 15))
        self.assertEqual(kwargs["params"]["i"], "tt1234567")
        self.assertNotIn("t", kwargs["params"])

    def test_fallback_disambiguates_title_year_and_type(self):
        session = Mock(); session.get.return_value = reply({"Response": "True"})
        OmdbClient("test-key", session).fetch({"title": "Example", "year": "2025", "type": "series"})
        params = session.get.call_args.kwargs["params"]
        self.assertEqual((params["t"], params["y"], params["type"]), ("Example", "2025", "series"))
        self.assertNotEqual(lookup_key({"title": "Example", "year": "2025", "type": "series"}), lookup_key({"title": "Example", "year": "2024", "type": "movie"}))

    def test_na_and_invalid_ratings_are_omitted(self):
        for rating in ("N/A", "", "0", "11", "garbage"):
            session = Mock(); session.get.return_value = reply({"Response": "True", "imdbRating": rating, "Plot": "N/A", "Ratings": [{"Source": "Rotten Tomatoes", "Value": "N/A"}, {"Source": "Metacritic", "Value": "101/100"}]})
            payload, _, _ = OmdbClient("test-key", session).fetch({"title": "Example"})
            self.assertNotIn("imdb_rating", payload)
            self.assertNotIn("rotten_tomatoes", payload)
            self.assertNotIn("metacritic", payload)
            self.assertEqual(payload["plot"], "")

    def test_optional_rt_and_metacritic_are_separate_sources(self):
        session = Mock(); session.get.return_value = reply({"Ratings": [{"Source": "Rotten Tomatoes", "Value": "78%"}, {"Source": "Metacritic", "Value": "64/100"}]})
        payload, _, _ = OmdbClient("test-key", session).fetch({"title": "Example"})
        self.assertEqual((payload["rotten_tomatoes"], payload["metacritic"]), ("78%", "64/100"))

    def test_daily_quota_and_http_rate_limit_have_global_backoff(self):
        session = Mock(); session.get.return_value = reply({"Response": "False", "Error": "Request limit reached!"})
        self.assertEqual(OmdbClient("test-key", session).fetch({"title": "Example"})[1:], ("rate_limited", 86400))
        session.get.return_value = reply(status=429, headers={"Retry-After": "120"})
        self.assertEqual(OmdbClient("test-key", session).fetch({"title": "Example"})[1:], ("rate_limited", 120))

    def test_invalid_key_not_found_and_offline_are_distinct(self):
        session = Mock()
        for data, expected in (({"Response": "False", "Error": "Invalid API key!"}, "invalid_key"), ({"Response": "False", "Error": "Movie not found!"}, "not_found")):
            session.get.return_value = reply(data)
            self.assertEqual(OmdbClient("test-key", session).fetch({"title": "Example"})[1], expected)
        session.get.side_effect = requests.Timeout("URL includes secret-test-key")
        with patch("xbmc.log") as log:
            self.assertEqual(OmdbClient("secret-test-key", session).fetch({"title": "Example"})[1], "offline")
            log.assert_not_called()

    def test_malformed_json_does_not_break_browsing(self):
        session = Mock(); response = reply(); response.json.side_effect = ValueError("invalid response")
        session.get.return_value = response
        self.assertEqual(OmdbClient("test-key", session).fetch({"title": "Example"})[1], "offline")


class OmdbState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = Clock()
        self.cache = OmdbCache(Path(self.tmp.name) / "omdb.sqlite", self.clock)
        self.settings = {"omdb_enabled": True, "omdb_api_key": "test-key"}
        addon = Mock()
        addon.getSettingBool.side_effect = lambda key: bool(self.settings.get(key, False))
        addon.getSetting.side_effect = lambda key: str(self.settings.get(key, ""))
        self.window = kodi.Window(); self.window.values.clear()
        with patch("xbmcaddon.Addon", return_value=addon):
            self.monitor = OmdbMonitor(self.window, self.cache, self.clock, Mock(return_value=Mock()))
        self.labels = {"ListItem.DBTYPE": "movie", "ListItem.Label": "Example", "ListItem.Title": "Example", "ListItem.Year": "2025", "ListItem.IMDBNumber": "tt1234567"}
        self.info_patch = patch("xbmc.getInfoLabel", side_effect=lambda key: self.labels.get(key, ""))
        self.info_patch.start(); self.addCleanup(self.info_patch.stop)

    def test_ttl_bounded_stale_cache_and_negative_cache(self):
        self.cache.configure(True, "test-key")
        self.cache.put("x", {"imdb_rating": "8/10"}, ttl=10)
        self.clock.value += 11
        self.assertIsNone(self.cache.get("x"))
        self.assertEqual(self.cache.get("x", stale=True)["imdb_rating"], "8/10")
        self.clock.value += 31 * 86400
        self.assertIsNone(self.cache.get("x", stale=True))
        self.cache.put("missing", {}, ttl=900)
        self.assertEqual(self.cache.get("missing"), {})

    def test_key_change_and_removal_invalidate_provider_cache(self):
        self.cache.configure(True, "one")
        self.cache.put("x", {"imdb_rating": "8/10"})
        self.cache.configure(True, "two")
        self.assertIsNone(self.cache.get("x", stale=True))
        self.cache.put("x", {"imdb_rating": "8/10"})
        self.cache.configure(False, "")
        self.assertIsNone(self.cache.get("x", stale=True))
        self.assertNotIn(b"test-key", Path(self.cache.path).read_bytes())

    def test_debounce_and_cached_results_do_not_repeat_http(self):
        with patch("modules.monitors.omdb.Thread") as thread:
            self.monitor.process_current_item()
            thread.assert_not_called()
            self.clock.value += .19
            self.monitor.process_current_item()
            thread.assert_not_called()
            self.clock.value += .03
            self.monitor.process_current_item()
            thread.assert_called_once()
        self.cache.put("imdb:tt1234567", {"imdb_rating": "8/10"})
        self.monitor.process_current_item()
        self.assertEqual(self.window.getProperty("foundry.omdb.imdb_rating"), "8/10")

    def test_stale_focus_response_cannot_replace_new_item(self):
        self.monitor._read_config()
        self.monitor.current = "imdb:tt2222222"
        self.monitor._complete_fetch("imdb:tt1234567", self.monitor.generation, {"imdb_rating": "8/10"}, "ready", 0)
        self.assertEqual(self.window.getProperty("foundry.omdb.imdb_rating"), "")
        self.assertEqual(self.cache.get("imdb:tt1234567")["imdb_rating"], "8/10")

    def test_key_removal_discards_inflight_response(self):
        self.monitor._read_config(); generation = self.monitor.generation
        self.monitor.current = "imdb:tt1234567"
        self.settings["omdb_api_key"] = ""
        self.monitor._read_config()
        self.monitor._complete_fetch("imdb:tt1234567", generation, {"imdb_rating": "8/10"}, "ready", 0)
        self.assertIsNone(self.cache.get("imdb:tt1234567", stale=True))
        self.assertEqual(self.window.getProperty("foundry.omdb.status"), "missing_key")

    def test_global_quota_blocks_new_titles_and_offline_keeps_cached_metadata(self):
        self.monitor._read_config(); self.monitor.current = "imdb:tt1234567"
        self.cache.put(self.monitor.current, {"imdb_rating": "8/10"}, ttl=1)
        self.clock.value += 2
        self.monitor._complete_fetch(self.monitor.current, self.monitor.generation, {}, "offline", 30)
        self.assertEqual(self.window.getProperty("foundry.omdb.imdb_rating"), "8/10")
        self.assertEqual(self.cache.blocked_status(), "offline")
        self.monitor._complete_fetch(self.monitor.current, self.monitor.generation, {}, "rate_limited", 3600)
        self.labels["ListItem.IMDBNumber"] = "tt2222222"
        with patch("modules.monitors.omdb.Thread") as thread:
            self.monitor.process_current_item(); self.clock.value += .3; self.monitor.process_current_item()
            thread.assert_not_called()
        self.assertEqual(self.window.getProperty("foundry.omdb.status"), "rate_limited")

    def test_disabled_provider_does_not_request_or_retain_ratings(self):
        self.settings["omdb_enabled"] = False
        with patch("modules.monitors.omdb.Thread") as thread:
            self.monitor.process_current_item()
            thread.assert_not_called()
        self.assertEqual(self.window.getProperty("foundry.omdb.status"), "disabled")

    def test_settings_callback_invalidates_cache_without_active_browsing(self):
        self.monitor.refresh_config()
        self.cache.put("imdb:tt1234567", {"imdb_rating": "8.0/10"})
        self.settings["omdb_enabled"] = False
        self.monitor.refresh_config()
        self.assertIsNone(self.cache.get("imdb:tt1234567", stale=True))

    def test_focus_change_during_metadata_snapshot_starts_no_lookup(self):
        reads = [0]
        def info(name):
            if name == "ListItem.Label":
                reads[0] += 1
                return "First" if reads[0] == 1 else "Second"
            return self.labels.get(name, "")
        with patch("xbmc.getInfoLabel", side_effect=info), patch("modules.monitors.omdb.Thread") as thread:
            self.monitor.process_current_item()
            thread.assert_not_called()
        self.assertEqual(self.monitor.current, "")


if __name__ == "__main__":
    unittest.main()
