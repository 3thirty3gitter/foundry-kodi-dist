"""Source contract tests. Native Kodi/Shield rendering is a separate QA gate."""
from pathlib import Path
import ast
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'src/weather.foundry.canada'
SKIN = ROOT.parent / 'skin.foundry-nimbus'
PROVIDER = 'weather.foundry.canada'
SELECTED = 'String.IsEqual(Weather.Plugin,' + PROVIDER + ')'


class WeatherIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = ET.parse(SKIN / 'xml/Home.xml').getroot()
        cls.widget = ET.parse(SKIN / 'xml/Includes_FoundryCanadaWeather.xml').getroot()

    def test_omega_registration_has_no_startup_service(self):
        addon = ET.parse(ADDON / 'addon.xml').getroot()
        self.assertEqual(addon.get('id'), PROVIDER)
        self.assertEqual(addon.find("extension[@point='xbmc.python.weather']").get('library'), 'default.py')
        self.assertIsNone(addon.find("extension[@point='xbmc.service']"))
        self.assertEqual(addon.find("requires/import[@addon='xbmc.python']").get('version'), '3.0.0')

    def test_settings_default_to_manual_locations(self):
        root = ET.parse(ADDON / 'resources/settings.xml').getroot()
        for slot in range(1, 4):
            field = root.find(".//setting[@id='location%d_id']" % slot)
            self.assertFalse(field.findtext('default'))
            action = root.find(".//setting[@id='choose%d']/data" % slot).text
            self.assertEqual(action, 'RunScript(weather.foundry.canada,choose:%d)' % slot)

    def test_no_provider_or_profile_setting_mutation(self):
        source = (ADDON / 'default.py').read_text(encoding='utf-8')
        self.assertNotIn('Settings.SetSettingValue', source)
        self.assertNotIn('weather.addon', source)
        self.assertNotIn('executeJSONRPC', source)
        ast.parse(source, feature_version=(3, 8))

    def test_new_include_is_registered_once(self):
        includes = ET.parse(SKIN / 'xml/Includes.xml').getroot()
        paths = [x.get('file') for x in includes.findall('include')]
        self.assertEqual(paths.count('Includes_FoundryCanadaWeather.xml'), 1)

    def test_home_keeps_legacy_providers_separate(self):
        weather = self.home.find(".//control[@id='15000']")
        card = weather.find("include[@content='FoundryCanadaWeatherWidget']")
        self.assertIsNotNone(card)
        self.assertEqual(card.find("param[@name='id']").get('value'), '15150')
        legacy = next(x for x in weather.findall('control') if x.findtext('include') == 'WeatherPanel')
        self.assertEqual(legacy.findtext('visible'), '!' + SELECTED)
        self.assertIsNone(legacy.find('include').get('condition'))
        self.assertEqual(weather.find("control[@id='15001']/visible").text, '!' + SELECTED)
        self.assertIsNone(weather.find("include[@content='WidgetUpDownArrows']").get('condition'))
        scroll = next(x for x in weather.findall('control') if x.find("include[@content='WidgetScrollbar']") is not None)
        self.assertEqual(scroll.findtext('visible'), '!' + SELECTED)
        self.assertEqual(scroll.find('include').get('condition'), 'Skin.HasSetting(touchmode)')

    def test_weather_menu_retains_other_providers_and_empty_setup(self):
        item = next(x for x in self.home.findall('.//item') if x.findtext("property[@name='id']") == 'weather')
        actions = item.findall('onclick')
        self.assertTrue(any(x.text == 'SetFocus(15150)' and x.get('condition') == SELECTED for x in actions))
        self.assertTrue(any(x.text == 'ReplaceWindow(servicesettings,weather)' for x in actions))
        for x in actions:
            if x.text in ('Weather.LocationNext', 'ReplaceWindow(Weather)'):
                self.assertIn('!' + SELECTED, x.get('condition', ''))

    def test_card_navigation_has_return_and_action_paths(self):
        card = self.widget.find(".//control[@id='$PARAM[id]']")
        self.assertEqual(card.findtext('onback'), '9000')
        self.assertEqual(card.findtext('ondown'), '15151')
        expected = ['RunScript(weather.foundry.canada,alerts)', 'Weather.LocationNext',
                    'Weather.Refresh', 'Addon.OpenSettings(weather.foundry.canada)']
        for index, action in enumerate(expected, 15151):
            button = self.widget.find(".//control[@id='%d']" % index)
            self.assertEqual(button.findtext('onclick'), action)
            self.assertEqual(button.findtext('onback'), '9000')
            self.assertEqual(button.findtext('onup'), '$PARAM[id]')

    def test_missing_current_guard_and_footer_do_not_use_core_zero(self):
        group = self.widget.find(".//control[visible='String.IsEqual(Window(weather).Property(Foundry.Weather.HasCurrent),true)']")
        self.assertIsNotNone(group)
        text = (SKIN / 'xml/Includes_FoundryCanadaWeather.xml').read_text(encoding='utf-8')
        self.assertNotIn('$INFO[Weather.Temperature]', text)
        values = self.widget.find("variable[@name='FoundryCanadaHomeWeatherVar']").findall('value')
        self.assertIn('HasCurrent', values[0].get('condition'))
        self.assertEqual(values[1].get('condition'), SELECTED)
        self.assertFalse(values[1].text)
        self.assertEqual(values[-1].text, '$VAR[HomeMenuWeatherVar]')

    def test_fonts_exist_in_all_fontsets(self):
        expected = {'foundry_weather_small', 'foundry_weather_body', 'foundry_weather_title', 'foundry_weather_temperature'}
        for fontset in ET.parse(SKIN / 'xml/Font.xml').getroot().findall('fontset'):
            names = [x.findtext('name') for x in fontset.findall('font')]
            self.assertTrue(expected.issubset(names))
            for name in expected:
                self.assertEqual(names.count(name), 1)

    def test_static_control_ids_do_not_collide_with_existing_skin(self):
        for path in (SKIN / 'xml').glob('*.xml'):
            if path.name == 'Includes_FoundryCanadaWeather.xml':
                continue
            for control in ET.parse(path).getroot().iter('control'):
                self.assertNotIn(control.get('id'), {'15150', '15151', '15152', '15153', '15154'}, str(path))

    def test_new_assets_and_language_actions_exist(self):
        for name in ('card.png', 'line.png'):
            self.assertTrue((SKIN / 'media/foundry-weather' / name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
        for language in ('en_gb', 'fr_fr'):
            data = (ADDON / ('resources/language/resource.language.%s/strings.po' % language)).read_text(encoding='utf-8')
            codes = re.findall(r'msgctxt "#(\d+)"', data)
            self.assertEqual(len(codes), len(set(codes)))
            for code in ('30022', '30023', '30024'):
                self.assertIn(code, codes)


if __name__ == '__main__':
    unittest.main()
