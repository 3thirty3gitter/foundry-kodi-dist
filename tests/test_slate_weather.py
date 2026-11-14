from pathlib import Path
import unittest, xml.etree.ElementTree as E, ast
from PIL import Image
P=Path(__file__).resolve().parents[1];S=P/'src/skin.foundry.slate';X=S/'xml'
class Canvas(unittest.TestCase):
 def setUp(self):
  self.r=E.parse(X/'Includes_FoundryCanadaWeather.xml');self.h=E.parse(X/'Home.xml');self.l=self.r.find('.//control[@id="15150"]')
 def test_xml(self):self.assertIsNotNone(self.l)
 def test_seven_real_days(self):
  items=self.l.findall('content/item');self.assertEqual(len(items),7)
  for n,it in enumerate(items,1):
   self.assertIn(f'Day.{n}.Title',it.findtext('visible'));self.assertIn(f'Day{n-1}.OutlookIcon',it.findtext('icon'))
   self.assertIn(f'Day.{n}.Summary',it.findtext('property[@name="summary"]'))
 def test_focus_drives_expansion(self):
  s=(X/'Includes_FoundryCanadaWeather.xml').read_text();self.assertIn('Control.HasFocus(15150)',s);self.assertIn('Container(15150).ListItem.Property(summary)',s)
 def test_no_persistent_widget(self):self.assertIn('weather',self.h.find('.//control[@id="15000"]/visible').text)
 def test_exit_paths(self):
  for k in ['onleft','onright','onup','onback']:self.assertEqual(self.l.findtext(k),'9000')
  self.assertEqual(self.l.findtext('ondown'),'15151')
  for b in self.r.findall('.//control[@type="button"]'):self.assertEqual(b.findtext('ondown'),'700');self.assertEqual(b.findtext('onback'),'9000');self.assertIn('9000',[u.text for u in b.findall('onup')])
 def test_menu_entry_and_empty_fallback(self):
  s=(X/'Home.xml').read_text();self.assertIn('SetFocus(15154)',s);self.assertIn('SetFocus(15150,0,absolute)',s)
 def test_provider_and_original_not_in_patch(self):self.assertEqual(S.name,'skin.foundry.slate'); self.assertNotIn('resource://resource.images.weathericons.default/',(X/'Includes_FoundryCanadaWeather.xml').read_text())
 def test_no_opaque_card(self):self.assertNotIn('foundry-weather/card.png',(X/'Includes_FoundryCanadaWeather.xml').read_text())
 def test_data_states_and_attribution(self):
  s=(X/'Includes_FoundryCanadaWeather.xml').read_text()
  for x in ['Attribution','Stale','needs_location','unavailable','!Weather.IsFetched','HasAlerts']:self.assertIn(x,s)
 def test_icon_coverage(self):
  m=ast.parse((P/'src/weather.foundry.canada/resources/lib/model.py').read_text());codes=next(ast.literal_eval(n.value) for n in m.body if isinstance(n,ast.Assign) and any(getattr(a,'id','')=='ICONS' for a in n.targets));
  for n in set(codes.values())|{'na'}:
   im=Image.open(S/f'media/slate-weather/{n}.png');self.assertEqual(im.size,(256,256));self.assertEqual(im.mode,'RGBA');self.assertTrue(im.getbbox())
if __name__=='__main__':unittest.main()

