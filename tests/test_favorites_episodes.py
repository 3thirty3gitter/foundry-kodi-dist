"""Favorites retain media identity and episodes expose their actual detail fields."""
from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch,Mock
from urllib.parse import quote
import xml.etree.ElementTree as E
import test_release as kodi
from modules.favorites import remember,resolve,saved_target,source_key
from modules.metadata_cache import MetadataCache
from modules.catalog_metadata import episode_heading,details
from modules.catalog_source import DirectorySource
from modules.monitors.metadata import snapshot,values

ROOT=Path(__file__).resolve().parents[2]
EPISODE={'type':'episode','title':'The Signal','showtitle':'Fixture Series','season':1,'episode':2,
         'premiered':'2026-11-01','runtime':2700,'plot':'Episode plot','year':2026,
         'uniqueid':{'imdb':'tt1234567'},'file':'plugin://provider/play?token=private%2Fvalue&episode=2',
         'art':{'poster':'poster.png'},'ratings':{'imdb':{'rating':8.1}}}

def favorite(target,label='Saved episode'):
    return {'label':label,'type':'favorite','foundry.favorite':True,'file':'favourites://'+quote('PlayMedia("'+target+'")',safe='')+'/'}

class FavoritesEpisodes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.cache=MetadataCache(Path(self.tmp.name)/'metadata.sqlite')

    def test_episode_details_include_show_number_title_air_date_and_plot(self):
        result=details(EPISODE,True,'episode')
        self.assertTrue(result['details'].startswith('Fixture Series · S01E02 · The Signal'))
        self.assertEqual(result['released'],'Aired Nov 1, 2026')
        self.assertEqual(result['plot'],'Episode plot')

    def test_specials_preserve_zero_and_missing_numbers_are_not_invented(self):
        self.assertIn('S00E00',episode_heading(dict(EPISODE,season=0,episode=0)))
        self.assertEqual(episode_heading({'type':'episode','title':'Unknown'}),'Unknown')
        self.assertIn('Specials',episode_heading(dict(EPISODE,type='season',season=0)))

    def test_saved_action_decoder_does_not_decode_the_playback_target_twice(self):
        item=favorite(EPISODE['file']);self.assertEqual(saved_target(item['file']),('media',EPISODE['file']))
        for action in ('RunScript("evil")','RunAddon("plugin.video.x")','PlayMedia("x");RunScript("evil")'):
            self.assertIsNone(saved_target('favourites://'+quote(action,safe='')))

    def test_favorite_recovers_details_without_executing_a_plugin(self):
        remember(self.cache,EPISODE)
        row={'type':'media','title':'Saved episode','path':EPISODE['file'],'thumbnail':'fav.png'}
        with patch('modules.favorites.rpc',return_value={'favourites':[row]}) as call:
            result=resolve(favorite(EPISODE['file']),self.cache)
        self.assertEqual(result['title'],'The Signal');self.assertEqual(result['episode'],2)
        self.assertEqual(result['file'],EPISODE['file'])
        self.assertEqual([c.args[0] for c in call.call_args_list],['Favourites.GetFavourites'])

    def test_metadata_history_contains_no_playback_urls_or_arbitrary_secrets(self):
        remember(self.cache,dict(EPISODE,api_key='never-store',password='never-store'))
        payload=self.cache.get('source','v1',source_key(EPISODE['file']))
        text=json.dumps(payload);self.assertNotIn(EPISODE['file'],text);self.assertNotIn('never-store',text)

    def test_favorites_reordering_duplicate_aliases_and_other_actions_do_not_misidentify(self):
        remember(self.cache,EPISODE)
        row={'type':'media','title':'Saved episode','path':'plugin://another/film'}
        with patch('modules.favorites.rpc',return_value={'favourites':[row]}):self.assertIsNone(resolve(favorite(EPISODE['file']),self.cache))
        row['path']=EPISODE['file']
        with patch('modules.favorites.rpc',return_value={'favourites':[row,row]}):self.assertIsNone(resolve(favorite(EPISODE['file']),self.cache))

    def test_native_favorite_uses_library_metadata_and_keeps_its_target(self):
        path='videodb://movies/titles/12/'
        row={'type':'window','title':'My movie','window':'videos','windowparameter':path}
        item={'label':'My movie','file':'favourites://'+quote('ActivateWindow(10025,"'+path+'",return)',safe='')+'/'}
        with patch('modules.favorites.rpc',side_effect=[{'favourites':[row]},{'filedetails':{'type':'movie','id':12,'title':'Real title','file':'/actual/movie.mkv','plot':'Full plot'}}]):result=resolve(item,self.cache)
        self.assertEqual(result['file'],path);self.assertEqual(result['title'],'Real title');self.assertTrue(result['foundry.native_library'])

    def test_unknown_plugin_favorite_is_not_executed_or_guessed_from_its_alias(self):
        row={'type':'media','title':'Saved episode','path':EPISODE['file']}
        with patch('modules.favorites.rpc',return_value={'favourites':[row]}) as call:self.assertIsNone(resolve(favorite(EPISODE['file']),self.cache))
        self.assertEqual(call.call_count,1)

    def test_sparse_favorite_snapshot_is_still_eligible_for_metadata_lookup(self):
        item=favorite(EPISODE['file']);labels={'ListItem.Label':item['label'],'ListItem.FileNameAndPath':item['file']}
        owner,result=snapshot(False,lambda key:labels.get(key,''))
        self.assertTrue(result['foundry.favorite']);self.assertEqual(owner[-1],item['file'])

    def test_shared_properties_keep_episode_zero_and_identification(self):
        config={'show_tmdb':True,'show_imdb':True}
        result=values(dict(EPISODE,season=0,episode=0),{},config)
        self.assertEqual((result['season'],result['episode']),('0','0'));self.assertIn('S00E00',result['episode_heading'])

    def test_directory_fallback_retains_episode_identity(self):
        with patch('modules.catalog_source.rpc',side_effect=[RuntimeError(),{'files':[EPISODE]}]) as call:
            result=DirectorySource('plugin://provider/episodes','episodes').load()
        self.assertEqual(result['items'][0]['episode'],2)
        self.assertTrue({'season','episode','showtitle','uniqueid'}<=set(call.call_args.args[1]['properties']))

    def test_favorites_use_catalog_view_and_service_and_owner_path_guards(self):
        skin=ROOT/'skin.foundry-nimbus/xml'
        view=E.parse(skin/'MyFavourites.xml');self.assertEqual(view.findtext('defaultcontrol'),'57')
        self.assertIsNotNone(view.find("controls/include[.='View_57_StreamPilot']"))
        self.assertIn('favouritesbrowser',(ROOT/'script.foundry.helper/resources/lib/service.py').read_text())
        guards=E.parse(skin/'Includes_Metadata.xml');self.assertIn('owner_path',guards.findtext("expression[@name='FoundryMetadataCurrentItem']"))

if __name__=='__main__':unittest.main()
