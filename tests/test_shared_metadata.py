"""Direct API, shared cache, ownership and skin bindings; no real keys needed."""
from concurrent.futures import Future
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as E
import test_release as kodi
from modules.metadata_cache import MetadataCache
from modules.metadata_tmdb import TmdbMetadataClient
from modules.metadata import MetadataService, fingerprint, item_key, omdb_query, omdb_matches, omdb_metadata
from modules.monitors.metadata import MetadataMonitor, snapshot, values
from modules.apis.omdb import OmdbClient


def response(payload=None,status=200,headers=None):
    result=Mock(status_code=status,headers=headers or {})
    result.json.return_value=payload or {}
    return result


MOVIE={'id':42,'title':'Film','original_title':'Film','overview':'TMDb plot','release_date':'2020-01-02',
       'poster_path':'/poster.jpg','backdrop_path':'/fanart.jpg','runtime':120,'vote_average':8.4,'vote_count':123,
       'genres':[{'id':1,'name':'Drama'}],'production_companies':[{'name':'Studio','logo_path':'/studio.png'}],
       'external_ids':{'imdb_id':'tt1234567'},'credits':{'cast':[{'name':'Actor','character':'Role','profile_path':'/actor.jpg'}], 'crew':[{'name':'Director','job':'Director'}]},
       'images':{'logos':[{'file_path':'/wrong.png','iso_639_1':'fr','width':3000},{'file_path':'/right.png','iso_639_1':'en','width':200}]},
       'release_dates':{'results':[{'iso_3166_1':'US','release_dates':[{'certification':'R','type':3}]},{'iso_3166_1':'CA','release_dates':[{'certification':'14A','type':3}]}]}}
ITEM={'type':'movie','title':'Film','year':2020,'file':'plugin://source/play?auth=opaque%26data', 'filetype':'directory','id':77,'playcount':3,'uniqueid':{'tmdb':'42'},'art':{'poster':'provider.jpg'}}
CONFIG={'tmdb':'test-token','omdb':'test-key','language':'en-US','region':'CA','show_tmdb':True,'show_imdb':True,'show_rt':True,'show_metacritic':True}


