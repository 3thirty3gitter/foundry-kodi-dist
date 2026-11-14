import importlib.util,json,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('icon_gate',R/'tools/record_release_validation.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class Gate(unittest.TestCase):
 def test_requires_real_completed_icon_evidence(self):
  m={'packages':[{'id':'resource.images.foundry.slate.icons'}]}
  with tempfile.TemporaryDirectory() as d:
   q=Path(d);p=q/'native/slate-icons/native-icon-report.json';p.parent.mkdir(parents=True)
   with self.assertRaises(FileNotFoundError):g.require_icon_evidence(q,m)
   r={'passed':True,'native':{'passed':True},'texture_failures':[],'captures':{n:'a'*64 for n in ('icons-home','icons-settings','icons-skinsettings','icons-keyboard','icons-default-placeholders','icons-default-folder','icons-default-file','icons-playback-osd')}}
   p.write_text(json.dumps(r));g.require_icon_evidence(q,m)
   for key,value in [('passed',False),('texture_failures',['bad texture']),('captures',{})]:
    bad=dict(r);bad[key]=value;p.write_text(json.dumps(bad))
    with self.assertRaises(AssertionError):g.require_icon_evidence(q,m)
 def test_old_releases_unaffected(self):g.require_icon_evidence(Path('absent'),{'packages':[]})
if __name__=='__main__':unittest.main()
