"""Catalog Back must advance exactly one owned navigation level."""
from concurrent.futures import Future
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
import test_release as kodi
import test_library_partial_load as partial_load
from modules.catalog_model import CatalogState
from modules.catalog_source import DirectorySource
from modules import catalog_window


class NativeHistory:
    def __init__(self, path):
        self.windows=['home','videos','catalog']
        self.paths=['plugin://fixture/movies',path]
        self.close_calls=0
        self.back_calls=0
    def close(self):
        # Omega Window.close() clears iOldWindowId. A repeated close sends a
        # generic PreviousWindow and pops the native Videos window as well.
        self.close_calls+=1
        if len(self.windows)>1:self.windows.pop()
    def builtin(self, action):
        if action in ('Action(Back)','Action(Back,videos)'):
            self.back_calls+=1
            if self.windows[-1]=='videos' and len(self.paths)>1:self.paths.pop()
    def visible(self, query):
        return query=='Window.IsActive(videos)' and self.windows[-1]=='videos'


class CatalogBackNavigation(unittest.TestCase):
    def tearDown(self):kodi.Window.values.clear()

    def window(self):
        w=partial_load.PartialLoad().window([])
        w.pending=None;w.search=False;w.stack=[];w.exit_back=False
        w.close=Mock();w.executor=Mock();w.request=1;w.close_requested=False
        w.source=DirectorySource('plugin://fixture/trending?token=opaque%26value')
        return w

    def run_entry(self, w, history, after_show=None):
        def show():
            w.back()
            if after_show:after_show()
        w.show=show;w.close=history.close
        with patch.object(catalog_window,'CatalogWindow',return_value=w), \
             patch.object(kodi.xbmc,'executebuiltin',side_effect=history.builtin), \
             patch.object(kodi.xbmc,'getCondVisibility',side_effect=history.visible), \
             patch.object(kodi.xbmc,'getInfoLabel',side_effect=lambda _:history.paths[-1]):
            return catalog_window.open_catalog(history.paths[-1], source=w.source)

    def test_home_movies_trending_back_returns_to_movies_not_home(self):
        w=self.window();history=NativeHistory(w.source.path)
        self.assertTrue(self.run_entry(w,history))
        self.assertEqual(history.windows,['home','videos'])
        self.assertEqual(history.paths,['plugin://fixture/movies'])
        self.assertEqual(history.close_calls,1)
        self.assertEqual(history.back_calls,1)

    def test_repeated_back_and_disposal_close_native_window_only_once(self):
        w=self.window()
        w.back();w.back();w.dispose()
        self.assertEqual(w.close.call_count,1)
        self.assertTrue(w.exit_back)

    def test_open_in_kodi_keeps_requested_native_directory_after_cleanup(self):
        w=self.window()
        target='plugin://fixture/source?token=opaque%26value'
        with patch.object(catalog_window,'rpc') as rpc:
            w.open_native(target)
            w.dispose()
        w.close.assert_called_once()
        rpc.assert_called_once_with('GUI.ActivateWindow',{'window':'videos','parameters':[target,'return']})
        self.assertFalse(w.exit_back)
        self.assertEqual(kodi.Window().getProperty('foundry.catalog.handled_path'),target)

    def test_nested_page_back_restores_parent_and_discards_running_child_result(self):
        w=self.window()
        parent=CatalogState(items=[{'type':'movie','title':'Parent item','file':'plugin://fixture/parent-item'}],selected=0)
        source=DirectorySource('plugin://fixture/parent')
        w.stack=[(source,parent)]
        future=Future();future.set_running_or_notify_cancel()
        w.pending=(w.request,'load',future)
        with patch.object(catalog_window,'listitem',side_effect=lambda item,*_:item):
            w.back()
            future.set_result({'items':[{'title':'Stale child'}]})
            w.tick()
        self.assertIs(w.source,source)
        self.assertIs(w.state,parent)
        self.assertEqual(w.hero['title'],'Parent item')
        self.assertIsNone(w.pending)
        self.assertEqual(w.getProperty('catalog.loading'),'')
        w.close.assert_not_called()

    def test_search_back_returns_to_search_then_library_without_native_close(self):
        w=self.window();w.search=True;w.focus_id=51;w.leave_search=Mock()
        w.back();self.assertEqual(w.focus_pending,5801)
        w.focus_id=5801;w.back();w.leave_search.assert_called_once()
        w.close.assert_not_called()

    def test_late_dispose_does_not_back_out_of_newer_window(self):
        w=self.window();history=NativeHistory(w.source.path)
        self.run_entry(w,history,lambda:history.windows.append('settings'))
        self.assertEqual(history.windows[-1],'settings')
        self.assertEqual(history.back_calls,0)
        self.assertEqual(history.close_calls,1)

    def test_late_dispose_does_not_back_out_of_newer_native_path(self):
        w=self.window();history=NativeHistory(w.source.path)
        self.run_entry(w,history,lambda:history.paths.append('plugin://fixture/newer-navigation'))
        self.assertEqual(history.paths[-1],'plugin://fixture/newer-navigation')
        self.assertEqual(history.back_calls,0)
        self.assertEqual(history.close_calls,1)

    def test_clicks_queued_after_close_do_not_navigate_again(self):
        w=self.window();w.back()
        w.rail=[{'kind':'next'}];w.turn_page=Mock()
        w.onClick(50)
        w.turn_page.assert_not_called()
