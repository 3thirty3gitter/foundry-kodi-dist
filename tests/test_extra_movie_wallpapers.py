"""Requested Genres through In Progress artwork, exact context and immutable plate."""
import hashlib,json,unittest
import test_release as kodi
from PIL import Image,ImageChops
from test_movie_submenu_wallpapers import ROOT,SKIN,SkinConditions,native
from modules.movie_submenu import canonical_label,movie_context

LABELS={'Genres':'genres','Providers':'providers','Languages':'languages','Years':'years','Decades':'decades','Certifications':'certifications','Because You Watched...':'because-you-watched','Watched':'watched','Recently Watched':'recently-watched','In Progress':'in-progress'}
ART=SKIN/'media/foundry-movie-submenus'

class ExtraMovieWallpapers(unittest.TestCase):
    def test_exact_ten_source_bytes_dimensions_and_fixed_background(self):
        doc=json.loads((ART/'SOURCE-extra-categories-20261112.json').read_text())
        pinned=json.loads((ROOT/'tests/fixtures/extra-categories-20261112.json').read_text())
        self.assertEqual({row['label']:row['slug'] for row in doc['files']},LABELS)
        self.assertEqual(doc['files'],pinned['files'])
        base=Image.open(SKIN/'media/foundry-home-backdrop.png').convert('RGB')
        self.assertEqual(hashlib.sha256((SKIN/'media/foundry-home-backdrop.png').read_bytes()).hexdigest(),doc['background_sha256'])
        for row in doc['files']:
            p=ART/row['filename']
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),row['sha256'])
            self.assertEqual(p.stat().st_size,row['bytes'])
            with Image.open(p) as im:
                self.assertEqual(im.size,(1672,941))
                self.assertEqual(im.convert('RGBA').getchannel('A').getextrema(),(255,255))
                diff=ImageChops.difference(base,im.convert('RGB'))
                self.assertEqual(list(diff.getbbox()),row['foreground_bbox'])
                self.assertGreaterEqual(row['foreground_bbox'][0],1000)
                diff.paste((0,0,0),tuple(row['foreground_bbox']))
                self.assertIsNone(diff.getbbox())

    def test_every_label_matches_native_focus_directory_and_verified_catalog(self):
        for label,slug in LABELS.items():
            expected='special://skin/media/foundry-movie-submenus/'+slug+'.png'
            with self.subTest(label=label):
                self.assertEqual(native(label).variable('FoundryMovieSubmenuWallpaper'),expected)
                self.assertEqual(native('A film',label,'movies',is_folder=False).variable('FoundryMovieSubmenuWallpaper'),expected)
                ctx=SkinConditions({'Window.Property(catalog.section)':'Movies','Window.Property(foundry.movie_submenu_label)':label})
                self.assertEqual(ctx.variable('FoundryMovieSubmenuWallpaper'),expected)
                self.assertEqual(canonical_label('VOD / Movies / '+label),label)
                self.assertEqual(movie_context('Movies',[{'type':'movie'}],'movies',label),label)

    def test_custom_fanart_tv_mixed_and_similar_labels_stay_excluded(self):
        for label in LABELS:
            self.assertEqual(native(label,category='tvshows').variable('FoundryMovieSubmenuWallpaper'),'')
            self.assertEqual(native(label,content='episodes').variable('FoundryMovieSubmenuWallpaper'),'')
            self.assertEqual(native(label+' Extra').variable('FoundryMovieSubmenuWallpaper'),'')
            self.assertEqual(canonical_label(label+' Extra'),'')
            self.assertEqual(movie_context('Movies',[{'type':'episode'}],'movies',label),'')
            self.assertEqual(movie_context('TV Shows',[{'type':'movie'}],'movies',label),'')
            self.assertFalse(native(label,extra={'Skin.String(NimbusCustomBackground)':'custom.jpg'}).condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))
            self.assertFalse(native('Film',label,'movies',is_folder=False,extra={'ListItem.Art(fanart)':'film.jpg'}).condition('$EXP[FoundryMovieSubmenuBackdropVisible]'))

    def test_child_back_retains_each_parent_and_root_back_unchanged(self):
        for label,slug in LABELS.items():
            ctx=native('..',folder=label);ctx.flags['ListItem.IsParentFolder']=True
            self.assertTrue(ctx.variable('FoundryMovieSubmenuWallpaper').endswith('/'+slug+'.png'))
        ctx=native('..');ctx.flags['ListItem.IsParentFolder']=True
        self.assertTrue(ctx.variable('FoundryMovieSubmenuWallpaper').endswith('/movies-back.png'))

    def test_packaging_requires_all_ten_exact_images(self):
        import sys,tempfile,shutil
        from unittest.mock import patch
        sys.path.insert(0,str(ROOT/'tools'))
        from validate_extra_movie_wallpapers import validate_extra_movie_wallpapers
        self.assertEqual(len(validate_extra_movie_wallpapers(SKIN)),10)
        with tempfile.TemporaryDirectory() as temp:
            from pathlib import Path
            root=Path(temp);folder=root/'media/foundry-movie-submenus'
            shutil.copytree(ART,folder)
            path=folder/'genres.png';path.write_bytes(path.read_bytes()+b'changed')
            with self.assertRaises(ValueError):validate_extra_movie_wallpapers(root)
            path.unlink()
            with self.assertRaises(OSError):validate_extra_movie_wallpapers(root)
