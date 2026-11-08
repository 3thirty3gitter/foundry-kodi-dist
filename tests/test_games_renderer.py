"""Contract checks for the native runner, not a substitute for executing Kodi."""
import ast
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class GamesRendererTests(unittest.TestCase):
    def test_embedded_fixture_python38_syntax(self):
        source = (ROOT / 'tools/render_games.py').read_text(encoding='utf-8')
        tree = ast.parse(source, feature_version=(3, 8))
        fixture = next(node.value.value for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'FIXTURE' for target in node.targets))
        fixture_tree = ast.parse(fixture, feature_version=(3, 8))
        self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(fixture_tree)),
                         'Embedded Kodi Python may be optimized: use explicit require/raise')
        self.assertIn('scanned=db.scan(sid)', fixture)
        self.assertIn('require(scanned==45', fixture)
        self.assertIn('NOT A ROM', source)
        self.assertIn("tempfile.TemporaryDirectory(prefix='foundry-games-qa-')", source)
        self.assertIn("HOME=str(base / 'empty-home')", source)
        self.assertIn("['release']", source)
        self.assertNotIn('releases/1.3.9-qa', source)

    def test_skin_view_uses_game_properties(self):
        path = ROOT.parent / 'skin.foundry-nimbus/xml/View_58_FoundryGames.xml'
        if not path.exists(): self.skipTest('Skin checkout not supplied')
        root = ET.parse(path).getroot()
        view = root.find("include[@name='View_58_FoundryGames']")
        panel = view.find("control[@id='58']")
        self.assertEqual('horizontal', panel.findtext('orientation'))
        self.assertIn('plugin.games.foundry', panel.findtext('visible'))
        text = path.read_text(encoding='utf-8')
        self.assertIn('Foundry.Game.Overview', text)
        self.assertIn('Foundry.Game.Platform', text)
        self.assertNotIn('foundry.metadata', text)
        for control in view.iter('control'):
            if control.attrib.get('type') in ('label', 'textbox'):
                self.assertIsNotNone(control.find('width'))
                self.assertIsNotNone(control.find('height'))


if __name__ == '__main__': unittest.main()
