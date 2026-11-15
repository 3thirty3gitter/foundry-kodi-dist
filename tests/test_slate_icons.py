from pathlib import Path
import unittest,json,hashlib,xml.etree.ElementTree as E
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'src/resource.images.foundry.slate.icons'
class SlateIconPackTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.m=json.loads((PACK/'resources/manifest.json').read_text())
 def test_metadata(self):
  a=E.parse(PACK/'addon.xml').getroot();self.assertEqual(a.get('id'),'resource.images.foundry.slate.icons');self.assertIsNotNone(a.find("extension[@point='kodi.resource.images']"));self.assertIsNotNone(E.parse(ROOT/'src/skin.foundry.slate/addon.xml').getroot().find("requires/import[@addon='resource.images.foundry.slate.icons']"))
 def test_glyphs_render_transparent_and_nonempty(self):
  for n in self.m['glyphs']:
   with self.subTest(n=n):
    im=Image.open(PACK/'resources/icons'/f'{n}.png').convert('RGBA');self.assertEqual(im.size,(256,256));self.assertIsNotNone(im.getbbox());self.assertEqual(im.getpixel((0,0))[3],0)
    bbox=im.getbbox();self.assertTrue(bbox[0]>0 and bbox[1]>0 and bbox[2]<256 and bbox[3]<256)
 def test_all_aliases_exist(self):
  for alias in [*self.m['texture_aliases'],*self.m['system_rows']]:self.assertTrue((PACK/'resources/aliases'/alias).is_file(),alias)
 def test_default_fallback_parity(self):
  for alias in self.m['texture_aliases']:
   if '/' not in alias and alias.startswith(('Default','Overlay')):
    self.assertEqual((ROOT/'src/skin.foundry.slate/media'/alias).read_bytes(),(PACK/'resources/aliases'/alias).read_bytes(),alias)
 def test_original_has_no_resource_dependency(self):
  p=ROOT/'src/skin.foundry/addon.xml'
  if p.exists():self.assertNotIn('resource.images.foundry.slate.icons',p.read_text())
 def test_resource_xml_paths_resolve(self):
  prefix='resource://resource.images.foundry.slate.icons/'
  for f in (ROOT/'src/skin.foundry.slate/xml').glob('*.xml'):
   e=E.parse(f)
   for n in e.iter():
    for value in [n.text or '',*n.attrib.values()]:
     if value.startswith(prefix) and '$' not in value:
      self.assertTrue((PACK/'resources'/value[len(prefix):]).is_file(),f'{f.name}: {value}')
 def test_rows_dimensions(self):
  import re
  for alias in self.m['system_rows']:
   mt=re.search(r'(?:-(\d+))?-(?:normal|focus)\.png$',alias);h=int(mt.group(1) or 70)
   with Image.open(PACK/'resources/aliases'/alias) as im:self.assertEqual(im.size,(320,h))
if __name__=='__main__':unittest.main()
