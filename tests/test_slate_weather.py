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
   self.assertIn(f'Day.{n}.Title',it.findtext('visible'));self.assertEqual(it.findtext('icon'),f'$VAR[SlateWeatherDay{n}Icon]')
   self.assertIn(f'Day.{n}.Summary',it.findtext('property[@name="summary"]'))
 def test_focus_drives_expansion(self):
  s=(X/'Includes_FoundryCanadaWeather.xml').read_text();self.assertIn('Control.HasFocus(15150)',s);self.assertIn('Container(15150).ListItem.Property(summary)',s)
 def test_no_persistent_widget(self):self.assertIn('weather',self.h.find('.//control[@id="15000"]/visible').text)
 def test_exit_paths(self):
  for k in ['onleft','onback']:self.assertEqual(self.l.findtext(k),'9000')
  for k in ['onup','onright']:self.assertEqual(self.l.findtext(k),'15149')
  self.assertEqual(self.l.findtext('ondown'),'700')
  hero=self.r.find('.//control[@id="15149"]');self.assertEqual(hero.findtext('onright'),'RunScript(weather.foundry.canada,next)');self.assertEqual(hero.findtext('onback'),'9000')
 def test_menu_entry_and_empty_fallback(self):
  s=(X/'Home.xml').read_text();self.assertIn('SetFocus(15149)',s);self.assertIn('SetFocus(15150,0,absolute)',s)
 def test_provider_and_original_not_in_patch(self):self.assertEqual(S.name,'skin.foundry.slate'); self.assertNotIn('Current.OutlookIcon',(X/'Includes_FoundryCanadaWeather.xml').read_text())
 def test_no_opaque_card(self):self.assertNotIn('foundry-weather/card.png',(X/'Includes_FoundryCanadaWeather.xml').read_text())
 def test_data_states_and_attribution(self):
  s=(X/'Includes_FoundryCanadaWeather.xml').read_text()
  for x in ['Stale','needs_location','unavailable','!Weather.IsFetched']:self.assertIn(x,s)
  self.assertNotIn('Attribution',s);self.assertNotIn('HasAlerts',s)
 def test_visual_contracts(self):
  s=(X/'Includes_FoundryCanadaWeather.xml').read_text()
  for caption in ['Advisories','Next city','Refresh','Settings']:self.assertNotIn('<label>'+caption+'</label>',s)
  for n in range(15151,15155):self.assertIsNone(self.r.find('.//control[@id="%d"]'%n))
  group=self.r.find("include[@name='FoundryCanadaWeatherWidget']/definition/control")
  for c in group.findall("control[@type='label']"):self.assertLess(int(c.findtext('top')),285)
  self.assertIn('$VAR[SlateWeatherDay1Icon]',s)
  self.assertIn('$VAR[SlateWeatherHeroIcon]',s)
  self.assertIsNotNone(self.r.find("variable[@name='SlateWeatherCanvasWallpaper']"))
  self.assertIn('SlateWeatherCanvasWallpaper',(X/'Home.xml').read_text())
 def test_real_missing_observation_icon_does_not_erase_forecast(self):
  from test_weather_client_model import feature,period,model,NOW
  from foundry_weather_test_lib import kodi_bridge
  f=feature();f['properties']['currentConditions']['iconCode']={'format':'gif'}
  f['properties']['forecastGroup']={'forecasts':[period('Today','high',5)]}
  p=kodi_bridge.build_properties(model.normalize(f,now=NOW),NOW.timestamp())
  self.assertTrue(p['Foundry.Weather.Icon'].endswith('/na.png'))
  self.assertTrue(p['Foundry.Weather.Day.1.Icon'].endswith('/16.png'))
  hero=self.r.find("variable[@name='SlateWeatherHeroIcon']")
  self.assertEqual(hero.findall('value')[-1].text,'$VAR[SlateWeatherDay1Icon]')
  self.assertIn('forecast',self.r.find("variable[@name='SlateWeatherHeroTitle']").findall('value')[-1].text)
 def test_attribution_remains_in_forecast_details(self):
  provider=(P/'src/weather.foundry.canada/default.py').read_text()
  self.assertIn("parts.append(WINDOW.getProperty(PREFIX+'Attribution'))",provider)
 def test_icon_coverage(self):
  m=ast.parse((P/'src/weather.foundry.canada/resources/lib/model.py').read_text());codes=next(ast.literal_eval(n.value) for n in m.body if isinstance(n,ast.Assign) and any(getattr(a,'id','')=='ICONS' for a in n.targets));
  for n in set(codes.values())|{'na'}:
   im=Image.open(S/f'media/slate-weather/{n}.png');self.assertEqual(im.size,(256,256));self.assertEqual(im.mode,'RGBA');self.assertTrue(im.getbbox())
if __name__=='__main__':unittest.main()

