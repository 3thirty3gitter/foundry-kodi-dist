"""Only requested media selection/art changes may alter published packages."""
import json,hashlib,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def files(path,aid):
 with zipfile.ZipFile(path) as z:return {n[len(aid)+1:]:z.read(n) for n in z.namelist() if not n.endswith('/')}
class MediaScope(unittest.TestCase):
 def test_prior_releases_preserved(self):
  prior=json.loads((ROOT/'tests/fixtures/media-prior-release.json').read_text());new=json.loads((ROOT/'release.json').read_text());current={p['id']:p for p in new['packages']}
  changes={'skin.foundry','script.foundry.helper','skin.foundry.slate','script.foundry.slate.helper','script.program.foundry-build','script.program.foundry-bootstrap'}
  self.assertEqual(new['release'],'1.5.6');self.assertEqual(len(current),15)
  for p in prior['packages']:
   self.assertEqual(hashlib.sha256((ROOT/p['path']).read_bytes()).hexdigest(),p['sha256'])
   if p['id'] not in changes:self.assertEqual(current[p['id']],p)
 def test_original_exact_scope(self):
  current={p['id']:p for p in json.loads((ROOT/'release.json').read_text())['packages']}
  cases=[('skin.foundry','1.5.5',{'addon.xml','docs/handoffs/LATEST.md','xml/Home.xml','xml/Custom_1121_SearchResults.xml','xml/Includes.xml','xml/Includes_StreamPilotOSD.xml','xml/SkinSettings.xml','xml/Variables.xml'},set()),('script.foundry.helper','1.3.6',{'addon.xml','docs/handoffs/LATEST.md','resources/lib/modules/router.py','resources/lib/service.py'},{'resources/lib/modules/media_pack.py'})]
  for aid,version,changed,added in cases:
   old=files(ROOT/aid/(aid+'-'+version+'.zip'),aid);new=files(ROOT/current[aid]['path'],aid)
   self.assertEqual(set(old)-set(new),set());self.assertEqual(set(new)-set(old),added);self.assertEqual({p for p in old if old[p]!=new[p]},changed)
if __name__=='__main__':unittest.main()
