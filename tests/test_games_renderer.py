"""Contract checks for the native runner, not a substitute for executing Kodi."""
import ast
import importlib.util
import tempfile
import json
import sys
import time
import types
from urllib.parse import parse_qs, urlsplit
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

    def test_favorites_waits_for_native_refresh_and_uses_real_menu_route(self):
        fixture = self.runner().FIXTURE
        self.assertIn("wait_directory(favorite_route,before_favorite)", fixture)
        self.assertLess(fixture.index('wait_directory(favorite_route,before_favorite)'), fixture.index("home_item(1,'Favorites')"))
        self.assertIn("directory_id()!=previous", fixture)
        self.assertIn("Container.Update(", fixture)
        self.assertIn("Input.SendText", fixture)
        self.assertIn("info('Container.FolderPath')==before_cancel['path']", fixture)
        self.assertNotIn('xbmc.sleep(500)', fixture)

    def helper(self, name):
        tree = ast.parse(self.runner().FIXTURE)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<native-helper>', 'exec'), namespace)
        return namespace[name]

    def test_missing_core_rejects_generic_addon_failure_and_unrelated_modal(self):
        check = self.helper('native_core_dialog')
        expected = dict(chooser='Select emulator for .nes', heading='Failed to play game',
                        messages=["This game isn't compatible with any available emulators.", 'Extract compressed files.'])
        for state in (dict(dialog_id=12000, dialog_heading=expected['chooser'], dialog_message=''),
                      dict(dialog_id=12002, dialog_heading=expected['heading'], dialog_message=expected['messages'][0])):
            self.assertTrue(check(state, expected))
        for state in (dict(dialog_id=12002, dialog_heading='Foundry Games', dialog_message='Unable to complete this operation. StagingError'),
                      dict(dialog_id=12002, dialog_heading=expected['heading'], dialog_message='Unknown error'),
                      dict(dialog_id=12000, dialog_heading='Select source', dialog_message=''),
                      dict(dialog_id=10147, dialog_heading=expected['chooser'], dialog_message='')):
            self.assertFalse(check(state, expected))

    def test_core_readiness_waits_for_progress_but_rejects_settled_wrong_dialog(self):
        tree = ast.parse(self.runner().FIXTURE)
        function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'core_ready')
        state = dict(modal=True, dialog_id=12002, dialog_heading='', dialog_message='', progress_visible=True, updating=False)
        expected = dict(chooser='Select emulator', heading='Failed to play game', messages=['No emulator'])
        def require(condition, message):
            if not condition: raise AssertionError(message)
        namespace = dict(snapshot=lambda:state, expected_core=expected, require=require,
                         native_core_dialog=self.helper('native_core_dialog'), json=json)
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<core-readiness>', 'exec'), namespace)
        ready = namespace['core_ready']
        self.assertFalse(ready())
        state.update(progress_visible=False)
        with self.assertRaisesRegex(AssertionError, 'Unexpected game launch dialog'):
            ready()
        state.update(dialog_heading=expected['heading'], dialog_message=expected['messages'][0])
        self.assertTrue(ready())
        state.update(updating=True)
        self.assertFalse(ready())

    def test_cancel_cannot_complete_from_old_or_running_invocation(self):
        complete = self.helper('invocation_complete')
        records = {'old': dict(id='old', action='search', phase='completed', error='')}
        self.assertFalse(complete(records, 'new', 'search'))
        records['new'] = dict(id='new', action='search', phase='started', error='')
        self.assertFalse(complete(records, 'new', 'search'))
        records['new']['phase'] = 'completed'
        self.assertTrue(complete(records, 'new', 'search'))
        self.assertFalse(complete(records, 'new', 'play'))
        records['new']['error'] = 'traceback'
        self.assertFalse(complete(records, 'new', 'search'))
        fixture = self.runner().FIXTURE
        self.assertLess(fixture.index("wait_invocation_complete(cancel_invocation,'search')"), fixture.index("directory_id()==previous"))
        self.assertLess(fixture.index("wait_invocation_complete(play_invocation,'play',75)"), fixture.index("require(not xbmc.Player().isPlaying()"))

    def test_instrumented_copy_keeps_real_invoker_globals_and_always_completes(self):
        runner = self.runner()
        for error in (False, True):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary); addon = base / 'addon'; addon.mkdir()
                original = "import sys\nresult=(__name__,__file__,list(sys.argv),existing_global)\n"
                if error: original += "raise RuntimeError('fixture error')\n"
                (addon / 'default.py').write_text(original, encoding='utf-8')
                runner.instrument_entrypoint(addon, base / 'records')
                scope = dict(__name__='__main__', __file__=str(addon / 'default.py'), existing_global='retained')
                args = ['plugin://plugin.games.foundry/', '7', '?action=search']
                with patch.object(sys, 'argv', args):
                    if error:
                        with self.assertRaisesRegex(RuntimeError, 'fixture error'):
                            exec((addon / 'default.py').read_text(), scope)
                    else: exec((addon / 'default.py').read_text(), scope)
                self.assertEqual(scope['result'], ('__main__', str(addon / 'default.py'), args, 'retained'))
                records = list((base / 'records').glob('*.json'))
                self.assertEqual(len(records), 1)
                record = json.loads(records[0].read_text())
                self.assertEqual((record['action'], record['phase']), ('search', 'completed'))
                self.assertEqual(bool(record['error']), error)
                self.assertGreaterEqual(record['completed'], record['started'])

    def test_native_game_log_requires_completed_actual_retroplayer_path_and_no_traceback(self):
        runner = self.runner()
        native = '[Foundry Games QA] missing-core begin\nRetroPlayer[PLAYER]: No compatible game client selected, aborting playback\n[Foundry Games QA] missing-core end'
        self.assertEqual((True, True, []), tuple(runner.native_game_log_report(native)[key] for key in ('complete', 'native_gameclient_path', 'failures')))
        self.assertFalse(runner.native_game_log_report(native.split('[Foundry Games QA] missing-core end')[0])['complete'])
        self.assertFalse(runner.native_game_log_report(native.replace('RetroPlayer[PLAYER]', 'Unrelated player'))['native_gameclient_path'])
        self.assertTrue(runner.native_game_log_report(native + '\nPythonToCppException: staging failed')['failures'])

    def test_startup_waits_for_both_real_widgets_and_stable_owned_home(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); records = base / 'records'; records.mkdir()
            log = base / 'kodi.log'
            healthy_log='load skin from: '+str(base/'skin.foundry')+' (version:1.5.0)\nskin loaded...\nWindow Init (Home.xml)'
            log.write_text(healthy_log)
            for mode, phase in (('recent', 'completed'), ('favorites', 'started')):
                (records / (mode + '.json')).write_text(json.dumps(dict(id=mode, action='games', mode=mode, phase=phase, error='', runtime_skin_path=str(base/'skin.foundry'))))
            def rpc(method, params):
                if method == 'GUI.GetProperties': return dict(currentwindow=dict(id=10000), skin=dict(id='skin.foundry'))
                if method == 'Settings.GetSettingValue': return {'value': 'owned-fixture'}
                if method == 'XBMC.GetInfoLabels': return {'Container(9000).NumItems':'19','Container(9000).ListItem.Property(menu_id)':'7000','Container(9000).ListItem.Property(id)':'music'}
                return {'Window.IsVisible(startup)': False, 'System.HasActiveModalDialog': False, 'Container.IsUpdating': False}
            ticks = iter(index / 10 for index in range(100))
            def finish_widget(unused):
                (records / 'favorites.json').write_text(json.dumps(dict(id='favorites', action='games', mode='favorites', phase='completed', error='', runtime_skin_path=str(base/'skin.foundry'))))
            with patch.object(runner.time, 'monotonic', side_effect=lambda: next(ticks)), patch.object(runner.time, 'sleep', side_effect=finish_widget):
                result = runner.settle_startup(rpc, records, log, lambda: True, base, 'owned-fixture', base/'skin.foundry', timeout=3, quiet=.2)
            self.assertTrue(result['passed'])
            self.assertEqual({record['mode'] for record in result['completed_game_widgets']}, {'recent', 'favorites'})
            self.assertGreaterEqual(len(result['observations']), 2)
            self.assertTrue((base / 'startup-readiness.json').exists())
            for failure in ('missing-widget', 'wrong-owner', 'native-crash', 'python-error', 'active-modal', 'configured-only', 'wrong-home-signature'):
                with self.subTest(failure=failure):
                    ticks = iter(index / 10 for index in range(100))
                    def failing_rpc(method, params):
                        value = rpc(method, params)
                        if failure == 'wrong-owner' and method == 'Settings.GetSettingValue': return {'value': 'somebody-else'}
                        if failure == 'wrong-home-signature' and method == 'XBMC.GetInfoLabels': return {'Container(9000).NumItems':'19','Container(9000).ListItem.Property(menu_id)':'','Container(9000).ListItem.Property(id)':'music'}
                        if failure == 'active-modal' and method == 'XBMC.GetInfoBooleans': value['System.HasActiveModalDialog'] = True
                        return value
                    if failure == 'missing-widget': (records / 'favorites.json').unlink()
                    if failure == 'python-error': log.write_text('PythonToCppException: failure')
                    if failure == 'configured-only': log.write_text(healthy_log.replace('skin.foundry','skin.estuary'))
                    with patch.object(runner.time, 'monotonic', side_effect=lambda: next(ticks)), patch.object(runner.time, 'sleep'), self.assertRaises((AssertionError, RuntimeError)):
                        runner.settle_startup(failing_rpc, records, log, lambda: failure != 'native-crash', base, 'owned-fixture', base/'skin.foundry', timeout=.5, quiet=.2)
                    finish_widget(0); log.write_text(healthy_log)

    def test_crash_evidence_keeps_atomic_invocation_records_and_genuine_sources(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); profile = base / 'profile'; output = base / 'output'; output.mkdir()
            for relative, contents in {'profile/temp/kodi.log': 'native log', 'error.txt': 'fixture error',
                    'invocations/search.json': '{"phase":"completed"}',
                    'profile/addons/plugin.games.foundry/default.py': 'genuine wrapper',
                    'profile/addons/script.foundry.gamesqa/fixture.py': 'fixture source',
                    'empty-home/kodi_crashlog-test.log': 'native backtrace'}.items():
                path = base / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(contents)
            (output / 'phase.txt').write_text('startup in progress')
            runner.preserve_fixture_evidence(base, profile, output)
            for relative in ('kodi.log', 'error.txt', 'invocations/search.json', 'instrumented-games-entrypoint.py', 'native-fixture.py', 'kodi_crashlog-test.log'):
                self.assertTrue((output / relative).exists(), relative)
            self.assertEqual((output / 'phase.txt').read_text(), 'startup in progress')

    def test_actual_skin_log_rejects_later_estuary_and_detects_restart_cycle(self):
        runner = self.runner()
        log='load skin from: /owned/skin.foundry/ (version:1.5.0)\nskin loaded...\nfirst Window Init (Home.xml)'
        first=runner.actual_skin_log_state(log,'/owned/skin.foundry')
        self.assertTrue(first['ready'])
        startup=runner.actual_skin_log_state(log+'\nWindow Init (Startup.xml)','/owned/skin.foundry')
        self.assertFalse(startup['ready'])
        restarted=runner.actual_skin_log_state(log+'\nWindow Init (Startup.xml)\nsecond Window Init (Home.xml)','/owned/skin.foundry')
        self.assertTrue(restarted['ready']);self.assertNotEqual(first['last_transition'],restarted['last_transition'])
        self.assertFalse(runner.actual_skin_log_state(log+'\nload skin from: /other/skin.estuary/ (version:4)\nskin loaded...\nWindow Init (Home.xml)','/owned/skin.foundry')['ready'])

    def test_only_exact_unchanged_timer_warning_is_classified_as_baseline(self):
        runner = self.runner()
        known = 'Error parsing boolean expression control.hasfocus($param[list_id])'
        result = runner.skin_boolean_report(known, runner.KNOWN_TIMER_SHA256)
        self.assertEqual(result['known_baseline_warnings']['timers'], [known])
        for log, digest in ((known, '0' * 64), ('Error parsing boolean expression bad.games.expression', runner.KNOWN_TIMER_SHA256)):
            with self.assertRaises(AssertionError): runner.skin_boolean_report(log, digest)
        for name in ('dev-validation.yml', 'release.yml'):
            self.assertIn('kodi gdb xvfb', (ROOT / '.github/workflows' / name).read_text())

    def test_plugin_directory_navigation_posts_then_yields_for_fresh_native_list(self):
        runner = self.runner(); tree = ast.parse(runner.FIXTURE)
        names = {'open_path', 'directory_ready', 'directory_id', 'wait_directory', 'wait', 'info'}
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        for active in (False, True):
            with self.subTest(active=active), tempfile.TemporaryDirectory() as temporary:
                events = []; state = {'path': '', 'directory_id': 'old-directory'}
                class Kodi:
                    def getCondVisibility(self, name): return active if name == 'Window.IsActive(games)' else False
                    def getInfoLabel(self, name):
                        return state['path'] if name == 'Container.FolderPath' else state['directory_id']
                    # Enqueue changes the visible route before native contents.
                    # A wait=True regression is rejected by this signature.
                    def executebuiltin(self, command):
                        events.append(('post', command))
                        state['path'] = 'plugin://plugin.games.foundry/?action=games&system=nes'
                    def sleep(self, duration):
                        # The dependent plugin can finish only when the controller
                        # yields; route/DB state alone must never count as ready.
                        events.append(('yield', duration)); state['directory_id'] = 'fresh-directory'
                namespace = dict(OUTPUT=Path(temporary), xbmc=Kodi(), snapshot=lambda: dict(state),
                                 json=json, time=time, parse_qs=parse_qs, urlsplit=urlsplit)
                exec(compile(ast.Module(body=functions, type_ignores=[]), '<native-navigation>', 'exec'), namespace)
                namespace['open_path']('action=games&system=nes')
                command = 'Container.Update(plugin://plugin.games.foundry/?action=games&system=nes)' if active else 'ActivateWindow(games,plugin://plugin.games.foundry/?action=games&system=nes,return)'
                self.assertEqual(events, [('post', command), ('yield', 100)])
                acknowledgment = json.loads((Path(temporary) / 'directory-acks.jsonl').read_text())
                self.assertEqual(acknowledgment['directory_id'], 'fresh-directory')

    def test_native_png_waits_for_partial_file_to_become_the_genuine_capture(self):
        runner = self.runner()
        from PIL import Image
        for initial in (b'', b'\x89PNG\r\n\x1a\n'):
            with self.subTest(initial=initial), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'actual-capture.png'; path.write_bytes(initial)
                def encode(unused): Image.new('RGB', (1920, 1080), '#123456').save(path)
                with patch.object(runner.time, 'sleep', side_effect=encode) as yielded:
                    runner.verify_capture(path)
                yielded.assert_called_once_with(.1)
                with Image.open(path) as capture:
                    self.assertEqual(capture.size, (1920, 1080))
                    self.assertEqual(capture.getpixel((0, 0)), (18, 52, 86))

    def test_native_png_never_accepts_a_permanently_truncated_capture(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'incomplete.png'; path.write_bytes(b'\x89PNG\r\n\x1a\n')
            ticks = iter(index / 10 for index in range(20))
            with patch.object(runner.time, 'monotonic', side_effect=lambda: next(ticks)), patch.object(runner.time, 'sleep'), self.assertRaisesRegex(AssertionError, 'did not finish encoding'):
                runner.verify_capture(path, timeout=.4)
            self.assertEqual(path.read_bytes(), b'\x89PNG\r\n\x1a\n')

    def test_native_png_rejects_wrong_dimensions_and_wait_precedes_teardown(self):
        runner = self.runner()
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'wrong-size.png'; Image.new('RGB', (100, 100)).save(path)
            with patch.object(runner.time, 'sleep') as sleep, self.assertRaisesRegex(AssertionError, 'wrong dimensions'):
                runner.verify_capture(path)
            sleep.assert_not_called()
        source = (ROOT / 'tools/render_games.py').read_text(encoding='utf-8')
        self.assertLess(source.index("verify_capture(output /"), source.index('stop_process_group(kodi)'))

    def test_capture_settles_after_real_fades_and_matches_dialog_state(self):
        runner=self.runner();tree=ast.parse(runner.FIXTURE)
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='settle_capture')
        clock={'now':0.0}
        def snapshot():
            return dict(directory_id='new',viewmode='Foundry Games',game_id='game',dialog_id=9999,modal=False,
                        updating=False,busy_visible=False,progress_visible=clock['now']<.25)
        class Kodi:
            def sleep(self,duration):clock['now']+=duration/1000
        namespace=dict(snapshot=snapshot,time=types.SimpleNamespace(monotonic=lambda:clock['now']),
                       xbmc=Kodi(),json=json,CAPTURE_SETTLE_SECONDS=.5)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<capture-settle>','exec'),namespace)
        result=namespace['settle_capture']()
        self.assertEqual(result['directory_id'],'new');self.assertGreaterEqual(clock['now'],.75)
        animations=ET.parse(ROOT.parent/'skin.foundry-nimbus/xml/Includes_Animations.xml').getroot()
        fade=animations.find("include[@name='Visible_Fade']")
        dialog=animations.find("include[@name='Animation_DialogPopupOpenClose']")
        bounds=[int(node.get('time','0'))+int(node.get('delay','0')) for node in list(fade.iter('animation'))+list(dialog.iter('effect'))]
        self.assertGreater(500,max(bounds))

    def test_capture_acknowledges_only_the_actual_fully_encoded_png_once(self):
        runner=self.runner();from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);output=base/'output';output.mkdir()
            path=output/'games-favorites.png';path.write_bytes(b'')
            (base/'capture-request.json').write_text(json.dumps(dict(sequence=1,case='games-favorites',stable_seconds=.5)))
            def encode(unused):
                self.assertFalse((base/'capture-complete.json').exists())
                Image.new('RGB',(1920,1080),'#345678').save(path)
            with patch.object(runner.time,'sleep',side_effect=encode):runner.acknowledge_capture(base,output)
            result=json.loads((base/'capture-complete.json').read_text())
            self.assertEqual((result['sequence'],result['case'],result['passed']),(1,'games-favorites',True))
            runner.acknowledge_capture(base,output)
            self.assertEqual(len((output/'capture-acknowledgments.jsonl').read_text().splitlines()),1)

    def test_shot_cannot_return_from_an_old_png_completion_ack(self):
        runner=self.runner();tree=ast.parse(runner.FIXTURE)
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in {'shot','wait','require'}]
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);state=dict(directory_id='fresh',viewmode='Foundry Games',game_id='game')
            (base/'capture-complete.json').write_text(json.dumps(dict(sequence=99,case='old',passed=True)))
            evidence=[];events=[]
            class Kodi:
                def executebuiltin(self,command):(base/'games-favorites.png').write_bytes(b'capture')
                def sleep(self,duration):
                    self.assert_no_evidence()
                    events.append('yielded-for-host')
                    (base/'capture-complete.json').write_text(json.dumps(dict(sequence=1,case='games-favorites',passed=True)))
                def assert_no_evidence(self):
                    if evidence:raise AssertionError('Capture advanced before matching PNG acknowledgment')
            namespace=dict(BASE=base,OUTPUT=base,xbmc=Kodi(),json=json,time=time,snapshot=lambda:dict(state),core_covers_busy=lambda state,expected:False,
                           settle_capture=lambda expected:dict(state),capture_sequence=0,CAPTURE_SETTLE_SECONDS=.5,evidence=evidence)
            exec(compile(ast.Module(body=functions,type_ignores=[]),'<capture-ack>','exec'),namespace)
            namespace['shot']('games-favorites')
            self.assertEqual(events,['yielded-for-host']);self.assertTrue(evidence[0]['png_completion_ack'])
            source=runner.FIXTURE
            self.assertIn("require(snapshot()==state,'Native state changed during PNG encoding')",source)

    def test_posterflow_warning_needs_exact_published_bytes_and_inputs(self):
        runner=self.runner();warning='Error parsing boolean expression '+runner.POSTERFLOW_EXPRESSION
        proof=dict(current_sha256=runner.KNOWN_POSTERFLOW_SHA256,published_140_sha256=runner.KNOWN_POSTERFLOW_SHA256,
                   bytes_equal=True,current_inputs=dict(runner.BASELINE_EXPRESSION_INPUTS),published_140_inputs=dict(runner.BASELINE_EXPRESSION_INPUTS))
        result=runner.skin_boolean_report(warning,runner.KNOWN_TIMER_SHA256,proof)
        self.assertEqual(result['known_baseline_warnings']['posterflow'],[warning])
        for changes in ({'current_sha256':'0'*64},{'published_140_sha256':'0'*64},{'bytes_equal':False},{'current_inputs':{}}):
            with self.subTest(changes=changes),self.assertRaises(AssertionError):runner.skin_boolean_report(warning,runner.KNOWN_TIMER_SHA256,dict(proof,**changes))
        with self.assertRaises(AssertionError):runner.skin_boolean_report(warning,runner.KNOWN_TIMER_SHA256)
        with self.assertRaises(AssertionError):runner.skin_boolean_report('Error parsing boolean expression new.games.condition',runner.KNOWN_TIMER_SHA256,proof)

    def test_only_exact_topmost_native_core_can_cover_render_suppressed_busy(self):
        runner=self.runner();tree=ast.parse(runner.FIXTURE)
        names={'native_core_dialog','core_covers_busy','settle_capture'}
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        expected=dict(chooser='Select emulator for .nes',heading='Failed to play game',messages=['No compatible emulator.'])
        base=dict(modal=True,dialog_id=12002,dialog_heading=expected['heading'],dialog_message=expected['messages'][0],
                  updating=False,progress_visible=False,busy_visible=True,busy_dialog_visible=True,busy_nocancel_visible=False)
        for failure in (None,'chooser','no-explicit-core','generic-error','busy-topmost','nocancel-busy','progress','unrelated-modal'):
            with self.subTest(failure=failure):
                clock={'now':0.0};state=dict(base)
                if failure=='chooser':state.update(dialog_id=12000,dialog_heading=expected['chooser'],dialog_message='')
                if failure=='generic-error':state.update(dialog_heading='Foundry Games',dialog_message='Unable to complete this operation')
                if failure=='busy-topmost':state['dialog_id']=10138
                if failure=='nocancel-busy':state['busy_nocancel_visible']=True
                if failure=='progress':state['progress_visible']=True
                if failure=='unrelated-modal':state.update(busy_visible=False,busy_dialog_visible=False,dialog_heading='Unrelated message')
                class Kodi:
                    def sleep(self,duration):clock['now']+=duration/1000
                namespace=dict(snapshot=lambda:dict(state),xbmc=Kodi(),time=types.SimpleNamespace(monotonic=lambda:clock['now']),json=json,CAPTURE_SETTLE_SECONDS=.5)
                exec(compile(ast.Module(body=functions,type_ignores=[]),'<native-modal-stack>','exec'),namespace)
                if failure in (None,'chooser'):
                    result=namespace['settle_capture'](expected,timeout=1)
                    self.assertTrue(namespace['core_covers_busy'](result,expected));self.assertGreaterEqual(clock['now'],.5)
                else:
                    with self.assertRaisesRegex(AssertionError,'did not settle'):
                        namespace['settle_capture'](None if failure=='no-explicit-core' else expected,timeout=.7)

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
            for name in ('Home.xml','MyGames.xml','Includes.xml','View_58_FoundryGames.xml','Font.xml','Timers.xml','View_51_PosterFlow.xml','Expressions.xml','Includes_Animations.xml'):
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
