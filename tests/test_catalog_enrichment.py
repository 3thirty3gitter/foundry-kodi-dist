"""Provider identity, cache readiness and actual source-defined catalog styling."""
import unittest,json,zipfile,xml.etree.ElementTree as E
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import test_release as kodi
from modules.catalog_enrichment import enrich,lookup,matching,merge
from modules.catalog_items import normalize
from modules.catalog_color import color,resolved

class Enrichment(unittest.TestCase):
    def test_ambiguous_title_alone_never_queries_provider(self):
        self.assertIsNone(lookup({'title':'The Thing'}))
        self.assertEqual(lookup({'title':'The Thing','year':1982})['year'],'1982')
        self.assertFalse(matching({'title':'The Thing','year':1982},{'title':'The Thing','year':2011},{'query':'The Thing'}))
    def test_known_ids_beat_title_and_are_encoded_by_caller(self):
        p=lookup({'title':'A,B','imdbnumber':'tt0084787','year':1982})
        self.assertEqual(p['imdb_id'],'tt0084787');self.assertNotIn('query',p)
        self.assertEqual(lookup({'uniqueid':{'tmdb':'1399'}},'TV Shows')['tmdb_type'],'tv')
        self.assertIsNone(lookup({'type':'episode','title':'Episode','year':2000}))
    def test_native_library_metadata_and_ratings_are_recovered(self):
        item={'id':9,'type':'movie','title':'Film','file':'plugin://provider/play','filetype':'file'}
        with patch('modules.catalog_enrichment.rpc',return_value={'moviedetails':{'art':{'clearlogo':'logo.png'},'ratings':{'imdb':{'rating':8}},'uniqueid':{'imdb':'tt1234'}}}) as rpc,patch.object(kodi.xbmc,'getCondVisibility',return_value=False):
            result=enrich(item,native_library=True)
        self.assertEqual(rpc.call_args.args[0],'VideoLibrary.GetMovieDetails')
        self.assertEqual(result['ratings']['imdb']['rating'],8)
        self.assertEqual(result['art']['clearlogo'],'logo.png')
        self.assertEqual(result['file'],item['file'])
    def test_tmdbhelper_details_supplies_real_art_and_known_tmdb_rating(self):
        item={'title':'Film','year':2000,'imdbnumber':'tt1234','file':'plugin://provider/play','art':{'poster':'provider.jpg'}}
        data={'files':[{'title':'Film','year':2000,'imdbnumber':'tt1234','rating':7.3,'file':'NEVER_PLAY_METADATA_URL','art':{'clearlogo':'correct-logo.png','poster':'tmdb-poster.jpg'}}]}
        with patch('modules.catalog_enrichment.rpc',return_value=data),patch.object(kodi.xbmc,'getCondVisibility',return_value=True):result=enrich(item)
        self.assertEqual(result['file'],item['file']);self.assertEqual(result['art']['poster'],'tmdb-poster.jpg')
        self.assertEqual(result['ratings']['tmdb']['rating'],7.3)
        self.assertNotIn('imdb',result['ratings'])
    def test_generic_rating_is_not_mislabelled_and_empty_art_keeps_base(self):
        result=merge({'art':{'poster':'base.png'}},{'rating':8,'art':{'poster':''}})
        self.assertEqual(result['art']['poster'],'base.png');self.assertEqual(result['ratings'],{})
    def test_failed_source_and_missing_addon_leave_original_item_usable(self):
        item={'title':'Film','year':2000,'file':'plugin://provider/play'}
        with patch('modules.catalog_enrichment.rpc',side_effect=RuntimeError),patch.object(kodi.xbmc,'getCondVisibility',return_value=True):self.assertEqual(enrich(item),normalize(item))
    def test_color_uses_actual_kodi_cache_mapping_and_white_fallback(self):
        p=kodi.PROFILE/'Thumbnails/a/cached.jpg';p.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(40,40),(130,130,130)).save(p)
        with patch('modules.catalog_color.rpc',return_value={'textures':[{'cachedurl':'a/cached.jpg'}]}):
            self.assertEqual(color('https://image.example/art.jpg'),'FFFFFFFF')
        with patch('modules.catalog_color.rpc',return_value={'textures':[]}):self.assertIsNone(color('https://image.example/not-cached.jpg'))
    def test_resolved_effect_tints_rgb_and_preserves_source_alpha_and_bytes(self):
        import hashlib
        template=Path(kodi.translate('special://skin/media/streampilot/catalog-glow.png'))
        before=template.read_bytes()
        with patch('modules.catalog_color.color',return_value='FF0036C7'):
            value,path=resolved('fixture://known-color')
            second=resolved('fixture://known-color')
        self.assertEqual(value,'FF0036C7');self.assertEqual(second,(value,path))
        self.assertEqual(template.read_bytes(),before)
        with Image.open(template) as source,Image.open(path) as effect:
            self.assertEqual(source.size,effect.size)
            self.assertEqual(source.convert('RGBA').getchannel('A').tobytes(),effect.getchannel('A').tobytes())
            self.assertEqual(effect.getpixel((effect.width//2,effect.height//2))[:3],(0,54,199))
    def test_missing_color_does_not_create_or_publish_an_effect(self):
        with patch('modules.catalog_color.color',return_value=None):self.assertIsNone(resolved('fixture://not-cached'))
    def test_native_artwork_redraw_restores_width_even_if_invalidation_fails(self):
        import importlib
        from unittest.mock import Mock
        window=importlib.import_module('modules.catalog_window')
        w=object.__new__(window.CatalogWindow);control=Mock();control.getWidth.return_value=1920
        w.getControl=lambda cid:control
        window.CatalogWindow.redraw_catalog_control(w,50)
        self.assertEqual([c.args for c in control.setWidth.call_args_list],[(1921,),(1920,)])
        control.reset_mock();control.setWidth.side_effect=[RuntimeError('controlled'),None]
        with self.assertRaises(RuntimeError):window.CatalogWindow.redraw_catalog_control(w,50)
        self.assertEqual(control.setWidth.call_args_list[-1].args,(1920,))
    def test_async_artwork_redraw_is_deferred_and_coalesced(self):
        import importlib
        window=importlib.import_module('modules.catalog_window')
        w=object.__new__(window.CatalogWindow);now=[10.0];w.clock=lambda:now[0];w.pending_artwork_redraw={};calls=[]
        w.redraw_catalog_control=lambda cid:calls.append(cid)
        w.schedule_artwork_redraw(50);now[0]=10.1;w.schedule_artwork_redraw(50);w.flush_artwork_redraw()
        self.assertEqual(calls,[])
        now[0]=10.3;w.flush_artwork_redraw();w.flush_artwork_redraw()
        self.assertEqual(calls,[50]);self.assertEqual(w.pending_artwork_redraw,{})
    def test_async_metadata_updates_native_year_ids_and_tv_type_without_playback_change(self):
        import importlib
        from unittest.mock import Mock
        window=importlib.import_module('modules.catalog_window');entry=Mock()
        window.apply_info(entry,{'title':'TV title','type':'unknown','year':2020,'imdbnumber':'tt12345','genre':['Drama',None],'file':'plugin://original/play'},'TV Shows')
        info=entry.setInfo.call_args.args[1]
        self.assertEqual((info['year'],info['imdbnumber'],info['mediatype']),(2020,'tt12345','tvshow'))
        self.assertEqual(info['genre'],['Drama']);entry.setPath.assert_not_called()
    def test_optional_rating_owner_matches_the_native_label_year_and_type(self):
        import importlib
        window=importlib.import_module('modules.catalog_window')
        item={'title':'Clean title','label':'[B]Provider label[/B]','type':'unknown','year':2021}
        self.assertEqual(window.rating_owner(item,'TV Shows'),('Clean title','2021','tvshow'))
    def test_approved_media_center_header_bytes_and_home_geometry(self):
        import hashlib
        skin=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus'
        self.assertEqual(hashlib.sha256((skin/'media/foundry-logo-traced.png').read_bytes()).hexdigest(),'e60c91fa4083614177c6600be56a47257c1bf2be384f060df14d6c2cdded1f99')
        home=E.parse(skin/'xml/Home.xml')
        control=next(c for c in home.iter('control') if c.findtext('texture')=='foundry-logo-traced.png')
        self.assertEqual([control.findtext(t) for t in ('left','top','width','height')],['60','40','380','115'])
    def test_library_port_preserves_the_complete_search_screen(self):
        root=Path(__file__).resolve().parents[1]
        with zipfile.ZipFile(root/'skin.foundry/skin.foundry-1.3.0.zip') as z:
            before=E.fromstring(z.read('skin.foundry/xml/script-foundry-vod.xml'))
        after=E.parse(root.parent/'skin.foundry-nimbus/xml/script-foundry-vod.xml').getroot()
        def normalized(n):return n.tag,n.attrib,(n.text or '').strip(),[normalized(c) for c in n]
        self.assertEqual(normalized(before.find('controls')[1]),normalized(after.find('controls')[1]))

if __name__=='__main__':unittest.main()
