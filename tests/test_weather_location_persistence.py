"""Settings source contract; native GUI/restart validation is separate."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
class LocationPersistenceContract(unittest.TestCase):
    def test_every_location_action_closes_settings_before_script(self):
        root = ET.parse(ROOT / 'src/weather.foundry.canada/resources/settings.xml').getroot()
        for slot in range(1, 4):
            action = root.find(".//setting[@id='choose%d']" % slot)
            self.assertEqual(action.findtext('data'), 'RunScript(weather.foundry.canada,choose:%d)' % slot)
            self.assertEqual(action.findtext('control/close'), 'true')

    def test_existing_saved_location_keys_are_preserved(self):
        root = ET.parse(ROOT / 'src/weather.foundry.canada/resources/settings.xml').getroot()
        for slot in range(1, 4):
            for field in ('id', 'label'):
                setting = root.find(".//setting[@id='location%d_%s']" % (slot, field))
                self.assertEqual(setting.get('type'), 'string')
                self.assertFalse(setting.findtext('default'))

    def test_empty_locations_are_valid_kodi_strings(self):
        root = ET.parse(ROOT / 'src/weather.foundry.canada/resources/settings.xml').getroot()
        for slot in range(1, 4):
            for field in ('id', 'label'):
                setting = root.find(".//setting[@id='location%d_%s']" % (slot, field))
                self.assertEqual(setting.findtext('constraints/allowempty'), 'true')
                if field == 'label':
                    self.assertEqual(setting.findtext('enable'), 'false')
                    self.assertIsNone(setting.find('dependencies'))
