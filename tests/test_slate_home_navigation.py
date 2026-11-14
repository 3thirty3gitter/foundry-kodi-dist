"""Slate-only focus wiring contracts; native remote/device QA is separate."""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class SlateHomeNavigation(unittest.TestCase):
    def setUp(self):
        self.home = ET.parse(ROOT / 'src/skin.foundry.slate/xml/Home.xml').getroot()
    def control(self, ident):
        return self.home.find(f".//control[@id='{ident}']")
    def test_main_menu_bottom_exits_to_footer_not_itself(self):
        menu = self.control(9000)
        self.assertEqual(menu.findtext('ondown'), '700')
        self.assertEqual(menu.findtext('onup'), '700')
        self.assertEqual(menu.findtext('onback'), '700')
        routes=menu.findall('onright')
        self.assertEqual(len(routes),3)
        self.assertEqual(routes[-1].text,'SetFocus($INFO[Container(9000).ListItem.Property(menu_id)])')
        self.assertEqual(routes[-1].get('condition'),'!String.IsEqual(Container(9000).ListItem.Property(id),weather) | !String.IsEqual(Weather.Plugin,weather.foundry.canada)')
    def test_footer_returns_to_menu_and_preserves_horizontal_navigation(self):
        footer = self.control(700)
        self.assertEqual(footer.findtext('orientation'), 'horizontal')
        self.assertEqual(footer.findtext('onup'), 'SetFocus(9000,99,absolute)')
        self.assertEqual(footer.findtext('ondown'), 'SetFocus(9000,0,absolute)')
        self.assertEqual(footer.findtext('onback'), '9000')
        self.assertEqual([c.attrib['id'] for c in footer.findall('control')][:3], ['801','802','803'])
        for ident, action in [(801,'$VAR[HomePowerButtonActionVar]'), (802,'ActivateWindow(settings)'), (803,'$VAR[HomeSearchButtonActionVar]')]:
            button = self.control(ident)
            self.assertEqual(button.findtext('visible'), 'true')
            self.assertEqual(button.findtext('onclick'), action)
if __name__ == '__main__':
    unittest.main()
