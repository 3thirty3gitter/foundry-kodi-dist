import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('playback_gate',Path(__file__).resolve().parents[1]/'tools/record_release_validation.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class PlaybackGate(unittest.TestCase):
 def test_complete_native_evidence_required(self):
  with tempfile.TemporaryDirectory() as d:
   q=Path(d);p=q/'native/playback-contract/native-contract-report.json';p.parent.mkdir(parents=True)
   m={'release':'1.5.5'}
   with self.assertRaises(FileNotFoundError):g.require_playback_contract_evidence(q,m)
   rows=[dict(skin=s,provider=a,route=r,stop_without_failure=True,after_stop_modal=False,receipt={'provider':a,'url':'plugin://'+a+'/?mode=play'},screenshots=['receipt']) for s in ('skin.foundry','skin.foundry.slate') for a in ('plugin.video.fenskeleton','plugin.video.foundry.resolverfixture') for r in ('info','context')]
   sources=[dict(addon=a,path='resources/lib/modules/'+n,sha256='a'*64,bytes=10,profile_copy_verified=True) for a in ('script.foundry.helper','script.foundry.slate.helper') for n in ('catalog_playback.py','catalog_window.py','router.py')]+[dict(addon=a,path='xml/DialogVideoInfo.xml',sha256='a'*64,bytes=10,profile_copy_verified=True) for a in ('skin.foundry','skin.foundry.slate')]
   report=dict(passed=True,exact_eight_cases=True,playback_log_error_gate=True,cases=rows,source_receipts=sources,screenshots=[dict(file=str(i)+'.png',sha256='a'*64,bytes=10,width=1920,height=1080,nonblank=True) for i in range(12)])
   p.write_text(json.dumps(report));g.require_playback_contract_evidence(q,m)
   for key,value in [('passed',False),('cases',rows[:-1]),('source_receipts',sources[:-1]),('screenshots',[])]:
    bad=dict(report);bad[key]=value;p.write_text(json.dumps(bad))
    with self.assertRaises(AssertionError):g.require_playback_contract_evidence(q,m)
 def test_historical_release_unaffected(self):g.require_playback_contract_evidence(Path('absent'),{'release':'1.5.4'})
