"""Cold-update recovery and atomic reload ordering for user widget includes."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = Path(os.environ.get('FOUNDRY_HELPER_SOURCE', ROOT.parent / 'script.foundry.helper'))
MODULES = HELPER / 'resources/lib/modules'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, MODULES / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class WidgetRestore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.properties = {}
        self.window = types.SimpleNamespace(
            getProperty=lambda key: self.properties.get(key, ''),
            setProperty=self.properties.__setitem__,
            clearProperty=lambda key: self.properties.pop(key, None))
        self.builtins = []
        self.version = '1.5.1'
        self.xbmc = types.SimpleNamespace(sleep=lambda ms: None, getInfoLabel=lambda key: '',
            getLocalizedString=lambda key: str(key), executebuiltin=self.builtins.append, executeJSONRPC=lambda request: '{}')
        def translate(path):
            return str(self.root / path.replace('special://', '').replace('/', os.sep))
        self.vfs = types.SimpleNamespace(translatePath=translate, exists=lambda p: Path(translate(p) if p.startswith('special:') else p).exists(),
            mkdir=lambda p: Path(p).mkdir(parents=True, exist_ok=True))
        def file(path, mode):
            dest = Path(translate(path))
            dest.parent.mkdir(parents=True, exist_ok=True)
            return dest.open(mode, encoding='utf-8')
        self.vfs.File = file
        self.gui = types.SimpleNamespace(Window=lambda n: self.window, Dialog=lambda: Mock(), ListItem=Mock(), getCurrentWindowId=lambda: 10000)
        self.addon = types.SimpleNamespace(Addon=lambda **kw: types.SimpleNamespace(getAddonInfo=lambda key: self.version))
        self.module_pkg = types.ModuleType('modules')
        self.module_pkg.__path__ = [str(MODULES)]
        self.patch = patch.dict(sys.modules, {'xbmc':self.xbmc, 'xbmcgui':self.gui, 'xbmcvfs':self.vfs,
            'xbmcaddon':self.addon, 'modules':self.module_pkg})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.version_module = load('restore_version_test', 'version_monitor.py')
        self.remake = Mock()
        self.reload = Mock()
        self.fake_cpaths = types.SimpleNamespace(remake_all_cpaths=self.remake, reload_generated_paths=self.reload)
        self.cpath_patch = patch.dict(sys.modules, {'modules.cpath_maker': self.fake_cpaths})
        self.cpath_patch.start()
        self.addCleanup(self.cpath_patch.stop)

    def test_cold_update_restores_before_marking_and_reload(self):
        self.version_module.save_version('skin.foundry', '1.5.0')
        self.remake.side_effect = lambda **kw: self.assertEqual(self.version_module.saved_versions()['skin.foundry']['version'], '1.5.0')
        self.reload.side_effect = lambda: self.assertEqual(self.version_module.saved_versions()['skin.foundry']['version'], '1.5.1')
        self.version_module.check_for_update('skin.foundry')
        self.remake.assert_called_once_with(silent=True, reload=False)
        self.reload.assert_called_once_with()
        self.assertEqual(self.properties['skin.foundry.installed_version'], '1.5.1')
        self.properties.clear()  # A second cold start must not reload again.
        self.version_module.check_for_update('skin.foundry')
        self.assertEqual(self.remake.call_count, 1)

    def test_legacy_missing_receipt_rebuilds_even_with_current_volatile_property(self):
        self.properties['skin.foundry.installed_version'] = self.version
        self.version_module.check_for_update('skin.foundry')
        self.remake.assert_called_once()

    def test_failed_rebuild_keeps_old_receipt_and_retries(self):
        self.version_module.save_version('skin.foundry', '1.5.0')
        self.remake.side_effect = OSError('fixture write failure')
        with self.assertRaises(OSError):
            self.version_module.check_for_update('skin.foundry')
        self.assertEqual(self.version_module.saved_versions()['skin.foundry']['version'], '1.5.0')
        self.assertNotIn('skin.foundry.rebuilding_paths', self.properties)
        self.reload.assert_not_called()
        self.remake.side_effect = None
        self.version_module.check_for_update('skin.foundry')
        self.assertEqual(self.remake.call_count, 2)

    def test_corrupt_receipt_recovers(self):
        dest = Path(self.version_module.VERSIONS_PATH)
        dest.parent.mkdir(parents=True)
        dest.write_text('broken', encoding='utf-8')
        self.version_module.check_for_update('skin.foundry')
        self.remake.assert_called_once()

    def test_reentrant_rebuild_skips(self):
        self.remake.side_effect = lambda **kw: self.version_module.check_for_update('skin.foundry')
        self.version_module.check_for_update('skin.foundry')
        self.remake.assert_called_once()

    def test_same_version_xml_replacement_is_restored(self):
        target = self.root / 'skin/xml/script-nimbus-widget_movies.xml'
        target.parent.mkdir(parents=True)
        target.write_text('user configured widget', encoding='utf-8')
        self.version_module.save_version('skin.foundry', self.version)
        target.write_text('shipped empty widget', encoding='utf-8')
        self.version_module.check_for_update('skin.foundry')
        self.remake.assert_called_once_with(silent=True, reload=False)

    def test_other_invoker_lock_skips_and_recovers_after_release(self):
        path = self.root / 'masterprofile/addon_data/script.foundry.helper/generated_paths_lock.db'
        path.parent.mkdir(parents=True)
        lock = sqlite3.connect(path)
        try:
            lock.execute('BEGIN IMMEDIATE')
            self.version_module.check_for_update('skin.foundry')
            self.remake.assert_not_called()
        finally:
            lock.close()
        self.version_module.check_for_update('skin.foundry')
        self.remake.assert_called_once()

    def test_normal_widget_edit_updates_only_its_receipt_without_second_reload(self):
        target = self.root / 'skin/xml/script-nimbus-widget_movies.xml'
        target.parent.mkdir(parents=True)
        target.write_text('old widget', encoding='utf-8')
        self.version_module.save_version('skin.foundry', self.version)
        self.module_pkg.xmls = load('restore_xml_test', 'xmls.py')
        cpaths = load('restore_cpaths_test', 'cpath_maker.py')
        paths = cpaths.CPaths('movie.widget')
        try:
            with patch.dict(sys.modules, {'modules.version_monitor': self.version_module}), patch.object(cpaths, 'Thread') as thread:
                paths.write_xml('special://skin/xml/script-nimbus-widget_movies.xml', 'new widget')
                thread.assert_called_once()
            self.version_module.check_for_update('skin.foundry')
            self.remake.assert_not_called()
            self.reload.assert_not_called()
            # Updating one intentional edit must not bless unrelated corruption.
            other = self.root / 'skin/xml/script-nimbus-widget_tvshows.xml'
            other.write_text('unexpected replacement', encoding='utf-8')
            self.version_module.record_generated_path('special://skin/xml/script-nimbus-widget_movies.xml')
            self.version_module.check_for_update('skin.foundry')
            self.remake.assert_called_once()
        finally:
            paths.dbcon.close()

    def test_partial_batch_does_not_stamp_normal_edit_receipts(self):
        self.module_pkg.xmls = load('restore_xml_test', 'xmls.py')
        cpaths = load('restore_cpaths_test', 'cpath_maker.py')
        stamp = Mock()
        with patch.dict(sys.modules, {'modules.version_monitor': types.SimpleNamespace(record_generated_path=stamp)}), patch.object(cpaths, 'Thread'):
            cpaths.remake_all_cpaths(silent=True, reload=False)
        stamp.assert_not_called()

    def test_false_vfs_write_fails_batch_without_reload(self):
        self.module_pkg.xmls = load('restore_xml_test', 'xmls.py')
        cpaths = load('restore_cpaths_test', 'cpath_maker.py')
        class FailedFile:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, content): return False
        with patch.object(cpaths.xbmcvfs, 'File', lambda *args: FailedFile()), patch.object(cpaths, 'Thread') as thread:
            with self.assertRaises(OSError):
                cpaths.remake_all_cpaths(silent=True)
            thread.assert_not_called()

    def test_batch_preserves_database_and_reloads_after_all_ten_writes(self):
        xmls = load('restore_xml_test', 'xmls.py')
        self.module_pkg.xmls = xmls
        cpaths = load('restore_cpaths_test', 'cpath_maker.py')
        seed = cpaths.CPaths('movie.widget')
        rows = [('movie.widget.1', 'plugin://example/?one=1&two=2', 'Saved "row"', 'WidgetListPoster', 'row'),
                ('tvshow.widget.50', 'plugin://example/tv', 'TV', 'WidgetListLandscape', 'tv'),
                ('movie.main_menu', 'plugin://example/movies', 'My movies', '', '')]
        seed.dbcon.executemany('INSERT INTO custom_paths VALUES (?, ?, ?, ?, ?)', rows)
        seed.dbcon.commit()
        seed.dbcon.close()
        thread_calls = []
        class Thread:
            def __init__(inner, target): inner.target = target
            def start(inner):
                files = list((self.root / 'skin/xml').glob('*.xml'))
                self.assertEqual(len(files), 10)
                thread_calls.append(inner.target)
        with patch.object(cpaths, 'Thread', Thread):
            cpaths.remake_all_cpaths(silent=True)
        self.assertEqual(len(thread_calls), 1)
        with sqlite3.connect(cpaths.database_path) as db:
            self.assertEqual(db.execute('SELECT * FROM custom_paths').fetchall(), rows)
        db.close()
        movie = (self.root / 'skin/xml/script-nimbus-widget_movies.xml').read_text()
        self.assertIn('plugin://example/?one=1&amp;two=2', movie)
        self.assertIn('Saved &quot;row&quot;', movie)
        tv = (self.root / 'skin/xml/script-nimbus-widget_tvshows.xml').read_text()
        self.assertIn('22060', tv)
        self.assertIn('My movies', (self.root / 'skin/xml/script-nimbus-main_menu_movies.xml').read_text())
        thread_calls.clear()
        with patch.object(cpaths, 'Thread', Thread):
            cpaths.remake_all_cpaths(silent=True, reload=False)
        self.assertEqual(thread_calls, [])


if __name__ == '__main__':
    unittest.main()