class DirectTmdb(unittest.TestCase):
    def client(self,data=None):
        session=Mock();session.get.return_value=response(data or MOVIE)
        return TmdbMetadataClient('test-token',session=session),session

    def test_direct_details_supplies_art_cast_ratings_and_canadian_certification(self):
        client,session=self.client()
        item,status,_=client.fetch(ITEM)
        self.assertEqual(status,'ready');self.assertEqual(item['mpaa'],'CA 14A')
        self.assertEqual(item['runtime'],7200)
        self.assertEqual(item['ratings']['tmdb'],{'rating':8.4,'votes':123})
        self.assertTrue(item['art']['clearlogo'].endswith('/right.png'))
        self.assertEqual(item['cast'][0]['name'],'Actor')
        self.assertEqual(item['uniqueid']['imdb'],'tt1234567')
        args,kwargs=session.get.call_args
        self.assertEqual(args[0],'https://api.themoviedb.org/3/movie/42')
        self.assertEqual(kwargs['headers']['Authorization'],'Bearer test-token')
        self.assertEqual(kwargs['timeout'],(5,10))

    def test_v3_key_is_supported_without_bearer(self):
        client,session=self.client();client.key='a'*32
        client.fetch(ITEM)
        self.assertEqual(session.get.call_args.kwargs['params']['api_key'],'a'*32)
        self.assertNotIn('Authorization',session.get.call_args.kwargs['headers'])

    def test_imdb_lookup_selects_correct_media_type(self):
        client,session=self.client()
        session.get.side_effect=[response({'movie_results':[{'id':42}],'tv_results':[{'id':99}]}),response(MOVIE)]
        item,status,_=client.fetch({'type':'movie','uniqueid':{'imdb':'tt1234567'}})
        self.assertEqual(status,'ready');self.assertEqual(item['uniqueid']['tmdb'],'42')

    def test_title_year_match_is_exact_and_ambiguous_remakes_are_rejected(self):
        client,session=self.client()
        session.get.return_value=response({'results':[{'id':42,'title':'Film','release_date':'2019-01-01'}]})
        self.assertEqual(client.fetch({'type':'movie','title':'Film','year':2020})[1],'not_found')
        session.get.return_value=response({'results':[{'id':42,'title':'Film','release_date':'2020-01-01'},{'id':43,'title':'Film','release_date':'2020-02-01'}]})
        self.assertEqual(client.fetch({'type':'movie','title':'Film','year':2020})[1],'not_found')

    def test_title_alone_and_source_menu_do_not_make_network_requests(self):
        client,session=self.client()
        self.assertEqual(client.fetch({'type':'movie','title':'Film'})[1],'unidentified')
        self.assertEqual(client.fetch({'type':'unknown','title':'Account settings'})[1],'unidentified')
        session.get.assert_not_called()

    def test_wrong_returned_imdb_or_tmdb_identity_is_rejected(self):
        client,session=self.client()
        self.assertEqual(client.fetch(dict(ITEM,imdbnumber='tt9999999'))[1],'not_found')
        session.get.return_value=response(dict(MOVIE,id=43))
        self.assertEqual(client.fetch(ITEM)[1],'not_found')

    def test_quota_invalid_credentials_and_offline_are_separate(self):
        client,session=self.client()
        for code,status in [(401,'invalid_key'),(429,'rate_limited'),(500,'offline'),(404,'not_found')]:
            session.get.return_value=response(status=code,headers={'Retry-After':'120'})
            self.assertEqual(client.fetch(ITEM)[1],status)
        import requests
        session.get.side_effect=requests.Timeout('secret-in-url')
        self.assertEqual(client.fetch(ITEM)[1],'offline')

    def test_season_and_episode_use_parent_id_and_specials_zero(self):
        client,session=self.client()
        parent={'id':12,'name':'Show','poster_path':'/show.jpg','external_ids':{'imdb_id':'tt1111111'}}
        episode={'id':34,'name':'Special','season_number':0,'episode_number':0,'still_path':'/still.jpg','external_ids':{'imdb_id':'tt2222222'}}
        session.get.side_effect=[response(parent),response(episode)]
        item,status,_=client.fetch({'type':'episode','uniqueid':{'tvshow.tmdb':'12'},'season':0,'episode':0})
        self.assertEqual(status,'ready');self.assertEqual(item['season'],0)
        self.assertTrue(session.get.call_args.args[0].endswith('/tv/12/season/0/episode/0'))
        self.assertEqual(item['uniqueid']['tvshow.imdb'],'tt1111111')
        self.assertTrue(item['art']['poster'].endswith('/show.jpg'))

    def test_episode_own_imdb_find_uses_show_id(self):
        client,session=self.client()
        session.get.side_effect=[response({'tv_episode_results':[{'show_id':12,'season_number':1,'episode_number':2}]}),response({'id':12,'name':'Show'}),response({'id':34,'season_number':1,'episode_number':2,'external_ids':{'imdb_id':'tt2222222'}})]
        item,status,_=client.fetch({'type':'episode','uniqueid':{'imdb':'tt2222222'}})
        self.assertEqual(status,'ready');self.assertEqual(item['episode'],2)

    def test_episode_lookup_rejects_conflicting_number_and_parent(self):
        client,session=self.client()
        session.get.return_value=response({'tv_episode_results':[{'show_id':12,'season_number':1,'episode_number':3}]})
        self.assertEqual(client.fetch({'type':'episode','uniqueid':{'imdb':'tt2222222'},'season':1,'episode':2})[1],'not_found')
        session.get.return_value=response({'id':99,'name':'Wrong show'})
        self.assertEqual(client.fetch({'type':'episode','uniqueid':{'tvshow.tmdb':'12'},'season':1,'episode':2})[1],'not_found')

    def test_episode_guest_stars_are_combined_without_duplicate_actors(self):
        client,_=self.client()
        data={'credits':{'cast':[{'name':'Actor'}],'guest_stars':[{'name':'Guest'},{'name':'Actor'}]}}
        self.assertEqual([r['name'] for r in client.convert(data,'episode')['cast']],['Actor','Guest'])

    def test_missing_parent_identity_never_treats_episode_id_as_series(self):
        client,session=self.client()
        self.assertEqual(client.fetch({'type':'episode','title':'Episode','uniqueid':{'tmdb':'34'},'season':1,'episode':2})[1],'unidentified')
        session.get.assert_not_called()

    def test_malformed_payload_is_contained_and_no_rating_is_invented(self):
        client,session=self.client()
        session.get.return_value=response({'id':42,'title':'Film','vote_average':'NaN','vote_count':1,'genres':[None,{}]})
        item,status,_=client.fetch(ITEM)
        self.assertEqual(status,'ready');self.assertEqual(item['ratings'],{})
        self.assertEqual(item['art'],{})


