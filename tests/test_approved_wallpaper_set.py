"""Independently pinned full-set approval, clean background and actual XML routing."""
import hashlib
import json
import re
from pathlib import Path
import unittest
import xml.etree.ElementTree as E
from PIL import Image, ImageChops
from test_movie_submenu_wallpapers import ROOT, SKIN, SkinConditions

RESOURCE = ROOT / 'src/resource.images.foundry.wallpapers'
SOURCE = 'SOURCE-trending-fixed-20261111.json'
APPROVED = json.loads((ROOT/'tests/fixtures/approved-wallpapers-trending-fixed-20261111.json').read_text())
HOME = {Path(name).stem for name in APPROVED if name.startswith('home/')}
BASE = APPROVED['background/trending-fixed.png']['sha256']
HISTORICAL = {
    SKIN/'media/foundry-movie-submenus/SOURCE.json': 'c184b8132ab188557f31f87c169b05ad0eac6dffaf2e595ddb61d7a7be40b81b',
    SKIN/'media/foundry-widget-wallpapers/SOURCE.json': '0dc1b067f054fc335f529822b48280b35fcb6fef5fa1aba68219590037121160',
    RESOURCE/'SOURCE.json': '43a07f9c942ab1db2bc1f067403572144561be0b8c5f950b66e66f7710bccbc9',
}


def target(name):
    section, filename = name.split('/')
    if section == 'home': return RESOURCE/'resources'/filename
    if section == 'widget': return SKIN/'media/foundry-widget-wallpapers'/filename
    if section == 'categories': return SKIN/'media/foundry-movie-submenus'/filename
    if section == 'navigation': return SKIN/'media/foundry-navigation'/('movies-back.png' if filename == 'back.png' else filename)
    return SKIN/'media/foundry-home-backdrop.png'


class HomeConditions(SkinConditions):
    def __init__(self, category='home', widgets=False, focus=None, extra=None):
        super().__init__({'Container(9000).ListItem.Property(id)': category, **(extra or {})})
        self.variables.update({n.get('name'): n for n in E.parse(SKIN/'xml/Variables_Artwork.xml').findall('variable')})
        self.expressions.update({'FoundryHomeHasWidgets': 'test.widgets', 'FoundryHomeWidgetsPresent': 'test.widgets'})
        self.flags.update({'test.widgets': widgets, 'Control.HasFocus(%s)' % focus: True})
    def value(self, token):
        if token.strip().startswith('Container('): return self.labels.get(token.strip(),'')
        return super().value(token)
    def condition(self, text):
        if text.strip() == 'test.widgets' or re.fullmatch(r'Control\.HasFocus\([^()]*\)', text.strip()):
            return self.flags.get(text.strip(), False)
        return super().condition(text)


