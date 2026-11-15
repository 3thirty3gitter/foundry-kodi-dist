import importlib.util,json,unittest
from pathlib import Path
from unittest.mock import patch
import test_media_pack as harness
BASE=Path(__file__).resolve().parents[1]
class ManifestCap(harness.Tests):
 def each_module(self):
  for name in ('script.foundry.helper','script.foundry.slate.helper'):
   spec=importlib.util.spec_from_file_location('cap_'+name,(BASE.parent/name if name=='script.foundry.helper' else BASE/'src'/name)/'resources/lib/modules/media_pack.py')
   m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);yield m
 def test_actual_approved_full105(self):
  raw=(BASE/'src/resource.images.foundry.media.puremarks/resources/media-pack.json').read_bytes();self.assertGreater(len(raw),65537)
  data=json.loads(raw);self.assertEqual(data['release_status'],'approved')
  (self.root/'resources/media-pack.json').write_bytes(raw)
  for m in self.each_module():
   pack=m.read_pack(self.id);self.assertIsNotNone(pack);self.assertEqual(len(pack['osd_derivatives']),40)
 def test_exact_byte_boundary_and_over(self):
  raw=json.dumps(self.data).encode()
  for m in self.each_module():
   p=self.root/'resources/media-pack.json';p.write_bytes(raw+b' '*(m.MAX_MANIFEST_BYTES-len(raw)))
   self.assertIsNotNone(m.read_pack(self.id))
   with p.open('ab') as f:f.write(b' ')
   with patch.object(m.json,'loads',side_effect=AssertionError('oversized data parsed')):
    self.assertIsNone(m.read_pack(self.id))
 def test_utf8_bytes_not_character_count(self):
  data=dict(self.data,padding='\u00e9'*140000);raw=json.dumps(data,ensure_ascii=False).encode('utf-8')
  self.assertLess(len(raw.decode()),256*1024);self.assertGreater(len(raw),256*1024)
  (self.root/'resources/media-pack.json').write_bytes(raw)
  for m in self.each_module():self.assertIsNone(m.read_pack(self.id))
 def test_invalid_utf8_and_truncated_json(self):
  for raw in (b'\xff',b'{"schema_version":'):
   (self.root/'resources/media-pack.json').write_bytes(raw)
   for m in self.each_module():self.assertIsNone(m.read_pack(self.id))
if __name__=='__main__':unittest.main()
