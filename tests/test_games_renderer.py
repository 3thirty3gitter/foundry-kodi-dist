"""Contract checks for the native runner, not a substitute for executing Kodi."""
import ast
import importlib.util
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch, call
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
        self.assertIn("info('Container(58).NumItems')", fixture)
        self.assertNotIn('control.size()', fixture)
        self.assertNotIn('getControl(58)', fixture)
        self.assertIn("'SetFocus(58,'+str(index)+',absolute)'", fixture)
        self.assertIn('NOT A ROM', source)
        self.assertIn("tempfile.TemporaryDirectory(prefix='foundry-games-qa-')", source)
        self.assertIn("HOME=str(base / 'empty-home')", source)
        self.assertIn("['release']", source)
        self.assertNotIn('releases/1.3.9-qa', source)

    def test_cleanup_kills_owned_group_after_launcher_exits(self):
        spec = importlib.util.spec_from_file_location('games_native_renderer', ROOT / 'tools/render_games.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        process = Mock(pid=54321)
        with patch.object(runner.os, 'killpg', create=True) as killpg, patch.object(runner.signal, 'SIGKILL', 9, create=True):
            runner.stop_process_group(process)
        self.assertEqual([call(54321, runner.signal.SIGTERM), call(54321, 9)], killpg.call_args_list)
        self.assertEqual([call(timeout=10), call(timeout=5)], process.wait.call_args_list)

    def test_full_skin_host_preserves_ui_and_disables_only_copied_services(self):
        spec = importlib.util.spec_from_file_location('games_native_renderer', ROOT / 'tools/render_games.py')
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); source = base / 'source'; home = base / 'kodi'; profile = home / 'portable_data'
            for aid in ('resource.images.foundry.wallpapers', 'resource.images.foundry.osd', 'resource.uisounds.foundry.pulse', 'script.foundry.helper', 'skin.foundry'):
                path = source / 'src' / aid; path.mkdir(parents=True)
                manifest = '<addon id="%s"><requires><import addon="xbmc.python"/><import addon="unused.network"/></requires>' % aid
                if aid == 'script.foundry.helper':
                    manifest += '<extension point="xbmc.service" library="service.py"/><extension point="xbmc.python.script" library="default.py"/>'
                    (path / 'default.py').write_text('original helper setup')
                (path / 'addon.xml').write_text(manifest + '</addon>')
            skin = source / 'src/skin.foundry'; (skin / 'xml').mkdir(); (skin / 'fonts').mkdir()
            for name in ('Home.xml','MyGames.xml','Includes.xml','View_58_FoundryGames.xml','Font.xml'):
                (skin / 'xml' / name).write_text('<unchanged name="%s" />' % name)
            (skin / 'fonts/example.ttf').write_bytes(b'original-font-fixture')
            ids, hashes = runner.prepare_shipped_skin(home, profile, skin, source / 'src/script.foundry.helper', source)
            self.assertIn('skin.foundry', ids)
            self.assertIn('fonts/example.ttf', hashes)
            for relative in hashes:
                self.assertEqual((skin / relative).read_bytes(), (profile / 'addons/skin.foundry' / relative).read_bytes())
            helper = profile / 'addons/script.foundry.helper'
            self.assertIsNone(ET.parse(helper / 'addon.xml').find("extension[@point='xbmc.service']"))
            self.assertIn('disabled', (helper / 'default.py').read_text())
            self.assertEqual('original helper setup', (source / 'src/script.foundry.helper/default.py').read_text())

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
