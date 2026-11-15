import hashlib,json,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]/'candidates/resource.images.foundry.studios'
class StudioResourceTests(unittest.TestCase):
 def test_standalone_resource_manifest(self):
  x=ET.parse(ROOT/'addon.xml').getroot()
  self.assertEqual(x.get('id'),'resource.images.foundry.studios')
  self.assertEqual([e.get('addon') for e in x.findall('./requires/import')],['kodi.resource'])
  self.assertEqual(x.find("./extension[@point='kodi.resource.images']").get('compile'),'false')
  self.assertFalse(list(ROOT.rglob('*.py')))
 def test_every_logo_preserves_provenance_bytes_and_resolution(self):
  assets=json.loads((ROOT/'provenance.json').read_text(encoding='utf-8'))['assets']
  self.assertEqual(len(assets),7428)
  for a in assets:
   with self.subTest(file=a['file']):
    p=ROOT/'resources'/a['file']
    self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),a['sha256'])
    with Image.open(p) as im:
     self.assertEqual(im.size,(a['width'],a['height']))
     im.verify()
  self.assertEqual(sum(a['hd_long_edge_512'] for a in assets),3)
 def test_license_and_transparent_coverage_claim(self):
  self.assertIn('Creative Commons',(ROOT/'LICENSE.txt').read_text(encoding='utf-8'))
  x=ET.parse(ROOT/'addon.xml').getroot()
  description=x.find('./extension/description').text
  self.assertIn('Coverage and HD availability vary',description)
if __name__=='__main__':unittest.main()
