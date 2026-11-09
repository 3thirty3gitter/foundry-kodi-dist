import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[1] / 'src/plugin.games.foundry/resources/lib'
spec = importlib.util.spec_from_file_location('foundry_games_library', LIB / 'library.py')
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)


class GamesLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.roms = self.root / 'roms'
        self.roms.mkdir()
        self.db = lib.Library(str(self.root / 'games.db'))
        self.sid = self.db.add_source(str(self.roms), 'nes')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def seed(self, name='Homebrew.nes'):
        (self.roms / name).write_bytes(b'test fixture, not a playable ROM')
        self.db.scan(self.sid)
        return self.db.games()[0]

    def test_all_seventeen_systems_preserved(self):
        self.assertEqual(17, len(lib.SYSTEMS))
        self.assertEqual('', lib.SYSTEMS['psp'][2])

    def test_source_requires_explicit_console(self):
        for system in ('auto', '', 'unknown'):
            with self.assertRaises(ValueError): self.db.add_source(str(self.roms), system)

    def test_web_sources_rejected(self):
        for path in ('https://example.test/roms', 'plugin://provider/', 'data:x'):
            with self.assertRaises(ValueError): self.db.add_source(path, 'nes')

    def test_scan_is_not_automatic(self):
        (self.roms / 'Game.nes').write_bytes(b'x')
        self.assertEqual([], self.db.games())

    def test_pagination_stable(self):
        for n in range(45): (self.roms / ('Game%02d.nes' % n)).write_bytes(b'x')
        self.db.scan(self.sid)
        self.assertEqual(21, len(self.db.games(page=0)))
        self.assertEqual('Game20', self.db.games(page=1)[0]['title'])
        self.assertEqual(5, len(self.db.games(page=2)))

    def test_cancel_keeps_complete_previous_library(self):
        before = self.seed()
        (self.roms / 'Other.nes').write_bytes(b'x')
        with self.assertRaises(lib.Cancelled): self.db.scan(self.sid, cancelled=lambda: True)
        self.assertEqual([before], self.db.games())

    def test_partial_io_failure_preserves_index(self):
        before = self.seed()
        class Broken(lib.LocalIO):
            def listdir(self, path): raise OSError('offline')
        with self.assertRaises(OSError): self.db.scan(self.sid, Broken())
        self.assertEqual([before], self.db.games())

    def test_non_authoritative_empty_vfs_preserves_games(self):
        before = self.seed()
        class SilentVFS(lib.LocalIO):
            authoritative = False
            def listdir(self, path): return [], []
        with self.assertRaisesRegex(lib.SourceUnavailable, 'empty or unavailable'):
            self.db.scan(self.sid, SilentVFS())
        self.assertEqual([before], self.db.games())

    def test_failed_budget_preserves_index(self):
        before = self.seed()
        with self.assertRaises(ValueError): self.db.scan(self.sid, max_files=0)
        self.assertEqual([before], self.db.games())

    def test_history_survives_rescan_and_source_removal(self):
        game = self.seed()
        self.db.favorite(game['id'])
        self.db.played(game['id'], 30, now=1234)
        self.db.remove_source(self.sid)
        self.assertTrue((self.roms / 'Homebrew.nes').exists())
        self.sid = self.db.add_source(str(self.roms), 'nes')
        self.db.scan(self.sid)
        restored = self.db.games(mode='favorites')[0]
        self.assertEqual(game['id'], restored['id'])
        self.assertEqual(30, restored['seconds'])

    def test_missing_files_hidden_then_restore_favorite(self):
        game = self.seed()
        self.db.favorite(game['id'])
        (self.roms / 'Homebrew.nes').unlink()
        self.db.scan(self.sid)
        self.assertEqual([], self.db.games())
        self.seed()
        self.assertEqual(1, self.db.games()[0]['favorite'])

    def test_same_title_different_sources_distinct_identity(self):
        first = self.seed()
        other = self.root / 'other'; other.mkdir()
        (other / 'Homebrew.nes').write_bytes(b'x')
        sid = self.db.add_source(str(other), 'nes')
        self.db.scan(sid)
        self.assertEqual(2, len({g['id'] for g in self.db.games()}))

    def test_local_metadata_and_art(self):
        (self.roms / 'Homebrew.json').write_text(json.dumps({'title': 'A title', 'year': 2026, 'overview': 'Local description', 'url': 'ignored'}))
        (self.roms / 'Homebrew-boxart.png').write_bytes(b'image fixture')
        game = self.seed()
        info = json.loads(game['metadata'])
        self.assertEqual('A title', game['title'])
        self.assertTrue(info['art']['poster'].endswith('-boxart.png'))
        self.assertNotIn('url', info)

    def test_malformed_metadata_does_not_break_scan(self):
        (self.roms / 'Homebrew.json').write_text('{not json')
        self.assertEqual('Homebrew', self.seed()['title'])

    def test_search_literal_sql_wildcards(self):
        self.seed('100%_Fun.nes')
        self.assertEqual(1, len(self.db.games(query='%_')))
        self.assertEqual(0, len(self.db.games(query="' OR 1=1 --")))

    def test_recent_order_and_favorites(self):
        self.seed('One.nes'); self.seed('Two.nes')
        games = self.db.games()
        self.db.played(games[0]['id'], now=50)
        self.db.played(games[1]['id'], now=100)
        self.assertEqual(games[1]['id'], self.db.games(mode='recent')[0]['id'])
        self.assertEqual([], self.db.games(mode='favorites'))

    def test_newer_database_refused(self):
        self.db.db.execute('PRAGMA user_version=99')
        with self.assertRaises(ValueError): lib.Library(str(self.root / 'games.db'))

    def test_selected_file_imports_only_that_file(self):
        self.seed()
        self.db.remove_source(self.sid)
        (self.roms / 'Other.nes').write_bytes(b'x')
        sid = self.db.add_source(str(self.roms / 'Homebrew.nes'), 'nes', selected_file=True)
        self.assertEqual(1, self.db.scan(sid))
        self.assertEqual('Homebrew', self.db.games()[0]['title'])

    def test_search_human_system_name(self):
        self.seed()
        self.assertEqual(1, len(self.db.games(query='Nintendo Entertainment')))

    def test_multidisc_playlist_hides_disc_entries(self):
        (self.roms / 'Collection.m3u').write_text('disc1.chd\ndisc2.chd\n')
        (self.roms / 'disc1.chd').write_bytes(b'x')
        (self.roms / 'disc2.chd').write_bytes(b'x')
        sid = self.db.add_source(str(self.roms), 'psx')
        self.assertEqual(1, self.db.scan(sid))
        self.assertEqual('Collection', self.db.games()[0]['title'])


if __name__ == '__main__': unittest.main()
