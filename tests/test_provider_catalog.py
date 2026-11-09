"""Provider-neutral payload contracts; these are not claims about live add-ons."""
import unittest
from unittest.mock import patch,Mock
import test_release as kodi
from modules.catalog_items import normalize,catalog_directory,section_for
from modules.catalog_source import DirectorySource,DIRECTORY_FIELDS
from modules.catalog_enrichment import enrich,matching,lookup,merge
from modules import vod

class ProviderPayloads(unittest.TestCase):
    def tearDown(self):kodi.Window.values.clear()
    def test_varied_provider_shapes_keep_opaque_urls_and_share_media_detection(self):
        cases=[{'type':'movie','title':'Film','file':'plugin://alpha/play?token=a%26b&id=1'},
               {'mediatype':'tvshow','title':'Series','filetype':'directory','file':'plugin://beta/list/series'},
               {'type':'unknown','title':'Film','year':'2020','plot':'Plot','art':{'poster':'image://opaque/'}},
               {'label':'Clip','filetype':'file','mimetype':'video/mp4','file':'https://host/video|Header=opaque'}]
        for item in cases:
            with self.subTest(item=item):
                value=normalize(item)
                self.assertTrue(catalog_directory([value],'files'))
                self.assertEqual(value.get('file'),item.get('file'))
    def test_icons_and_file_actions_do_not_force_configuration_screens(self):
        for item in ({'label':'Settings','filetype':'file','file':'plugin://x/settings'},
                     {'label':'Login','art':{'poster':'login.png'},'filetype':'directory'},
                     {'label':'Sources','filetype':'directory','art':{'thumb':'sources.png'}}):
            self.assertFalse(catalog_directory([normalize(item)],'files'))
            self.assertFalse(catalog_directory([normalize(item,'movies')],'movies'))
    def test_mixed_action_and_media_directory_remains_native(self):
        self.assertFalse(catalog_directory([normalize({'type':'movie','title':'Film'}),normalize({'label':'Account settings','filetype':'file'})]))
    def test_malformed_optional_payloads_cannot_become_fake_metadata(self):
        value=normalize({'type':{},'art':['wrong'],'ratings':{'imdb':'NaN','tmdb':True,'unknown':[]},'uniqueid':[],'year':True,'rating':'inf'})
        self.assertEqual((value['type'],value['art'],value['ratings'],value['uniqueid']),('unknown',{},{},{}))
        self.assertNotIn('year',value);self.assertNotIn('rating',value)
        self.assertEqual(normalize(value),value)
    def test_named_ratings_keep_provenance_and_anonymous_rating_is_not_imdb(self):
        item=normalize({'rating':8,'ratings':{'IMDb':{'rating':7.4},'themoviedb':6.2}})
        self.assertEqual(set(item['ratings']),{'imdb','themoviedb'})
        self.assertNotIn('tmdb',normalize({'rating':8})['ratings'])
    def test_episode_zero_and_tv_art_are_preserved(self):
        item=normalize({'type':'episode','season':0,'episode':'0','firstaired':'2020-01-01','art':{'tvshow.poster':'series.png'}})
        self.assertEqual((item['season'],item['episode']),(0,0))
        self.assertEqual(section_for([item]),'TV Shows')
    def test_generic_legacy_art_and_unique_ids_are_requested_without_unsupported_ratings(self):
        self.assertTrue({'uniqueid','season','episode','firstaired','mimetype'}<=set(DIRECTORY_FIELDS))
        self.assertNotIn('ratings',DIRECTORY_FIELDS)
        item=normalize({'fanart':'legacy.jpg','thumbnail':'thumb.jpg','uniqueid':{'TMDB':123}})
        self.assertEqual(item['art'],{'fanart':'legacy.jpg','thumb':'thumb.jpg'})
        self.assertEqual(item['uniqueid'],{'tmdb':'123'})
    def test_probe_reused_and_nondict_entries_ignored_without_touching_urls(self):
        source=DirectorySource('plugin://x/?opaque=a%26b','movies')
        with patch('modules.catalog_source.rpc',return_value={'files':[None,{'type':'movie','title':'Film','file':'plugin://x/play?opaque=a%26b'}]}):result=source.load()
        self.assertTrue(result['catalog_eligible']);self.assertEqual(result['items'][0]['file'],'plugin://x/play?opaque=a%26b')
    def test_invalid_directory_collection_reports_source_error(self):
        with patch('modules.catalog_source.rpc',return_value={'files':{}}):
            with self.assertRaises(RuntimeError):DirectorySource('plugin://x/').load()
    def test_native_episode_and_season_use_their_own_documented_field_sets(self):
        for kind in ('season','episode'):
            item={'type':kind,'id':4,'title':'Item','file':'videodb://original/','filetype':'directory' if kind=='season' else 'file'}
            with patch('modules.catalog_enrichment.rpc',return_value={kind+'details':{'art':{'tvshow.poster':'poster.jpg'},'firstaired':'2020-01-02'}}) as rpc,patch.object(kodi.xbmc,'getCondVisibility',return_value=False):result=enrich(item,native_library=True)
            self.assertEqual(rpc.call_args.args[0],'VideoLibrary.Get'+kind.title()+'Details')
            self.assertEqual(rpc.call_args.args[1][kind+'id'],4)
            self.assertEqual(result['file'],item['file']);self.assertEqual(result['type'],kind)
            self.assertNotIn('imdbnumber',rpc.call_args.args[1]['properties'])
    def test_provider_db_ids_are_never_used_as_native_library_ids(self):
        with patch('modules.catalog_enrichment.rpc') as rpc,patch.object(kodi.xbmc,'getCondVisibility',return_value=False):
            enrich({'type':'movie','id':2,'title':'Provider item'},native_library=False);rpc.assert_not_called()
    def test_malformed_ids_do_not_make_metadata_queries(self):
        self.assertIsNone(lookup({'uniqueid':{'imdb':{},'tmdb':'not-an-id'},'file':'http://[bad','title':'Film'}))
        with patch('modules.catalog_enrichment.rpc') as rpc,patch.object(kodi.xbmc,'getCondVisibility',return_value=False):
            enrich({'type':'movie','id':True,'title':'Film'},native_library=True);rpc.assert_not_called()
    def test_conflicting_ids_rejected_and_nonconflicting_id_maps_merged(self):
        self.assertFalse(matching({}, {'type':'tvshow'}, {'tmdb_type':'movie'}))
        self.assertFalse(matching({}, {'uniqueid':{'tmdb':12}}, {'tmdb_id':'34'}))
        self.assertFalse(matching({}, {'uniqueid':{'imdb':'tt12'}}, {'imdb_id':'tt34'}))
        result=merge({'file':'plugin://original','uniqueid':{'imdb':'tt34'}},{'file':'plugin://metadata','uniqueid':{'tmdb':34}})
        self.assertEqual(result['uniqueid'],{'imdb':'tt34','tmdb':'34'});self.assertEqual(result['file'],'plugin://original')
    def test_missing_native_filetype_is_inferred_without_overwriting_provider_folders(self):
        self.assertEqual(normalize({'type':'tvshow'})['filetype'],'directory')
        self.assertEqual(normalize({'type':'episode'})['filetype'],'file')
        self.assertEqual(normalize({'type':'movie','filetype':'directory'})['filetype'],'directory')
    def test_library_search_retains_file_and_external_ids_for_playback_and_metadata(self):
        with patch('modules.catalog_source.rpc',return_value={'tvshows':[{'title':'Series','tvshowid':3,'file':'/media/show/'}]}) as rpc:
            records=DirectorySource('videodb://tvshows/titles/').search('Series',True)
        self.assertEqual(records[0]['file'],'/media/show/')
        self.assertEqual(records[0]['catalog_path'],'videodb://tvshows/titles/3/')
        self.assertEqual(records[0]['filetype'],'directory')
        self.assertTrue({'file','uniqueid'}<=set(rpc.call_args.args[1]['properties']))
    def test_tv_search_opens_native_seasons_and_preserves_source_state_for_return(self):
        from modules.catalog_window import CatalogWindow
        w=object.__new__(CatalogWindow);w.section='TV Shows';w.search=False;w.source=DirectorySource('videodb://tvshows/titles/')
        original=w.source;w.state=object();state=w.state;w.stack=[];w.load=Mock();w.getCurrentListPosition=lambda:0
        w.rail=[{'type':'tvshow','title':'Series','filetype':'directory','file':'/media/show/','catalog_path':'videodb://tvshows/titles/3/'}]
        w.onClick(50)
        self.assertEqual((w.source.path,w.source.content),('videodb://tvshows/titles/3/','seasons'))
        self.assertEqual(w.stack,[(original,state)]);w.load.assert_called_once()
    def test_provider_folder_with_same_db_id_keeps_its_opaque_navigation_url(self):
        from modules.catalog_window import CatalogWindow
        w=object.__new__(CatalogWindow);w.section='TV Shows';w.search=False;w.source=DirectorySource('plugin://provider/');w.state=object();w.stack=[];w.load=Mock();w.getCurrentListPosition=lambda:0
        w.rail=[{'type':'tvshow','filetype':'directory','file':'plugin://provider/season?opaque=a%26b','catalog_path':'videodb://tvshows/titles/3/'}]
        w.onClick(50)
        self.assertEqual(w.source.path,'plugin://provider/season?opaque=a%26b')
    def test_nested_nonmedia_result_returns_to_native_kodi_without_url_rewrite(self):
        from modules.catalog_window import CatalogWindow
        w=object.__new__(CatalogWindow);w.close=Mock();w.setProperty=Mock();url='plugin://provider/source?auth=opaque%26value'
        with patch('modules.catalog_window.rpc') as rpc:
            w.open_native(url)
        self.assertTrue(w.closed);w.close.assert_called_once()
        w.setProperty.assert_called_once_with('foundry.movie_submenu_label','')
        self.assertEqual(rpc.call_args.args,('GUI.ActivateWindow',{'window':'videos','parameters':[url,'return']}))
        self.assertEqual(kodi.Window().getProperty('foundry.catalog.handled_path'),url)
    def test_shared_metadata_binding_accepts_malformed_art_ratings_and_episode_fields(self):
        from modules.catalog_window import listitem
        entry=Mock()
        with patch.object(kodi.xbmcgui,'ListItem',return_value=entry):
            listitem({'type':'episode','art':[],'ratings':[],'season':0,'episode':2,'file':'plugin://original'},'TV Shows')
        self.assertEqual(entry.setInfo.call_args.args[1]['mediatype'],'episode')
        self.assertEqual(entry.setInfo.call_args.args[1]['season'],0)
    def test_adoption_is_provider_neutral_for_movie_tv_episode_and_untyped_media(self):
        for content,item,section in (
            ('movies',{'type':'movie','title':'Film'},'Movies'),
            ('tvshows',{'type':'tvshow','title':'Series','filetype':'directory'},'TV Shows'),
            ('episodes',{'type':'episode','title':'Episode'},'TV Shows'),
            ('files',{'title':'Series','mediatype':'tvshow','filetype':'directory'},'TV Shows'),
            ('files',{'title':'Film','year':2020,'plot':'Plot'},'Videos')):
            path='plugin://arbitrary-provider/list?opaque=unaltered'
            def visible(query):
                return query=='Window.IsActive(videos)' or query=='Container.Content('+content+')' or (query==vod.CATALOG_CONTENT and content!='files') or (query=='Container.Content(files) + !Container.IsUpdating' and content=='files')
            kodi.Window.values.clear()
            with patch.object(kodi.xbmc,'getCondVisibility',side_effect=visible),patch.object(kodi.xbmc,'getInfoLabel',side_effect=lambda q:path if q=='Container.FolderPath' else 'Category'),patch('modules.catalog_source.rpc',return_value={'files':[item]}),patch('modules.catalog_window.open_catalog',return_value=True) as opened:
                self.assertTrue(vod.activate_catalog())
            self.assertEqual(opened.call_args.args[:2],(path,section))
            self.assertIsNotNone(opened.call_args.kwargs['source'].initial)
    def test_declared_media_content_with_untyped_settings_action_stays_native(self):
        def visible(query):return query in ('Window.IsActive(videos)','Container.Content(movies)',vod.CATALOG_CONTENT)
        with patch.object(kodi.xbmc,'getCondVisibility',side_effect=visible),patch.object(kodi.xbmc,'getInfoLabel',return_value='plugin://any/settings'),patch('modules.catalog_source.rpc',return_value={'files':[{'label':'Login','filetype':'file','art':{'poster':'icon.png'}}]}),patch('modules.catalog_window.open_catalog') as opened:
            self.assertFalse(vod.activate_catalog());opened.assert_not_called()
    def test_unknown_video_kind_does_not_guess_movie_metadata_endpoint(self):
        self.assertIsNone(lookup({'type':'unknown','title':'Undisambiguated video','year':2020},'Videos'))
        from modules.catalog_metadata import details
        self.assertEqual(details({},False,'video')['details'],'Video')

if __name__=='__main__':unittest.main()
