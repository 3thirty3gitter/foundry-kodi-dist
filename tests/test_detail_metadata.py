import importlib.util,json,sys,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import xml.etree.ElementTree as E
BASE=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
import test_release as kodi
CANDIDATE=BASE
def load(name):
    return __import__('importlib').import_module('modules.'+name.replace('/','.'))
model=load('catalog_model');metadata=load('catalog_metadata');source=load('catalog_source');enrichment=load('catalog_enrichment');window=load('catalog_window');monitor=load('monitors/metadata');vod=load('vod')
schema=json.loads((OUT/'fixtures/kodi_omega_detail_schema.json').read_text())
class DetailMetadataTests(unittest.TestCase):
    def test_all_detail_fields_are_valid_for_kodi_omega(self):
        names={'movie':'Movie','tvshow':'TVShow','season':'Season','episode':'Episode'}
        for kind,fields in enrichment.NATIVE_DETAIL_FIELDS.items():
            self.assertFalse(set(fields)-set(schema['Video.Fields.'+names[kind]]['items']['enum']),kind)
            self.assertEqual(len(fields),len(set(fields)),kind)
        self.assertFalse(set(enrichment.DETAIL_DIRECTORY_FIELDS)-set(schema['List.Fields.Files']['items']['enum']))

    def test_bulk_directory_requests_stay_lightweight(self):
        self.assertNotIn('cast',enrichment.DIRECTORY_FIELDS)
        self.assertNotIn('director',enrichment.DIRECTORY_FIELDS)

    def test_single_item_native_lookup_requests_cast_and_details(self):
        item={'type':'movie','id':7,'title':'Fixture','file':'fixture://original','art':{}}
        provider=Mock();provider.enrich.side_effect=lambda v,s:(v,{})
        data={'cast':[{'name':'Actor','role':'Role','thumbnail':'fixture://actor'}],'director':['Director'],'writer':['Writer'],
              'runtime':7200,'country':['Canada'],'tagline':'Tagline','trailer':'fixture://trailer',
              'dateadded':'2026-11-08 10:00:00','set':'Collection','tag':['Tag'],'art':{'fanart':'fixture://fanart'}}
        with patch.object(enrichment,'rpc',return_value={'moviedetails':data}) as rpc,patch('modules.metadata.service',return_value=provider),patch('modules.metadata.settings',return_value={}):
            result,_=enrichment.enrich_with_status(item,native_library=True)
        request=rpc.call_args.args[1]
        for key in data:self.assertIn(key,request['properties']);self.assertEqual(result[key],data[key])
        self.assertEqual(result['file'],item['file']);self.assertEqual(result['id'],7)

    def test_dialog_item_receives_cast_information_art_and_original_path(self):
        entry=Mock()
        item={'type':'movie','title':'Fixture','file':'fixture://original','runtime':7200,
              'cast':[{'name':'Actor','role':'Role','thumbnail':'fixture://actor'}],
              'director':['Director'],'writer':['Writer'],'country':['Canada'],'trailer':'fixture://trailer',
              'set':'Collection','tag':['Tag'],'dateadded':'2026-11-08 10:00:00','art':{'poster':'fixture://poster','fanart':'fixture://fanart'}}
        with patch.object(kodi.xbmcgui,'ListItem',return_value=entry),patch.object(window,'cached_artwork_color',return_value=None):
            window.listitem(item)
        info=entry.setInfo.call_args.args[1]
        self.assertEqual(info['director'],['Director']);self.assertEqual(info['duration'],7200)
        for key in ['trailer','set','tag','dateadded']:self.assertEqual(info[key],item[key])
        entry.setCast.assert_called_once_with(item['cast'])
        self.assertEqual(entry.setArt.call_args.args[0]['fanart'],'fixture://fanart')

    def test_restored_item_clears_removed_details(self):
        entry=Mock();window.apply_info(entry,{'type':'movie','title':'Fixture'},restoring=True)
        info=entry.setInfo.call_args.args[1]
        for key in ['trailer','set','dateadded','status']:self.assertEqual(info[key],'')
        self.assertEqual(info['tag'],[]);entry.setCast.assert_called_once_with([])

    def test_info_rows_allow_only_identity_guarded_metadata(self):
        root=E.parse(CANDIDATE/'skin.foundry-nimbus/xml/DialogVideoInfo.xml')
        info=root.find(".//control[@id='53']/content")
        for prop in ['Director','Writer','Premiered','Genre','Studio','Country']:
            row=next(i for i in info.findall('item') if i.findtext('label2')=='$VAR[FoundryMetadata'+prop+']')
            condition=row.findtext('visible')
            self.assertIn('$EXP[FoundryMetadataCurrentItem]',condition)
            self.assertIn('foundry.metadata.'+prop.lower(),condition)

    def test_live_cast_is_bounded_and_malformed_rows_are_filtered(self):
        actors=[{'name':'Actor %d'%i,'role':'Role','thumbnail':'fixture://actor%d'%i} for i in range(45)]
        result=monitor.values({'type':'movie','cast':[None,12,{}]+actors},{},{})
        self.assertEqual(result['cast.0.name'],'Actor 0')
        self.assertEqual(result['cast.39.name'],'Actor 39')
        self.assertNotIn('cast.40.name',result)

    def test_title_change_clears_old_cast_names_roles_and_images(self):
        host=kodi.Window();host.values.clear();worker=monitor.MetadataMonitor(host,provider=Mock())
        worker.config={}
        owner=('Fixture','2026','movie','','','','','','','fixture://one')
        worker.publish('foundry.metadata.',owner,{'type':'movie','cast':[{'name':'First','role':'Role','thumbnail':'fixture://first'}]}, {})
        self.assertEqual(host.getProperty('foundry.metadata.cast.0.thumbnail'),'fixture://first')
        worker.clear('foundry.metadata.')
        self.assertEqual(host.getProperty('foundry.metadata.cast.0.name'),'')
        self.assertEqual(host.getProperty('foundry.metadata.cast.0.thumbnail'),'')
        worker.stop()

    def test_fallback_cast_and_art_use_same_page_geometry_and_identity_guards(self):
        root=E.parse(CANDIDATE/'skin.foundry-nimbus/xml/Includes_DialogDetails.xml')
        cast=root.find("include[@name='FoundryDialogCastFallback']/control[@id='5050']")
        self.assertIn('$EXP[FoundryMetadataCurrentItem]',cast.findtext('visible'))
        self.assertEqual(cast.findtext('onleft'),'20000')
        self.assertEqual(cast.findtext('onback'),'SetFocus(20000)')
        self.assertEqual(len(cast.findall('content/item')),40)
        for item in cast.findall('content/item'):
            self.assertIn('$EXP[FoundryMetadataCurrentItem]',item.findtext('visible'))
        art=root.find("include[@name='FoundryDialogArtPreview']/control[@type='group']")
        self.assertEqual(art.findtext('left'),'620');self.assertEqual(art.findtext('width'),'1160')
        items=art.findall("control[@id='5051']/content/item")
        self.assertEqual([i.findtext('icon') for i in items[:3]],['$VAR[FoundryMetadataPoster]','$VAR[FoundryMetadataFanart]','$VAR[FoundryMetadataClearlogo]'])
        self.assertIn('Control.IsEnabled(10)',items[3].findtext('visible'))
        self.assertIn('ListItem.DBID',items[3].findtext('visible'))

    def test_show_context_reaches_seasons_and_episodes_without_copying_plot_or_date(self):
        show={'type':'tvshow','title':'Fixture Show','year':2018,'uniqueid':{'tmdb':'100','imdb':'tt100'},'id':3,'plot':'Show plot','premiered':'2018-01-01'}
        season=source.inherit_tv_context({'type':'season','season':0,'title':'Specials','showtitle':'','uniqueid':{}},show,True)
        self.assertEqual(season['uniqueid']['tvshow.tmdb'],'100');self.assertEqual(season['showtitle'],'Fixture Show')
        self.assertEqual(season['tvshowyear'],2018);self.assertNotIn('plot',season);self.assertNotIn('premiered',season)
        episode=source.inherit_tv_context({'type':'episode','episode':2,'title':'Special Episode','uniqueid':{'tmdb':'200'}},season,True)
        self.assertEqual(episode['season'],0);self.assertEqual(episode['episode'],2)
        self.assertEqual(episode['uniqueid']['tmdb'],'200');self.assertEqual(episode['uniqueid']['tvshow.tmdb'],'100')
        self.assertNotIn('year',episode);self.assertNotIn('premiered',episode)

    def test_conflicting_parent_ids_do_not_inherit_unrelated_metadata(self):
        child={'type':'episode','title':'Other','uniqueid':{'tvshow.tmdb':'999'}}
        parent={'type':'tvshow','title':'Fixture','year':2026,'uniqueid':{'tmdb':'100'}}
        self.assertEqual(source.inherit_tv_context(child,parent),child)

    def test_missing_episode_numbers_are_never_guessed(self):
        item=source.inherit_tv_context({'type':'episode','title':'Unknown'}, {'type':'season','season':3,'showtitle':'Fixture'})
        self.assertEqual(item['season'],3);self.assertNotIn('episode',item)
        heading=metadata.episode_heading(item);self.assertIn('S03',heading);self.assertNotIn('E00',heading)

    def test_episode_air_date_numbers_and_type_reach_catalog_and_native_dialog(self):
        item={'type':'episode','title':'Episode title','showtitle':'Fixture','season':2,'episode':7,'firstaired':'2026-11-01','premiered':'2018-01-01','plot':'Episode plot'}
        detail=metadata.details(item,True,'episode')
        self.assertIn('S02E07',detail['details']);self.assertIn('TV Episode',detail['details'])
        self.assertEqual(detail['released'],'Aired Nov 1, 2026');self.assertEqual(model.date(item),'2026-11-01')
        entry=Mock();window.apply_info(entry,item)
        info=entry.setInfo.call_args.args[1]
        self.assertEqual((info['season'],info['episode']),(2,7));self.assertEqual(info['premiered'],'2026-11-01')
        self.assertEqual(info['tvshowtitle'],'Fixture')

    def test_season_zero_is_specials_and_not_an_episode(self):
        result=metadata.details({'type':'season','season':0,'showtitle':'Fixture','title':'Specials','plot':'Season plot'},True,'season')
        self.assertIn('Specials',result['details']);self.assertIn('TV Season',result['details']);self.assertNotIn('E00',result['details'])
        self.assertEqual(result['plot'],'Season plot')

    def test_native_episode_parent_ids_are_recovered_without_replacing_story(self):
        item={'type':'episode','id':9,'title':'Episode','season':2,'episode':7,'file':'fixture://episode'}
        responses=[{'episodedetails':{'tvshowid':3,'plot':'Episode story','firstaired':'2026-11-01'}},
                   {'tvshowdetails':{'title':'Fixture','year':2018,'uniqueid':{'tmdb':'100','imdb':'tt100'}}}]
        provider=Mock();provider.enrich.side_effect=lambda i,s:(i,{})
        with patch.object(enrichment,'rpc',side_effect=responses) as rpc,patch('modules.metadata.service',return_value=provider),patch('modules.metadata.settings',return_value={}):
            result,_=enrichment.enrich_with_status(item,'TV Shows',native_library=True)
        self.assertEqual(rpc.call_count,2);self.assertEqual(result['uniqueid']['tvshow.tmdb'],'100')
        self.assertEqual(result['showtitle'],'Fixture');self.assertEqual(result['plot'],'Episode story')
        self.assertEqual((result['season'],result['episode']),(2,7));self.assertNotIn('premiered',result)

    def test_native_fallback_distinguishes_season_and_episode(self):
        for kind,expected in [('season','TV Season'),('episode','TV Episode')]:
            labels={'ListItem.DBTYPE':kind,'ListItem.Title':'Fixture','ListItem.Season':'0','ListItem.Episode':'2'}
            result=vod.catalog_details(lambda name:labels.get(name,''),kodi.Window())
            self.assertIn(expected,result['details'])

    def test_candidate_python_and_xml_parse(self):
        for path in (BASE/'script.foundry.helper/resources/lib').rglob('*.py'):compile(path.read_text(encoding='utf-8'),str(path),'exec')
        for path in (BASE/'skin.foundry-nimbus/xml').glob('*.xml'):E.parse(path)

if __name__=='__main__':
    suites=[unittest.defaultTestLoader.loadTestsFromTestCase(DetailMetadataTests)]
    for name in ['test_catalog_enrichment','test_shared_metadata','test_favorites_episodes','test_vod_catalog','test_provider_catalog','test_library_partial_load']:
        suites.append(unittest.defaultTestLoader.loadTestsFromName(name))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites));sys.exit(not result.wasSuccessful())
