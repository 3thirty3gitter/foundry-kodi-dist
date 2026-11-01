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
                self.assertEqual(bundle.namelist(), sorted(bundle.namelist()))
                self.assertTrue(all(entry.create_system == 3 for entry in bundle.infolist()))
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
            categories = [p.stem for p in (ROOT / "src/resource.images.foundry.wallpapers/resources").glob("*.png") if p.stem != "icon"]
            resolved = [uri.replace("$PARAM[category]", category) for category in categories] if "$PARAM[category]" in uri else [uri]
            for path in resolved:
                self.assertTrue(Path(translate(path)).is_file(), path)

    def test_core_addons_are_native_install_dependencies_on_clean_profiles(self):
        build = ET.parse(ROOT / "src/script.program.foundry-build/addon.xml").getroot()
        required = {d.get("addon") for d in build.findall("./requires/import")}
        self.assertTrue({"script.module.cocoscrapers", "plugin.video.themoviedb.helper",
                         "metadata.themoviedb.org.python", "metadata.tvshows.themoviedb.org.python",
                         "resource.uisounds.androidtv", "inputstream.adaptive",
                         "script.module.inputstreamhelper"}.issubset(required))
        # These feeds must be available before the skin has ever been loaded.
        repo = ET.parse(ROOT / "src/repository.foundry/addon.xml").getroot()
        feeds = [d.findtext("info") for d in repo.findall("./extension/dir")]
        self.assertTrue(any("slyguy.uk/" in url for url in feeds))
        self.assertTrue(any("repository.cocoscrapers/" in url for url in feeds))
        self.assertFalse(any("redirect" in url for url in feeds))

    def test_slyguy_native_install_requires_its_repository_to_exist_first(self):
        addons = {a.get("id"): a for a in ET.parse(ROOT / "tests/fixtures/upstream-addons.xml").getroot()}
        addons.update({a.get("id"): a for a in ET.parse(ROOT / "addons.xml").getroot()})
        # Kodi Omega AddonRepos.cpp::FindDependency rejects repositories as
        # dependencies. A complete XML dependency graph alone misses this rule.
        def can_install(aid, installed):
            for dep in addons[aid].findall("./requires/import"):
                target = dep.get("addon")
                if dep.get("optional") == "true" or target in installed or target == "script.module.pil" or target.startswith(("xbmc.", "kodi.")):
                    continue
                candidate = addons[target]
                if candidate.find("extension[@point='xbmc.addon.repository']") is not None:
                    return False
                if not can_install(target, installed):
                    return False
            return True
        self.assertFalse(can_install("slyguy.trailers", {"repository.foundry"}))
        self.assertTrue(can_install("script.program.foundry-build", {"repository.foundry"}))
        self.assertTrue(can_install("slyguy.trailers", {"repository.foundry", "repository.slyguy"}))

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
    def home_condition(self, condition, menu="addons", visible=(), counts=None, updating=(), settings=False):
        """Evaluate the native Home conditions against a simulated Kodi scene."""
        expressions = {e.get("name"): e.text for e in ET.parse(SKIN / "xml/Expressions.xml").getroot()}
        counts = counts or {}
        condition = re.sub(r"\$EXP\[([^]]+)\]", lambda m: "(" + expressions[m[1]] + ")" if m[1] == "FoundryHomeHasWidgets" else "False", condition)
        condition = re.sub(r"String.IsEqual\(Container\(9000\).ListItem.Property\(id\),(\w+)\)", lambda m: str(menu == m[1]), condition)
        condition = re.sub(r"Integer.IsGreater\(Container\((\d+)\).NumItems,0\)", lambda m: str(counts.get(int(m[1]), 0) > 0), condition)
        condition = re.sub(r"Container\((\d+)\).IsUpdating", lambda m: str(int(m[1]) in updating), condition)
        condition = re.sub(r"Control.IsVisible\((\d+)\)", lambda m: str(int(m[1]) in visible), condition)
        condition = condition.replace("ControlGroup(700).HasFocus", str(settings))
        for token in ("Player.HasVideo", "Player.HasAudio", "Visualisation.Enabled", "ControlGroup(2000).HasFocus"):
            condition = condition.replace(token, "False")
        condition = condition.replace("String.IsEmpty(Visualisation.Name)", "True")
        condition = condition.replace("[", "(").replace("]", ")")
        condition = condition.replace("!", " not ").replace("+", " and ").replace("|", " or ")
        return bool(eval(condition.strip(), {"__builtins__": {}}))

    def test_home_menu_has_no_background_or_empty_library_overlay(self):
        doc = ET.parse(SKIN / "xml/Home.xml")
        self.assertEqual(doc.findall(".//include[@content='MenuContentPanel']"), [])
        prompts = doc.findall(".//include[@content='ImageWidget']")
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0].find("param[@name='text_label']").get("value"), "$INFO[System.DVDLabel]")
        # Shared panels and empty-state controls in other windows are preserved.
        self.assertIsNotNone(ET.parse(SKIN / "xml/Includes.xml").find("include[@name='MenuContentPanel']"))
        self.assertIsNotNone(ET.parse(SKIN / "xml/Includes_Home.xml").find("include[@name='ImageWidget']"))

    def test_widget_wallpaper_follows_visible_rows_while_menu_has_focus(self):
        expression = ET.parse(SKIN / "xml/Expressions.xml").findtext("expression[@name='FoundryHomeHasWidgets']")
        self.assertTrue(self.home_condition(expression, visible={8100}, counts={8100: 4}))
        self.assertFalse(self.home_condition(expression, menu="music", visible={8100}, counts={8100: 4}))
        self.assertFalse(self.home_condition(expression, visible={8100}, counts={8100: 0}))
        self.assertFalse(self.home_condition(expression, counts={8100: 4}))
        self.assertTrue(self.home_condition(expression, visible={8100}, updating={8100}))
        self.assertFalse(self.home_condition(expression, visible={8100}, counts={8100: 4}, settings=True))
        for menu, last_row in (("movies", 19060), ("tvshows", 22060), ("custom1", 23060), ("custom2", 24060), ("custom3", 25060)):
            self.assertTrue(self.home_condition(expression, menu=menu, visible={last_row}, counts={last_row: 1}))

    def test_widget_wallpaper_never_keeps_the_large_category_title_below_it(self):
        doc = ET.parse(SKIN / "xml/Home.xml")
        controls = doc.findall("./controls/control")
        wallpaper = next(c for c in controls if c.findtext("description") == "Foundry full-screen category wallpaper")
        compact = next(c for c in controls if c.findtext("description") == "Foundry compact widget wallpaper")
        for active in (False, True):
            scene = dict(visible={8100} if active else set(), counts={8100: 2} if active else {})
            self.assertEqual(self.home_condition(wallpaper.findtext("visible"), **scene), not active)
            self.assertEqual(self.home_condition(compact.findtext("visible"), **scene), active)
        backdrop = compact.find("control[description='Original widget backdrop at full screen size']")
        self.assertEqual(backdrop.findtext("texture"), "$VAR[FoundryMenuBackground]")
        self.assertEqual((backdrop.findtext("left"), backdrop.findtext("top"), backdrop.findtext("width"), backdrop.findtext("height")), ("0", "0", "100%", "100%"))
        artwork = ET.parse(SKIN / "xml/Includes_Home.xml").find("include[@name='FoundryWidgetCategoryArtwork']/definition/control")
        title = artwork.find("control[description='Original category title at the top right']")
        self.assertEqual(title.findtext("texture"), "resource://resource.images.foundry.wallpapers/$PARAM[category].png")
        self.assertEqual(title.find("texture").get("diffuse"), "special://skin/media/foundry-widget-layers/$PARAM[category]-title.png")
        self.assertNotIn("$VAR[", title.find("texture").get("diffuse"))
        width, height = int(title.findtext("width")), int(title.findtext("height"))
        self.assertLess(width, 1920)
        self.assertLess(int(title.findtext("top")) + height * .72, 510)
        variables = ET.parse(SKIN / "xml/Variables_Artwork.xml")
        first = variables.find("variable[@name='FoundryBackgroundImage']/value")
        self.assertIn("FoundryHomeHasWidgets", first.get("condition"))
        self.assertTrue(Path(translate(first.text)).is_file())
        for source in ("foundry-widget-base.svg", "foundry-widget-fade.svg"):
            ET.parse(SKIN / "media" / source)

    def test_home_logo_uses_vector_outlines_and_an_oversampled_texture(self):
        from PIL import Image
        svg = ET.parse(SKIN / "media/foundry-logo.svg")
        self.assertEqual(svg.findall(".//{http://www.w3.org/2000/svg}text"), [])
        self.assertGreaterEqual(len(svg.findall(".//{http://www.w3.org/2000/svg}path")), 5)
        with Image.open(SKIN / "media/foundry-logo-hd.png") as current:
            self.assertEqual(current.mode, "RGBA")
            self.assertGreaterEqual(current.width, 380 * 6)
            self.assertAlmostEqual(current.width / current.height, 380 / 115, delta=.03)
            box = current.getchannel("A").getbbox()
            self.assertLessEqual(box[0], 2)
            self.assertLessEqual(box[1], 2)
            self.assertLessEqual(current.width - box[2], 2)
            self.assertLessEqual(current.height - box[3], 2)

    def test_all_fourteen_widget_layers_remove_only_the_original_title(self):
        from PIL import Image, ImageChops
        layers = SKIN / "media/foundry-widget-layers"
        paths = sorted(layers.glob("*-repair.png"))
        self.assertEqual(len(paths), 14)
        home = ET.parse(SKIN / "xml/Home.xml")
        routes = home.findall(".//include[@content='FoundryWidgetCategoryArtwork']")
        self.assertEqual({r.find("param[@name='category']").get("value") for r in routes}, {p.stem[:-7] for p in paths})
        compact = next(c for c in home.findall("./controls/control") if c.findtext("description") == "Foundry compact widget wallpaper")
        custom_guard = compact.find("control[@type='group']/visible").text
        self.assertIn("String.IsEmpty(Skin.String(HomeFanart.path))", custom_guard)
        self.assertIn("String.IsEmpty(Skin.String(NimbusCustomBackground))", custom_guard)
        for path in paths:
            category = path.stem[:-7]
            with self.subTest(category=category):
                original = Image.open(ROOT / "src/resource.images.foundry.wallpapers/resources" / (category + ".png")).convert("RGBA").resize((1920, 1080), Image.Resampling.LANCZOS)
                repair = Image.open(path).convert("RGBA")
                title = Image.open(layers / (category + "-title.png")).getchannel("A").resize(original.size, Image.Resampling.LANCZOS)
                self.assertEqual(repair.size, original.size)
                cleaned = Image.alpha_composite(original, repair)
                # Every untouched backdrop pixel remains exact, at full size.
                changed = ImageChops.difference(original.convert("RGB"), cleaned.convert("RGB")).convert("L")
                outside = repair.getchannel("A").point(lambda a: 255 if a == 0 else 0)
                self.assertIsNone(ImageChops.multiply(changed, outside).getbbox())
                # The old bright lettering and icon cannot bleed through.
                title_pixels = [(a, b) for a, b, alpha in zip(original.getdata(), cleaned.getdata(), title.getdata()) if alpha > 240 and min(a[:3]) > 170]
                self.assertGreater(len(title_pixels), 1000)
                self.assertTrue(all(max(b[:3]) < 170 for _, b in title_pixels))
                # The isolated artwork stays above widget rows starting at y=510.
                box = title.getbbox()
                self.assertLess(-55 + box[3] * 720 / 1080, 510)

    def test_home_positions_are_unchanged_except_logo_size_and_removed_tooltip(self):
        with zipfile.ZipFile(ROOT / "skin.foundry/skin.foundry-1.1.5.zip") as old:
            before = ET.fromstring(old.read("skin.foundry/xml/Home.xml"))
        after = ET.parse(SKIN / "xml/Home.xml").getroot()
        def strip_allowed_changes(doc):
            for parent in doc.iter():
                for child in list(parent):
                    if child.tag == "control" and child.findtext("label") == "$VAR[HomeSubmenuButtonLabelsVar]":
                        parent.remove(child)
            controls = doc.find("controls")
            for child in list(controls):
                if child.findtext("description") == "Foundry compact widget wallpaper":
                    controls.remove(child)
            logo = next(c for c in doc.iter("control") if c.findtext("texture") in {"foundry-logo.png", "foundry-logo-hd.png"})
            logo.find("texture").text = "foundry-logo.png"
            self.assertEqual((logo.findtext("left"), logo.findtext("top")), ("60", "40"))
            size = (int(logo.findtext("width")), int(logo.findtext("height")))
            for tag in ("width", "height"):
                logo.remove(logo.find(tag))
            return size
        previous_size = strip_allowed_changes(before)
        new_size = strip_allowed_changes(after)
        self.assertEqual(new_size, previous_size)
        def normalized(node):
            return (node.tag, node.attrib, (node.text or "").strip(), [normalized(c) for c in node])
        self.assertEqual(normalized(before), normalized(after))

    def test_action_hover_wallpapers_override_the_selected_category(self):
        variables = ET.parse(SKIN / "xml/Variables_Artwork.xml")
        defaults = variables.find("variable[@name='FoundryDefaultMenuBackground']")
        for control_id, filename in ((801, "foundry-shutdown-wallpaper.svg"), (803, "foundry-search-wallpaper.svg")):
            route = defaults.find("value[@condition='Control.HasFocus(%s)']" % control_id)
            self.assertEqual(route.text, "special://skin/media/" + filename)
            ET.parse(SKIN / "media" / filename)
        override = variables.find("variable[@name='FoundryMenuBackground']/value")
        self.assertEqual(override.text, "$VAR[FoundryDefaultMenuBackground]")
        for control_id in (801, 802, 803):
            self.assertIn("Control.HasFocus(%s)" % control_id, override.get("condition"))
        expression = ET.parse(SKIN / "xml/Expressions.xml").findtext("expression[@name='FoundryHomeHasWidgets']")
        self.assertFalse(self.home_condition(expression, settings=True, visible={8100}, counts={8100: 6}))

    def test_widget_selection_survives_menu_round_trip_for_all_layouts(self):
        doc = ET.parse(SKIN / "xml/Includes_Home.xml")
        # Kodi's group focus memory restores the last row; no always=true default.
        group = doc.find("include[@name='WidgetGroupListCommon']/defaultcontrol")
        self.assertEqual(group.get("always"), "false")
        self.assertEqual(group.text, "0")
        tested = 0
        for layout in doc.findall("include"):
            actions = [a for a in layout.findall(".//onfocus") if (a.text or "").startswith("Control.Move(")]
            if not actions:
                continue
            tested += 1
            for is_home in (True, False):
                selected = 6
                for action in actions:
                    condition = action.get("condition", "true")
                    active = not is_home if condition == "!Window.IsActive(Home)" else True
                    if active:
                        selected = 0  # Existing search reset behavior with no listposition.
                self.assertEqual(selected, 6 if is_home else 0, layout.get("name"))
        self.assertEqual(tested, 4)
        common = doc.find("include[@name='WidgetListCommon']")
        home_back = common.find("onback[@condition='Window.IsActive(Home)']")
        self.assertEqual(home_back.text, "9000")
        resets = [a for a in common.findall("onback") if (a.text or "").startswith("SetFocus(")]
        self.assertTrue(resets)
        self.assertTrue(all(a.get("condition").startswith("!Window.IsActive(Home)") for a in resets))

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
        logo = next(c for c in doc.iter("control") if c.findtext("texture") == "foundry-logo-hd.png")
        sidebar = next(c for c in doc.iter("control") if logo in list(c))
        action_group = next(c for c in sidebar.findall("control") if c.find("control[@id='700']") is not None)
        menu = sidebar.find("control[@id='9000']")
        bottom = lambda c: int(c.findtext("top", "0")) + int(c.findtext("height"))
        self.assertLessEqual(bottom(logo) + 10, int(action_group.findtext("top")))
        self.assertIsNone(action_group.find("control[@type='label']"))
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
                    condition = re.sub(r"Control.HasFocus\(80[123]\)", "False", condition)
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
        media = next(c for c in siblings if c.findtext("visible") and "ControlGroup(2000).HasFocus" in c.findtext("visible"))
        self.assertIn("$EXP[isContent]", media.findtext("visible"))

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
        self.assertIn("foundry-logo-hd.png", (SKIN / "xml/Home.xml").read_text())
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
        with patch.object(module, "ensure_trailers"), patch.object(xbmc, "getSkinDir", return_value="skin.foundry"), patch.object(xbmc, "executebuiltin") as execute:
            module.main()
        execute.assert_called_once_with("ReloadSkin()")

    def test_clean_build_prepares_original_slyguy_repo_before_native_trailer_install(self):
        spec = importlib.util.spec_from_file_location("foundry_slyguy", ROOT / "src/script.program.foundry-build/default.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        registry, events = {}, []
        destination = PROFILE / "addons" / "repository.slyguy"
        shutil.rmtree(destination, ignore_errors=True)
        class InstalledAddon(Addon):
            def getAddonInfo(self, key):
                if key == "path": return str(SKIN if self.id == "skin.foundry" else HELPER)
                return super().getAddonInfo(key)
        def rpc(request):
            request = json.loads(request)
            method, params = request["method"], request["params"]
            if method == "Addons.GetAddonDetails":
                aid = params["addonid"]
                if aid not in registry: return '{"error":{"code":-32602,"message":"Invalid params."}}'
                return json.dumps({"result": {"addon": dict(registry[aid], addonid=aid)}})
            if method == "Addons.SetAddonEnabled":
                aid = params["addonid"]
                if aid in registry: registry[aid]["enabled"] = True
                events.append("enable:" + aid)
                return '{"result":"OK"}'
            if method == "Settings.SetSettingValue": return '{"result":true}'
            raise AssertionError(method)
        def execute(command, *args):
            events.append(command)
            if command == "UpdateLocalAddons":
                self.assertTrue(destination.is_dir())
                manifest = ET.parse(destination / "addon.xml").getroot()
                self.assertEqual(manifest.get("id"), "repository.slyguy")
                registry["repository.slyguy"] = {"version": manifest.get("version"), "enabled": False}
            if command == "InstallAddon(slyguy.trailers)":
                self.assertEqual(args, (True,))
                self.assertTrue(registry["repository.slyguy"]["enabled"])
                registry["slyguy.trailers"] = {"version": "0.2.2", "enabled": True}
        with patch.object(xbmcaddon, "Addon", InstalledAddon), \
                patch.object(xbmc, "executeJSONRPC", side_effect=rpc), \
                patch.object(xbmc, "executebuiltin", side_effect=execute), \
                patch.object(xbmc, "getSkinDir", return_value="skin.estuary"):
            module.main()
            self.assertLess(events.index("enable:repository.slyguy"), events.index("InstallAddon(slyguy.trailers)"))
            self.assertLess(events.index("InstallAddon(slyguy.trailers)"), events.index("ActivateWindow(settings)"))
            # Reopening a completed setup does not reinstall or refresh anything.
            before = list(events)
            module.ensure_trailers()
            self.assertEqual(events, before)

    def test_build_enables_disabled_slyguy_components_without_reinstalling(self):
        spec = importlib.util.spec_from_file_location("foundry_enable", ROOT / "src/script.program.foundry-build/default.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, "addon_details", side_effect=[
                {"version": "0.0.9", "enabled": False}, {"version": "0.2.2", "enabled": False}]), \
                patch.object(module, "rpc", return_value="OK") as rpc, \
                patch.object(xbmc, "executebuiltin") as execute:
            module.ensure_trailers()
        self.assertEqual([c.args[1]["addonid"] for c in rpc.call_args_list], ["repository.slyguy", "slyguy.trailers"])
        execute.assert_not_called()

    def test_cancelled_trailer_install_reports_failure_and_does_not_activate(self):
        spec = importlib.util.spec_from_file_location("foundry_cancel", ROOT / "src/script.program.foundry-build/default.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, "addon_details", side_effect=[{"version": "0.0.9", "enabled": True}, None, None]), \
                patch.object(xbmc, "executebuiltin") as execute, patch.object(Dialog, "ok") as message:
            module.main()
        execute.assert_called_once_with("InstallAddon(slyguy.trailers)", True)
        self.assertIn("not installed", message.call_args.args[1])

    def test_slyguy_registration_failure_stops_before_trailers_and_skin(self):
        spec = importlib.util.spec_from_file_location("foundry_register_failure", ROOT / "src/script.program.foundry-build/default.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tools = types.SimpleNamespace(_extract_to_addons=lambda *args: True, _register_repos=lambda ids: ids)
        loader = types.SimpleNamespace(exec_module=lambda module: None)
        with patch.object(module, "addon_details", return_value=None), \
                patch.object(importlib.util, "spec_from_file_location", return_value=types.SimpleNamespace(loader=loader)), \
                patch.object(importlib.util, "module_from_spec", return_value=tools), \
                patch.object(xbmc, "executebuiltin") as execute, patch.object(Dialog, "ok") as message:
            module.main()
        execute.assert_not_called()
        self.assertIn("could not be registered", message.call_args.args[1])

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
        with patch.object(module, "ensure_trailers"), patch.object(xbmc, "getSkinDir", return_value="skin.estuary"), patch.object(xbmc, "executeJSONRPC", side_effect=rpc):
            module.main()
        self.assertEqual(requests[-1]["params"], {"setting": "lookandfeel.skin", "value": "skin.foundry"})


if __name__ == "__main__":
    unittest.main()
