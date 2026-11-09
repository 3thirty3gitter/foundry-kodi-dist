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

    def test_home_game_widgets_keep_native_row_and_declared_plugin_routes(self):
        group = ET.parse(SKIN / 'xml/Home.xml').find(".//control[@id='17001']")
        rows = [node for node in group.findall('include') if node.find("param[@name='list_id']") is not None]
        self.assertEqual(['17200', '17300', '17400'], [node.find("param[@name='list_id']").get('value') for node in rows])
        self.assertEqual('addons://sources/game/', rows[0].find("param[@name='content_path']").get('value'))
        self.assertIsNone(rows[0].get('condition'))
        for row, mode, title in zip(rows[1:], ('recent', 'favorites'), ('Recently played games', 'Favorite games')):
            self.assertEqual('WidgetListPoster', row.get('content'))
            self.assertEqual('System.HasAddon(plugin.games.foundry)', row.get('condition'))
            self.assertEqual('plugin://plugin.games.foundry/?action=games&mode=' + mode, row.find("param[@name='content_path']").get('value'))
            self.assertEqual(title, row.find("param[@name='widget_header']").get('value'))
            self.assertEqual('games', row.find("param[@name='widget_target']").get('value'))

    def test_build_requests_both_new_features_without_emulator_binaries(self):
        root = ET.parse(ROOT / 'src/script.program.foundry-build/addon.xml')
        dependencies = {n.get('addon'):n.get('version') for n in root.findall('requires/import')}
        self.assertEqual(dependencies['plugin.games.foundry'], '0.1.0')
        self.assertEqual(dependencies['weather.foundry.canada'], '0.1.0')
        self.assertFalse(any(name.startswith('game.libretro.') for name in dependencies))


if __name__ == '__main__':
    unittest.main()
