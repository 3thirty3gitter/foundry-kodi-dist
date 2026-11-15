from pathlib import Path
import importlib.util,json,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('shared_gate',ROOT/'tools/record_release_validation.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
class SharedNativeEvidence(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.qa=Path(self.tmp.name)
  self.manifest={'release':'1.5.5'}
  steps=[{'selected':'tile'+str(i),'screenshot':str(i)+'.png'} for i in range(17)]
  for x in steps:self.write('native/'+x['screenshot'],{})
  self.write('native/settings-grid-verification.json',dict(transparent_new_icon_count=12,frames_and_background_layers=False,native_directional_steps=steps,shipped_settings_xml_sha256='a'*64))
  self.write('native/search-providers/native-report.json',dict(passed=True,skins={s:dict(passed=True,legacy_xml_routes_unchanged=True,legacy_selections=list(range(5))) for s in ['skin.foundry','skin.foundry.slate']}))
  self.write('native/phone/phone-matrix-verification.json',dict(passed=True,cases=[dict(passed=True,skin=s,restricted_enumeration_real_ioctl=b,http_text_no_auto_confirm=True,bad_origin_and_token_rejected=True,cancel_closed_listener=True,back_closed_listener=True,hidden_has_no_phone=True,rapid_cancel_reopen_retains_new_session=True,source_sha256={'code':'a'*64},image_sha256={'actual-qr.png':'a'*64}) for s in ['skin.foundry','skin.foundry.slate'] for b in [False,True]]))
  self.write('native/simkl/native-report.json',dict(passed=True,phases=[dict(phase=p,verified_disclosure=True,cancelled=True,enabled_unchanged=True,fixture_executed=False,shipped_setup_unchanged=True) for p in ['missing','disabled','enabled']]))
 def write(self,name,value):
  p=self.qa/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value));return p
 def test_complete_proof_accepted(self):gate.require_shared_update_evidence(self.qa,self.manifest)
 def test_each_new_native_report_required(self):
  for name in ['settings-grid-verification.json','search-providers/native-report.json','phone/phone-matrix-verification.json','simkl/native-report.json']:
   p=self.qa/'native'/name;data=p.read_bytes();p.unlink()
   with self.assertRaises(FileNotFoundError):gate.require_shared_update_evidence(self.qa,self.manifest)
   p.write_bytes(data)
 def test_simkl_side_effect_and_missing_phone_case_rejected(self):
  p=self.qa/'native/simkl/native-report.json';d=json.loads(p.read_text());d['phases'][0]['fixture_executed']=True;p.write_text(json.dumps(d))
  with self.assertRaises(AssertionError):gate.require_shared_update_evidence(self.qa,self.manifest)
  d['phases'][0]['fixture_executed']=False;p.write_text(json.dumps(d));p=self.qa/'native/phone/phone-matrix-verification.json';d=json.loads(p.read_text());d['cases'].pop();p.write_text(json.dumps(d))
  with self.assertRaises(AssertionError):gate.require_shared_update_evidence(self.qa,self.manifest)
