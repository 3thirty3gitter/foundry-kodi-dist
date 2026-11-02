"""Approved rich pairs and the background-only OSD change are release invariants."""
from pathlib import Path
import copy,hashlib,json,sys,tempfile,unittest,xml.etree.ElementTree as E,zipfile
from PIL import Image
import test_release

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'
RESOURCE=ROOT/'src/resource.images.foundry.wallpapers'
sys.path.insert(0,str(ROOT/'tools'))
from validate_widget_assets import validate_rich_pairs,CATEGORIES

class RichRelease(unittest.TestCase):
    def test_all_28_corrected_assets_validate_exactly(self):
        pairs=validate_rich_pairs(SKIN,RESOURCE)
        for mode,folder,version in [('full',RESOURCE/'resources',0),('widget',SKIN/'media/foundry-widget-wallpapers',1)]:
            self.assertEqual(set(pairs[mode]),CATEGORIES)
            for category,entry in pairs[mode].items():
                self.assertEqual(entry['version'],version)
                with Image.open(folder/(category+'.png')) as im:
                    self.assertEqual(im.size,(1672,941))
                    self.assertEqual(im.convert('RGBA').getchannel('A').getextrema(),(255,255))
    def test_home_is_approved_media_center_asset(self):
        expected='c509a40773797459698ad2659d539379d777d01c88c14caeb017deb061679602'
        for path in [RESOURCE/'resources/home.png',SKIN/'media/foundry-home-backdrop.png',SKIN/'resources/foundry-fanart.png']:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected)
    def test_legacy_original_zip_bytes_are_unchanged(self):
        p=ROOT/'resource.images.foundry.wallpapers/resource.images.foundry.wallpapers-1.0.0.zip'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),'af0f3ca0d1c2e50387d1ad5c0bc5988a2e6a17edbe038360ff3a2e601c56ef8e')
    def test_home_header_widgets_and_fonts_remain_exactly_as_1_2_10(self):
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.1.9.zip') as z:
            for path in ['xml/Home.xml','xml/Includes_Home.xml','xml/Includes_Animations.xml','xml/Variables_Artwork.xml','xml/Font.xml']:
                data=(SKIN/path).read_bytes()
                if path=='xml/Home.xml':data=data.replace(b'<movement>6</movement>',b'<movement>7</movement>',1)
                self.assertEqual(data,z.read('skin.foundry/'+path),path)
    def test_osd_only_background_changes_and_fade_remains(self):
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.1.9.zip') as z:
            before=E.fromstring(z.read('skin.foundry/xml/Includes_StreamPilotOSD.xml'))
        after=E.parse(SKIN/'xml/Includes_StreamPilotOSD.xml')
        def norm(n):return n.tag,n.attrib,(n.text or '').strip(),[norm(c) for c in n]
        for name,height in [('StreamPilotVODCard',274),('StreamPilotLiveCard',320)]:
            old=before.find("include[@name='%s']/control"%name)
            new=after.find("include[@name='%s']/control"%name)
            self.assertEqual([norm(n) for n in old.findall('control')[1:]],[norm(n) for n in new.findall('control')[1:]])
            bg=new.find('control');self.assertEqual(bg.findtext('top'),'-36');self.assertEqual(int(bg.findtext('height')),height)
            self.assertEqual(bg.findtext('texture'),'streampilot/osd-feather.png')
            fade=bg.find('animation');self.assertEqual((fade.get('start'),fade.get('end')),('75','75'))
            for k in ('left','right','bottom','height'):self.assertEqual(old.findtext(k),new.findtext(k))
    def test_installer_dependency_requires_new_full_frame_resource(self):
        skin=E.parse(SKIN/'addon.xml');self.assertEqual(skin.find("requires/import[@addon='resource.images.foundry.wallpapers']").get('version'),'1.1.0')
        self.assertEqual(E.parse(RESOURCE/'addon.xml').getroot().get('version'),'1.1.0')
    def test_packager_rejects_stale_widget_revision_before_reading_image_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake=Path(tmp);folder=fake/'skin/media/foundry-widget-wallpapers';folder.mkdir(parents=True)
            doc=json.loads((SKIN/'media/foundry-widget-wallpapers/SOURCE.json').read_text())
            doc['files']['movies']['version']=0
            (folder/'SOURCE.json').write_text(json.dumps(doc))
            # Full assets validate first. Fake widget metadata must fail before any widget read.
            with self.assertRaisesRegex(ValueError,'stale widget'):
                # Put stale entry first so this test cannot fail on a missing sibling.
                doc['files']={'movies':doc['files']['movies'],**{k:v for k,v in doc['files'].items() if k!='movies'}}
                (folder/'SOURCE.json').write_text(json.dumps(doc))
                validate_rich_pairs(fake/'skin',RESOURCE)
