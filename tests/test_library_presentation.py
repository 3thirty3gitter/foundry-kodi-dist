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
        poster=document.find(".//control[@id='50']/focusedlayout/control/control")
        self.assertEqual([poster.findtext(k) for k in ('width','height')],['224','336'])
        self.assertFalse(any(n.text=='streampilot/catalog-frame.png' for n in document.iter('texture')))


class HoverRegression(unittest.TestCase):
    def test_revisited_artwork_restores_its_cached_accent_during_focus_change(self):
        w=object.__new__(CatalogWindow);w.section='Movies';w.enrichment_cache={};w.color_cache={'known':('FF1256AB','tinted.png')}
        w.p=Mock();w.clock=lambda:10;w.update_hero=Mock();w.publish_color=Mock()
        w.set_hero({'title':'Revisited','art':{'fanart':'known'}})
        w.publish_color.assert_called_once_with('FF1256AB','tinted.png')

    def test_an_arrow_never_inherits_the_last_movie_glow(self):
        w=object.__new__(CatalogWindow);w.p=Mock();w.getFocusId=lambda:50
        w.rail=[{'kind':'next'}];w.getCurrentListPosition=lambda:0;w.getListItem=Mock()
        w.publish_color('FF1256AB','movie-glow.png');w.getListItem.assert_not_called()

    def test_glow_has_soft_visible_pixels_outside_all_four_poster_edges(self):
        skin=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus'
        with Image.open(skin/'media/streampilot/catalog-glow.png') as im:
            self.assertEqual(im.size,(416,528));a=im.getchannel('A')
            # A 224x336 poster occupies [96,96,320,432]. Glow must survive
            # outside it, rather than hide inside three rescaled rectangles.
            for point in ((70,264),(346,264),(208,70),(208,458)):
                self.assertGreater(a.getpixel(point),10)
            for point in ((0,0),(415,0),(0,527),(415,527)):
                self.assertLessEqual(a.getpixel(point),1)

    def test_page_arrows_have_separate_focus_border_and_mirrored_shapes(self):
        from PIL import ImageChops,ImageOps
        skin=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus'
        with Image.open(skin/'media/streampilot/catalog-next.png') as n, Image.open(skin/'media/streampilot/catalog-previous.png') as p, Image.open(skin/'media/streampilot/catalog-next-focus.png') as f:
            self.assertEqual(n.size,(208,152))
            self.assertIsNone(ImageChops.difference(n,ImageOps.mirror(p)).getbbox())
            self.assertNotEqual(n.tobytes(),f.tobytes())
            # Source border is inside the complete arrow, including the shaft
            # edge that touches the raster canvas. Filtering must pad with zero.
            self.assertGreater(n.getpixel((1,76))[0],100)
            self.assertGreater(f.getpixel((1,76))[0],180)
            self.assertGreater(p.getpixel((206,76))[0],100)

    def test_source_tv_pivot_and_row_ends_are_explicit_in_both_views(self):
        skin=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus'
        for name,cid in [('script-foundry-vod.xml',50),('View_57_StreamPilot.xml',57)]:
            doc=E.parse(skin/'xml'/name);rail=doc.find(".//control[@id='%d']"%cid)
            self.assertEqual(rail.get('type'),'fixedlist');self.assertEqual(rail.findtext('focusposition'),'2')
            self.assertEqual(rail.findtext('movement'),'4')
            self.assertIn('-4.32,0',E.tostring(doc.getroot(),encoding='unicode'))
