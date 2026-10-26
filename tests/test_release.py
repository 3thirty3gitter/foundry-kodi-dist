"""Package and helper regression checks; no Kodi device is required."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
SKIN = WORK / "skin.foundry-nimbus"
HELPER = WORK / "script.foundry.helper"
sys.path.insert(0, str(HELPER / "resources/lib"))
sys.path.insert(0, str(WORK / "test-deps"))
TEMP = tempfile.TemporaryDirectory()
PROFILE = Path(TEMP.name)


class Window:
    values = {}
    def __init__(self, *args): pass
    def getProperty(self, key): return self.values.get(key, "")
    def setProperty(self, key, value): self.values[key] = str(value)
    def clearProperty(self, key): self.values.pop(key, None)


class Dialog:
    def yesno(self, *args, **kwargs): return True
    def ok(self, *args): pass
    def notification(self, *args): pass
    def select(self, *args, **kwargs): return -1


class Monitor:
    def __init__(self): self.aborted = False
    def abortRequested(self): return self.aborted
    def waitForAbort(self, seconds):
        time.sleep(min(seconds, .01))
        return self.aborted


def translate(path):
    if path.startswith("special://skin/"):
        return str(SKIN / path[len("special://skin/"):])
    for prefix in ("special://profile/", "special://userdata/", "special://home/"):
        if path.startswith(prefix): return str(PROFILE / path[len(prefix):])
    return path


def rpc_default(request):
    request = json.loads(request)
    if request["method"] == "Settings.SetSettingValue": return json.dumps({"result": True})
    return json.dumps({"result": "OK"})


xbmc = types.ModuleType("xbmc")
xbmc.Monitor = Monitor
xbmc.LOGINFO, xbmc.LOGERROR = 1, 3
xbmc.log = lambda *args, **kwargs: None
xbmc.sleep = lambda millis: None
xbmc.executebuiltin = lambda *args: None
xbmc.executeJSONRPC = rpc_default
xbmc.getInfoLabel = lambda *args: ""
xbmc.getSkinDir = lambda: "skin.foundry"
xbmc.getCondVisibility = lambda *args: False
xbmc.getLocalizedString = lambda code: str(code)
xbmcgui = types.ModuleType("xbmcgui")
xbmcgui.Window, xbmcgui.Dialog = Window, Dialog
xbmcgui.ListItem = type("ListItem", (), {})
xbmcgui.WindowXMLDialog = type("WindowXMLDialog", (), {})
xbmcgui.NOTIFICATION_INFO = 0
xbmcgui.getCurrentWindowId = lambda: 10000
xbmcvfs = types.ModuleType("xbmcvfs")
xbmcvfs.translatePath = translate
xbmcvfs.exists = lambda path: Path(translate(path)).exists()
xbmcvfs.mkdir = xbmcvfs.mkdirs = lambda path: Path(translate(path)).mkdir(parents=True, exist_ok=True)
xbmcvfs.File = lambda path, mode="r": open(translate(path), mode)
xbmcvfs.copy = lambda source, dest: shutil.copyfile(translate(source), translate(dest)) or True
xbmcaddon = types.ModuleType("xbmcaddon")
class Addon:
    def __init__(self, id="script.foundry.helper"): self.id = id
    def getAddonInfo(self, key):
        return {"id": self.id, "version": "1.0.1", "path": str(HELPER), "name": "Foundry"}.get(key, "")
xbmcaddon.Addon = Addon
sys.modules.update(xbmc=xbmc, xbmcgui=xbmcgui, xbmcvfs=xbmcvfs, xbmcaddon=xbmcaddon)


class Packages(unittest.TestCase):
    def test_feed_zip_checksums_and_manifest_match(self):
        feed = (ROOT / "addons.xml").read_bytes()
        self.assertEqual(hashlib.md5(feed).hexdigest(), (ROOT / "addons.xml.md5").read_text().strip())
        for addon in ET.fromstring(feed):
            aid, version = addon.get("id"), addon.get("version")
            path = ROOT / aid / (aid + "-" + version + ".zip")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), Path(str(path) + ".sha256").read_text().strip())
            with zipfile.ZipFile(path) as bundle:
                self.assertIsNone(bundle.testzip())
                self.assertEqual({n.split("/")[0] for n in bundle.namelist()}, {aid})
                manifest = ET.fromstring(bundle.read(aid + "/addon.xml"))
                normalize = lambda e: (e.tag, e.attrib, (e.text or "").strip(), [normalize(child) for child in e])
                self.assertEqual(normalize(addon), normalize(manifest))
                for ext in manifest.findall("extension"):
                    if ext.get("library"): self.assertIn(aid + "/" + ext.get("library"), bundle.namelist())
                for asset in manifest.findall("./extension/assets/*"):
                    self.assertIn(aid + "/" + asset.text, bundle.namelist())

    def test_dependency_closure(self):
        addons = {a.get("id"): a for a in ET.parse(ROOT / "addons.xml").getroot()}
        official = {"xbmc.gui", "xbmc.python", "script.module.requests", "script.module.pil"}
        visited = set()
        def visit(aid, stack=()):
            self.assertNotIn(aid, stack, "Dependency cycle")
            for dep in addons[aid].findall("./requires/import"):
                target = dep.get("addon")
                if target in official: continue
                self.assertIn(target, addons)
                version = lambda s: tuple(int(n) for n in s.split("."))
                self.assertGreaterEqual(version(addons[target].get("version")), version(dep.get("version")))
                visit(target, stack + (aid,))
            visited.add(aid)
        visit("script.program.foundry-build")
        self.assertTrue({"skin.foundry", "script.foundry.helper"}.issubset(visited))

    def test_all_python_xml_and_skin_references(self):
        for source in (SKIN, HELPER, ROOT / "src"):
            for path in source.rglob("*"):
                if path.suffix == ".py": ast.parse(path.read_text())
                elif path.suffix in {".xml", ".xsp"}: ET.parse(path)
        files = {p.name for p in (SKIN / "xml").glob("*.xml")}
        docs = [(p, ET.parse(p)) for p in (SKIN / "xml").glob("*.xml") if not p.name.endswith("-old.xml")]
        names = {e.get("name") for _, doc in docs for e in doc.findall("./include") if e.get("name")}
        for path, doc in docs:
            text = path.read_text()
            self.assertNotIn("script.nimbus.helper", text)
            self.assertNotIn("skin.nimbus", text)
            for ref in doc.iter("include"):
                if ref.get("file"): self.assertIn(ref.get("file"), files, path.name)
                target = ref.get("content") or (ref.text or "").strip()
                if target and "$" not in target: self.assertIn(target, names, path.name + ": " + target)
        for font in ET.parse(SKIN / "xml/Font.xml").findall(".//font/filename"):
            if font.text == "arial.ttf": continue  # Kodi's bundled Unicode fallback.
            self.assertTrue((SKIN / "fonts" / font.text).exists())


class Runtime(unittest.TestCase):
    def test_foundry_branding_and_development_routes_are_packaged(self):
        self.assertIn("foundry-logo.png", (SKIN / "xml/Home.xml").read_text())
        self.assertIn("Welcome to Foundry", (SKIN / "xml/Custom_1116_StartHelp.xml").read_text())
        self.assertNotIn("Welcome to Nimbus", (SKIN / "xml/Custom_1116_StartHelp.xml").read_text())
        self.assertIn("media/foundry-home-backdrop.png", (SKIN / "xml/Variables_Artwork.xml").read_text())
        self.assertIn("mode=ensure_repos", (SKIN / "xml/Includes_Home.xml").read_text())
        self.assertIn("mode=choose_search_provider", (SKIN / "xml/Custom_1121_SearchResults.xml").read_text())
        icon = (SKIN / "resources/icon.png").read_bytes()
        self.assertEqual(hashlib.sha1(b"blob " + str(len(icon)).encode() + b"\0" + icon).hexdigest(), "2011947cb44e329c5fb48b22a619fc910e21cf32")

    def test_bundled_repositories_install_offline_and_setup_is_idempotent(self):
        from modules import repo_installer as repos
        destination = PROFILE / "bundled-addons"
        registry = set()
        def register(ids):
            registry.update(ids)
            return []
        with patch.object(repos, "ADDONS_DIR", str(destination)), \
                patch.object(repos, "_has_addon", side_effect=lambda aid: aid in registry), \
                patch.object(repos, "install_repo", side_effect=AssertionError("Network fallback was unnecessary")), \
                patch.object(repos, "_register_repos", side_effect=register) as registrations:
            self.assertTrue(repos.ensure_repos())
            self.assertFalse(repos.ensure_repos())
            self.assertEqual(len(registry), 12)
            self.assertEqual(registrations.call_args_list[0].args[0], [p["addon_id"] for p in repos.REPOS])
            for repo in repos.REPOS:
                manifest = ET.parse(destination / repo["addon_id"] / "addon.xml").getroot()
                self.assertEqual(manifest.get("id"), repo["addon_id"])
        self.assertEqual(Window().getProperty("foundry.repos.installing"), "")

    def test_new_repositories_are_enabled(self):
        from modules import repo_installer as repos
        calls = []
        def rpc(request):
            calls.append(json.loads(request))
            return '{"result":"OK"}'
        with patch.object(repos, "_has_addon", return_value=True), patch.object(xbmc, "executeJSONRPC", side_effect=rpc):
            self.assertEqual(repos._register_repos(["repository.example"]), [])
        self.assertEqual([c["params"]["addonid"] for c in calls], ["repository.example"])
        self.assertTrue(calls[0]["params"]["enabled"])

    def test_search_provider_uses_only_installed_enabled_addons(self):
        from modules import search_provider
        with patch.object(xbmc, "getCondVisibility", side_effect=lambda value: "plugin.video.umbrella" in value), \
                patch.object(Dialog, "select", return_value=0), patch.object(xbmc, "executebuiltin") as execute:
            search_provider.choose_search_provider()
        execute.assert_called_once_with("Skin.SetString(current_search_provider,2)")

    def test_installer_refreshes_existing_foundry_skin(self):
        spec = importlib.util.spec_from_file_location("foundry_refresh", ROOT / "src/script.program.foundry-build/default.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(xbmc, "getSkinDir", return_value="skin.foundry"), patch.object(xbmc, "executebuiltin") as execute:
            module.main()
        execute.assert_called_once_with("ReloadSkin()")

    def test_helper_modules_import_on_clean_profile(self):
        import modules.router, modules.actions, modules.custom_actions
        import modules.cpath_maker, modules.search_utils, modules.version_monitor
        import modules.repo_installer, modules.monitors.image, modules.monitors.ratings
        import service
        service.Service()

    def test_widget_escaping_and_cancel(self):
        from modules.cpath_maker import CPaths
        from modules import xmls
        c = CPaths("movie.widget")
        c.refresh_cpaths = True
        captured = []
        c.write_xml = lambda path, content: captured.append(content)
        value = 'A & B "quoted" <movie>'
        url = 'plugin://test/?first=1&other="2"&amp;literal=yes'
        c.make_widget_xml({1: {"cpath_path": url, "cpath_header": value, "cpath_type": "WidgetListPoster", "cpath_label": value}})
        doc = ET.fromstring(captured[-1])
        values = {e.get("name"): e.get("value") for e in doc.findall(".//param")}
        self.assertEqual(values["widget_header"], value)
        self.assertEqual(values["content_path"], url)
        c.widget_type = lambda: None
        c.create_and_update_widget("movie.widget.1", url, value)
        c.path_browser = lambda: None
        with patch("modules.cpath_maker.files_get_directory", return_value=None):
            # No installed providers must present an empty picker safely.
            CPaths("movie.widget").path_browser()
        c.dbcon.close()

    def test_cache_size_counts_nested_bytes(self):
        from modules.helper import calculate_cache_size
        path = PROFILE / "size-test"
        (path / "nested").mkdir(parents=True, exist_ok=True)
        (path / "a").write_bytes(b"a" * 1024)
        (path / "nested/b").write_bytes(b"b" * 2048)
        self.assertEqual(calculate_cache_size(str(path)), 3072 / (1024 * 1024))
        self.assertEqual(calculate_cache_size(str(path / "missing")), 0)

    def test_search_history_survives_restart(self):
        from modules.search_utils import SPaths
        a = SPaths()
        a.search_input("Foundry & Kodi / test")
        a.dbcon.close()
        Window.values.clear()
        b = SPaths()
        b.refresh_search_history()
        self.assertEqual(Window().getProperty("nimbus.search.history.1"), "Foundry & Kodi / test")
        b.dbcon.close()

    def test_repo_presence_parses_rpc_errors_and_rejects_unsafe_zip(self):
        from modules.repo_installer import _has_addon, _extract_to_addons
        with patch.object(xbmc, "executeJSONRPC", return_value='{"error":{"code":-32602}}'):
            self.assertFalse(_has_addon("repository.test"))
        with patch.object(xbmc, "executeJSONRPC", return_value='{"result":{"addon":{"addonid":"repository.test"}}}'):
            self.assertTrue(_has_addon("repository.test"))
        path = PROFILE / "unsafe.zip"
        with zipfile.ZipFile(path, "w") as bundle: bundle.writestr("repository.test/../../outside.txt", "bad")
        with self.assertRaises(ValueError): _extract_to_addons(str(path), "repository.test")

    def test_ratings_database_optional_year(self):
        from modules.databases.ratings import RatingsDatabase
        db = RatingsDatabase()
        db.cache_ids("Example", None, "movie", "tt123", "123")
        self.assertEqual(db.get_cached_ids("Example", None, "movie"), ("tt123", "123"))
        db.update_ratings("tt123", {"imdbid": "tt123", "imdbRating": "8.0"})
        self.assertEqual(db.get_cached_ratings("tt123")["imdbRating"], "8.0")

    def test_network_session_has_deadline(self):
        from modules.apis.base import BoundedSession
        import requests
        with patch.object(requests.Session, "request", return_value=None) as request:
            BoundedSession().get("https://example.invalid/")
            self.assertEqual(request.call_args.kwargs["timeout"], (5, 10))

    def test_image_monitor_stops_on_kodi_shutdown(self):
        from modules.monitors.image import ImageMonitor
        monitor = Monitor()
        monitor.aborted = True
        with patch.object(xbmc, "Monitor", return_value=monitor):
            thread = ImageMonitor(lambda **kwargs: None)
            thread.start()
            thread.join(timeout=1)
            self.assertFalse(thread.is_alive())

    def test_native_skin_activation(self):
        spec = importlib.util.spec_from_file_location("foundry_build", ROOT / "src/script.program.foundry-build/default.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        requests = []
        def rpc(request):
            data = json.loads(request)
            requests.append(data)
            return json.dumps({"result": True if data["method"] == "Settings.SetSettingValue" else "OK"})
        with patch.object(xbmc, "getSkinDir", return_value="skin.estuary"), patch.object(xbmc, "executeJSONRPC", side_effect=rpc):
            module.main()
        self.assertEqual(requests[-1]["params"], {"setting": "lookandfeel.skin", "value": "skin.foundry"})


if __name__ == "__main__":
    unittest.main()
