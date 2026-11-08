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
    def runner(self):
        spec = importlib.util.spec_from_file_location('games_native_renderer', ROOT / 'tools/render_games.py')
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        return runner

    def test_enable_prompt_matches_only_exact_fixture_addon(self):
        runner = self.runner()
        labels = {'Control.GetLabel(1)':'Disabled add-ons','Control.GetLabel(9)':'Would you like to enable this add-on?\nFoundry Wallpapers'}
        self.assertTrue(runner.fixture_enable_prompt(labels, 'Foundry Wallpapers'))
        self.assertFalse(runner.fixture_enable_prompt(labels, 'Other addon'))
        labels['Control.GetLabel(9)'] += ' and another addon'
        self.assertFalse(runner.fixture_enable_prompt(labels, 'Foundry Wallpapers'))

    def test_dependency_readiness_rejects_unrelated_dialog_without_accepting(self):
        runner = self.runner(); calls = []
        def rpc(method, params=None):
            calls.append(method)
            if method == 'Addons.GetAddonDetails': return {'addon':{'name':'Foundry Wallpapers','enabled':False}}
            if method == 'XBMC.GetInfoBooleans': return {'System.HasActiveModalDialog':True}
            if method == 'XBMC.GetInfoLabels': return {'Control.GetLabel(1)':'Terms','Control.GetLabel(9)':'Accept unrelated terms?'}
            return 'OK'
        with self.assertRaisesRegex(AssertionError, 'Unrelated dialog'):
            runner.enable_fixture_addons(rpc, ['resource.images.foundry.wallpapers'], {'resource.images.foundry.wallpapers':'Foundry Wallpapers'})
        self.assertNotIn('Input.Select', calls)

    def test_dependency_readiness_waits_for_confirmed_enable(self):
        runner = self.runner(); calls = []; state = {'enabled':False,'prompt':False}
        def rpc(method, params=None):
            calls.append((method, params))
            if method == 'Addons.GetAddonDetails': return {'addon':{'name':'Foundry Wallpapers','enabled':state['enabled']}}
            if method == 'Addons.SetAddonEnabled': state['prompt'] = True
            if method == 'XBMC.GetInfoBooleans': return {'System.HasActiveModalDialog':state['prompt']}
            if method == 'XBMC.GetInfoLabels': return {'Control.GetLabel(1)':'Disabled add-ons','Control.GetLabel(9)':'Would you like to enable this add-on?\nFoundry Wallpapers'}
            if method == 'Input.Select': state.update(enabled=True,prompt=False)
            return 'OK'
        runner.enable_fixture_addons(rpc, ['resource.images.foundry.wallpapers'], {'resource.images.foundry.wallpapers':'Foundry Wallpapers'})
        self.assertTrue(state['enabled'])
        self.assertEqual(1, sum(method == 'Input.Select' for method, params in calls))
        self.assertEqual('Addons.GetAddonDetails', calls[-1][0])

    def test_queued_pulse_before_wallpapers_uses_verified_fixture_allowlist(self):
        runner = self.runner()
        names = {'resource.images.foundry.wallpapers':'Foundry Wallpapers', 'resource.uisounds.foundry.pulse':'Foundry Pulse UI Sounds'}
        enabled = dict.fromkeys(names, False); pending = ['resource.uisounds.foundry.pulse', 'resource.images.foundry.wallpapers']; accepted = []
        def rpc(method, params=None):
            if method == 'Addons.GetAddonDetails':
                aid = params['addonid']; return {'addon':{'name':names[aid],'enabled':enabled[aid]}}
            if method == 'XBMC.GetInfoBooleans': return {'System.HasActiveModalDialog':bool(pending)}
            if method == 'XBMC.GetInfoLabels': return {'Control.GetLabel(1)':'Disabled add-ons','Control.GetLabel(9)':'Would you like to enable this add-on?\n'+names[pending[0]]}
            if method == 'Input.Select':
                aid = pending.pop(0); enabled[aid] = True; accepted.append(aid)
            return 'OK'
        runner.enable_fixture_addons(rpc, list(names), names)
        self.assertEqual(['resource.uisounds.foundry.pulse','resource.images.foundry.wallpapers'], accepted)
        self.assertTrue(all(enabled.values()))

    def test_dependency_allowlist_requires_matching_copied_manifest_name(self):
        runner = self.runner()
        rpc = Mock(return_value={'addon':{'name':'Unexpected name','enabled':False}})
        with self.assertRaisesRegex(AssertionError, 'differs from copied manifest'):
            runner.enable_fixture_addons(rpc, ['copied.id'], {'copied.id':'Expected name'})
        self.assertEqual(['Addons.GetAddonDetails'], [args.args[0] for args in rpc.call_args_list])

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
