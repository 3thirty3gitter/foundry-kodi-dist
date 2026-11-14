"""Authorized original 1.5.5 scope preserves every unrelated published byte."""
from pathlib import Path
import json,unittest,zipfile
ROOT=Path(__file__).resolve().parents[1]
def contents(path,aid):
 with zipfile.ZipFile(path) as z:return {n[len(aid)+1:]:z.read(n) for n in z.namelist() if not n.endswith('/')}
class OriginalScope(unittest.TestCase):
 def test_only_authorized_original_skin_and_helper_files_changed(self):
  current={p['id']:p for p in json.loads((ROOT/'release.json').read_text())['packages']}
  cases=[('skin.foundry','1.5.4',{'addon.xml','docs/handoffs/LATEST.md','xml/Custom_1116_StartHelp.xml','xml/Includes.xml','xml/Settings.xml','xml/DialogVideoInfo.xml','xml/Variables_MyVariables.xml','xml/Variables_Search.xml'}),('script.foundry.helper','1.3.5',{'addon.xml','docs/handoffs/LATEST.md','resources/lib/modules/catalog_window.py','resources/lib/modules/cpath_maker.py','resources/lib/modules/databases/ratings.py','resources/lib/modules/helper.py','resources/lib/modules/phone_entry_network.py','resources/lib/modules/router.py','resources/lib/modules/search_provider.py','resources/lib/modules/search_utils.py'})]
  for aid,version,allowed in cases:
   old=contents(ROOT/aid/(aid+'-'+version+'.zip'),aid);new=contents(ROOT/current[aid]['path'],aid)
   self.assertTrue(set(old)<=set(new),(aid,'Unexpected removed file'))
   changed={p for p in old if old[p]!=new[p]};self.assertEqual(changed,allowed)
   added=set(new)-set(old)
   if aid=='skin.foundry':
    self.assertEqual(len(added),12);self.assertTrue(all(p.startswith('media/foundry-settings-icons/') and p.endswith('.png') for p in added))
   else:self.assertEqual(added,{'resources/lib/modules/catalog_playback.py'})
if __name__=='__main__':unittest.main()
