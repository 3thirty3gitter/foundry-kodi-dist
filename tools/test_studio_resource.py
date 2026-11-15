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
  self.assertEqual(sum(a['hd_long_edge_512'] for a in assets),6)
 def test_rebuild_batch_is_exactly_three_verified_variants(self):
  q=json.loads((ROOT/'quality-summary.json').read_text())
  self.assertEqual(q['rebuilt'],3)
  self.assertTrue(q['not_claimed_all_HD'])
  m=json.loads((ROOT/'hd-provenance.json').read_text())['matched']
  self.assertEqual([x['targets'] for x in m],[['A24.png'],['HBO.png'],['StudioCanal.png']])
  self.assertEqual(m[0]['dimensions'],[2048,840])
  self.assertGreater(m[0]['shape_alpha_iou'],.95)
  self.assertEqual(hashlib.sha256((ROOT/'resources/A24.png').read_bytes()).hexdigest(),m[0]['replacement_sha256'])
 def test_vector_sources_preserve_paths_and_are_inert(self):
  m=json.loads((ROOT/'hd-provenance.json').read_text())
  for row in m['matched']:
   record=next(r for r in m['sources'] if r.get('svg')==row['source'])
   original=ROOT/row['source'];adapted=ROOT/row.get('adapted_vector',row['source'])
   self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),record['source_sha256'])
   a=ET.parse(original).getroot();b=ET.parse(adapted).getroot()
   self.assertEqual([n.get('d') for n in a.iter() if n.tag.endswith('}path')],[n.get('d') for n in b.iter() if n.tag.endswith('}path')])
   for tree in (a,b):
    for n in tree.iter():
     self.assertNotIn(n.tag.rsplit('}',1)[-1],('script','image','foreignObject'))
     self.assertFalse(any(k.rsplit('}',1)[-1]=='href' and not v.startswith('#') for k,v in n.attrib.items()))
 def test_license_and_transparent_coverage_claim(self):
  self.assertIn('Creative Commons',(ROOT/'LICENSE.txt').read_text(encoding='utf-8'))
  x=ET.parse(ROOT/'addon.xml').getroot()
  description=x.find('./extension/description').text
  self.assertIn('Coverage and HD availability vary',description)
if __name__=='__main__':unittest.main()
