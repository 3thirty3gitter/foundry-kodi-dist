"""The Home Add-ons launcher keeps its navigation without a solid menu panel."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

SKIN = Path(__file__).resolve().parents[2] / 'skin.foundry-nimbus'

class AddonMenuTransparency(unittest.TestCase):
    def test_addon_menu_keeps_controls_but_has_no_panel(self):
        root = ET.parse(SKIN / 'xml/Custom_1100_AddonLauncher.xml').getroot()
        self.assertFalse(root.findall(".//include[@content='MenuContentPanel']"))
        menu = root.find(".//control[@id='9000']")
        self.assertIsNotNone(menu)
        self.assertEqual(menu.get('type'), 'fixedlist')
        self.assertEqual(menu.findtext('left'), '25')
        self.assertEqual(menu.findtext('top'), '250')
        self.assertEqual(menu.findtext('onright'), 'SetFocus($INFO[Container(9000).ListItem.Property(menu_id)])')
        self.assertEqual(len(root.findall(".//include[@content='AddonLauncherPanel']")), 8)

    def test_shared_search_panel_is_preserved(self):
        root = ET.parse(SKIN / 'xml/Custom_1121_SearchResults.xml').getroot()
        self.assertTrue(root.findall(".//include[@content='MenuContentPanel']"))

if __name__ == '__main__':
    unittest.main()
