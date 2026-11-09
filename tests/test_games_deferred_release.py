"""Published 1.4.0 and the preserved Games originals remain immutable."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / 'skin.foundry-nimbus'


class DeferredGamesRelease(unittest.TestCase):
    def test_published_140_installer_and_skin_exclude_games(self):
        for addon, version in (('script.program.foundry-build', '1.4.0'), ('skin.foundry', '1.4.0')):
            with zipfile.ZipFile(ROOT / addon / (addon + '-' + version + '.zip')) as bundle:
                manifest = ET.fromstring(bundle.read(addon + '/addon.xml'))
                self.assertNotIn('plugin.games.foundry', [node.get('addon') for node in manifest.findall('./requires/import')])
                if addon == 'skin.foundry':
                    home = bundle.read(addon + '/xml/Home.xml').decode('utf-8')
                    self.assertNotIn('plugin.games.foundry', home)
                    self.assertNotIn(addon + '/xml/View_58_FoundryGames.xml', bundle.namelist())

    def test_original_deferred_source_is_preserved(self):
        if not (ROOT / '.git').exists():
            self.skipTest('Preserved originals are excluded from extracted-package workspaces')
        self.assertTrue((ROOT / 'deferred/games/src/plugin.games.foundry/addon.xml').exists())
        self.assertTrue((ROOT / 'deferred/games/tools/render_games.py').exists())
        self.assertTrue((ROOT / 'src/plugin.games.foundry/addon.xml').exists())

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
