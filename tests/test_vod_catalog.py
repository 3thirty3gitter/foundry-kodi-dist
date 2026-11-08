"""Catalog geometry/navigation contracts against the pinned StreamPilot layout."""
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import test_release as kodi
from modules import vod

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / "skin.foundry-nimbus"


class CatalogLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = ET.parse(SKIN / "xml/View_57_StreamPilot.xml")
        cls.view = cls.doc.find("include[@name='View_57_StreamPilot']/control")

    def test_full_fanart_no_persistent_category_sidebar_and_footer_below_rail(self):
        backdrop = self.view.find("control[@type='image']")
        self.assertEqual((backdrop.findtext("width"), backdrop.findtext("height")), ("100%", "100%"))
        self.assertEqual(backdrop.findtext("aspectratio"), "scale")
        self.assertFalse(any(g.findtext("orientation", "vertical") == "vertical" for g in self.view.findall(".//control[@type='grouplist']")))
        self.assertIsNone(self.view.find("control[@id='5703']"))

    def test_poster_ratio_fixed_slot_focus_scale_and_unclipped_vertical_glow(self):
        rail = self.view.find("control[@id='57']")
        self.assertEqual(rail.get("type"), "fixedlist")
        self.assertEqual(rail.findtext("orientation"), "horizontal")
        self.assertEqual(rail.find("itemlayout").attrib, rail.find("focusedlayout").attrib)
        poster = self.doc.find("include[@name='FoundryVODPoster']/definition/control/control")
        width, height = (int(poster.findtext(k)) for k in ("width", "height"))
        self.assertEqual((width, height), (224, 336))
        zoom = poster.find("animation/effect")
        self.assertEqual(zoom.get("end"), "119")
        self.assertEqual((int(rail.findtext("top")), int(rail.findtext("height"))), (428, 600))
        outer = poster.find("control[texture='$VAR[FoundryVODGlow]']")
        self.assertEqual((outer.findtext('left'),outer.findtext('top')),('-96','-96'))
        self.assertEqual((outer.findtext('width'),outer.findtext('height')),('416','528'))
        # Negligible transparent tails can extend beyond the viewport; the
        # visible halo itself must retain space above and below the poster.
        self.assertLess(int(outer.findtext('top')),0)
        self.assertGreater(int(outer.findtext('height'))-96,336)
        art_y = int(rail.findtext('top')) + int(poster.findtext('top'))
        studio = self.view.find(".//control[@type='image'][texture='$VAR[FoundryVODStudioLogo]']")
        self.assertLess(int(studio.findtext('top')) + int(studio.findtext('height')), art_y - 336 * .19 / 2)

    def test_hero_clearlogo_studio_and_description_follow_reference_geometry(self):
        logo = self.view.find(".//control[@type='image'][texture='$VAR[FoundryVODClearlogo]']")
        self.assertEqual((logo.findtext("width"), logo.findtext("height")), ("520", "132"))
        self.assertEqual(logo.findtext("aspectratio"), "keep")
        studio = self.view.find(".//control[@type='image'][texture='$VAR[FoundryVODStudioLogo]']")
        self.assertEqual((studio.findtext("width"), studio.findtext("height")), ("240", "80"))
        plot = self.view.find(".//control[@type='textbox'][label='$VAR[FoundryVODPlot]']")
        self.assertEqual(plot.findtext("autoscroll"), "Skin.HasSetting(autoscroll)")
        self.assertLess(int(plot.findtext("top")) + int(plot.findtext("height")), 576)

    def test_native_playback_context_and_restored_focus_are_not_replaced(self):
        rail = self.view.find("control[@id='57']")
        self.assertEqual(rail.findall("onclick"), [])  # Kodi handles playable items and folders.
        self.assertEqual(rail.findall("onback"), [])
        self.assertFalse(any("SetFocus" in (a.text or "") or "Control.Move" in (a.text or "") for a in rail.findall("onfocus")))
        self.assertEqual(rail.findtext("ondown"), "57")
        self.assertIsNone(self.view.find("control[@id='5703']"))
        self.assertEqual(self.view.findtext("control[@id='5701']/onup"), "9000")
        common = ET.parse(SKIN / "xml/Includes_MediaMenu.xml").find("include[@name='MediaMenuListCommon']/definition")
        self.assertEqual(common.findtext("onback[@condition='Control.IsVisible(57)']"), "57")

    def test_loading_empty_and_missing_metadata_have_safe_distinct_states(self):
        loading = self.view.find("control[@type='group'][visible='Container(57).IsUpdating']")
        self.assertIsNone(loading)
        empty = next(c for c in self.view.findall("control[@type='label']") if (c.findtext("label") or "").startswith("No library matches"))
        self.assertIn("!Container(57).IsUpdating", empty.findtext("visible"))
        plot = self.doc.find("variable[@name='FoundryVODPlot']")
        self.assertEqual(plot.findall("value")[-1].text, "No description available.")
        imdb = self.doc.find("variable[@name='FoundryVODIMDb']")
        self.assertIn("foundry.omdb.imdb_rating", imdb[1].text)
        self.assertIn("ListItem.Rating(imdb)", imdb[2].text)
        self.assertFalse((imdb[-1].text or "").strip())

    def test_settings_are_optional_key_masked_and_disabled_by_default(self):
        settings = ET.parse(ROOT.parent / "script.foundry.helper/resources/settings.xml")
        self.assertEqual(settings.find(".//setting[@id='omdb_enabled']").get("default"), "false")
        key = settings.find(".//setting[@id='omdb_api_key']")
        self.assertEqual((key.get("option"), key.get("default")), ("hidden", ""))


