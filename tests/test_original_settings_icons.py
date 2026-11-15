"""Original Foundry settings artwork contract. No Kodi or user profile access."""
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from PIL import Image

SKIN = Path(os.environ.get('FOUNDRY_SKIN_ROOT', str(Path(__file__).resolve().parents[2] / 'skin.foundry-nimbus')))
NAMES = {'skin', 'folder', 'addons', 'info', 'player', 'media', 'tv', 'network', 'games', 'interface', 'profiles', 'system'}
# Frozen from pre-restyle original Settings.xml. Includes conditional LibreELEC item.
BASELINE = [
 ('Skin settings', 'ActivateWindow(skinsettings)', None),
 ('$LOCALIZE[10003]', 'ActivateWindow(filemanager)', None),
 ('$LOCALIZE[24001]', 'ActivateWindow(addonbrowser)', None),
 ('$LOCALIZE[138]', 'ActivateWindow(systeminfo)', None),
 ('$LOCALIZE[14200]', 'ActivateWindow(PlayerSettings)', None),
 ('$LOCALIZE[14211]', 'ActivateWindow(MediaSettings)', None),
 ('$LOCALIZE[14204]', 'ActivateWindow(PVRSettings)', None),
 ('$LOCALIZE[14036]', 'ActivateWindow(ServiceSettings)', None),
 ('$LOCALIZE[15016]', 'ActivateWindow(GameSettings)', 'System.GetBool(gamesgeneral.enable)'),
 ('$LOCALIZE[14206]', 'ActivateWindow(InterfaceSettings)', None),
 ('$LOCALIZE[13200]', 'ActivateWindow(Profiles)', None),
 ('$LOCALIZE[13000]', 'ActivateWindow(SystemSettings)', None),
 ('LibreELEC', 'RunAddon(service.libreelec.settings)', 'System.AddonIsEnabled(service.libreelec.settings)'),
]

class OriginalSettingsIconsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = ET.parse(SKIN / 'xml/Settings.xml')
        cls.panel = ET.parse(SKIN / 'xml/Includes.xml').getroot().find("include[@name='SettingsPanel']")
        assert cls.panel is not None

    def test_exact_twelve_assets_and_paths(self):
        expected = {'foundry-settings-icons/' + name + '.png' for name in NAMES}
        self.assertEqual({node.text for node in self.settings.findall('.//icon')}, expected)
        folder = SKIN / 'media/foundry-settings-icons'
        self.assertEqual({p.name for p in folder.glob('*.png')}, {name + '.png' for name in NAMES})
        for name in expected:
            self.assertTrue((SKIN / 'media' / name).is_file(), name)

    def test_true_alpha_and_protected_margins(self):
        for name in sorted(NAMES):
            with self.subTest(icon=name), Image.open(SKIN / 'media/foundry-settings-icons' / (name + '.png')) as icon:
                self.assertEqual(icon.format, 'PNG')
                self.assertEqual(icon.mode, 'RGBA')
                self.assertEqual(icon.size, (362, 362))
                alpha = icon.getchannel('A')
                self.assertEqual(alpha.getextrema(), (0, 255))
                # AI export has harmless alpha-1 specks; visible content must have a clear margin.
                bounds = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
                self.assertIsNotNone(bounds)
                self.assertGreater(bounds[0], 0); self.assertGreater(bounds[1], 0)
                self.assertLess(bounds[2], icon.width); self.assertLess(bounds[3], icon.height)
                self.assertGreater(alpha.histogram()[0], icon.width * icon.height * .15)

    def test_no_backing_or_frame_layers(self):
        images = self.panel.findall('.//control[@type="image"]')
        self.assertEqual(len(images), 2)
        for node in images:
            self.assertEqual(node.findtext('texture'), '$INFO[ListItem.Icon]')
            self.assertEqual(node.findtext('aspectratio'), 'keep')
        self.assertFalse(self.panel.findall('.//bordertexture'))
        self.assertFalse(self.panel.findall('.//bordersize'))
        self.assertNotIn('masks/', ET.tostring(self.panel, encoding='unicode'))
        self.assertFalse(self.panel.findall('.//control[@type="button"]'))

    def test_actions_visibility_and_grid_contract_unchanged(self):
        items = self.settings.findall('.//control[@id="9000"]/content/item')
        self.assertEqual([(n.findtext('label'), n.findtext('onclick'), n.findtext('visible')) for n in items], BASELINE)
        control = self.settings.find('.//control[@id="9000"]')
        self.assertEqual(control.get('type'), 'panel')
        self.assertEqual(control.findtext('include'), 'SettingsPanel')
        self.assertEqual(control.findtext('onup'), '9000')
        self.assertEqual([n.text for n in control.findall('ondown')], ['9000', 'Control.SetFocus(9001,$INFO[Container(9000).Position],absolute)'])
        for tag in ('itemlayout', 'focusedlayout'):
            layout = self.panel.find(tag)
            self.assertEqual((layout.get('height'), layout.get('width')), ('230', '370'))

    def test_focus_is_enlarged_with_accent_label_without_distortion(self):
        normal = self.panel.find('itemlayout/control[@type="image"]')
        focus = self.panel.find('focusedlayout/control/control[@type="image"]')
        for axis in ('width', 'height'):
            self.assertAlmostEqual(float(focus.findtext(axis)) / float(normal.findtext(axis)), 1.1)
        label = self.panel.find('focusedlayout/control/control[@type="label"]')
        self.assertEqual(label.findtext('textcolor'), '$VAR[FocusColorTheme]')
        self.assertEqual(focus.findtext('centerleft'), normal.findtext('centerleft'))
        self.assertEqual(float(focus.findtext('top')) + float(focus.findtext('height')) / 2,
                         float(normal.findtext('top')) + float(normal.findtext('height')) / 2)

if __name__ == '__main__':
    unittest.main()
