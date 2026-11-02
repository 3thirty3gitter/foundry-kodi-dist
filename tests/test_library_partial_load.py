"""A loaded poster rail must survive a failure in optional hero metadata."""
from concurrent.futures import Future
import importlib
from pathlib import Path
import unittest
from unittest.mock import patch
import test_release as kodi
from modules.catalog_model import CatalogState
from modules.catalog_metadata import details,names
from modules.catalog_source import DirectorySource

with patch.object(kodi.xbmcgui,'WindowXML',object,create=True):
    window_module=importlib.import_module('modules.catalog_window')

class PartialLoad(unittest.TestCase):
    def window(self,items=None,error=None):
        w=object.__new__(window_module.CatalogWindow)
        w.section='Movies';w.reported_errors=set();w.initialized=True;w.closed=False;w.focus_pending=None;w.request=1;w.search=False;w.hero=None;w.state=CatalogState();w.rail=[];w.last_focus=(-1,-1)
        w.props={};w.native=[];w.index=0;w.focus_id=50
        w.setProperty=lambda n,v:w.props.__setitem__(n,v)
        w.getProperty=lambda n:w.props.get(n,'')
        class Control:
            def setWidth(self,width):pass
            def isVisible(self):return True
        w.getControl=lambda cid:Control()
        w.getFocusId=lambda:w.focus_id
        w.setFocusId=lambda cid:setattr(w,'focus_id',cid)
        w.getCurrentListPosition=lambda:w.index
        w.setCurrentListPosition=lambda index:setattr(w,'index',index)
        w.clearList=lambda:w.native.clear()
        w.addItems=lambda items:w.native.extend(items)
        w.update_optional_ratings=lambda:None
        future=Future()
        if error:future.set_exception(error)
        else:future.set_result({'items':items or []})
        w.pending=(1,'load',future)
        return w
    def test_loaded_posters_and_logo_survive_metadata_error_and_navigation(self):
        items=[{'title':'Title '+str(i),'label':'Title '+str(i),'plot':'Available plot','file':'fixture://'+str(i),'art':{'clearlogo':'local-logo.png'}} for i in range(3)]
        w=self.window(items)
        def broken(item):
            w.p('clearlogo',item['art']['clearlogo'])
            raise TypeError('DO_NOT_LOG_PROVIDER_VALUE')
        w.update_hero=broken
        with patch.object(window_module,'listitem',side_effect=lambda i,*args:i),patch.object(kodi.xbmc,'log') as log:
            w.tick()
            self.assertEqual(len(w.native),3)
            self.assertEqual(w.props['catalog.message'],'')
            self.assertEqual(w.props['catalog.clearlogo'],'local-logo.png')
            self.assertEqual(w.props['catalog.details'],'Movie')
            self.assertEqual(w.props['catalog.plot'],'Available plot')
            w.index=1;w.tick()
            self.assertEqual(w.state.selected,1)
            self.assertEqual(w.hero['title'],'Title 1')
            self.assertEqual(w.props['catalog.message'],'')
            self.assertEqual(log.call_count,1)
            self.assertNotIn('DO_NOT_LOG_PROVIDER_VALUE',str(log.call_args))
    def test_genuine_source_failure_keeps_source_error_and_focuses_back(self):
        w=self.window(error=RuntimeError('controlled source failure'))
        with patch.object(kodi.xbmc,'log'):w.tick()
        self.assertIn('This source could not be loaded',w.props['catalog.message'])
        self.assertEqual(w.focus_pending,5701)
        self.assertEqual(w.native,[])
    def test_empty_catalog_has_valid_back_focus(self):
        w=self.window([])
        with patch.object(window_module,'listitem',side_effect=lambda i,*args:i):w.tick()
        self.assertEqual(w.focus_pending,5701)
    def test_optional_rating_failure_cannot_escape_navigation(self):
        w=self.window([]);w.pending=None
        def broken():raise ValueError('optional failure')
        w.update_optional_ratings=broken
        with patch.object(kodi.xbmc,'log') as log:w.tick();w.tick()
        self.assertEqual(log.call_count,1)
    def test_directory_query_omits_invalid_ratings_but_library_search_retains_it(self):
        with patch('modules.catalog_source.rpc',return_value={'files':[]}) as rpc:
            DirectorySource('plugin://fixture/catalog').load()
            self.assertNotIn('ratings',rpc.call_args.args[1]['properties'])
            self.assertIn('premiered',rpc.call_args.args[1]['properties'])
        with patch('modules.catalog_source.rpc',return_value={'movies':[]}) as rpc:
            DirectorySource('videodb://movies/titles/').search('title')
            self.assertIn('ratings',rpc.call_args.args[1]['properties'])
    def test_dates_genres_studios_missing_and_mixed_metadata_are_safe(self):
        movie=details({'premiered':'2026-09-28','genre':['Drama',None,'Comedy','Mystery','Crime'],'studio':['Studio',None],'plot':'Plot','mpaa':'CA 14A'})
        self.assertEqual(movie['released'],'Released Sep 28, 2026')
        self.assertEqual(movie['certification'],'14A')
        self.assertIn('Drama',movie['details']);self.assertNotIn('Crime',movie['details']);self.assertNotIn('None',movie['details'])
        self.assertEqual(details({},True)['details'],'TV Series')
        self.assertEqual(details({'premiered':'2026-99-99'})['released'],'Released 2026-99-99')
        self.assertEqual(names(['A',None,{'name':'B'}]),['A'])