class ApprovedWallpaperSet(unittest.TestCase):
    def test_exact_45_approved_frames_and_opaque_dimensions(self):
        self.assertEqual(len(APPROVED),45)
        for name, expected in APPROVED.items():
            with self.subTest(name=name):
                path=target(name)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected['sha256'])
                with Image.open(path) as im:
                    self.assertEqual(im.format,'PNG')
                    self.assertEqual(im.size,(1672,941))
                    self.assertEqual(im.convert('RGBA').getchannel('A').getextrema(),(255,255))

    def test_identical_clean_background_outside_approved_foreground(self):
        with Image.open(target('background/trending-fixed.png')) as im:
            base=im.convert('RGB')
        for name, expected in APPROVED.items():
            with self.subTest(name=name), Image.open(target(name)) as im:
                difference=ImageChops.difference(im.convert('RGB'),base)
                bbox=difference.getbbox()
                self.assertEqual(list(bbox) if bbox else None,expected['foreground_bbox'])
                if bbox:
                    difference.paste((0,0,0),tuple(expected['foreground_bbox']))
                self.assertIsNone(difference.getbbox())

    def test_widget_foreground_is_55_percent_and_background_not_scaled(self):
        for category in HOME:
            full=APPROVED['home/'+category+'.png']['foreground_bbox']
            small=APPROVED['widget/'+category+'.png']['foreground_bbox']
            for axis in (0,1):
                self.assertAlmostEqual((small[axis+2]-small[axis])/(full[axis+2]-full[axis]),.55,delta=.015)
            self.assertLess(small[3],full[3])
            self.assertNotEqual(APPROVED['home/'+category+'.png']['sha256'],APPROVED['widget/'+category+'.png']['sha256'])

    def test_active_manifests_match_independent_approval_and_have_complete_membership(self):
        groups=[(RESOURCE,'full','home'),(SKIN/'media/foundry-widget-wallpapers','widget','widget'),
                (SKIN/'media/foundry-movie-submenus','category','categories'),
                (SKIN/'media/foundry-navigation','navigation','navigation')]
        for folder,mode,section in groups:
            doc=json.loads((folder/SOURCE).read_text())
            self.assertEqual(doc['schema_version'],3)
            self.assertEqual(doc['mode'],mode)
            self.assertEqual(doc['dimensions'],[1672,941])
            self.assertEqual(doc['widget_group_scale'],.55)
            self.assertEqual(doc['background_sha256'],BASE)
            self.assertTrue(doc['review_library_file_id'])
            self.assertEqual(doc['approval']['quote'],'Great job nova, update all in the app')
            names={Path(name).stem for name in APPROVED if name.startswith(section+'/')}
            self.assertEqual(len(doc['files']),len(names))
            seen=set()
            for entry in doc['files']:
                filename=Path(entry['filename']).name
                name='back.png' if filename=='movies-back.png' else filename
                seen.add(Path(name).stem)
                approved=APPROVED[section+'/'+name]
                self.assertEqual(entry['sha256'],approved['sha256'])
                self.assertEqual(entry['dimensions'],[1672,941])
                self.assertEqual((folder/entry['filename']).resolve(),target(section+'/'+name).resolve())
                self.assertEqual(entry['bytes'],(folder/entry['filename']).stat().st_size)
            self.assertEqual(seen,names)

    def test_packager_rejects_changed_bytes_incomplete_and_scaled_sets(self):
        import tempfile
        import shutil
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from validate_widget_assets import validate_widget_assets
        with tempfile.TemporaryDirectory() as directory:
            skin=Path(directory)
            folder=skin/'media/foundry-widget-wallpapers'
            shutil.copytree(SKIN/'media/foundry-widget-wallpapers',folder)
            original=json.loads((folder/SOURCE).read_text())
            for field,value in [('widget_group_scale',.5),('files',original['files'][:-1]),('schema_version',2)]:
                doc={**original,field:value}
                (folder/SOURCE).write_text(json.dumps(doc))
                with self.assertRaises(ValueError): validate_widget_assets(skin)
            (folder/SOURCE).write_text(json.dumps(original))
            path=folder/'movies.png'
            data=path.read_bytes()
            path.write_bytes(data[:-1]+bytes([data[-1]^1]))
            with self.assertRaisesRegex(ValueError,'bytes differ'): validate_widget_assets(skin)

    def test_previous_source_approval_documents_preserved_byte_for_byte(self):
        for path,digest in HISTORICAL.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest,str(path))

    def test_all_home_standard_and_widget_routes_and_settings_hover(self):
        for category in HOME:
            for widgets in (False,True):
                prefix='special://skin/media/foundry-widget-wallpapers/' if widgets else 'resource://resource.images.foundry.wallpapers/'
                self.assertEqual(HomeConditions(category,widgets).variable('FoundryHomeWallpaper'),prefix+category+'.png')
        for widgets in (False,True):
            expected=('special://skin/media/foundry-widget-wallpapers/' if widgets else 'resource://resource.images.foundry.wallpapers/')+'settings.png'
            self.assertEqual(HomeConditions('movies',widgets,802).variable('FoundryHomeWallpaper'),expected)
            for focus,name in [(801,'shutdown'),(803,'search')]:
                self.assertEqual(HomeConditions('movies',widgets,focus).variable('FoundryHomeWallpaper'),'special://skin/media/foundry-navigation/'+name+'.png')

    def test_custom_home_backgrounds_keep_priority_over_widget_art(self):
        for widgets in (False,True):
            self.assertEqual(HomeConditions('movies',widgets,extra={'Skin.String(NimbusCustomBackground)':'custom.png'}).variable('FoundryHomeWallpaper'),'custom.png')
            self.assertEqual(HomeConditions('movies',widgets,extra={'Skin.String(HomeFanart.path)':'custom/','Skin.String(HomeFanart.ext)':'.jpg'}).variable('FoundryHomeWallpaper'),'custom/movies.jpg')

    def test_app_branding_is_pinned_separate_from_home_and_clean_fallbacks(self):
        digest='a30da8f51f0828f2b11f398eab546ae2f880550b624244aff4810cf98a3971a9'
        for path in ['resources/foundry-fanart.png','media/foundry-backdrops/foundry-loading-splash.png']:
            self.assertEqual(hashlib.sha256((SKIN/path).read_bytes()).hexdigest(),digest)
            with Image.open(SKIN/path) as im:
                self.assertEqual(im.size,(1672,941))
                self.assertEqual(im.convert('RGBA').getchannel('A').getextrema(),(255,255))
        with Image.open(SKIN/'resources/foundry-fanart.png') as app, Image.open(target('background/trending-fixed.png')) as clean:
            self.assertEqual(ImageChops.difference(app.convert('RGB'),clean.convert('RGB')).getbbox(),(979,303,1633,647))
        self.assertNotEqual(digest,BASE)
        self.assertNotEqual(digest,APPROVED['home/home.png']['sha256'])
        addon=E.parse(SKIN/'addon.xml')
        self.assertEqual(addon.findtext("extension[@point='xbmc.addon.metadata']/assets/fanart"),'resources/foundry-fanart.png')
        base=json.loads((SKIN/'media/foundry-backdrops'/SOURCE).read_text())
        app_files={'foundry-loading-splash.png','../../resources/foundry-fanart.png'}
        clean_files={'../foundry-home-backdrop.png','../foundry-widget-base.png','../streampilot/catalog-base.png'}
        self.assertEqual({row['filename'] for row in base['files']},app_files|clean_files)
        for row in base['files']:
            self.assertEqual(row['sha256'],digest if row['filename'] in app_files else BASE)
            if row['filename'] in app_files: self.assertEqual(row['role'],'app-branding')

    def test_cleanplate_fallbacks_and_no_old_svg_routes(self):
        for path in ['media/foundry-home-backdrop.png','media/foundry-widget-base.png','media/streampilot/catalog-base.png']:
            self.assertEqual(hashlib.sha256((SKIN/path).read_bytes()).hexdigest(),BASE)
        doc=json.loads((SKIN/'media/foundry-backdrops'/SOURCE).read_text())
        self.assertEqual(doc['mode'],'base')
        for entry in doc['files']:
            path=SKIN/'media/foundry-backdrops'/entry['filename']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),entry['sha256'])
            self.assertEqual(path.stat().st_size,entry['bytes'])
        for path in (SKIN/'xml').glob('*.xml'):
            text=path.read_text(encoding='utf-8')
            for old in ['foundry-widget-base.svg','foundry-search-wallpaper.svg','foundry-shutdown-wallpaper.svg']:
                self.assertNotIn(old,text,str(path))


if __name__=='__main__': unittest.main()
