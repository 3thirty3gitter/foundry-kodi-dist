import unittest,json,hashlib,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SlateOptional(unittest.TestCase):
 def test_original_unchanged(self):
  old=json.loads((ROOT/'tests/fixtures/slate-original-packages.json').read_text())
  new=json.loads((ROOT/'release.json').read_text())
  # Weather fix and separately authorized original Foundry 1.5.5 updates are scoped below.
  current={p['id']:p for p in new['packages']}
  for package in old['packages']:
   if package['id'] not in {'weather.foundry.canada','skin.foundry','script.foundry.helper','script.program.foundry-build','script.program.foundry-bootstrap'}:self.assertEqual(current[package['id']],package)
  self.assertEqual(current['weather.foundry.canada']['version'],'0.1.1')
  self.assertEqual(new['release'],'1.5.6')
  for aid,version in [('skin.foundry','1.5.6'),('script.foundry.helper','1.3.7'),('script.program.foundry-build','1.5.6'),('script.program.foundry-bootstrap','1.5.6')]:self.assertEqual(current[aid]['version'],version)
  for p in old['packages']: self.assertEqual(hashlib.sha256((ROOT/p['path']).read_bytes()).hexdigest(),p['sha256'])
 def test_optional_separate_ids(self):
  new=json.loads((ROOT/'release.json').read_text())
  self.assertEqual({p['id'] for p in new['packages'][10:]},{'skin.foundry.slate','script.foundry.slate.helper','resource.images.foundry.slate.icons','script.program.foundry-simkl','resource.images.foundry.media.puremarks'})
  for name in ('script.program.foundry-build','script.program.foundry-bootstrap'):
   p=next(p for p in new['packages'] if p['id']==name)
   with zipfile.ZipFile(ROOT/p['path']) as z:
    for n in z.namelist():
     if n.endswith(('.py','.xml')): self.assertNotIn(b'foundry.slate',z.read(n))
