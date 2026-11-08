"""Portable fixture construction checks, not a claim of native Linux rendering."""
import ast
import importlib.util
import json
from pathlib import Path
import runpy
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as E

from test_weather_client_model import model, NOW
from foundry_weather_test_lib import client, kodi_bridge
from test_weather_kodi_bridge import Window

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('foundry_weather_renderer', ROOT / 'tools/render_weather.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class WeatherRendererTests(unittest.TestCase):
    def test_output_follows_generated_release_not_historical_constant(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            renderer.write(root / 'release.json', json.dumps({'release': '1.4.0-test'}))
            self.assertEqual(renderer.output_directory(root=root), root / 'releases/1.4.0-test-qa')
            self.assertEqual(renderer.output_directory(root / 'chosen'), root / 'chosen')
            renderer.write(root / 'release.json', json.dumps({'release': '../../outside'}))
            with self.assertRaises(ValueError):renderer.output_directory(root=root)

    def test_synthetic_fresh_exercises_complete_contract(self):
        case = renderer.scenario(now=NOW)
        model.validate_feature(case['payload'], 'on-118')
        normalized = model.normalize(case['payload'], 'en', NOW)
        values = kodi_bridge.build_properties(normalized, case['fetched'])
        self.assertEqual(values['Foundry.Weather.Temperature'], '0\u00b0C')
        self.assertEqual(values['Foundry.Weather.DayCount'], '7')
        self.assertEqual(values['Foundry.Weather.HourCount'], '24')
        self.assertEqual(values['Foundry.Weather.AlertCount'], '1')
        self.assertIn('SYNTHETIC TEST ADVISORY', values['Foundry.Weather.Alert.1.Headline'])

    def test_synthetic_missing_and_stale(self):
        case = renderer.scenario('missing', NOW)
        values = kodi_bridge.build_properties(model.normalize(case['payload'], 'en', NOW), case['fetched'])
        self.assertEqual(values['Foundry.Weather.Temperature'], '')
        self.assertEqual(values['Foundry.Weather.HasCurrent'], 'false')
        self.assertEqual(values['Foundry.Weather.HourCount'], '0')
        case = renderer.scenario('stale', NOW)
        values = kodi_bridge.build_properties(model.normalize(case['payload'], 'en', NOW), case['fetched'], case['stale'])
        self.assertEqual(values['Foundry.Weather.AlertStatus'], 'unverified')
        self.assertEqual(values['Foundry.Weather.Stale'], 'true')

    def test_embedded_kodi_scripts_compile_without_execution(self):
        for source in (renderer.FIXTURE, renderer.PROVIDER_WRAPPER):
            tree = ast.parse(source, feature_version=(3, 8))
            self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(tree)),
                             'Kodi optimizes embedded Python; mandatory checks must use explicit raises')
        compile((ROOT / 'tools/render_weather.py').read_text(encoding='utf-8'), 'render_weather.py', 'exec')

    def test_controller_uses_native_navigation_not_borrowed_controls(self):
        self.assertNotIn('.getControl(', renderer.FIXTURE)
        self.assertNotIn('menu.size()', renderer.FIXTURE)
        self.assertNotIn('getListItem(', renderer.FIXTURE)
        self.assertIn('Container(9000).NumItems', renderer.FIXTURE)
        self.assertIn('SetFocus(9000,%d,absolute)', renderer.FIXTURE)
        self.assertIn("xbmc.getInfoLabel('Control.GetLabel(5)')", renderer.FIXTURE)

    def test_refresh_qa_clicks_shipped_home_buttons_without_weather_window_initialization(self):
        source = (ROOT / 'tools/render_weather.py').read_text(encoding='utf-8')
        self.assertNotIn('Weather.Refresh', renderer.FIXTURE)
        self.assertNotIn('ActivateWindow(weather)', source)
        self.assertIn('click_action(15153)', source)
        self.assertIn('click_action(15152)', source)
        self.assertIn("{'setting': 'weather.currentlocation'}", source)

    def test_command_acknowledgment_follows_completed_action(self):
        tree = ast.parse(renderer.FIXTURE)
        dispatch = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                        and ast.unparse(node.test) == 'command.exists()')
        code = compile(ast.Module(body=[dispatch], type_ignores=[]), '<fixture-command>', 'exec')
        with tempfile.TemporaryDirectory() as temp:
            command = Path(temp) / 'command.json'
            renderer.atomic_json(command, {'action': 'focus-menu'})
            def focusing():
                self.assertTrue(command.exists(), 'Host must still wait while native focus changes')
            exec(code, {'command': command, 'json': json, 'focus_menu': focusing})
            self.assertFalse(command.exists())
            renderer.atomic_json(command, {'action': 'focus-menu'})
            def failed():
                raise RuntimeError('native menu still missing')
            with self.assertRaises(RuntimeError):
                exec(code, {'command': command, 'json': json, 'focus_menu': failed})
            self.assertTrue(command.exists(), 'Failed action must not acknowledge completion')

    def test_menu_readiness_rejects_stale_card_or_wrong_window_state(self):
        ready = {'window': 10000, 'focus': 9000, 'category': 'weather', 'dialog': False}
        self.assertTrue(renderer.weather_menu_ready(ready))
        for patch_value in ({'focus': 15150}, {'category': 'musicvideos'}, {'window': 10025}, {'dialog': True}):
            self.assertFalse(renderer.weather_menu_ready(dict(ready, **patch_value)))
        tree = ast.parse((ROOT / 'tools/render_weather.py').read_text(encoding='utf-8'))
        command = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'command')
        statements = [ast.unparse(node) for node in command.body]
        self.assertTrue(statements[1].startswith('atomic_json('))
        self.assertTrue(statements[2].startswith('wait_for('))
        self.assertIn('weather_menu_ready(state())', statements[3])

    def test_visibility_observes_shipped_parent_without_modifying_xml(self):
        condition = renderer.card_parent_visibility(ROOT.parent / 'skin.foundry-nimbus')
        self.assertEqual(condition, 'String.IsEqual(Weather.Plugin,weather.foundry.canada)')
        self.assertIn('parent_visible=xbmc.getCondVisibility(CARD_PARENT_VISIBLE)', renderer.FIXTURE)
        self.assertIn('card_visible=child_visible and parent_visible', renderer.FIXTURE)
        self.assertIn("ControlGroup(15001).HasFocus", renderer.FIXTURE)
        source = (ROOT / 'tools/render_weather.py').read_text(encoding='utf-8')
        self.assertIn("rpc('Input.Right')", source)
        self.assertNotIn('SetFocus(15150)', source)
        with tempfile.TemporaryDirectory() as temp:
            skin = Path(temp)
            renderer.write(skin / 'xml/Includes_FoundryCanadaWeather.xml', '<includes/>')
            with self.assertRaises(ValueError):renderer.card_parent_visibility(skin)

    def test_title_render_check_has_positive_and_absent_controls(self):
        from PIL import Image, ImageDraw
        absent = Image.new('RGB', (1920, 1080), (10, 20, 35))
        present = absent.copy()
        ImageDraw.Draw(present).rectangle((338, 318, 637, 351), fill=(73, 220, 242))
        self.assertEqual(renderer.card_title_pixels(absent), 0)
        self.assertEqual(renderer.card_title_pixels(present), 300 * 34)

    def test_private_port_rejects_an_existing_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            with self.assertRaises(OSError):renderer.available_port(listener.getsockname()[1])
            self.assertNotEqual(renderer.available_port(), listener.getsockname()[1])

    def test_readiness_requires_own_log_and_unique_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            logfile = Path(temp) / 'kodi.log'
            rpc = Mock(side_effect=['pong', {'value': 'weather-private-fixture'}])
            self.assertFalse(renderer.fixture_ready(rpc, logfile, 54321, 'weather-private-fixture'))
            rpc.assert_not_called()
            renderer.write(logfile, 'info <CWebserver[54321]>: Started\n')
            self.assertTrue(renderer.fixture_ready(rpc, logfile, 54321, 'weather-private-fixture'))
            rpc.side_effect = ['pong', {'value': 'older-renderer'}]
            self.assertFalse(renderer.fixture_ready(rpc, logfile, 54321, 'weather-private-fixture'))
            rpc.side_effect = TimeoutError('starting')
            self.assertFalse(renderer.fixture_ready(rpc, logfile, 54321, 'weather-private-fixture'))

    def test_cleanup_kills_remaining_children_after_launcher_exits(self):
        process = Mock(pid=43210)
        with patch.object(renderer.os, 'killpg', create=True) as killpg, \
                patch.object(renderer.signal, 'SIGKILL', 9, create=True):
            renderer.stop_process_group(process)
        self.assertEqual([call.args[1] for call in killpg.call_args_list],
                         [renderer.signal.SIGTERM, 0, 9])
        self.assertTrue(all(call.args[0] == process.pid for call in killpg.call_args_list))

    def test_cleanup_does_not_signal_a_nonexistent_group(self):
        process = Mock(pid=43210)
        with patch.object(renderer.os, 'killpg', side_effect=ProcessLookupError, create=True) as killpg:
            renderer.stop_process_group(process)
        self.assertEqual(killpg.call_count, 2)

    def test_fixture_executes_shipped_entrypoint_with_synthetic_client(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            window = Window()
            settings = {'language': 'en', 'location1_id': 'on-118', 'location1_label': 'Ottawa, ON'}
            addon = Mock()
            addon.getSetting.side_effect = lambda key: settings.get(key, '')
            addon.getAddonInfo.return_value = str(base / 'profile')
            def native_default_addon():
                # Match Omega LanguageHook::GetAddonId rather than a constant
                # lambda, so runpy losing Kodi's __main__ identity is caught.
                current = vars(sys.modules['__main__'])
                self.assertEqual(current.get('__xbmcaddonid__'), renderer.PROVIDER)
                self.assertEqual(current.get('__xbmcapiversion__'), '3.0.0')
                self.assertEqual(current.get('__xbmcinvokerid__'), 91)
                return addon
            modules = {'xbmc': types.SimpleNamespace(getInfoLabel=lambda _: renderer.PROVIDER,
                    getRegion=lambda key: '\u00b0C' if key == 'tempunit' else '%H:%M', LOGWARNING=2, log=Mock(),
                    executeJSONRPC=lambda _: '{"result":{"value":1}}'),
                'xbmcaddon': types.SimpleNamespace(Addon=native_default_addon),
                'xbmcgui': types.SimpleNamespace(Window=lambda _: window),
                'xbmcvfs': types.SimpleNamespace(translatePath=lambda value: value),
                'resources': types.ModuleType('resources'),
                'resources.lib': sys.modules['foundry_weather_test_lib'],
                'resources.lib.client': client, 'resources.lib.model': model,
                'resources.lib.kodi_bridge': kodi_bridge}
            original = (ROOT / 'src/weather.foundry.canada/default.py').read_text(encoding='utf-8')
            renderer.write(base / 'shipped_default.py', original)
            renderer.atomic_json(base / 'scenario.json', renderer.scenario())
            wrapper = base / 'default.py'
            renderer.write(wrapper, 'from pathlib import Path\nBASE=Path(%r)\n' % str(base) + renderer.PROVIDER_WRAPPER)
            with patch.dict(sys.modules, modules), patch.object(sys, 'argv', [str(wrapper), '1']), \
                    patch.object(client, 'Client'), patch.object(client, 'transport'):
                runpy.run_path(str(wrapper), init_globals={'__xbmcaddonid__': renderer.PROVIDER,
                    '__xbmcapiversion__': '3.0.0', '__xbmcinvokerid__': 91}, run_name='__main__')
            self.assertEqual(window.getProperty('Foundry.Weather.Temperature'), '0\u00b0C')
            self.assertEqual(window.getProperty('Foundry.Weather.HourCount'), '24')
            self.assertFalse((base / 'provider-error.txt').exists())
            completed = json.loads((base / 'provider-complete.json').read_text(encoding='utf-8'))
            self.assertEqual(completed['argument'], '1')
            self.assertEqual(completed['kind'], 'fresh')

    def test_fixture_preparation_preserves_original_home_and_entrypoint(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            dist, skin, helper, kodi, work = [base / name for name in ('dist', 'skin', 'helper', 'kodi-source', 'work')]
            def addon(path, identifier, extensions=''):
                renderer.write(path / 'addon.xml', '<addon id="%s"><requires><import addon="xbmc.python"/><import addon="script.module.requests"/></requires>%s</addon>' % (identifier, extensions))
            addon(skin, 'skin.foundry')
            addon(helper, 'script.foundry.helper', '<extension point="xbmc.python.library" library="resources/lib/default.py"/><extension point="xbmc.service" library="service.py"/>')
            renderer.write(helper / 'resources/lib/default.py', "raise RuntimeError('Original helper must not run')\n")
            for identifier in ('resource.images.foundry.wallpapers', 'resource.images.foundry.osd', 'resource.uisounds.foundry.pulse', renderer.PROVIDER):
                addon(dist / 'src' / identifier, identifier)
            provider = dist / 'src' / renderer.PROVIDER
            original = "print('original shipped entrypoint')\n"
            renderer.write(provider / 'default.py', original)
            for name in ('Home.xml', 'Includes.xml', 'Includes_FoundryCanadaWeather.xml', 'Font.xml'):
                renderer.write(skin / 'xml' / name, '<fixture name="%s"/>\n' % name)
            addon(kodi / 'addons/service.fixture', 'service.fixture', '<extension point="xbmc.service" library="service.py"/>')
            with patch.object(renderer, 'ROOT', dist):
                home, profile, identifiers, hashes = renderer.prepare(work, kodi, skin, helper)
            self.assertEqual((profile / 'addons/weather.foundry.canada/shipped_default.py').read_text(encoding='utf-8'), original)
            self.assertEqual((provider / 'default.py').read_text(encoding='utf-8'), original)
            self.assertEqual((profile / 'addons/skin.foundry/xml/Home.xml').read_bytes(), (skin / 'xml/Home.xml').read_bytes())
            self.assertIn('weather_default.py', hashes)
            self.assertIn('client.Client=SyntheticClient', (profile / 'addons/weather.foundry.canada/default.py').read_text(encoding='utf-8'))
            self.assertNotIn('RuntimeError', (profile / 'addons/script.foundry.helper/resources/lib/default.py').read_text(encoding='utf-8'))
            self.assertIsNone(E.parse(home / 'addons/service.fixture/addon.xml').find("extension[@point='xbmc.service']"))
            self.assertIsNotNone(E.parse(kodi / 'addons/service.fixture/addon.xml').find("extension[@point='xbmc.service']"))
            self.assertLess(identifiers.index('script.foundry.helper'), identifiers.index('skin.foundry'))


if __name__ == '__main__':
    unittest.main()
