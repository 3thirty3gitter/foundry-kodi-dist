"""Games navigation, native fallback, dependencies and declared view contracts."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / 'skin.foundry-nimbus'


class GamesIntegration(unittest.TestCase):
    def test_home_uses_plugin_only_when_installed_and_retains_native_fallback(self):
        root = ET.parse(SKIN / 'xml/Home.xml')
        items = [item for item in root.findall('.//item') if item.findtext("property[@name='id']") == 'games']
        self.assertEqual(len(items), 1)
        self.assertEqual([(c.get('condition'), c.text) for c in items[0].findall('onclick')], [
            ('System.HasAddon(plugin.games.foundry)', 'ActivateWindow(games,plugin://plugin.games.foundry/,return)'),
            ('!System.HasAddon(plugin.games.foundry)', 'ActivateWindow(Games)')])

    def test_game_view_is_registered_and_other_views_remain(self):
        root = ET.parse(SKIN / 'xml/MyGames.xml')
        self.assertEqual(root.findtext('views').split(','), ['50','51','52','54','56','58','500','501'])
        self.assertEqual(len([n for n in root.findall('.//include') if n.text == 'View_58_FoundryGames']), 1)
        includes = ET.parse(SKIN / 'xml/Includes.xml')
        self.assertEqual(len(includes.findall("include[@file='View_58_FoundryGames.xml']")), 1)

    def test_build_requests_both_new_features_without_emulator_binaries(self):
        root = ET.parse(ROOT / 'src/script.program.foundry-build/addon.xml')
        dependencies = {n.get('addon'):n.get('version') for n in root.findall('requires/import')}
        self.assertEqual(dependencies['plugin.games.foundry'], '0.1.0')
        self.assertEqual(dependencies['weather.foundry.canada'], '0.1.0')
        self.assertFalse(any(name.startswith('game.libretro.') for name in dependencies))


if __name__ == '__main__':
    unittest.main()
