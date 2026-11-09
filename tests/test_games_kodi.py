import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'src/plugin.games.foundry'


class GamesKodiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.modules = {name: MagicMock() for name in ('xbmc', 'xbmcaddon', 'xbmcgui', 'xbmcplugin', 'xbmcvfs')}
        self.modules['xbmcvfs'].translatePath.return_value = self.temp.name
        self.patcher = patch.dict(sys.modules, self.modules)
        self.patcher.start()
        sys.path.insert(0, str(ROOT / 'resources/lib'))
        spec = importlib.util.spec_from_file_location('games_kodi_test_ui', ROOT / 'resources/lib/kodi_ui.py')
        self.ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ui)

    def tearDown(self):
        sys.path.remove(str(ROOT / 'resources/lib'))
        self.patcher.stop()
        self.temp.cleanup()

    def game(self, system='nes'):
        return dict(id='abc', title='Homebrew', path='C:/roms/game.nes', system=system, metadata=json.dumps({'year':'2026','genre':'Puzzle','overview':'Test','art':{'poster':'local.png'}}))

    def test_omega_tag_api_and_native_resume(self):
        item = self.ui.game_item(self.game())
        tag = item.getGameInfoTag()
        tag.setTitle.assert_called_once_with('Homebrew')
        tag.setPlatform.assert_called_once_with('Nintendo Entertainment System')
        tag.setYear.assert_called_once_with(2026)
        tag.setGenres.assert_called_once_with(['Puzzle'])
        tag.setGameClient.assert_not_called()
        item.setArt.assert_called_once_with({'poster':'local.png'})

    def test_psp_never_launches_or_stages(self):
        with patch.object(self.ui.staging, 'prepare') as prepare:
            self.ui.launch(MagicMock(), self.game('psp'), self.temp.name)
            prepare.assert_not_called()
            self.modules['xbmc'].Player.assert_not_called()
            self.modules['xbmcgui'].Dialog().ok.assert_called_once()

    def test_home_lists_all_systems_without_scanning(self):
        with patch.object(self.ui.Library, 'scan') as scan:
            self.ui.run(['plugin://plugin.games.foundry/', '1', ''])
            scan.assert_not_called()
        self.assertEqual(21, self.modules['xbmcplugin'].addDirectoryItem.call_count)

    def test_search_cancel_has_no_library_change(self):
        self.modules['xbmc'].Keyboard().isConfirmed.return_value = False
        with patch.object(self.ui.Library, 'scan') as scan:
            self.ui.run(['plugin://plugin.games.foundry/', '1', '?action=search'])
            scan.assert_not_called()
        self.modules['xbmcplugin'].endOfDirectory.assert_called_once_with(1, succeeded=False)

    def test_completed_lists_have_fresh_native_directory_identity(self):
        self.ui.run(['plugin://plugin.games.foundry/', '1', ''])
        first = self.modules['xbmcplugin'].setProperty.call_args.args
        self.ui.run(['plugin://plugin.games.foundry/', '1', ''])
        second = self.modules['xbmcplugin'].setProperty.call_args.args
        self.assertEqual((1, 'Foundry.Games.DirectoryId'), first[:2])
        self.assertNotEqual(first[2], second[2])

    def test_favorite_waits_for_its_origin_refresh_after_commit(self):
        events = []
        self.modules['xbmc'].getInfoLabel.return_value = self.ui.url(action='games', system='nes')
        self.modules['xbmc'].executebuiltin.side_effect = lambda *args, **kwargs: events.append(('refresh', args, kwargs))
        with patch.object(self.ui.Library, 'favorite', side_effect=lambda *args: events.append(('commit', args))):
            self.ui.run([self.ui.BASE, '-1', '?action=favorite&id=abc'])
        self.assertEqual(['commit', 'refresh'], [event[0] for event in events])
        self.assertEqual(('Container.Refresh',), events[1][1])
        self.assertEqual({'wait': True}, events[1][2])
        self.modules['xbmcplugin'].endOfDirectory.assert_not_called()

    def test_favorite_does_not_refresh_after_navigation(self):
        self.modules['xbmc'].getInfoLabel.side_effect = [self.ui.url(action='games', system='nes'), self.ui.url(action='games', mode='favorites')]
        with patch.object(self.ui.Library, 'favorite') as favorite:
            self.ui.run([self.ui.BASE, '-1', '?action=favorite&id=abc'])
        favorite.assert_called_once_with('abc')
        self.modules['xbmc'].executebuiltin.assert_not_called()

    def test_source_choice_cancel_does_not_browse(self):
        self.modules['xbmcgui'].Dialog().select.return_value = -1
        self.ui.run(['plugin://plugin.games.foundry/', '1', '?action=add'])
        self.modules['xbmcgui'].Dialog().browse.assert_not_called()

    def test_vfs_reads_binary_not_text(self):
        self.modules['xbmcvfs'].File().readBytes.return_value = bytearray(b'\x00\xff')
        self.assertEqual(b'\x00\xff', self.ui.VFS().read('smb://source/file', 5))
        self.modules['xbmcvfs'].File().read.assert_not_called()
        self.modules['xbmcvfs'].File().close.assert_called_once()

    def test_url_parameters_are_encoded(self):
        self.assertNotIn('a&b', self.ui.url(action='games', query='a&b'))

    def test_manifest_native_game_plugin(self):
        root = ET.parse(ROOT / 'addon.xml').getroot()
        self.assertEqual('plugin.games.foundry', root.attrib['id'])
        ext = root.find("extension[@point='xbmc.python.pluginsource']")
        self.assertEqual('game', ext.findtext('provides'))
        self.assertTrue((ROOT / ext.attrib['library']).is_file())
        self.assertEqual(['xbmc.python'], [x.attrib['addon'] for x in root.findall('requires/import')])


if __name__ == '__main__': unittest.main()
