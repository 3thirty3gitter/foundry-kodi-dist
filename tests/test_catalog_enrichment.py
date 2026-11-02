"""Provider identity, cache readiness and actual source-defined catalog styling."""
import unittest,json,zipfile,xml.etree.ElementTree as E
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import test_release as kodi
from modules.catalog_enrichment import enrich,lookup,matching,merge
from modules.catalog_color import color

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
        with patch('modules.catalog_enrichment.rpc',side_effect=RuntimeError),patch.object(kodi.xbmc,'getCondVisibility',return_value=True):self.assertEqual(enrich(item),item)
    def test_color_uses_actual_kodi_cache_mapping_and_white_fallback(self):
        p=kodi.PROFILE/'Thumbnails/a/cached.jpg';p.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(40,40),(130,130,130)).save(p)
        with patch('modules.catalog_color.rpc',return_value={'textures':[{'cachedurl':'a/cached.jpg'}]}):
            self.assertEqual(color('https://image.example/art.jpg'),'FFFFFFFF')
        with patch('modules.catalog_color.rpc',return_value={'textures':[]}):self.assertIsNone(color('https://image.example/not-cached.jpg'))
    def test_catalog_layout_changes_are_only_outline_removal_and_context_correct_color(self):
        root=Path(__file__).resolve().parents[1]
        with zipfile.ZipFile(root/'skin.foundry/skin.foundry-1.2.1.zip') as z:before=E.fromstring(z.read('skin.foundry/xml/script-foundry-vod.xml'))
        for parent in before.iter():
            for child in list(parent):
                if child.tag=='control' and child.findtext('texture')=='streampilot/catalog-frame.png':parent.remove(child)
            texture=parent.find('texture')
            if texture is not None and texture.text=='streampilot/catalog-glow.png':
                texture.attrib.pop('colordiffuse');node=E.Element('colordiffuse');node.text='$INFO[Window(Home).Property(foundry.catalog.accent)]';parent.insert(list(parent).index(texture),node)
        after=E.parse(root.parent/'skin.foundry-nimbus/xml/script-foundry-vod.xml').getroot()
        def normalized(n):return n.tag,n.attrib,(n.text or '').strip(),[normalized(c) for c in n]
        self.assertEqual(normalized(before),normalized(after))

if __name__=='__main__':unittest.main()
