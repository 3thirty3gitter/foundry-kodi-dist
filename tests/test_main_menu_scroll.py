"""Visible focus must stay inside the unchanged seven-row Home menu viewport."""
from pathlib import Path
import unittest,xml.etree.ElementTree as E,zipfile
from home_contracts import without_home_favorites

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'
class MainMenuScroll(unittest.TestCase):
    def setUp(self):
        self.home=E.parse(SKIN/'xml/Home.xml');self.menu=self.home.find(".//control[@id='9000']")
        self.item_height=int(E.parse(SKIN/'xml/Includes_ListItem.xml').findtext("include[@name='List']/param[@name='height']"))
    def test_movement_stops_at_last_fully_visible_row(self):
        viewport=int(self.menu.findtext('height'));movement=int(self.menu.findtext('movement'))
        self.assertEqual((viewport,self.item_height),(535,75))
        self.assertEqual(movement,viewport//self.item_height-1)
        self.assertLessEqual((movement+1)*self.item_height,viewport)
    def test_only_the_main_menu_movement_byte_changes_in_home(self):
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.2.0.zip') as z:old=z.read('skin.foundry/xml/Home.xml')
        new=(SKIN/'xml/Home.xml').read_bytes().replace(b'\r\n',b'\n');start=new.index(b'<control type="fixedlist" id="9000">');end=new.index(b'</control>',start)
        normalized=new[:start]+new[start:end].replace(b'<movement>6</movement>',b'<movement>7</movement>')+new[end:]
        self.assertEqual(without_home_favorites(normalized.replace(b'\t  <include>FoundryWidgetMetadata</include>\n',b'')),without_home_favorites(old))
    def test_weather_visibility_and_main_menu_navigation_are_retained(self):
        # ElementTree cannot select nested attribute predicates consistently on all Python versions.
        weather=next(i for i in self.menu.findall('content/item') if i.findtext("property[@name='id']")=='weather')
        self.assertEqual(weather.findtext('visible'),'!Skin.HasSetting(HomeMenuNoWeatherButton)')
        self.assertEqual((self.menu.findtext('onup'),self.menu.findtext('ondown')),('700','9000'))
        self.assertIn('SetFocus(',self.menu.findtext('onright'))
    def test_short_and_custom_menu_end_positions_fit(self):
        movement=int(self.menu.findtext('movement'));focus=int(self.menu.findtext('focusposition'));per_page=int(self.menu.findtext('height'))//self.item_height
        # Official Kodi fixed-list cursor range includes itemsPerPage itself;
        # the skin must bound movement to prevent that extra clipped row.
        for count in (1,2,3,7,8,16,33,64):
            max_cursor=min(focus+movement,per_page,count-1)
            self.assertLessEqual((max_cursor+1)*self.item_height,int(self.menu.findtext('height')))

