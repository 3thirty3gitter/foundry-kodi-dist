"""Studio paths across catalog, native/library widgets and playback; no provider keys."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_release as kodi
from modules import studio_art
from modules.monitors.metadata import snapshot, values
from modules.metadata import omdb_metadata


class StudioArtwork(unittest.TestCase):
    def setUp(self):
        studio_art._index.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.resource = 'resource://resource.images.studios.white/'
        self.patchers = [
            patch.object(kodi.xbmc, 'getCondVisibility', side_effect=lambda query: query == 'System.HasAddon(resource.images.studios.white)'),
            patch.object(kodi.xbmcvfs, 'exists', side_effect=lambda path: (self.root / path.removeprefix(self.resource)).is_file()),
            patch.object(kodi.xbmcvfs, 'listdir', create=True, side_effect=lambda path: ([], [p.name for p in self.root.iterdir()])),
        ]
        for patcher in self.patchers:
            patcher.start(); self.addCleanup(patcher.stop)

    def asset(self, name):
        # Actual local PNGs, not guessed path responses.
        from PIL import Image
        Image.new('RGBA', (12, 8), (255, 255, 255, 255)).save(self.root / name)
        return self.resource + name

    def test_each_source_alias_precedes_pack(self):
        self.asset('Studio.png')
        for key in studio_art.ART_KEYS:
            self.assertEqual(studio_art.resolve({'art':{key:'https://example.test/logo.png'},'studio':'Studio'}), 'https://example.test/logo.png')

    def test_blank_and_na_art_do_not_hide_valid_alias(self):
        self.assertEqual(studio_art.resolve({'art':{'studiologo':'N/A','studio.logo':'0','tvshow.studiologo':'valid.png'}}), 'valid.png')

    def test_second_studio_used_when_first_missing(self):
        expected=self.asset('Second Studio.png')
        self.assertEqual(studio_art.resolve({'studio':['Missing', 'Second Studio']}), expected)

    def test_case_punctuation_accents_and_ampersand_match_existing_asset(self):
        expected=self.asset('Pathe Films and Television.png')
        self.assertEqual(studio_art.resolve({'studio':'PATHÉ Films & Television'}), expected)

    def test_multiple_studio_string_is_split(self):
        expected=self.asset('Second Studio.png')
        for name in ('Missing / Second Studio', 'Missing, Second Studio', 'Missing; Second Studio'):
            self.assertEqual(studio_art.resolve({'studio':name}), expected)

    def test_complete_company_name_precedes_comma_split(self):
        expected=self.asset('Studio, Inc.png');self.asset('Studio.png')
        self.assertEqual(studio_art.resolve({'studio':'Studio, Inc'}), expected)

    def test_missing_image_never_returns_invented_resource(self):
        self.assertEqual(studio_art.resolve({'studio':'Missing'}), '')

    def test_missing_pack_never_returns_resource(self):
        self.asset('Studio.png')
        with patch.object(kodi.xbmc,'getCondVisibility',return_value=False):
            self.assertEqual(studio_art.resolve({'studio':'Studio'}), '')

    def test_ambiguous_normalization_is_not_selected(self):
        self.asset('A-B.png');self.asset('A B.png')
        self.assertEqual(studio_art.resolve({'studio':'AB'}), '')
        self.assertEqual(studio_art.resolve({'studio':'A-B'}), self.resource+'A-B.png')

    def test_untrusted_studio_cannot_escape_resource(self):
        for name in ('../secret','C:\\secret','file://elsewhere','..'):
            self.assertEqual(studio_art.resolve({'studio':name}), '')

    def test_index_reuses_listing_and_refreshes(self):
        self.asset('STUDIO.png')
        with patch.object(kodi.xbmcvfs,'exists',return_value=False), patch.object(kodi.xbmcvfs,'listdir',create=True,return_value=([],['STUDIO.png'])) as listing, patch.object(studio_art.time,'monotonic',side_effect=[1,2,62]):
            for _ in range(3):self.assertTrue(studio_art.resolve({'studio':'studio'}))
            self.assertEqual(listing.call_count,2)

    def test_listing_failure_still_allows_exact_and_next_studio(self):
        expected=self.asset('Second.png')
        with patch.object(kodi.xbmcvfs,'listdir',create=True,side_effect=RuntimeError('unavailable')):
            self.assertEqual(studio_art.resolve({'studio':['Missing','Second']}),expected)

    def test_native_snapshot_preserves_parent_and_alternate_studio_art(self):
        for key in studio_art.ART_KEYS:
            labels={'ListItem.DBTYPE':'episode','ListItem.Label':'Episode','ListItem.Art('+key+')':'source.png'}
            owner,item=snapshot(info=lambda name:labels.get(name,''))
            self.assertEqual(item['art'][key],'source.png')
            self.assertEqual(values(item,{}, {})['studiologo'],'source.png')

    def test_native_and_playback_presentation_use_real_pack_fallback(self):
        expected=self.asset('Known.png')
        for kind in ('movie','tvshow','episode'):
            self.assertEqual(values({'type':kind,'studio':['Missing','Known']},{},{})['studiologo'],expected)

    def test_omdb_supplies_no_invented_logo(self):
        self.assertEqual(omdb_metadata({'studio':'Known','imdb_rating':'8/10'})['art'],{})

    def test_native_xml_uses_aliases_without_guessing_resource_filename(self):
        import xml.etree.ElementTree as E
        root=E.parse(kodi.SKIN/'xml/View_57_StreamPilot.xml')
        values=root.find("variable[@name='FoundryVODStudioLogo']").findall('value')
        textures=[value.text or '' for value in values]
        for key in ('studio.logo','tvshow.studiologo','tvshow.studio.logo'):
            self.assertIn('$INFO[ListItem.Art('+key+')]',textures)
        self.assertFalse(any('resource://' in value or 'ListItem.Studio' in value for value in textures))
        self.assertIn('$INFO[Window(Home).Property(foundry.metadata.studiologo)]',textures)

    def test_catalog_uses_same_resolver(self):
        from modules.catalog_window import CatalogWindow
        import inspect
        self.assertIn('studio_logo=resolve_studio(item)',inspect.getsource(CatalogWindow.update_hero))


if __name__ == '__main__':unittest.main()
