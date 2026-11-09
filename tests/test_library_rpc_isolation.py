"""Library native RPC must belong to its own disposable Kodi profile."""
import importlib.util
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('library_rpc_renderer',ROOT/'tools/render_library.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)


class LibraryRpcIsolation(unittest.TestCase):
    def test_allocator_avoids_existing_listener_and_rejects_busy_explicit_port(self):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1',0));listener.listen(1)
            busy=listener.getsockname()[1]
            self.assertNotEqual(renderer.available_port(),busy)
            with self.assertRaises(OSError):renderer.available_port(busy)

    def test_missing_or_other_port_log_cannot_trigger_rpc(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile=Path(temporary)/'kodi.log';rpc=Mock()
            self.assertFalse(renderer.fixture_ready(rpc,logfile,12345,'owned-library'))
            logfile.write_text('info <CWebserver[54321]>: Started',encoding='utf-8')
            self.assertFalse(renderer.fixture_ready(rpc,logfile,12345,'owned-library'))
            rpc.assert_not_called()

    def test_own_log_and_pong_still_require_unique_profile_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile=Path(temporary)/'kodi.log'
            logfile.write_text('info <CWebserver[12345]>: Started',encoding='utf-8')
            rpc=Mock(side_effect=['pong',{'value':'older-library-renderer'}])
            self.assertFalse(renderer.fixture_ready(rpc,logfile,12345,'owned-library'))
            rpc.side_effect=['pong',{'value':'owned-library'}]
            self.assertTrue(renderer.fixture_ready(rpc,logfile,12345,'owned-library'))
            rpc.side_effect=TimeoutError('starting')
            self.assertFalse(renderer.fixture_ready(rpc,logfile,12345,'owned-library'))
