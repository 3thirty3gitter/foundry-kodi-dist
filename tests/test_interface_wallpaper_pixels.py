"""Wallpaper QA must distinguish approved foregrounds sharing one background."""
import importlib.util
from pathlib import Path
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wallpaper_interface_renderer',ROOT/'tools/render_interface.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
FULL=ROOT/'src/resource.images.foundry.wallpapers/resources/settings.png'
WIDGET=ROOT.parent/'skin.foundry-nimbus/media/foundry-widget-wallpapers/settings.png'


def frame(path):
    with Image.open(path) as image:return image.convert('RGB').resize((1920,1080))


class InterfaceWallpaperPixels(unittest.TestCase):
    def test_both_approved_variants_match_their_foreground(self):
        for expected,other in ((FULL,WIDGET),(WIDGET,FULL)):
            with self.subTest(expected=expected.name,folder=expected.parent):
                evidence=renderer.wallpaper_evidence(frame(expected),expected,other)
                self.assertEqual(max(evidence['mean_absolute_errors']),0)
                self.assertGreater(max(evidence['other_variant_errors']),3)

    def test_wrong_variant_is_rejected_in_both_directions(self):
        for expected,other in ((FULL,WIDGET),(WIDGET,FULL)):
            with self.assertRaises(AssertionError):renderer.wallpaper_evidence(frame(other),expected,other)

    def test_matching_old_sample_pixels_cannot_hide_wrong_foreground(self):
        wrong=frame(FULL);expected=frame(WIDGET)
        for point in ((1400,230),(1550,400),(600,720)):
            wrong.putpixel(point,expected.getpixel(point))
        with self.assertRaises(AssertionError):renderer.wallpaper_evidence(wrong,WIDGET,FULL)

    def test_identical_reference_variants_cannot_pass(self):
        with self.assertRaises(AssertionError):renderer.wallpaper_evidence(frame(FULL),FULL,FULL)


if __name__=='__main__':unittest.main()
