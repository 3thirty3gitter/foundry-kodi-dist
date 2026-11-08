"""First-paint catalog handoff tests. Run through run_review_tests.py."""
from concurrent.futures import Future
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import test_release as kodi
import test_library_partial_load as partial_load
from modules.catalog_source import DirectorySource
from modules import catalog_window, vod


class CatalogHandoff(unittest.TestCase):
    def tearDown(self):
        kodi.Window.values.clear()

    def window(self, initial):
        w = partial_load.PartialLoad().window([])
        w.initialized = False
        w.pending = None
        w.history = []
        w.breadcrumb = 'VOD / Movies / Your Library'
        w.setContent = Mock()
        w.getListSize = lambda: len(w.native)
        w.source = DirectorySource('plugin://fixture/list?opaque=a%26b', 'movies')
        w.source.initial = initial
        w.source.load = Mock(wraps=w.source.load)
        w.executor = Mock()
        w.executor.submit.return_value = Future()
        w.clock = lambda: 100.0
        return w

    def items(self):
        return [{'title': 'Film', 'type': 'movie', 'file': 'plugin://fixture/play?opaque=a%26b',
                 'plot': 'Source metadata', 'art': {'poster': 'cached-poster.png'}}]

    def test_probed_initial_page_is_populated_before_first_oninit_returns(self):
        w = self.window({'items': self.items(), 'next_path': 'plugin://fixture/page?x=opaque%26b'})
        with patch.object(catalog_window, 'listitem', side_effect=lambda item, *_: item):
            w.onInit()
        self.assertEqual(len(w.native), 2)
        self.assertEqual(w.state.next_path, 'plugin://fixture/page?x=opaque%26b')
        self.assertEqual(w.hero['plot'], 'Source metadata')
        self.assertEqual(w.hero['file'], 'plugin://fixture/play?opaque=a%26b')
        self.assertIsNone(w.pending)
        self.assertIsNone(w.source.initial)
        w.executor.submit.assert_not_called()
        w.source.load.assert_not_called()
        self.assertNotEqual(w.getProperty('catalog.loading'), 'true')

    def test_cached_first_page_is_not_rebound_by_later_ticks_or_reinit(self):
        w = self.window({'items': self.items()})
        with patch.object(catalog_window, 'listitem', side_effect=lambda item, *_: item):
            w.onInit()
            self.assertEqual(len(w.native), 1)
            w.clearList = Mock(wraps=w.clearList)
            w.onInit()
            w.tick()
        w.clearList.assert_not_called()
        w.source.load.assert_not_called()
        self.assertEqual(w.index, 0)

    def test_native_list_lost_to_playback_is_rehydrated_without_source_reload(self):
        w = self.window({'items': self.items()})
        with patch.object(catalog_window, 'listitem', side_effect=lambda item, *_: item):
            w.onInit()
            w.native.clear()
            w.onInit()
        self.assertEqual(len(w.native), 1)
        w.executor.submit.assert_not_called()
        w.source.load.assert_not_called()

    def test_sources_without_initial_data_still_load_asynchronously(self):
        w = self.window(None)
        w.onInit()
        w.executor.submit.assert_called_once_with(w.source.load)
        self.assertEqual(w.pending[1], 'load')
        self.assertEqual(w.native, [])
        self.assertEqual(w.getProperty('catalog.loading'), 'true')

    def test_new_navigation_load_is_not_served_the_consumed_initial_page(self):
        w = self.window({'items': self.items()})
        with patch.object(catalog_window, 'listitem', side_effect=lambda item, *_: item):
            w.onInit()
        w.load()
        w.executor.submit.assert_called_once_with(w.source.load)
        self.assertIsNone(w.source.initial)
        self.assertEqual(len(w.native), 1, 'Keep the completed page visible during replacement loading')

    def test_synchronous_metadata_failure_retains_the_complete_rail(self):
        w = self.window({'items': self.items()})
        w.update_hero = Mock(side_effect=ValueError('DO_NOT_LOG_ITEM_DATA'))
        with patch.object(catalog_window, 'listitem', side_effect=lambda item, *_: item), patch.object(kodi.xbmc, 'log') as log:
            w.onInit()
        self.assertEqual(len(w.native), 1)
        self.assertEqual(w.getProperty('catalog.plot'), 'Source metadata')
        self.assertNotIn('DO_NOT_LOG_ITEM_DATA', str(log.call_args))
        self.assertEqual(w.getProperty('catalog.message'), '')

    def test_direct_delayed_adoption_guards_native_view_until_catalog_opens(self):
        home = kodi.Window()
        path = 'plugin://fixture/list?opaque=a%26b'
        def visible(query):
            return query in ('Window.IsActive(videos)', vod.CATALOG_CONTENT, 'Container.Content(movies)')
        def probe(*_):
            self.assertEqual(home.getProperty('foundry.catalog.routing'), 'true')
            return {'files': self.items()}
        def opened(*_, **kwargs):
            self.assertEqual(home.getProperty('foundry.catalog.routing'), 'true')
            self.assertEqual(kwargs['source'].initial['items'][0]['file'], self.items()[0]['file'])
            return True
        with patch.object(kodi.xbmc, 'getCondVisibility', side_effect=visible), \
             patch.object(kodi.xbmc, 'getInfoLabel', side_effect=lambda q: path if q == 'Container.FolderPath' else ''), \
             patch('modules.catalog_source.rpc', side_effect=probe) as rpc, \
             patch.object(catalog_window, 'open_catalog', side_effect=opened):
            self.assertTrue(vod.activate_catalog())
        self.assertEqual(rpc.call_count, 1, 'The adoption probe must not be duplicated inside Foundry')
        self.assertEqual(home.getProperty('foundry.catalog.routing'), '')
        self.assertEqual(home.getProperty('foundry.catalog.opening'), '')

    def test_routing_monitor_guards_before_launch_and_does_not_launch_twice(self):
        home = kodi.Window()
        now = [100.0]
        monitor = vod.CatalogRoutingMonitor(clock=lambda: now[0])
        def launch(*_):
            self.assertEqual(home.getProperty('foundry.catalog.routing'), 'true')
        with patch.object(kodi.xbmc, 'getInfoLabel', return_value='plugin://fixture/list'), \
             patch.object(kodi.xbmc, 'getCondVisibility', side_effect=lambda q: q != 'Container.IsUpdating'), \
             patch.object(kodi.xbmc, 'executebuiltin', side_effect=launch) as action:
            monitor.process()
            now[0] += .3
            monitor.process()
            monitor.process()
        action.assert_called_once()

    def test_nonmedia_and_source_failure_release_guard_for_native_navigation(self):
        for result in ({'files': [{'label': 'Settings', 'filetype': 'directory', 'file': 'plugin://fixture/settings'}]},
                       RuntimeError('source unavailable')):
            with self.subTest(result=type(result).__name__):
                home = kodi.Window()
                with patch.object(kodi.xbmc, 'getCondVisibility', side_effect=lambda q: q in ('Window.IsActive(videos)', vod.CATALOG_CONTENT, 'Container.Content(movies)')), \
                     patch.object(kodi.xbmc, 'getInfoLabel', return_value='plugin://fixture/'), \
                     patch('modules.catalog_source.rpc', side_effect=result if isinstance(result, Exception) else lambda *_: result), \
                     patch.object(catalog_window, 'open_catalog') as opened:
                    self.assertFalse(vod.activate_catalog())
                opened.assert_not_called()
                self.assertEqual(home.getProperty('foundry.catalog.routing'), '')
                self.assertEqual(home.getProperty('foundry.catalog.opening'), '')