class SharedService(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.clock=[1000.0]
        self.cache=MetadataCache(Path(self.tmp.name)/'metadata.sqlite',lambda:self.clock[0])
        self.config=dict(CONFIG)
        self.tmdb=Mock();self.omdb=Mock()
        self.tmdb.fetch.return_value=({'plot':'TMDb plot','art':{'poster':'tmdb.jpg'},'uniqueid':{'imdb':'tt1234567'},'ratings':{'tmdb':{'rating':8.4}}},'ready',0)
        self.omdb.fetch.return_value=({'imdb_id':'tt1234567','plot':'OMDb fallback','imdb_rating':'8.2/10','rotten_tomatoes':'78%','metacritic':'64/100'},'ready',0)
        self.service=MetadataService(self.cache,lambda:dict(self.config),Mock(return_value=self.tmdb),Mock(return_value=self.omdb))

    def test_native_and_other_addon_urls_reuse_metadata_without_changing_identity(self):
        first,status=self.service.enrich(copy.deepcopy(ITEM))
        second,_=self.service.enrich(dict(ITEM,file='/local/film.mkv'))
        self.tmdb.fetch.assert_called_once();self.omdb.fetch.assert_called_once()
        self.assertEqual(first['file'],ITEM['file']);self.assertEqual(second['file'],'/local/film.mkv')
        for field in ('id','filetype','playcount'):self.assertEqual(first[field],ITEM[field])
        self.assertEqual(first['plot'],'TMDb plot');self.assertEqual(first['ratings']['imdb']['rating'],8.2)
        self.assertEqual(first['ratings']['rottentomatoes']['rating'],7.8)

    def test_restart_uses_disk_cache(self):
        self.service.enrich(ITEM)
        other=MetadataService(MetadataCache(self.cache.path,lambda:self.clock[0]),lambda:dict(self.config),Mock(return_value=self.tmdb),Mock(return_value=self.omdb))
        other.enrich(ITEM);self.tmdb.fetch.assert_called_once();self.omdb.fetch.assert_called_once()

    def test_ids_reuse_cache_despite_different_addon_labels_or_missing_year(self):
        self.service.enrich(ITEM)
        other=dict(ITEM,title='[B]Provider Film[/B]',year=None,file='plugin://other/play')
        self.service.enrich(other)
        self.tmdb.fetch.assert_called_once();self.omdb.fetch.assert_called_once()

    def test_cached_id_cannot_override_conflicting_provider_imdb_identity(self):
        self.service.enrich(ITEM)
        conflicting=dict(ITEM,imdbnumber='tt9999999')
        result,status=self.service.enrich(conflicting)
        self.assertEqual(status['tmdb'],'not_found')
        self.assertEqual(result['art']['poster'],'provider.jpg')

    def test_busy_lookup_retries_soon_and_clearing_cache_keeps_active_slot(self):
        first=self.cache.claim('tmdb','x','one');second=self.cache.claim('omdb','x','two')
        result,status=self.service.enrich(ITEM)
        self.assertEqual(status['tmdb'],'busy');self.assertEqual(result['foundry.metadata_ttl'],1)
        self.cache.clear()
        self.assertFalse(self.cache.claim('tmdb','x','three'))
        self.cache.release(first);self.cache.release(second)

    def test_cache_clear_revision_discards_inflight_response(self):
        def fetch(item):
            self.config['revision']='new'
            return {'plot':'old response'},'ready',0
        self.tmdb.fetch.side_effect=fetch
        result,status=self.service.enrich(ITEM)
        self.assertEqual(status['tmdb'],'changed');self.assertNotEqual(result.get('plot'),'old response')

    def test_key_change_and_disabled_provider_never_reuse_old_provider_payload(self):
        result,_=self.service.enrich(ITEM)
        self.config['tmdb']='new-token';self.tmdb.fetch.return_value=({},'invalid_key',86400)
        self.config['omdb']=''
        current,_=self.service.enrich(result)
        self.assertEqual(current['art']['poster'],'provider.jpg')
        self.assertNotIn('imdb',current['ratings'])
        self.config['tmdb']=''
        self.service.enrich(ITEM)
        self.assertEqual(self.tmdb.fetch.call_count,2)

    def test_rate_limit_is_shared_between_titles(self):
        self.tmdb.fetch.return_value=({},'rate_limited',120)
        self.service.enrich(ITEM)
        other=dict(ITEM,title='Other',uniqueid={'tmdb':'99'})
        self.service.enrich(other)
        self.tmdb.fetch.assert_called_once()

    def test_expired_cache_survives_offline_but_is_bounded(self):
        self.service.enrich(ITEM);self.clock[0]+=8*86400
        self.tmdb.fetch.return_value=({},'offline',30)
        result,status=self.service.enrich(ITEM)
        self.assertEqual(result['plot'],'TMDb plot');self.assertEqual(status['tmdb'],'offline')
        self.clock[0]+=31*86400
        result,_=self.service.enrich(ITEM)
        self.assertNotEqual(result.get('plot'),'TMDb plot')

    def test_negative_results_are_cached(self):
        self.tmdb.fetch.return_value=({},'not_found',0)
        self.service.enrich(ITEM);self.service.enrich(ITEM)
        self.tmdb.fetch.assert_called_once()

    def test_requests_are_deduplicated_and_limited_across_instances(self):
        other=MetadataCache(self.cache.path,lambda:self.clock[0])
        a=self.cache.claim('tmdb','owner','one');self.assertTrue(a)
        self.assertFalse(other.claim('tmdb','owner','one'))
        b=other.claim('omdb','owner','two');self.assertTrue(b)
        self.assertFalse(self.cache.claim('tmdb','owner','three'))
        self.cache.release(a);self.assertTrue(other.claim('tmdb','owner','three'))

    def test_abandoned_request_lease_expires(self):
        self.cache.claim('tmdb','owner','one');self.clock[0]+=121
        self.assertTrue(self.cache.claim('tmdb','owner','one'))

    def test_configuration_changed_during_fetch_discards_response(self):
        def fetch(item):
            self.config['tmdb']=''
            return {'plot':'must be discarded'},'ready',0
        self.tmdb.fetch.side_effect=fetch
        result,status=self.service.enrich(ITEM)
        self.assertEqual(status['tmdb'],'changed');self.assertNotEqual(result.get('plot'),'must be discarded')

    def test_no_secret_key_or_playback_url_is_persisted_in_cache(self):
        self.service.enrich(ITEM)
        data=Path(self.cache.path).read_bytes()
        for secret in ('test-key','test-token',ITEM['file']):self.assertNotIn(secret.encode(),data)

    def test_omdb_identity_and_episode_numbers_are_verified(self):
        self.assertFalse(omdb_matches({'imdb_id':'tt7654321'},{'imdb_id':'tt1234567','type':'movie'}))
        self.assertFalse(omdb_matches({'title':'Film','year':'2019'},{'title':'Film','year':2020,'type':'movie'}))
        self.assertIsNone(omdb_query({'type':'season','title':'Season 1'}))
        self.assertIsNone(omdb_query({'type':'episode','title':'Episode 1','year':2020}))
        self.assertNotEqual(item_key({'type':'episode','season':1,'episode':1}),item_key({'type':'episode','season':1,'episode':2}))

    def test_omdb_episode_query_and_metascore_fallback(self):
        session=Mock();session.get.return_value=response({'imdbID':'tt2222222','Type':'episode','Season':'0','Episode':'0','Metascore':'64'})
        payload,status,_=OmdbClient('test-key',session).fetch({'imdb_id':'tt1111111','season':0,'episode':0})
        self.assertEqual(status,'ready');self.assertEqual(payload['metacritic'],'64/100')
        self.assertEqual(session.get.call_args.kwargs['params']['Season'],0)
        self.assertTrue(omdb_matches(payload,{'imdb_id':'tt1111111','season':0,'episode':0,'type':'episode'}))


class MonitorBindings(unittest.TestCase):
    def setUp(self):
        self.window=kodi.Window();self.window.values.clear()
        self.now=[1.0];self.config=dict(CONFIG)
        self.executor=Mock();self.future=Future();self.executor.submit.return_value=self.future
        self.monitor=MetadataMonitor(self.window,provider=Mock(),clock=lambda:self.now[0],executor=self.executor)
        self.labels={'ListItem.Label':'Film','ListItem.Title':'Film','ListItem.Year':'2020','ListItem.DBTYPE':'movie','ListItem.UniqueID(tmdb)':'42'}
        self.patches=[patch('modules.monitors.metadata.settings',side_effect=lambda:dict(self.config)),patch.object(kodi.xbmc,'getInfoLabel',side_effect=lambda k:self.labels.get(k,'')),patch.object(kodi.xbmc,'getCondVisibility',return_value=False)]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def start(self):
        self.monitor.process_current_item();self.now[0]+=.3;self.monitor.process_current_item()

    def test_focus_debounce_and_late_response_cannot_replace_new_title(self):
        self.start();self.executor.submit.assert_called_once()
        self.labels.update({'ListItem.Label':'Other','ListItem.Title':'Other'})
        self.future.set_result(({'title':'Film','plot':'old title'},{'tmdb':'ready'}))
        self.monitor.process_current_item()
        self.assertEqual(self.window.getProperty('foundry.metadata.plot'),'')

    def test_published_shared_properties_match_focused_owner(self):
        self.start();self.future.set_result((dict(ITEM,plot='Shared plot',ratings={'imdb':{'rating':8.2}}),{'tmdb':'ready','omdb':'ready'}))
        self.monitor.process_current_item()
        self.assertEqual(self.window.getProperty('foundry.metadata.plot'),'Shared plot')
        self.assertEqual(self.window.getProperty('foundry.metadata.owner_label'),'Film')
        self.assertEqual(self.window.getProperty('foundry.metadata.imdb'),'8.2/10')

    def test_key_removal_invalidates_inflight_properties(self):
        self.start();self.config['tmdb']='';self.config['omdb']=''
        self.future.set_result((dict(ITEM,plot='old key'),{'tmdb':'ready'}))
        self.monitor.process_current_item()
        self.assertEqual(self.window.getProperty('foundry.metadata.plot'),'')

    def test_leaving_media_and_stopping_clears_properties(self):
        self.start();self.labels.clear();self.monitor.process_current_item();self.monitor.stop()
        self.assertEqual(self.window.getProperty('foundry.metadata.owner_label'),'')
        self.executor.shutdown.assert_called_once()

    def test_rating_preferences_are_independent(self):
        item={'ratings':{'tmdb':{'rating':7.2},'imdb':{'rating':8.1},'rottentomatoes':{'rating':7.8},'metacritic':{'rating':6.4}}}
        result=values(item,{},dict(CONFIG,show_imdb=False,show_rt=False))
        self.assertEqual(result['imdb'],'');self.assertEqual(result['rotten_tomatoes'],'')
        self.assertEqual(result['tmdb'],'7.2');self.assertEqual(result['metacritic'],'64/100')

    def test_player_uses_own_identity_and_live_tv_does_not_match_movies(self):
        self.labels.update({'VideoPlayer.DBTYPE':'episode','VideoPlayer.Title':'Episode','VideoPlayer.Season':'0','VideoPlayer.Episode':'2','VideoPlayer.UniqueID(imdb)':'tt2222222','Player.FilenameAndPath':'plugin://play'})
        with patch.object(kodi.xbmc,'getCondVisibility',side_effect=lambda q:q in ('Player.HasVideo','VideoPlayer.Content(episodes)')):
            owner,item=snapshot(True)
        self.assertEqual(item['type'],'episode');self.assertEqual(item['episode'],'2')
        with patch.object(kodi.xbmc,'getCondVisibility',return_value=True):self.assertIsNone(snapshot(True))

    def test_pause_invalidates_late_result_and_clears_visible_metadata(self):
        self.start();self.window.setProperty('foundry.metadata.plot','old plot')
        self.monitor.pause()
        self.future.set_result((dict(ITEM,plot='late plot'),{'tmdb':'ready'}))
        self.monitor.process_current_item()
        self.assertEqual(self.window.getProperty('foundry.metadata.plot'),'')

    def test_unchanged_label_but_different_id_rejects_late_response(self):
        self.start();self.labels['ListItem.UniqueID(tmdb)']='43'
        self.future.set_result((dict(ITEM,plot='wrong film'),{'tmdb':'ready'}))
        self.monitor.process_current_item()
        self.assertEqual(self.window.getProperty('foundry.metadata.plot'),'')

    def test_xml_registers_shared_bindings_and_guards_episode_ownership(self):
        skin=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus'
        doc=E.parse(skin/'xml/Includes_Metadata.xml')
        self.assertIn('owner_episode',doc.find("expression[@name='FoundryMetadataCurrentItem']").text)
        self.assertIn('owner_tmdb',doc.find("expression[@name='FoundryMetadataCurrentItem']").text)
        self.assertIn('owner_season',doc.find("expression[@name='FoundryPlayerCurrentItem']").text)
        self.assertTrue(E.parse(skin/'xml/Includes.xml').find("include[@file='Includes_Metadata.xml']") is not None)
        for filename in ('DialogVideoInfo.xml','Variables_Artwork.xml','Includes_StreamPilotOSD.xml','Variables_Ratings.xml'):
            self.assertIn('Foundry', (skin/'xml'/filename).read_text())


class CatalogRefresh(unittest.TestCase):
    def test_transient_results_expire_instead_of_hiding_a_busy_lookup_for_an_hour(self):
        from modules.catalog_window import metadata_fresh
        self.assertTrue(metadata_fresh((10,{'foundry.metadata_ttl':1}),10.5))
        self.assertFalse(metadata_fresh((10,{'foundry.metadata_ttl':1}),11))

    def test_key_removal_restores_existing_item_and_clears_enriched_art_and_ratings(self):
        from modules.catalog_window import CatalogWindow
        w=object.__new__(CatalogWindow);entry=Mock()
        w.section='Movies';w.rail=[dict(ITEM,art={'poster':'new.jpg','clearlogo':'new.png'},
            ratings={'imdb':{'rating':8.2}},**{'foundry.metadata_original':copy.deepcopy(ITEM)})]
        w.search=False;w.hero=w.rail[0]
        w.getListItem=lambda index:entry;w.schedule_artwork_redraw=Mock();w.set_hero=Mock()
        w.restore_metadata()
        self.assertEqual(w.rail[0]['file'],ITEM['file'])
        self.assertEqual(w.rail[0]['art'],ITEM['art'])
        self.assertEqual(entry.setArt.call_args.args[0]['clearlogo'],'')
        entry.getVideoInfoTag().setRatings.assert_called_with({},'')
        self.assertEqual(entry.setInfo.call_args.args[1]['plot'],'')
        entry.setPath.assert_not_called()


if __name__=='__main__':unittest.main()
