import unittest,json,hashlib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SlateOptional(unittest.TestCase):
 def test_original_unchanged(self):
  old=json.loads((ROOT/'tests/fixtures/slate-original-packages.json').read_text())
  new=json.loads((ROOT/'release.json').read_text())
  self.assertEqual(new['packages'][:10],old['packages'])
  self.assertEqual(new['release'],old['release'])
  for p in old['packages']: self.assertEqual(hashlib.sha256((ROOT/p['path']).read_bytes()).hexdigest(),p['sha256'])
 def test_optional_separate_ids(self):
  new=json.loads((ROOT/'release.json').read_text())
  self.assertEqual({p['id'] for p in new['packages'][10:]},{'skin.foundry.slate','script.foundry.slate.helper'})
  for name in ('script.program.foundry-build','script.program.foundry-bootstrap'):
   p=next(p for p in new['packages'] if p['id']==name)
   with zipfile.ZipFile(ROOT/p['path']) as z:
    for n in z.namelist():
     if n.endswith(('.py','.xml')): self.assertNotIn(b'foundry.slate',z.read(n))
