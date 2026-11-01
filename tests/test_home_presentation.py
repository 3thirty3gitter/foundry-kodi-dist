"""Home wallpaper routing and row restoration contracts, independent of Kodi."""
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / "skin.foundry-nimbus"
sys.path.insert(0, str(ROOT / "tools"))
from validate_widget_assets import CATEGORIES, validate_widget_assets


class HomePresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = ET.parse(SKIN / "xml/Home.xml")
        cls.variables = {v.get("name"): v for v in ET.parse(SKIN / "xml/Variables_Artwork.xml").getroot()}

    def choose(self, name, category, widgets, strings=None, action=None):
        strings = strings or {}
        def condition(text):
            text = text.replace("$EXP[FoundryHomeHasWidgets]", str(widgets))
            text = re.sub(r"Control.HasFocus\((\d+)\)", lambda m: str(action == int(m[1])), text)
            text = re.sub(r"String.IsEqual\(Container\(9000\).ListItem.Property\(id\),(\w+)\)", lambda m: str(category == m[1]), text)
            text = re.sub(r"String.IsEmpty\(Skin.String\(([^)]+)\)\)", lambda m: str(not strings.get(m[1])), text)
            return bool(eval(text.replace("!", " not ").replace("+", " and ").replace("|", " or ").strip(), {"__builtins__": {}}))
        for value in self.variables[name]:
            if value.get("condition") and not condition(value.get("condition")):
                continue
            text = value.text
            if text.startswith("$VAR["):
                return self.choose(text[5:-1], category, widgets, strings, action)
            text = text.replace("$INFO[Container(9000).ListItem.Property(id)]", category)
            return re.sub(r"\$INFO\[Skin.String\(([^)]+)\)\]", lambda m: strings.get(m[1], ""), text)
        self.fail("No wallpaper route")

    def test_all_categories_switch_both_directions_to_complete_frames(self):
        for category in CATEGORIES:
            for widgets in (False, True, False, True):
                with self.subTest(category=category, widgets=widgets):
                    expected = "special://skin/media/foundry-widget-wallpapers/" if widgets else "resource://resource.images.foundry.wallpapers/"
                    self.assertEqual(self.choose("FoundryHomeWallpaper", category, widgets), expected + category + ".png")

    def test_rapid_focus_round_trips_do_not_restart_wallpaper_or_change_selection(self):
        focus_actions = ET.parse(SKIN / "xml/Includes_Home.xml").findall(".//onfocus")
        resets = [a for a in focus_actions if (a.text or "").startswith("Control.Move(")]
        self.assertTrue(resets)
        self.assertTrue(all(a.get("condition") == "!Window.IsActive(Home)" for a in resets))
        for category in ("movies", "tvshows", "custom1"):
            for selected in (0, 5, 6, 19, 49, 99):
                paths = []
                for _ in range(80):
                    # Focus changes alone never alter the texture routing input.
                    paths.extend(self.choose("FoundryHomeWallpaper", category, True) for focus in ("menu", "widget", "menu", "widget"))
                self.assertEqual(len(set(paths)), 1)

    def test_category_changes_and_empty_loading_populated_transitions_have_no_blank_route(self):
        sequence = [("movies", False), ("movies", True), ("tvshows", True), ("music", False), ("music", True), ("movies", True)] * 50
        for category, widgets in sequence:
            self.assertTrue(self.choose("FoundryHomeWallpaper", category, widgets).endswith(category + ".png"))

    def test_custom_backgrounds_and_action_buttons_keep_priority(self):
        for widgets in (False, True):
            self.assertEqual(self.choose("FoundryHomeWallpaper", "movies", widgets, {"NimbusCustomBackground": "/mine.png"}), "/mine.png")
            self.assertEqual(self.choose("FoundryHomeWallpaper", "tvshows", widgets, {"HomeFanart.path": "/custom/", "HomeFanart.ext": ".jpg"}), "/custom/tvshows.jpg")
            self.assertTrue(self.choose("FoundryHomeWallpaper", "movies", widgets, action=801).endswith("foundry-shutdown-wallpaper.svg"))
            self.assertTrue(self.choose("FoundryHomeWallpaper", "movies", widgets, action=803).endswith("foundry-search-wallpaper.svg"))

    def test_crossfade_keeps_one_owner_fixed_geometry_and_missing_image_fallback(self):
        image = next(c for c in self.home.findall("./controls/control") if c.findtext("description") == "Foundry full-frame Home wallpaper")
        self.assertEqual([image.findtext(t) for t in ("left", "top", "width", "height", "aspectratio", "fadetime")], ["0", "0", "100%", "100%", "keep", "450"])
        self.assertEqual(image.find("texture").get("fallback"), "$VAR[FoundryMenuBackground]")
        self.assertEqual(image.findall("animation"), [])
        self.assertNotIn("HasFocus", image.findtext("visible"))
        self.assertEqual(self.variables["FoundryBackgroundImage"][0].text, "special://skin/media/foundry-widget-base.svg")

    def test_first_return_and_repeated_entries_cannot_enable_home_hero_presentation(self):
        expression = ET.parse(SKIN / "xml/Expressions.xml").findtext("expression[@name='FoundryHomeRowPresentation']")
        self.assertEqual(expression, "Window.IsActive(Home) + $EXP[FoundryHomeHasWidgets]")
        # Presence, not index, focus history or menu category, determines row mode.
        for is_home in (True, False):
            for selected in (0, 5, 6, 49, 99):
                for widgets in (False, True, True, True):
                    source = expression.replace("Window.IsActive(Home)", str(is_home)).replace("$EXP[FoundryHomeHasWidgets]", str(widgets)).replace("+", " and ")
                    row_mode = bool(eval(source, {"__builtins__": {}}))
                    self.assertEqual(row_mode, is_home and widgets)
                    if is_home and widgets:
                        self.assertFalse(not row_mode)  # Media metadata cannot trigger Home hero mode.
        guards = [v.text for v in self.home.iter("visible") if v.text and "!$EXP[FoundryHomeRowPresentation]" in v.text]
        self.assertEqual(len(guards), 2)  # Full fanart and Flix detail panel only.

    def test_native_widget_geometry_and_focus_actions_are_unchanged(self):
        with zipfile.ZipFile(ROOT / "skin.foundry/skin.foundry-1.1.6.zip") as old:
            before = ET.fromstring(old.read("skin.foundry/xml/Home.xml"))
            old_includes = ET.fromstring(old.read("skin.foundry/xml/Includes_Home.xml"))
        after = self.home.getroot()
        normalize = lambda n: (n.tag, n.attrib, (n.text or "").strip(), [normalize(c) for c in n])
        old_group = next(c for c in before.iter("control") if c.get("id") == "2000")
        new_group = next(c for c in after.iter("control") if c.get("id") == "2000")
        self.assertEqual(normalize(old_group), normalize(new_group))
        current = ET.parse(SKIN / "xml/Includes_Home.xml")
        for name in ("WidgetGroupListCommon", "WidgetListCommon", "WidgetListPoster", "WidgetListLandscape", "WidgetListSquare"):
            self.assertEqual(normalize(old_includes.find("include[@name='%s']" % name)), normalize(current.find("include[@name='%s']" % name)))

    def test_packaging_rejects_incomplete_unapproved_artwork(self):
        self.assertEqual(set(validate_widget_assets(SKIN)), CATEGORIES)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "incomplete"):
                validate_widget_assets(Path(tmp))


if __name__ == "__main__":
    unittest.main()
