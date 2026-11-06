"""Catalog parity state, provider boundaries, custom UI and routing regressions."""
from pathlib import Path
import ast
import json
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E
import test_release as kodi
from modules.catalog_model import CatalogState, SORTS, ordered, split_directory
from modules.catalog_source import DirectorySource
from modules import vod

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'
HELPER=ROOT.parent/'script.foundry.helper'

class CatalogStateTests(unittest.TestCase):
    def items(self,n):return [{'title':'Movie %03d'%i,'label':'Movie %03d'%i,'file':'plugin://provider/play?id='+str(i),'year':2000+i,'premiered':str(2000+i)+'-01-01','filetype':'file'} for i in range(n)]
    def test_page_size_is_twenty_and_arrows_are_part_of_rail(self):
        s=CatalogState(items=self.items(45))
        self.assertEqual(len(s.page_items()),20)
        self.assertEqual(s.total_pages,3)
        self.assertEqual(s.rail()[-1]['kind'],'next')
        self.assertEqual(s.rail()[0]['kind'],'media')
        s.move_page('next')
        self.assertEqual((s.page,s.selected),(2,0))
        self.assertEqual([s.rail()[i]['kind'] for i in (0,-1)],['previous','next'])
        self.assertEqual(s.page_items()[0]['title'],'Movie 020')
        s.move_page('next');self.assertEqual(len(s.page_items()),5)
        self.assertEqual(s.rail()[-1]['kind'],'media')
    def test_page_boundaries_empty_single_and_partial(self):
        for n in (0,1,19,20,21,40,45):
            s=CatalogState(items=self.items(n))
            for _ in range(8):s.move_page('next')
            self.assertEqual(s.page,s.total_pages)
            for _ in range(8):s.move_page('previous')
            self.assertEqual(s.page,1)
    def test_four_sorts_reset_page_and_selection_only_when_changed(self):
        for key,_ in SORTS:
            s=CatalogState(items=self.items(45),page=2,selected=19)
            self.assertTrue(s.set_sort(key));self.assertEqual((s.page,s.selected),(1,0))
            s.selected=4;self.assertFalse(s.set_sort(key));self.assertEqual(s.selected,4)
        self.assertEqual(len(SORTS),4)
    def test_unknown_dates_are_last_in_both_directions(self):
        items=[{'title':'Missing'},{'title':'Older','year':2000},{'title':'Newer','premiered':'2020-01-01'}]
        self.assertEqual([i['title'] for i in ordered(items,'date_asc')],['Older','Newer','Missing'])
        self.assertEqual([i['title'] for i in ordered(items,'date_desc')],['Newer','Older','Missing'])
    def test_dates_tie_by_title_and_titles_tie_stably_by_path(self):
        items=[{'title':'Z','year':2020},{'title':'A','year':2020},{'title':'A','year':2020,'file':'a'}]
        self.assertEqual([i.get('file','') for i in ordered(items,'date_desc')],['','a',''])
    def test_search_is_case_insensitive_and_resets_page(self):
        s=CatalogState(items=self.items(45),page=3,selected=4)
        self.assertTrue(s.set_query(' MOVIE 02 '));self.assertEqual((s.page,s.selected),(1,0))
        self.assertEqual(len(s.filtered()),10)
        self.assertFalse(s.set_query('MOVIE 02'))
    def test_original_playback_urls_are_unchanged_by_sort_page_and_filter(self):
        items=self.items(45);items[23]['file']='plugin://provider/play?title=a,b&token=opaque%2Fvalue'
        s=CatalogState(items=items);s.set_sort('title_desc');s.set_query('023')
        self.assertEqual(s.page_items()[0]['file'],items[23]['file'])
    def test_provider_navigation_is_not_faked_or_parameter_rewritten(self):
        items=self.items(2)+[{'label':'[B]Next Page[/B]','filetype':'directory','file':'plugin://x/?cursor=opaque%3Dfoo&category=4'}]
        media,nxt,prev=split_directory(items)
        self.assertEqual(len(media),2);self.assertEqual(nxt,items[-1]['file']);self.assertEqual(prev,'')
        s=CatalogState(items=media,next_path=nxt,server_page=2)
        self.assertEqual(s.page_label(),'Page 2 / ?')
        s.server_total_pages=500;self.assertEqual(s.page_label(),'Page 2 / 500')
    def test_non_page_folders_are_preserved(self):
        item={'label':'Next Episode','filetype':'directory','file':'plugin://x/episodes'}
        self.assertEqual(split_directory([item]),([item],'',''))
    def test_rejects_invalid_state_actions(self):
        s=CatalogState()
        with self.assertRaises(ValueError):s.set_sort('random')
        with self.assertRaises(ValueError):s.move_page('jump')

