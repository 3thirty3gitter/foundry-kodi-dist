"""The expedited release must not install or publish the deferred Games port."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / 'skin.foundry-nimbus'


class DeferredGamesRelease(unittest.TestCase):
    def test_release_feed_and_installer_exclude_games(self):
        release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
        self.assertEqual(len(release['packages']), 9)
        self.assertNotIn('plugin.games.foundry', [p['id'] for p in release['packages']])
        self.assertNotIn('plugin.games.foundry', [a.get('id') for a in ET.parse(ROOT / 'addons.xml').getroot()])
        imports = ET.parse(ROOT / 'src/script.program.foundry-build/addon.xml').findall('./requires/import')
        self.assertNotIn('plugin.games.foundry', [a.get('addon') for a in imports])
        self.assertFalse((ROOT / 'src/plugin.games.foundry').exists())
        self.assertFalse((ROOT / 'plugin.games.foundry/plugin.games.foundry-0.1.0.zip').exists())

    def test_skin_retains_only_native_games_navigation(self):
        home = ET.parse(SKIN / 'xml/Home.xml')
        actions = [x for x in home.iter('onclick') if 'ActivateWindow(Games)' == x.text]
        self.assertEqual(len(actions), 1)
        self.assertIsNone(actions[0].get('condition'))
        self.assertNotIn('plugin.games.foundry', (SKIN / 'xml/Home.xml').read_text(encoding='utf-8'))
        games = ET.parse(SKIN / 'xml/MyGames.xml').getroot()
        self.assertNotIn('58', games.findtext('views').split(','))
        self.assertNotIn('View_58_FoundryGames', (SKIN / 'xml/Includes.xml').read_text(encoding='utf-8'))
        self.assertFalse((SKIN / 'xml/View_58_FoundryGames.xml').exists())

    def test_deferred_work_is_not_copied_into_packaged_validation(self):
        spec = importlib.util.spec_from_file_location('deferred_packaging_qa', ROOT / 'tools/verify_packaged_sources.py')
        qa = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(qa)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / 'source'
            (root / 'deferred/games').mkdir(parents=True)
            (root / 'deferred/games/not-shipped.py').write_text('not a package')
            staged = qa.stage_workspace(root, base / 'validation', {'packages': []})
            self.assertFalse((staged / 'deferred').exists())


if __name__ == '__main__':
    unittest.main()
