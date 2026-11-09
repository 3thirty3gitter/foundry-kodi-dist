"""Native playback diagnostics must not silently pass callback failures."""
import ast
import importlib.util
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('playback_interface_renderer',ROOT/'tools/render_interface.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)


class PlaybackStopRenderer(unittest.TestCase):
    def test_native_traceback_is_preserved_inside_playback_interval(self):
        trace='PythonToCppException\nError Contents: native list missing\nTraceback (most recent call last):\n  catalog_window.py: tick\nRuntimeError: native control unavailable'
        log='Unrelated startup error\n[Foundry playback QA] begin\n'+trace+'\n[Foundry playback QA] end\nLater shutdown trace'
        result=renderer.playback_log_report(log)
        self.assertTrue(result['complete'])
        self.assertEqual(len(result['failures']),3)
        self.assertIn(trace,result['log'])
        self.assertNotIn('Unrelated startup error',result['log'])
        self.assertNotIn('Later shutdown trace',result['log'])

    def test_swallowed_optional_metadata_diagnostic_fails_the_same_gate(self):
        result=renderer.playback_log_report('[Foundry playback QA] begin\n[Foundry catalog] enrichment RuntimeError at catalog_window.py:300\n[Foundry playback QA] end')
        self.assertTrue(result['complete'])
        self.assertEqual(len(result['failures']),1)

    def test_missing_begin_or_end_never_claims_complete_playback(self):
        for log in ('','[Foundry playback QA] end','[Foundry playback QA] begin\npartial playback'):
            self.assertFalse(renderer.playback_log_report(log)['complete'])
        result=renderer.playback_log_report('[Foundry playback QA] begin\nnormal stop\n[Foundry playback QA] end')
        self.assertTrue(result['complete']);self.assertEqual(result['failures'],[])

    def test_port_allocation_rejects_existing_listener(self):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1',0));listener.listen(1)
            with self.assertRaises(OSError):renderer.available_port(listener.getsockname()[1])
            self.assertNotEqual(renderer.available_port(),listener.getsockname()[1])

    def test_readiness_requires_own_log_and_profile_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile=Path(temporary)/'kodi.log';rpc=Mock()
            self.assertFalse(renderer.fixture_ready(rpc,logfile,12345,'my-interface-profile'))
            rpc.assert_not_called()
            logfile.write_text('info <CWebserver[12345]>: Started')
            rpc.side_effect=['pong',{'value':'my-interface-profile'}]
            self.assertTrue(renderer.fixture_ready(rpc,logfile,12345,'my-interface-profile'))
            rpc.side_effect=['pong',{'value':'some-other-renderer'}]
            self.assertFalse(renderer.fixture_ready(rpc,logfile,12345,'my-interface-profile'))

    def test_embedded_mandatory_checks_survive_kodi_python_optimization(self):
        tree=ast.parse(renderer.FIXTURE,feature_version=(3,8))
        self.assertFalse(any(isinstance(node,ast.Assert) for node in ast.walk(tree)))

    def test_atomic_request_keeps_old_complete_contents_until_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'command';target.write_text('previous')
            replace=Path.replace
            def publishing(source,destination):
                self.assertEqual(target.read_text(),'previous')
                self.assertEqual(source.read_text(),'next-complete-request')
                return replace(source,destination)
            with patch.object(Path,'replace',autospec=True,side_effect=publishing):
                renderer.atomic_text(target,'next-complete-request')
            self.assertEqual(target.read_text(),'next-complete-request')

    def test_command_ack_follows_action_and_failed_action_stays_unacknowledged(self):
        tree=ast.parse(renderer.FIXTURE)
        dispatch=next(node for node in ast.walk(tree) if isinstance(node,ast.If)
                      and ast.unparse(node.test)=='command.exists()')
        code=compile(ast.Module(body=[dispatch],type_ignores=[]),'<interface-command>','exec')
        with tempfile.TemporaryDirectory() as temporary:
            command=Path(temporary)/'command'
            renderer.atomic_text(command,'clear-widget')
            def clearing():self.assertTrue(command.exists())
            row=Mock();row.reset.side_effect=clearing
            scope={'command':command,'row':row,'command_sequence':4}
            exec(code,scope)
            self.assertFalse(command.exists());self.assertEqual(scope['command_sequence'],5)
            renderer.atomic_text(command,'clear-widget')
            row.reset.side_effect=RuntimeError('native clear failed')
            with self.assertRaises(RuntimeError):exec(code,scope)
            self.assertTrue(command.exists());self.assertEqual(scope['command_sequence'],5)