class SourceTests(unittest.TestCase):
    def test_directory_snapshot_reuses_probe_and_never_logs_credentials(self):
        s=DirectorySource('plugin://provider/library?cursor=opaque')
        s.initial={'items':[{'title':'Saved'}]}
        with patch('modules.catalog_source.rpc') as call:
            self.assertEqual(s.load()['items'][0]['title'],'Saved');call.assert_not_called()
    def test_directory_fields_fallback_and_preserves_page_url(self):
        s=DirectorySource('plugin://x/');payload={'files':[{'label':'Next Page','filetype':'directory','file':'plugin://x/?page=2'}]}
        with patch('modules.catalog_source.rpc',side_effect=[RuntimeError(),payload]) as call:
            result=s.load();self.assertEqual(result['next_path'],'plugin://x/?page=2');self.assertEqual(call.call_count,2)
    def test_library_search_queries_complete_kodi_index(self):
        with patch('modules.catalog_source.rpc',return_value={'movies':[{'title':'Match'}]}) as call:
            self.assertEqual([i['title'] for i in DirectorySource('videodb://movies/titles/').search('Match')],['Match'])
            self.assertEqual(call.call_args.args[0],'VideoLibrary.GetMovies')
            self.assertEqual(call.call_args.args[1]['filter']['value'],'Match')
    def test_provider_search_has_explicit_scope_and_no_guessed_api(self):
        with patch('modules.catalog_source.rpc') as call:
            self.assertIsNone(DirectorySource('plugin://x/library').search('Match'));call.assert_not_called()

class WindowContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=E.parse(SKIN/'xml/script-foundry-vod.xml')
        cls.source=(HELPER/'resources/lib/modules/catalog_window.py').read_text(encoding='utf-8-sig')
    def test_arrows_are_in_the_same_native_container_as_posters(self):
        rail=self.doc.find(".//control[@id='50']")
        self.assertEqual(rail.findtext('orientation'),'horizontal')
        self.assertEqual(rail.findtext('width'),'1808')
        self.assertTrue(rail.findall(".//control/visible"))
        self.assertIn('ListItem.Property(catalog.arrow)',E.tostring(rail,encoding='unicode'))
        self.assertIsNone(self.doc.find(".//control[@id='5704']"))
        self.assertIsNone(self.doc.find(".//control[@id='5705']"))
    def test_search_has_32_68_panels_three_columns_and_ten_history_slots(self):
        panel=self.doc.find(".//control[@id='51']");self.assertEqual(panel.findtext('left'),'662')
        self.assertEqual(int(panel.findtext('width'))//int(panel.find('itemlayout').get('width')),3)
        self.assertTrue(all(self.doc.find(".//control[@id='%d']"%(5830+i)) is not None for i in range(10)))
        self.assertIn('>=.25',self.source)
        self.assertIn('getSelectedPosition()%3==0',self.source)
    def test_sort_menu_has_exact_four_options_and_no_native_sort_dialog(self):
        for i,(_,name) in enumerate(SORTS):self.assertEqual(self.doc.findtext(".//control[@id='%d']/label"%(5750+i)),name)
        self.assertNotIn('SendClick(3)',E.tostring(self.doc.getroot(),encoding='unicode'))
    def test_search_return_does_not_reset_native_rail_or_focus_to_zero(self):
        module=ast.parse(self.source);cls=next(n for n in module.body if isinstance(n,ast.ClassDef));method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='leave_search')
        body=ast.get_source_segment(self.source,method)
        self.assertNotIn('.refresh(',body);self.assertNotIn('.reset(',body);self.assertNotIn('.selectItem(',body)
    def test_context_playback_uses_structured_jsonrpc(self):
        self.assertIn("rpc('Player.Open',{'item':{'file':item.get('file','')}})",self.source)
        self.assertNotIn("'PlayMedia('",self.source)
    def test_kodi_bundled_python_compatible_and_generation_guards_exist(self):
        self.assertNotIn('removeprefix(',self.source);self.assertNotIn('cancel_futures=',self.source)
        self.assertIn('generation==self.request',self.source);self.assertIn('self.focus_pending=cid',self.source)
    def test_routing_catches_delayed_plugin_loads_and_keeps_source_link_directories(self):
        source=(HELPER/'resources/lib/modules/vod.py').read_text()
        self.assertIn('for _ in range(300)',source)
        self.assertIn('class CatalogRoutingMonitor',source)
        self.assertIn('Source/group-link directories keep their file-browser presentation',source)
        self.assertIn('source.initial = data',source)
    def test_actual_rating_badges_and_corrected_footer_anchor(self):
        for n in ('rating_rt_fresh','rating_rt_rotten','rating_metacritic'):
            self.assertTrue((SKIN/'media/streampilot'/('source-'+n+'.png')).is_file())
        self.assertEqual(self.doc.findtext(".//control[@id='5703']/left"),'280')

if __name__=='__main__':unittest.main()
