"""Native parent selection keeps one page-themed background, not provider fanart."""
import unittest
import xml.etree.ElementTree as E
from test_movie_submenu_wallpapers import APPROVED, SKIN, native


def parent(folder='Movies', **kwargs):
    context = native('..', folder=folder, **kwargs)
    context.flags['ListItem.IsParentFolder'] = True
    return context


class MovieBackWallpaper(unittest.TestCase):
    def test_movies_root_parent_has_dedicated_back_plate(self):
        context = parent(extra={'ListItem.Art(fanart)': 'provider.jpg',
                                'Window(Home).Property(foundry.metadata.fanart)': 'stale-film.jpg'})
        self.assertEqual(context.variable('FoundryMovieSubmenuWallpaper'),
                         'special://skin/media/foundry-navigation/movies-back.png')
        self.assertTrue(context.condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))
        self.assertEqual(context.variable('FoundryNativeLoadingBackdrop'),
                         context.variable('FoundryMovieSubmenuWallpaper'))

    def test_back_plate_exists_as_opaque_page_aspect_png(self):
        from PIL import Image
        with Image.open(SKIN/'media/foundry-navigation/movies-back.png') as image:
            self.assertEqual(image.size, (1672, 941))
            self.assertEqual(image.convert('RGBA').getchannel('A').getextrema(), (255, 255))

    def test_parent_inside_every_submenu_retains_its_specific_plate(self):
        for label, (slug, _) in APPROVED.items():
            context = parent(label)
            self.assertTrue(context.variable('FoundryMovieSubmenuWallpaper').endswith('/'+slug+'.png'))
            self.assertTrue(context.condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))

    def test_repeated_category_parent_focus_does_not_reuse_last_category(self):
        context = parent()
        for label, (slug, _) in list(APPROVED.items()) * 2:
            context.flags['ListItem.IsParentFolder'] = False
            context.labels['ListItem.Label'] = label
            self.assertTrue(context.variable('FoundryMovieSubmenuWallpaper').endswith('/'+slug+'.png'))
            context.flags['ListItem.IsParentFolder'] = True
            context.labels['ListItem.Label'] = '..'
            self.assertTrue(context.variable('FoundryMovieSubmenuWallpaper').endswith('/movies-back.png'))

    def test_other_pages_and_regular_items_do_not_gain_movies_back_art(self):
        for context in [parent('TV Shows'), parent('Unknown'), parent(category='tvshows'),
                        parent(content='addons'), parent(window='home'), native('..')]:
            self.assertFalse(context.condition('$EXP[FoundryMovieSubmenuBack]'))

    def test_custom_backgrounds_and_playback_keep_priority(self):
        context = parent(extra={'Skin.String(NimbusCustomBackground)': 'custom.jpg'})
        self.assertEqual(context.variable('FoundryMovieSubmenuBase'), 'custom.jpg')
        self.assertFalse(context.condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))
        context = parent(extra={'Skin.String(HomeFanart.path)': '/custom/', 'Skin.String(HomeFanart.ext)': '.png'})
        self.assertEqual(context.variable('FoundryMovieSubmenuBase'), '/custom/movies.png')
        self.assertFalse(context.condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))
        for flag in ['Player.HasVideo', 'Player.HasAudio', 'Control.IsVisible(57)']:
            context = parent()
            context.flags[flag] = True
            self.assertFalse(context.condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))

    def test_list_provider_overlay_is_excluded_for_parent_plate(self):
        root = E.parse(SKIN/'xml/View_50_List.xml')
        overlays = [n for n in root.iter('control') if n.find('texture') is not None
                    and n.find('texture').get('diffuse') == 'overlays/fanart-diffuse.png']
        self.assertEqual(len(overlays), 1)
        self.assertTrue(overlays[0].findtext('visible').strip().startswith(
            '!$EXP[FoundryMovieSubmenuBackdropVisible] +'))
        self.assertFalse(parent().condition('!$EXP[FoundryMovieSubmenuBackdropVisible]'))


if __name__ == '__main__':
    unittest.main()
