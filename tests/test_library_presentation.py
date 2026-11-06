"""Source-sized library artwork, measured spacing and asynchronous identity."""
from concurrent.futures import Future
import hashlib
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as E
from PIL import Image, ImageDraw
import test_release as kodi
from modules.catalog_presentation import studio_logo, footer_geometry, release_geometry
from modules.catalog_window import CatalogWindow


class Presentation(unittest.TestCase):
    def fixture(self, color):
        path=kodi.PROFILE/('studio-%s.png'%(color,))
        image=Image.new('RGBA',(100,80));ImageDraw.Draw(image).rectangle((20,10,69,49),fill=color)
        image.save(path)
        return path

    def test_monochrome_studio_is_cropped_tinted_and_source_is_unchanged(self):
        path=self.fixture('black');before=hashlib.sha256(path.read_bytes()).hexdigest()
        with patch('modules.catalog_presentation.cached_paths',return_value=[path]):prepared=studio_logo('fixture://black')
        with Image.open(prepared) as result:
            self.assertEqual(result.size,(50,40));self.assertEqual(result.getpixel((0,0)),(255,255,255,255))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_colored_studio_preserves_its_original_rgb(self):
        path=self.fixture('red')
        with patch('modules.catalog_presentation.cached_paths',return_value=[path]):prepared=studio_logo('fixture://red')
        with Image.open(prepared) as result:self.assertEqual(result.getpixel((0,0)),(255,0,0,255))

    def test_not_cached_and_fully_transparent_studios_have_no_invented_logo(self):
        with patch('modules.catalog_presentation.cached_paths',return_value=[]):self.assertIsNone(studio_logo('fixture://absent'))
        path=self.fixture((0,0,0,0))
        with patch('modules.catalog_presentation.cached_paths',return_value=[path]):self.assertIsNone(studio_logo('fixture://empty'))

    def test_page_and_sort_spacing_is_measured_for_large_page_counts(self):
        small=footer_geometry('Page 1 / 1','Sort By')
        large=footer_geometry('Page 99999 / 99999','Sort By · Alphabetical · Z-A')
        self.assertGreater(large[0],small[0]);self.assertGreater(large[2],small[2])
        for width,x,button in (small,large):
            self.assertEqual(x-(112+width),28)
            self.assertGreaterEqual(button,116)

    def test_certification_follows_date_and_starts_at_left_when_date_missing(self):
        self.assertEqual(release_geometry('','14A')[0],92)
        self.assertGreater(release_geometry('Released Sep 30, 2026','14A')[0],92)
        self.assertGreater(release_geometry('','PG-13')[1],release_geometry('','R')[1])

    def test_late_studio_result_cannot_replace_the_current_title(self):
        w=object.__new__(CatalogWindow);future=Future();future.set_result('old-prepared.png')
        w.studio_job=('old-url',future);w.studio_cache={};w.studio_attempts=10;w.studio_retry=0
        w.getProperty=lambda key:'new-url';w.p=Mock();w.tick_studio(10)
        w.p.assert_not_called();self.assertEqual(w.studio_cache['old-url'],'old-prepared.png')

    def test_closing_catalog_cancels_three_field_enrichment_jobs(self):
        w=object.__new__(CatalogWindow);future=Mock()
        w.request=1;w.enrichment_executor=Mock();w.executor=Mock();w.close=Mock()
        w.enrichment_jobs={'key':({},future,'configuration-stamp')};w.color_job=None;w.studio_job=None
        w.dispose();future.cancel.assert_called_once();w.close.assert_called_once()

    def test_source_dimensions_and_unique_runtime_control_ids(self):
        skin=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus'
        document=E.parse(skin/'xml/script-foundry-vod.xml')
        ids=[n.get('id') for n in document.iter('control') if n.get('id')]
        self.assertEqual(len(ids),len(set(ids)))
        poster=document.find(".//control[@id='50']/focusedlayout/control")
        self.assertEqual([poster.findtext(k) for k in ('width','height')],['224','336'])
        self.assertFalse(any(n.text=='streampilot/catalog-frame.png' for n in document.iter('texture')))
