"""Approved rich pairs and the background-only OSD change are release invariants."""
from pathlib import Path
import copy,hashlib,json,re,sys,tempfile,unittest,xml.etree.ElementTree as E,zipfile
from PIL import Image
import test_release
from home_contracts import without_home_favorites

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'
RESOURCE=ROOT/'src/resource.images.foundry.wallpapers'
sys.path.insert(0,str(ROOT/'tools'))
from validate_widget_assets import validate_rich_pairs,CATEGORIES,ACTIVE_SOURCE,BACKGROUND_SHA256

class RichRelease(unittest.TestCase):
    def test_all_28_corrected_assets_validate_exactly(self):
        pairs=validate_rich_pairs(SKIN,RESOURCE)
        for mode,folder,version in [('full',RESOURCE/'resources',0),('widget',SKIN/'media/foundry-widget-wallpapers',1)]:
            self.assertEqual(set(pairs[mode]),CATEGORIES)
            for category,entry in pairs[mode].items():
                self.assertEqual(entry['dimensions'],[1672,941])
                with Image.open(folder/(category+'.png')) as im:
                    self.assertEqual(im.size,(1672,941))
                    self.assertEqual(im.convert('RGBA').getchannel('A').getextrema(),(255,255))
    def test_home_retains_approved_home_frame(self):
        expected='6216450ac8bd07b0144c28301b09b086a600e837e4b4d0e6c4723f97bbb16510'
        for path in [RESOURCE/'resources/home.png']:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected)
    def test_legacy_original_zip_bytes_are_unchanged(self):
        p=ROOT/'resource.images.foundry.wallpapers/resource.images.foundry.wallpapers-1.0.0.zip'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),'af0f3ca0d1c2e50387d1ad5c0bc5988a2e6a17edbe038360ff3a2e601c56ef8e')
    def test_home_header_widgets_and_fonts_remain_exactly_as_1_2_10(self):
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.1.9.zip') as z:
            for path in ['xml/Home.xml','xml/Includes_Home.xml','xml/Includes_Animations.xml','xml/Variables_Artwork.xml','xml/Font.xml']:
                data=(SKIN/path).read_bytes().replace(b'\r\n',b'\n')
                if path=='xml/Home.xml':data=data.replace(b'\t  <include>FoundryWidgetMetadata</include>\n',b'')
                if path=='xml/Includes_Home.xml':
                    data=data.replace(b'$PARAM[visible] + !Window.IsActive(Home)',b'$PARAM[visible]')
                    data=data.replace(b' | Integer.IsEqual($PARAM[list_id],14100)',b'')
                if path=='xml/Home.xml':
                    data=data.replace(b'<movement>6</movement>',b'<movement>7</movement>',1).replace(b'foundry-widget-base.png',b'foundry-widget-base.svg')
                if path=='xml/Font.xml':
                    data=re.sub(rb'^[ \t]*<font><name>(?:sp_library_[^<]+|foundry_weather_(?:small|body|temperature|title))</name>[^\n]*</font>\n',b'',data,flags=re.M)
                if path=='xml/Variables_Artwork.xml':
                    data=data.replace(b'foundry-navigation/shutdown.png',b'foundry-shutdown-wallpaper.svg').replace(b'foundry-navigation/search.png',b'foundry-search-wallpaper.svg').replace(b'foundry-widget-base.png',b'foundry-widget-base.svg')
                    data=re.sub(rb'    <value condition="Control.HasFocus\(802\) \+ \$EXP\[FoundryHomeWidgetsPresent\]">[^\n]*</value>\n',b'',data)
                    # Shared metadata values are allowed; every original artwork
                    # fallback, menu binding and control remains byte-identical.
                    data=re.sub(rb'\n    <value condition="\$EXP\[FoundryMetadataCurrentItem\][^\n]*</value>',b'',data)
                old=z.read('skin.foundry/'+path)
                if path=='xml/Home.xml':data,old=without_home_favorites(data),without_home_favorites(old)
                self.assertEqual(data,old,path)
    def test_osd_uses_the_stream_pilot_rounded_frame(self):
        after=E.parse(SKIN/'xml/Includes_StreamPilotOSD.xml')
        for name,kind,height,layers in [('StreamPilotVODCard','vod',202,2),('StreamPilotLiveCard','live',248,3)]:
            card=after.find("include[@name='%s']/control"%name)
            controls=card.findall('control')
            self.assertEqual(card.findtext('height'),str(height))
            self.assertEqual(controls[0].findtext('texture'),'streampilot/'+kind+'-shadow.png')
            self.assertEqual(controls[1].findtext('texture'),'streampilot/'+kind+'-panel.png')
            self.assertEqual(controls[1].findtext('height'),str(height))
            self.assertEqual(controls[1].findtext('left'),'0')
            self.assertEqual(controls[1].findtext('top'),'0')
            if layers==3:self.assertEqual(controls[2].findtext('texture'),'streampilot/live-edge.png')
            self.assertIsNotNone(card.find("animation[@effect='fade']"))
    def test_installer_dependency_requires_new_full_frame_resource(self):
        skin=E.parse(SKIN/'addon.xml');self.assertEqual(skin.find("requires/import[@addon='resource.images.foundry.wallpapers']").get('version'),'1.1.1')
        self.assertEqual(E.parse(RESOURCE/'addon.xml').getroot().get('version'),'1.1.1')
    def test_packager_rejects_stale_widget_approval_before_reading_image_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake=Path(tmp);folder=fake/'skin/media/foundry-widget-wallpapers';folder.mkdir(parents=True)
            doc=json.loads((SKIN/'media/foundry-widget-wallpapers'/ACTIVE_SOURCE).read_text())
            doc['schema_version']=2
            (folder/ACTIVE_SOURCE).write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,'complete fixed-background artwork approval'):
                validate_rich_pairs(fake/'skin',RESOURCE)