class CatalogNavigation(unittest.TestCase):
    def test_page_navigation_first_last_and_partial_pages(self):
        cases = [(1, 13, "next", 6), (6, 13, "next", 6), (7, 13, "next", 12), (12, 13, "next", 12), (13, 13, "next", 12), (13, 13, "previous", 6), (7, 13, "previous", 0), (1, 13, "previous", 0), (1, 1, "next", 0), (0, 0, "next", None)]
        for current, total, direction, expected in cases:
            self.assertEqual(vod.page_target(current, total, direction), expected)
        self.assertIsNone(vod.page_target("bad", "bad", "next"))

    def test_explicit_paging_stays_in_video_catalog_and_selects_first_item(self):
        with patch("xbmc.getCondVisibility", return_value=True), patch("xbmc.getInfoLabel", side_effect=lambda k: {"Container(57).CurrentItem": "12", "Container(57).NumItems": "13"}[k]), patch("xbmc.executebuiltin") as action:
            self.assertTrue(vod.page("next"))
            action.assert_called_once_with("SetFocus(57,12,absolute)")
        with patch("xbmc.getCondVisibility", return_value=False), patch("xbmc.executebuiltin") as action:
            self.assertFalse(vod.page("next")); action.assert_not_called()

    def test_reopening_an_active_catalog_keeps_selected_item_and_scroll(self):
        with patch("xbmc.getCondVisibility", side_effect=lambda q:q!='Container.IsUpdating'), patch("xbmc.executebuiltin") as action:
            self.assertTrue(vod.activate_catalog())
            action.assert_not_called()

    def test_activation_does_not_replace_other_library_or_file_windows(self):
        with patch("xbmc.getCondVisibility", return_value=False), patch("xbmc.executebuiltin") as action:
            self.assertFalse(vod.activate_catalog()); action.assert_not_called()
        def visible(query): return query not in {"Control.IsVisible(57)",'Container.IsUpdating'}
        with patch("xbmc.getCondVisibility", side_effect=visible), patch("xbmc.executebuiltin") as action:
            self.assertTrue(vod.activate_catalog()); action.assert_called_once_with("Container.SetViewMode(57)")

    def test_artwork_monitor_follows_item_changes_without_fetching_network(self):
        class Clock:
            value = 1000
            def __call__(self): return self.value
        clock = Clock(); monitor = vod.CatalogArtworkMonitor(clock)
        labels = {"ListItem.Art(fanart)": "one", "ListItem.Label": "Title"}
        with patch("xbmc.getCondVisibility", return_value=True), patch("xbmc.getInfoLabel", side_effect=lambda k: labels.get(k, "")), patch("modules.vod.prepare_artwork") as prepare:
            monitor.process_current_item(); prepare.assert_called_once()
            clock.value += .01; monitor.process_current_item(); prepare.assert_called_once()
            labels["ListItem.Art(fanart)"] = "two"; monitor.process_current_item(); self.assertEqual(prepare.call_count, 2)
            clock.value += .01; monitor.process_current_item(); self.assertEqual(prepare.call_count, 2)

    def test_details_format_date_limit_genres_and_omit_missing_fields(self):
        labels = {"ListItem.Label": "Example", "ListItem.DBTYPE": "movie", "ListItem.Year": "2025", "ListItem.Premiered": "2025-09-28", "ListItem.Genre": "Drama / Comedy / Mystery / Crime", "ListItem.Studio": "N/A"}
        result = vod.catalog_details(lambda k: labels.get(k, ""), kodi.Window())
        self.assertEqual(result["released_label"], "Released Sep 28, 2025")
        self.assertEqual(result["genres"], "Drama / Comedy / Mystery")
        self.assertNotIn("N/A", result["details"])
        self.assertFalse(result["details"].endswith("\u2022"))

    def test_old_provider_metadata_is_not_used_for_a_new_title(self):
        window = kodi.Window(); window.values.clear()
        window.setProperty("foundry.omdb.owner_label", "Old title")
        window.setProperty("foundry.omdb.owner_year", "2025")
        window.setProperty("foundry.omdb.owner_type", "movie")
        window.setProperty("foundry.omdb.studio", "Old studio")
        labels = {"ListItem.Label": "New title", "ListItem.Year": "2025", "ListItem.DBTYPE": "movie"}
        result = vod.catalog_details(lambda k: labels.get(k, ""), window)
        self.assertNotIn("Old studio", result["details"])
        self.assertEqual(result["details"], "Movie")


if __name__ == "__main__":
    unittest.main()

