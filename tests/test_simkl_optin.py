import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
class SetupTests(unittest.TestCase):
    def setUp(self):
        guard=patch.dict(sys.modules);guard.start();self.addCleanup(guard.stop)
    def run_case(self, installed, answer):
        calls = []
        class Dialog:
            def yesno(self, *args, **kw):
                calls.append(('prompt', args[1])); return answer
            def ok(self, *args): calls.append(('notice', args))
        xbmc = types.SimpleNamespace(executeJSONRPC=lambda _: json.dumps(
            {'error': {'code': -32602}} if installed is None else {'result': {'addon': installed}}),
            executebuiltin=lambda command: calls.append(('builtin', command)))
        sys.modules['xbmc'] = xbmc
        sys.modules['xbmcgui'] = types.SimpleNamespace(Dialog=Dialog)
        sys.modules['xbmcaddon'] = types.SimpleNamespace(Addon=lambda _: types.SimpleNamespace(openSettings=lambda: calls.append(('settings',))))
        spec = importlib.util.spec_from_file_location('setup_under_test', ROOT/'src/script.program.foundry-simkl/default.py')
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        self.assertEqual(calls, [])  # loading never runs setup
        mod.main(); return calls
    def test_consent_text_is_concise_and_complete(self):
        for state, question in ((None, 'Install the official SIMKL tracker?'), ({'enabled':True}, 'Open SIMKL settings?')):
            body = self.run_case(state, False)[0][1]
            self.assertIn('Linked profiles may resume tracking and upload queued history.', body)
            self.assertIn("Foundry won't sign you in or change settings.", body)
            self.assertTrue(body.endswith(question))
            self.assertLessEqual(len(body), 160)
        disabled = self.run_case({'enabled':False},False)[0][1][1]
        self.assertIn('will stay disabled',disabled)
        self.assertLessEqual(max(map(len,disabled.splitlines())), 55)
    def test_cancel_no_install(self):
        calls = self.run_case(None, False)
        self.assertFalse(any(c[0] in ('builtin', 'settings') for c in calls))
    def test_opt_in_install_only(self):
        calls = self.run_case(None, True)
        self.assertEqual([c for c in calls if c[0]=='builtin'], [('builtin','InstallAddon(script.simkl)')])
        self.assertIn('queued history', calls[0][1])
    def test_disabled_no_enable(self):
        self.assertEqual([c[0] for c in self.run_case({'enabled':False},True)], ['notice'])
    def test_enabled_cancel(self):
        self.assertEqual([c[0] for c in self.run_case({'enabled':True},False)], ['prompt'])
    def test_enabled_settings_only(self):
        self.assertEqual([c[0] for c in self.run_case({'enabled':True},True)], ['prompt','settings'])
if __name__ == '__main__': unittest.main()
