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
    if path.startswith("resource://"):
        addon, relative = path[len("resource://"):].split("/", 1)
        return str(ROOT / "src" / addon / "resources" / relative)
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
        addons = {a.get("id"): a for a in ET.parse(ROOT / "tests/fixtures/upstream-addons.xml").getroot()}
        addons.update({a.get("id"): a for a in ET.parse(ROOT / "addons.xml").getroot()})
        # Kodi ships Pillow itself; the other core interfaces are virtual.
        native = {"script.module.pil"}
        visited = set()
        def visit(aid, stack=()):
            self.assertNotIn(aid, stack, "Dependency cycle")
            for dep in addons[aid].findall("./requires/import"):
                target = dep.get("addon")
                if dep.get("optional") == "true" or target in native or target.startswith(("xbmc.", "kodi.")): continue
                self.assertIn(target, addons)
                version = lambda s: tuple(int(n) for n in re.findall(r"\d+", s or "0"))
                self.assertGreaterEqual(version(addons[target].get("version")), version(dep.get("version")), target)
                visit(target, stack + (aid,))
            visited.add(aid)
        visit("script.program.foundry-build")
        self.assertTrue({"skin.foundry", "script.foundry.helper"}.issubset(visited))

    def test_original_resource_assets_and_all_skin_resource_paths_are_packaged(self):
        for addon in ("resource.images.foundry.wallpapers", "resource.images.foundry.osd"):
            source = ROOT / "src" / addon
            provenance = json.loads((source / "SOURCE.json").read_text())
            with zipfile.ZipFile(ROOT / addon / (addon + "-1.0.0.zip")) as bundle:
                for filename, expected in provenance["files"].items():
                    data = bundle.read(addon + "/resources/" + filename)
                    self.assertEqual(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(), expected)
        paths = set()
        for path in (SKIN / "xml").glob("*.xml"):
            paths.update(re.findall(r"resource://resource\.images\.foundry\.[^<\s\"]+", path.read_text()))
        self.assertGreaterEqual(len(paths), 28)
        for uri in paths:
            self.assertTrue(Path(translate(uri)).is_file(), uri)

    def test_core_addons_are_native_install_dependencies_on_clean_profiles(self):
        build = ET.parse(ROOT / "src/script.program.foundry-build/addon.xml").getroot()
        required = {d.get("addon") for d in build.findall("./requires/import")}
        self.assertTrue({"script.module.cocoscrapers", "slyguy.trailers", "plugin.video.themoviedb.helper",
                         "metadata.themoviedb.org.python", "metadata.tvshows.themoviedb.org.python",
                         "resource.uisounds.androidtv", "inputstream.adaptive",
                         "script.module.inputstreamhelper"}.issubset(required))
        # These feeds must be available before the skin has ever been loaded.
        repo = ET.parse(ROOT / "src/repository.foundry/addon.xml").getroot()
        feeds = [d.findtext("info") for d in repo.findall("./extension/dir")]
        self.assertTrue(any("slyguy.uk/" in url for url in feeds))
        self.assertTrue(any("repository.cocoscrapers/" in url for url in feeds))
        self.assertFalse(any("redirect" in url for url in feeds))

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
    def test_first_skin_confirmation_has_an_unconditional_readable_card(self):
        from PIL import Image
        shared = ET.parse(SKIN / "xml/Includes.xml").find("include[@name='DialogBackgroundCommons']")
        self.assertEqual(shared.findtext("param[@name='darken_bg']"), "true")
        card = next(c for c in shared.findall("definition/control")
                    if (c.findtext("texture") or "").startswith("special://skin/"))
        self.assertIsNone(card.find("visible"))
        self.assertEqual({name: card.findtext(name) for name in ("left", "right", "top", "bottom")},
                         dict.fromkeys(("left", "right", "top", "bottom"), "-20"))
        texture = card.find("texture")
        tint = texture.get("colordiffuse")
        self.assertRegex(tint, r"^[A-F0-9]{8}$")
        with Image.open(translate(texture.text)) as image:
            red, green, blue, alpha = image.convert("RGBA").getpixel((image.width // 2, image.height // 2))
        opacity = alpha / 255 * int(tint[:2], 16) / 255
        self.assertGreater(opacity, .8)
        self.assertLess(opacity, 1)
        # Worst-case bright artwork behind the translucent card and dimmer.
        rgb = [channel * int(tint[i:i+2], 16) / 255 for channel, i in zip((red, green, blue), (2, 4, 6))]
        behind = 255 * (1 - 0x66 / 255)
        composite = [opacity * channel + (1 - opacity) * behind for channel in rgb]
        def luminance(channels):
            def linear(value):
                value /= 255
                return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
            return sum(weight * linear(value) for value, weight in zip(channels, (.2126, .7152, .0722)))
        self.assertGreater((luminance((240, 240, 240)) + .05) / (luminance(composite) + .05), 7)
        self.assertEqual(ET.parse(SKIN / "xml/DialogConfirm.xml").findtext(".//control[@id='9']/textcolor"), "white")
        variables = ET.parse(SKIN / "xml/Variables_MyVariables.xml")
        for name in ("DialogBackgroundColorVar", "DialogBackgroundTextureVar"):
            fallback = variables.find("variable[@name='%s']/value[last()]" % name)
            self.assertTrue(fallback.text)
            self.assertIsNone(fallback.get("condition"))

    def test_home_logo_actions_and_menu_have_separate_bounds(self):
        doc = ET.parse(SKIN / "xml/Home.xml")
        logo = next(c for c in doc.iter("control") if c.findtext("texture") == "foundry-logo.png")
        sidebar = next(c for c in doc.iter("control") if logo in list(c))
        action_group = next(c for c in sidebar.findall("control") if c.find("control[@id='700']") is not None)
        menu = sidebar.find("control[@id='9000']")
        bottom = lambda c: int(c.findtext("top", "0")) + int(c.findtext("height"))
        label = action_group.find("control[@type='label']")
        self.assertLessEqual(bottom(logo) + 5, int(action_group.findtext("top")) + int(label.findtext("top")))
        self.assertLessEqual(bottom(action_group) + 15, int(menu.findtext("top")))
        actions = action_group.find("control[@id='700']")
        count = len(actions.findall("include[@content='IconButton']"))
        button = ET.parse(SKIN / "xml/Includes_Buttons.xml").find("include[@name='IconButton']/definition/control")
        full_width = count * int(button.findtext("width")) + (count - 1) * int(actions.findtext("itemgap"))
        self.assertLessEqual(full_width, int(actions.findtext("width")))
        self.assertLessEqual(int(action_group.findtext("left")) + full_width, 549)
        self.assertLessEqual(bottom(menu), 877)  # Clock starts below the scrolling menu.

    def test_menu_backgrounds_follow_menu_focus_and_preserve_custom_art(self):
        variables = {e.get("name"): e for e in ET.parse(SKIN / "xml/Variables_Artwork.xml").getroot()}
        def choose(name, menu, strings=None):
            strings = strings or {}
            for value in variables[name]:
                condition = value.get("condition")
                if condition:
                    condition = re.sub(r"String.IsEqual\(Container\(9000\).ListItem.Property\(id\),(\w+)\)",
                                       lambda m: str(menu == m[1]), condition)
                    condition = re.sub(r"String.IsEmpty\(Skin.String\(([^)]+)\)\)",
                                       lambda m: str(not strings.get(m[1])), condition)
                    condition = condition.replace("!", " not ").replace("+", " and ").replace("|", " or ")
                    condition = condition.replace("Control.HasFocus(802)", "False")
                    if not eval(condition.strip(), {"__builtins__": {}}):
                        continue
                text = value.text
                if text.startswith("$VAR["):
                    return choose(text[5:-1], menu, strings)
                text = text.replace("$INFO[Container(9000).ListItem.Property(id)]", menu)
                return re.sub(r"\$INFO\[Skin.String\(([^)]+)\)\]", lambda m: strings.get(m[1], ""), text)
        menus = ["movies", "tvshows", "music", "musicvideos", "livetv", "radio", "games", "addons", "pictures", "video", "favorites", "weather"]
        appearances = [(choose("FoundryMenuBackground", menu), choose("FoundryMenuBackgroundTint", menu)) for menu in menus]
        self.assertEqual(len(set(appearances)), len(menus))
        for path, tint in appearances:
            self.assertTrue(Path(translate(path)).is_file())
            self.assertRegex(tint, r"^[A-F0-9]{8}$")
        custom = {"HomeFanart.path": "/my/backgrounds/", "HomeFanart.ext": ".jpg"}
        self.assertEqual(choose("FoundryMenuBackground", "tvshows", custom), "/my/backgrounds/tvshows.jpg")
        self.assertEqual(choose("FoundryMenuBackground", "tvshows", {"NimbusCustomBackground": "/my/custom.png"}), "/my/custom.png")
        priority = variables["HomeFanartVar"][0]
        self.assertEqual(priority.text, "$VAR[FoundryMenuBackground]")
        self.assertIn("!ControlGroup(2000).HasFocus", priority.get("condition"))
        background = ET.parse(SKIN / "xml/Includes.xml").find("include[@name='ColoredBackgroundImages']")
        self.assertTrue(any(e.text == "$VAR[FoundryBackgroundImage]" for e in background.iter("texture")))

    def test_category_wallpaper_renders_independently_of_blur_and_widget_art(self):
        doc = ET.parse(SKIN / "xml/Home.xml")
        wallpaper = next(c for c in doc.findall("./controls/control")
                         if c.findtext("description") == "Foundry full-screen category wallpaper")
        self.assertEqual(wallpaper.findtext("texture"), "$VAR[FoundryMenuBackground]")
        self.assertEqual(wallpaper.findtext("width"), "100%")
        self.assertEqual(wallpaper.findtext("height"), "100%")
        self.assertNotIn("Blur", wallpaper.findtext("visible"))
        siblings = doc.findall("./controls/control")
        self.assertIn("ControlGroup(2000).HasFocus", siblings[siblings.index(wallpaper) + 1].findtext("visible"))

    def test_osd_back_focus_and_button_bounds(self):
        osd = ET.parse(SKIN / "xml/Includes_StreamPilotOSD.xml")
        for name in ("StreamPilotVODCard", "StreamPilotLiveCard"):
            card = osd.find("include[@name='%s']/control" % name)
            buttons = card.findall(".//control[@type='button']")
            ids = {b.get("id") for b in buttons}
            self.assertTrue(ids)
            for button in buttons:
                self.assertEqual(button.findtext("onback"), "Dialog.Close(videoosd)")
                self.assertIn(button.findtext("onleft"), ids)
                self.assertIn(button.findtext("onright"), ids)
                self.assertLessEqual(int(button.findtext("top")) + int(button.findtext("height")), int(card.findtext("height")))
        self.assertEqual(ET.parse(SKIN / "xml/VideoOSD.xml").findtext("defaultcontrol"), "8702")

    def test_osd_timer_hides_after_five_seconds_and_pauses_in_settings(self):
        timer = ET.parse(SKIN / "xml/Timers.xml").find("timer[name='autoclosevideoosd']")
        self.assertIn("Skin.TimerElapsedSecs(autoclosevideoosd),5", timer.findtext("stop"))
        self.assertEqual(timer.findtext("onstop"), "Dialog.Close(videoosd)")
        for settings in ("1101", "osdsubtitlesettings", "osdaudiosettings", "osdvideosettings"):
            self.assertIn("!Window.IsActive(%s)" % settings, timer.findtext("start"))
            self.assertIn("Window.IsActive(%s)" % settings, timer.findtext("reset"))

    def test_osd_seek_uses_active_video_player_and_exact_relative_seconds(self):
        from modules.osd import seek
        for seconds in (-30, 30):
            with patch.object(xbmc, "executeJSONRPC", side_effect=[
                    '{"result":[{"playerid":0,"type":"audio"},{"playerid":1,"type":"video"}]}',
                    '{"result":{"percentage":10}}']) as rpc:
                self.assertTrue(seek(seconds))
                request = json.loads(rpc.call_args_list[1].args[0])
                self.assertEqual(request["method"], "Player.Seek")
                self.assertEqual(request["params"], {"playerid": 1, "value": {"seconds": seconds}})

    def test_osd_seek_rejects_bad_input_missing_player_and_kodi_errors(self):
        from modules.osd import seek
        with patch.object(xbmc, "executeJSONRPC") as rpc:
            for value in (0, 10, 60, "bad", None):
                self.assertFalse(seek(value))
            rpc.assert_not_called()
        for response in ('{"result":[]}', '{"error":{"code":-1}}', 'invalid'):
            with patch.object(xbmc, "executeJSONRPC", return_value=response):
                self.assertFalse(seek(30))
        with patch.object(xbmc, "executeJSONRPC", side_effect=[
                '{"result":[{"playerid":1,"type":"video"}]}', '{"error":{"code":-1}}']):
            self.assertFalse(seek(30))

    def test_osd_artwork_color_reads_cached_image_and_reuses_result(self):
        from modules import osd
        from PIL import Image
        path = PROFILE / "osd-poster.png"
        Image.new("RGB", (72, 96), (200, 20, 30)).save(path)
        Window.values.clear()
        with patch.object(xbmc, "getInfoLabel", return_value="https://art.invalid/poster.png"), \
                patch.object(osd, "_cached_paths", return_value=[str(path)]) as paths:
            osd.prepare_artwork()
            self.assertEqual(Window().getProperty("foundry.osd.accent"), "FFC8141E")
            self.assertEqual(Window().getProperty("foundry.osd.shade"), "FF3C0609")
            osd.prepare_artwork()
            paths.assert_called_once()

    def test_osd_missing_artwork_retries_and_stale_artwork_cannot_replace_color(self):
        from modules import osd
        Window.values.clear()
        with patch.object(xbmc, "getInfoLabel", return_value="https://art.invalid/missing.png"), \
                patch.object(osd, "_cached_paths", return_value=[]):
            osd.prepare_artwork()
            self.assertEqual(Window().getProperty("foundry.osd.artwork"), "")
            self.assertEqual(Window().getProperty("foundry.osd.accent"), "FF182A3B")
        with patch.object(xbmc, "getInfoLabel", side_effect=["a", "a", "b", "b"]), \
                patch.object(osd, "_cached_paths", return_value=[]):
            osd.prepare_artwork()
            self.assertEqual(Window().getProperty("foundry.osd.accent"), "FF182A3B")

    def test_slyguy_is_default_and_handles_items_without_scraped_trailers(self):
        from modules.custom_actions import play_trailer
        with patch.object(xbmc, "getInfoLabel", return_value=""), \
                patch.object(xbmc, "getCondVisibility", side_effect=lambda expression: expression == "System.HasAddon(slyguy.trailers)"), \
                patch.object(xbmc, "executebuiltin") as execute:
            play_trailer()
        calls = [call.args[0] for call in execute.call_args_list]
        self.assertIn("RunScript(slyguy.trailers)", calls)
        self.assertFalse(any(value.startswith("PlayMedia(") for value in calls))

    def test_missing_trailer_provider_does_not_leave_preview_locked(self):
        from modules.custom_actions import play_trailer
        with patch.object(xbmc, "getInfoLabel", return_value="2"), \
                patch.object(xbmc, "getCondVisibility", return_value=False), \
                patch.object(xbmc, "executebuiltin") as execute:
            play_trailer()
        execute.assert_called_once_with("Skin.Reset(TrailerPlaying)")

    def test_android_sound_default_applies_once_and_can_retry_after_failure(self):
        from modules.experience import configure_experience
        def visible(expression):
            return expression == "System.HasAddon(resource.uisounds.androidtv)"
        with patch.object(xbmc, "getCondVisibility", side_effect=visible), \
                patch.object(xbmc, "executeJSONRPC", return_value='{"result":false}'), \
                patch.object(xbmc, "executebuiltin") as execute:
            self.assertFalse(configure_experience())
            execute.assert_not_called()
        with patch.object(xbmc, "getCondVisibility", side_effect=visible), \
                patch.object(xbmc, "executeJSONRPC", return_value='{"result":true}') as rpc, \
                patch.object(xbmc, "executebuiltin") as execute:
            self.assertTrue(configure_experience())
            self.assertEqual(json.loads(rpc.call_args.args[0])["params"],
                             {"setting": "lookandfeel.soundskin", "value": "resource.uisounds.androidtv"})
            execute.assert_called_once_with("Skin.SetBool(foundry.sounds.default.v1)")
        with patch.object(xbmc, "getCondVisibility", return_value=True), \
                patch.object(xbmc, "executeJSONRPC") as rpc:
            self.assertFalse(configure_experience())
            rpc.assert_not_called()

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
