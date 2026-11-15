import unittest,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(Path(__file__).parent))
from prune_slate_default_xbt import parse
class XbtDefaults(unittest.TestCase):
 def test_packed_defaults_do_not_override_resource_shadows(self):
  skin=ROOT/'src/skin.foundry.slate';res=ROOT/'src/resource.images.foundry.slate.icons/resources'
  xbt=skin/'media/Textures.xbt'
  if not xbt.exists():
   base=Path(__file__).parent;xbt=base/'Textures.defaults-pruned.xbt';res=base/'resource.images.foundry.slate.icons/resources';skin=base/'qa/src/skin.foundry.slate'
  entries,header=parse(xbt.read_bytes())
  manifest=json.loads((res/'manifest.json').read_text())
  for name in manifest['texture_aliases']:
   if '/' not in name and name.startswith(('Default','Overlay')):
    self.assertNotIn(name.casefold(),entries)
    self.assertEqual((skin/'media'/name).read_bytes(),(res/'aliases'/name).read_bytes())
  self.assertEqual(len(entries),748)
  self.assertEqual(hashlib.sha256(xbt.read_bytes()).hexdigest(),'33ba98a43ea6bf77a13085177d7ce88f1f9e004eac90b6cf7a3a4540593e4258')
if __name__=='__main__':unittest.main()
