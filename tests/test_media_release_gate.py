"""Fail-closed 1.5.6 media publication evidence bound to final ZIP members."""
import copy, hashlib, importlib.util, io, json, tempfile, unittest, zipfile
from pathlib import Path
from PIL import Image
HERE=Path(__file__).resolve().parent
GATE=HERE/'record_release_validation.py'
if not GATE.exists():GATE=HERE.parent/'tools/record_release_validation.py'
spec=importlib.util.spec_from_file_location('media_release_gate',GATE);gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
def sha(data):return hashlib.sha256(data).hexdigest()
def png(size):
 out=io.BytesIO();Image.new('RGBA',size,(255,255,255,255)).save(out,format='PNG');return out.getvalue()
class MediaGateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.qa=self.root/'releases/1.5.6-qa';self.artdir=self.qa/'native/media-art';self.seldir=self.qa/'native/media-selector';self.artdir.mkdir(parents=True);self.seldir.mkdir(parents=True)
  asset=png((4,2));screen=png((1920,1080));assets=[{'path':('flags/audiochannel/'+str((1,3,4,5,7,10)[i])+'.png') if i<6 else f'flags/audiocodec/format{i}.png','sha256':sha(asset),'dimensions':[4,2],'status':'sourced-format-mark' if i<31 else 'original-technical-glyph','release_approved':True} for i in range(105)]
  self.meta={'schema_version':1,'kind':'foundry-media-flags','release_status':'approved','coverage_complete':True,'asset_root':'flags','unresolved_paths':[],'authentic_mark_paths':31,'original_technical_glyph_paths':74,'assets':assets}
  self.pack={'resources/'+a['path']:asset for a in assets};self.pack['resources/media-pack.json']=json.dumps(self.meta).encode();self.pack['addon.xml']=b'<addon/>'
  self.manifest={'release':'1.5.6','packages':[]};self.contents={gate.MEDIA_ID:self.pack}
  for aid in gate.MEDIA_HELPERS:self.contents[aid]={'resources/lib/'+n:(aid+n).encode() for n in ('service.py','modules/router.py','modules/media_pack.py')}
  for aid in gate.MEDIA_SKINS:self.contents[aid]={'xml/'+n:(aid+n).encode() for n in gate.MEDIA_XML}
  for aid,files in self.contents.items():
   path=self.root/(aid+'.zip')
   with zipfile.ZipFile(path,'w') as z:
    for name,data in files.items():z.writestr(aid+'/'+name,data)
   data=path.read_bytes();self.manifest['packages'].append({'id':aid,'version':'0.1.0','path':path.name,'size':len(data),'sha256':sha(data)})
  names=[f'page{i}.png' for i in range(105)]
  for name in names:(self.artdir/name).write_bytes(screen)
  cases=[{'box':[w,h],'background':list(bg),'mean_rgb_error':.1,'ink_rgb_error':.2,'visible_pixels':5} for w,h in ((115,60),(76,54)) for bg in ((255,255,255),(32,32,32))]
  self.art={'passed':True,'native':{'passed':True,'pages':names,'resource_hash_verified':105},'asset_count':105,'manifest_release_status':'approved','manifest_sha256':sha(self.pack['resources/media-pack.json']),'source_receipts':[{'file':n,'sha256':sha(d)} for n,d in self.pack.items()],'pages':[{'file':a['path'],'cases':copy.deepcopy(cases),'screenshot_sha256':sha(screen)} for a in assets]}
  self.result={'passed':True,'skins':{s:{'passed':True} for s in gate.MEDIA_SKINS},'release_source_mode':'packaged-no-overlay','actual_pack_id':gate.MEDIA_ID,'actual_pack_manifest_sha256':sha(self.pack['resources/media-pack.json']),'source_receipts':[{'file':a+'/'+n,'sha256':sha(d)} for a,files in self.contents.items() if a!=gate.MEDIA_ID for n,d in files.items()],'screenshots':[]}
  self.geometry={};self.channels={}
  for skin in gate.MEDIA_SKINS:
   pages=[]
   for card in ('StreamPilotVODCard','StreamPilotLiveCard'):
    for v in ('wide','builtin','missing-derivative','wide-restored'):
     wide=v in ('wide','wide-restored');name=skin+card+v+'.png';(self.seldir/name).write_bytes(screen)
     pages.append({'card':card,'variant':v,'wide':wide,'codec':'ac3','channels':'2','title':'A long title','derived_xml_geometry':{'audio':[0,0,160 if wide else 76,54],'gap':40},'visible_ink_recall':1.0,'path':'/addons/'+gate.MEDIA_ID+'/resources/flags-osd/audiocodec/ac3.png' if wide else '', 'file':name,'screenshot_sha256':sha(screen)})
     self.result['screenshots'].append({'file':name,'sha256':sha(screen)})
   self.geometry[skin]={'passed':True,'original_pack_status':'approved','geometry_source':{'source_sha256':sha(self.contents[skin]['xml/Includes_StreamPilotOSD.xml'])},'pages':pages}
  for skin in gate.MEDIA_SKINS:
   pages=[]
   for card in ('StreamPilotVODCard','StreamPilotLiveCard'):
    for count in (1,3,4,5,7,10):
     for selected in (False,True):
      name=skin+card+str(count)+str(selected)+'.png';(self.seldir/name).write_bytes(screen)
      pages.append({'card':card,'channels':count,'actual_channels':str(count),'actual_codec':'pcm_s16le','selected':selected,'channel_control_visible':selected,'path':'/addons/'+gate.MEDIA_ID+'/resources/flags/audiochannel/'+str(count)+'.png','file':name,'fixture':{'file':'pcm.mkv','channels':count,'codec':'pcm_s16le','sha256':'a'*64,'bytes':100},'source_sha256':sha(asset),'visible_ink_recall':1.0,'screenshot_sha256':sha(screen)})
      self.result['screenshots'].append({'file':name,'sha256':sha(screen)})
   self.channels[skin]={'passed':True,'pages':pages,'geometry_source':self.geometry[skin]['geometry_source']}
  for i in range(38):
   name=f'selector{i}.png';(self.seldir/name).write_bytes(screen);self.result['screenshots'].append({'file':name,'sha256':sha(screen)})
  self.save()
 def save(self):
  (self.artdir/'native-mediaflags-report.json').write_text(json.dumps(self.art));(self.seldir/'native-report.json').write_text(json.dumps(self.result))
  for s,g in self.geometry.items():(self.seldir/(s+'-audio-geometry.json')).write_text(json.dumps(g))
  for s,g in self.channels.items():(self.seldir/(s+'-channel-geometry.json')).write_text(json.dumps(g))
 def run_gate(self):self.save();gate.require_media_evidence(self.root,self.qa,self.manifest)
 def fails(self):
  with self.assertRaises((AssertionError,KeyError,FileNotFoundError)):self.run_gate()
 def test_complete_evidence_passes(self):self.run_gate()
 def test_historical_release_unaffected(self):gate.require_media_evidence(self.root,self.qa,{'release':'1.5.5','packages':[]})
 def test_missing_package_fails(self):self.manifest['packages']=[p for p in self.manifest['packages'] if p['id']!=gate.MEDIA_ID];self.fails()
 def test_wrong_package_version_fails(self):self.manifest['packages'][0]['version']='0.0.1';self.fails()
 def test_package_bytes_changed_fails(self):(self.root/self.manifest['packages'][0]['path']).write_bytes(b'corrupt');self.fails()
 def test_partial_art_fails(self):self.art['asset_count']=31;self.fails()
 def test_partial_receipts_fail(self):self.art['source_receipts'].pop();self.fails()
 def test_wrong_manifest_hash_fails(self):self.art['manifest_sha256']='0'*64;self.fails()
 def test_experimental_art_fails(self):self.art['manifest_release_status']='experimental';self.fails()
 def test_art_threshold_not_relaxed(self):self.art['pages'][0]['cases'][0]['ink_rgb_error']=30;self.fails()
 def test_missing_art_page_fails(self):self.art['pages'].pop();self.fails()
 def test_png_tamper_fails(self):(self.artdir/'page0.png').write_bytes(b'not png');self.fails()
 def test_overlaid_product_rejected(self):self.result['release_source_mode']='candidate-overlay';self.fails()
 def test_wrapper_resource_rejected(self):self.result['actual_pack_id']='resource.images.foundry.media.qaactual';self.fails()
 def test_missing_skin_fails(self):self.result['skins'].pop('skin.foundry.slate');self.fails()
 def test_missing_source_receipt_fails(self):self.result['source_receipts'].pop();self.fails()
 def test_source_hash_mismatch_fails(self):self.result['source_receipts'][0]['sha256']='0'*64;self.fails()
 def test_geometry_source_mismatch_fails(self):self.geometry['skin.foundry']['geometry_source']['source_sha256']='0'*64;self.fails()
 def test_missing_geometry_state_fails(self):self.geometry['skin.foundry']['pages'].pop();self.fails()
 def test_overlap_fails(self):self.geometry['skin.foundry']['pages'][4]['derived_xml_geometry']['gap']=0;self.fails()
 def test_wrong_width_fails(self):self.geometry['skin.foundry']['pages'][0]['derived_xml_geometry']['audio'][2]=76;self.fails()
 def test_wrong_playback_metadata_fails(self):self.geometry['skin.foundry']['pages'][0]['codec']='fake';self.fails()
 def test_missing_channel_count_fails(self):self.channels['skin.foundry']['pages'].pop();self.fails()
 def test_fake_channel_metadata_fails(self):self.channels['skin.foundry']['pages'][0]['actual_channels']='2';self.fails()
 def test_unexpected_builtin_channel_badge_fails(self):self.channels['skin.foundry']['pages'][0]['channel_control_visible']=True;self.fails()
 def test_channel_png_hash_mismatch_fails(self):self.channels['skin.foundry']['pages'][1]['source_sha256']='0'*64;self.fails()
 def test_source_scope_runs_before_evidence(self):
  with self.assertRaises(AssertionError):gate.require_release_scope({'release':'1.5.6','packages':[{'id':'plugin.games.foundry','version':'0.1.0'}]})
if __name__=='__main__':unittest.main()
