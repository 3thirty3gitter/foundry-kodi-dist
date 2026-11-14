"""Source-level Slate wallpaper checks (not a native Kodi runtime claim)."""
import hashlib,json,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image,ImageChops
ROOT=Path(__file__).resolve().parents[1]; SKIN=ROOT/'src/skin.foundry.slate'; MEDIA=SKIN/'media'
class SlateWallpapers(unittest.TestCase):
 def test_complete_assets_and_safe_area(self):
  record=json.loads((MEDIA/'slate-wallpapers/manifest.json').read_text()); self.assertEqual(len(record['artwork']),59)
  base=Image.open(MEDIA/'slate-background.png').convert('RGB')
  for row in record['artwork']:
   p=MEDIA/row['path'];im=Image.open(p).convert('RGB');self.assertEqual(im.size,(1920,1080));self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),row['sha256'])
   self.assertIsNone(ImageChops.difference(im.crop((0,0,950,1080)),base.crop((0,0,950,1080))).getbbox(),row['path'])
 def test_home_routes_and_no_double_title(self):
  root=ET.parse(SKIN/'xml/Variables_Artwork.xml').getroot();v={x.attrib['name']:x for x in root.findall('variable')}
  self.assertEqual(len(v['FoundryDefaultMenuBackground']),17)
  self.assertEqual(len(v['FoundryWidgetWallpaper']),14)
  self.assertTrue(any('FoundryHomeHasWidgets' in x.attrib.get('condition','') for x in v['FoundryHomeWallpaper']))
  self.assertNotIn('<font>SlateCategory</font>',(SKIN/'xml/Home.xml').read_text())
  for n in ['FoundryDefaultMenuBackground','FoundryWidgetWallpaper','FoundryHomeWallpaper']:
   for x in v[n]:
    if x.text and x.text.startswith('special://skin/'):
     self.assertTrue((SKIN/x.text.removeprefix('special://skin/')).is_file(),x.text)
 def test_categories_and_back_retained(self):
  p=SKIN/'xml/Includes_FoundryMovieSubmenus.xml';text=p.read_text();root=ET.parse(p).getroot()
  self.assertIn('ListItem.IsParentFolder',text);self.assertNotIn('resource://resource.images.foundry.wallpapers/',text)
  files=set(x.text for x in root.find("variable[@name='FoundryMovieSubmenuWallpaper']") if x.text)
  self.assertEqual(len(files),24)
  for path in files:self.assertTrue((SKIN/path.removeprefix('special://skin/')).is_file())
 def test_standard_widget_and_utility_routes(self):
  from unittest.mock import patch
  import test_approved_wallpaper_set as home
  import test_movie_submenu_wallpapers as categories
  with patch.object(home,'SKIN',SKIN),patch.object(categories,'SKIN',SKIN):
   for key in ['home','movies','tvshows','music','musicvideos','livetv','radio','games','addons','pictures','video','favorites','weather','settings']:
    for widget in [False,True]:
     prefix='foundry-widget-wallpapers/' if widget else 'slate-wallpapers/'
     self.assertEqual(home.HomeConditions(key,widget).variable('FoundryHomeWallpaper'),'special://skin/media/'+prefix+key+'.png')
   for focus,key in [(801,'shutdown'),(802,'settings'),(803,'search')]:
    self.assertEqual(home.HomeConditions('movies',True,focus).variable('FoundryHomeWallpaper'),'special://skin/media/foundry-widget-wallpapers/'+key+'.png')
 def test_xml_parses(self):
  for p in SKIN.rglob('*.xml'): ET.parse(p)
if __name__=='__main__':unittest.main()
