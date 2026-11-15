from pathlib import Path
import os,json,shutil,subprocess,time,urllib.request,xml.etree.ElementTree as E
import argparse,tempfile,hashlib,sys
from PIL import Image, ImageDraw
import traceback, importlib.util
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',type=Path,required=True);parser.add_argument("--stage",type=Path);parser.add_argument("--audio-stage",type=Path);parser.add_argument("--actual-pack",type=Path,required=True);parser.add_argument("--derivatives",type=Path);parser.add_argument("--ac3-fixture",type=Path,required=True);parser.add_argument("--channel-fixtures",type=Path,required=True);args=parser.parse_args();ROOT=args.root.resolve();base=Path(tempfile.mkdtemp(prefix='media-pack-native-'));out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
# Evidence may be copied from an earlier published release. Never accept stale reports.
for stale in out.iterdir():
 if stale.is_file() and (stale.suffix == '.png' or stale.name in ('native-report.json',)):
  stale.unlink()
profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True);addons=profile/'addons';addons.mkdir()
for source in [ROOT/'src/skin.foundry.slate',ROOT/'src/script.foundry.slate.helper',ROOT.parent/'skin.foundry-nimbus',ROOT.parent/'script.foundry.helper']+[ROOT/'src'/x for x in ('resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','resource.images.foundry.slate.icons')]:
 aid=E.parse(source/'addon.xml').getroot().get('id');shutil.copytree(source,addons/aid,ignore=shutil.ignore_patterns('.git'))
if args.stage:
 for name,aid in [('skin.foundry-nimbus','skin.foundry'),('skin.foundry.slate','skin.foundry.slate'),('script.foundry.helper','script.foundry.helper'),('script.foundry.slate.helper','script.foundry.slate.helper')]:
  shutil.copytree(args.stage/name,addons/aid,dirs_exist_ok=True)
if args.audio_stage:
 for name,aid in [('skin.foundry-nimbus','skin.foundry'),('skin.foundry.slate','skin.foundry.slate'),('script.foundry.helper','script.foundry.helper'),('script.foundry.slate.helper','script.foundry.slate.helper')]:
  shutil.copytree(args.audio_stage/name,addons/aid,dirs_exist_ok=True)
assert hashlib.sha256(args.ac3_fixture.read_bytes()).hexdigest()=='e603358c27c79788ceb776c5902c50d650ad7de4471e541ca02efcec7ccab760'
shutil.copy2(args.ac3_fixture,base/'geometry-ac3.mkv')
for helper in addons.glob('script.*helper'):
 t=E.parse(helper/'addon.xml');r=t.getroot()
 for n in list(r.findall("extension[@point='xbmc.service']")):r.remove(n)
 for n in list(r.find('requires')):
  if n.get('addon')!='xbmc.python':r.find('requires').remove(n)
 t.write(helper/'addon.xml') # Keep actual helper entry/router for skin-control QA
 # Isolate picker UI from first-run menu rebuild/repository bootstrap. These
 # unrelated Home callbacks can ReloadSkin while Keep skin? is still open.
 entry=helper/'resources/lib/default.py'
 original=entry.read_text()
 guard='import sys as _qa_sys\nfrom urllib.parse import parse_qsl as _qa_parse\n_qa_mode=dict(_qa_parse(_qa_sys.argv[1] if len(_qa_sys.argv)>1 else "")).get("mode", "")\nif _qa_mode not in ("choose_media_icon_pack",):\n raise SystemExit\n'
 entry.write_text(guard+original)

for p in (home/'addons').glob('*/addon.xml'):
 t=E.parse(p)
 for e in t.getroot().findall("extension[@point='xbmc.service']"):t.getroot().remove(e)
 t.write(p)
for aid in ('skin.foundry','skin.foundry.slate'):
 d=userdata/'addon_data'/aid;d.mkdir(parents=True);(d/'settings.xml').write_text('<settings><setting id="firsttimerun" type="bool">true</setting></settings>')
(userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">18991</setting><setting id="services.webserverauthentication">false</setting><resolutions/><viewstates/><skinsettings/></settings>')

import struct
from io import BytesIO
# Every resource here is synthetic and restricted to disposable QA.
CATS={'videocodec':['h264','mjpeg'],'videoresolution':['1080','720','480','360'], 'videohdr':['hdr10'], 'aspectratio':['1.78'], 'audiocodec':['ac3','pcm','pcm_s16le'], 'audiochannel':['6','2']}
PACKS=['resource.images.foundry.media.qaa','resource.images.foundry.media.qab','resource.images.foundry.media.qaexperimental','resource.images.foundry.media.qadisabled']
for ix,aid in enumerate(PACKS):
 d=addons/aid;(d/'resources').mkdir(parents=True)
 (d/'addon.xml').write_text('<addon id="'+aid+'" version="1.0.0" name="QA '+str(ix)+'" provider-name="QA"><extension point="kodi.resource.images"/></addon>')
 manifest={'schema_version':1,'kind':'foundry-media-flags','name':['QA A','QA B','QA Experimental','QA Disabled'][ix],'asset_root':'flags','categories':list(CATS),'release_status':'experimental' if ix==2 else 'approved'}
 (d/'resources/media-pack.json').write_text(json.dumps(manifest))
 for cat,aliases in CATS.items():
  for alias in aliases:
   dest=d/'resources/flags'/cat/(alias+'.png');dest.parent.mkdir(parents=True,exist_ok=True)
   im=Image.new('RGBA',(120,60),(0,0,0,0));ImageDraw.Draw(im).rectangle((5,5,114,54), fill=(245,30,160,255) if ix==0 else (30,240,90,255));im.save(dest)
ACTUAL_QA='resource.images.foundry.media.puremarks'
actual_qa=addons/ACTUAL_QA;shutil.copytree(args.actual_pack,actual_qa)
assert not args.derivatives,'Final release runner requires packaged derivatives, no overlay'
manifest_path=actual_qa/'resources/media-pack.json';m=json.loads(manifest_path.read_text());original_status=m.get('release_status')
assert original_status=='approved' and E.parse(actual_qa/'addon.xml').getroot().get('id')==ACTUAL_QA
assert len(m['assets'])==105 and len(m['osd_derivatives'])==40
actual_source_receipts=[{'file':str(p.relative_to(args.actual_pack)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(args.actual_pack.rglob('*')) if p.is_file()]
derivative_receipts=[r for r in actual_source_receipts if 'flags-osd/' in r['file']]
channel_fixture_receipts=json.loads((args.channel_fixtures/'manifest.json').read_text())
assert sorted(r['channels'] for r in channel_fixture_receipts)==[1,3,4,5,7,10]
for r in channel_fixture_receipts:
 assert hashlib.sha256((args.channel_fixtures/r['file']).read_bytes()).hexdigest()==r['sha256']
 shutil.copy2(args.channel_fixtures/r['file'],base/r['file'])
SERVICE_QA=['script.foundry.mediapackmonitor','script.foundry.mediapackmonitorslate']
for qaid,helper,tag in zip(SERVICE_QA,('script.foundry.helper','script.foundry.slate.helper'),('original','slate')):
 d=addons/qaid;d.mkdir()
 (d/'addon.xml').write_text('<addon id="'+qaid+'" version="1.0.0" name="QA actual service" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
 preamble='from pathlib import Path\nENTRY=Path('+repr(str(addons/helper/'resources/lib'))+')\nOUT=Path('+repr(str(out))+')\nTAG='+repr(tag)+'\n'
 (d/'default.py').write_text(preamble+'"""QA addon payload. Values ENTRY, OUT and TAG supplied by native runner."""\nimport sys,types,json,time,traceback,hashlib,importlib.util\nfrom pathlib import Path\nimport xbmc\nsys.path.insert(0,str(ENTRY))\nclass Noop:\n def __init__(self,*args,**kwargs):pass\n def __getattr__(self,name):return lambda *args,**kwargs:None\ndef stub(name,**exports):\n m=types.ModuleType(name)\n for k,v in exports.items():setattr(m,k,v)\n sys.modules[name]=m\nstub(\'modules.logger\',logger=lambda *a,**k:None)\nstub(\'modules.file_sources\',ensure_file_sources=lambda:None)\nstub(\'modules.startup_splash\',install_startup_splash=lambda:None)\nstub(\'modules.monitors.ratings\',RatingsMonitor=Noop)\nstub(\'modules.monitors.metadata\',MetadataMonitor=Noop)\nstub(\'modules.vod\',CatalogArtworkMonitor=Noop,CatalogRoutingMonitor=Noop)\nstub(\'modules.monitors.image\',ImageMonitor=Noop,ImageBlur=Noop,ImageAnalysisConfig=Noop)\nstub(\'modules.databases.ratings\',RatingsDatabase=Noop)\nstub(\'modules.config\',SETTINGS_PATH=str(OUT/(TAG+\'-settings\')))\nfrom modules import media_pack\nspec=importlib.util.spec_from_file_location(\'qa_unchanged_service\',ENTRY/\'service.py\')\nm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nreport={\'scope\':\'Unchanged Service loop and native Monitor; unrelated workers/startup stubbed; media monitor unchanged apart from observation wrappers\',\'source\':{},\'samples\':[],\'waits\':[],\'passed\':False}\nfor name,p in [(\'service\',ENTRY/\'service.py\'),(\'media_pack\',ENTRY/\'modules/media_pack.py\')]:report[\'source\'][name]=hashlib.sha256(p.read_bytes()).hexdigest()\ndef save():(OUT/(TAG+\'-scheduler.json\')).write_text(json.dumps(report,indent=2))\ntry:\n service=m.Service()\n process=service.media_pack_monitor.process\n wait=service.waitForAbort\n def observed_process():\n  process()\n  report[\'samples\'].append({\'at\':time.monotonic(),\'skin\':xbmc.getSkinDir(),\'paused\':service._should_pause(),\'pack\':service.media_pack_monitor.window.getProperty(media_pack.PREFIX+\'.pack\'),\'setting\':xbmc.getInfoLabel(\'Skin.String(MediaIconPack)\')})\n  report[\'samples\']=report[\'samples\'][-1000:];save()\n def observed_wait(seconds):\n  report[\'waits\'].append(seconds);report[\'waits\']=report[\'waits\'][-1000:]\n  return wait(seconds)\n service.media_pack_monitor.process=observed_process\n service.waitForAbort=observed_wait\n service.run()\n report[\'passed\']=True\nexcept Exception:report[\'error\']=traceback.format_exc();raise\nfinally:save()\n')
qa=addons/'script.foundry.searchqa';qa.mkdir()
(qa/'addon.xml').write_text('<addon id="script.foundry.searchqa" version="1.0.0" name="Search QA" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
driver=addons/'script.foundry.searchdriver';driver.mkdir()
(driver/'addon.xml').write_text('<addon id="script.foundry.searchdriver" version="1.0.0" name="Search driver QA" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'home/.config'),XDG_CACHE_HOME=str(base/'home/.cache'),DISPLAY=':98',KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL');(base/'home').mkdir()
log=(out/'native-console.log').open('w');x=subprocess.Popen(['Xvfb',':98','-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log);time.sleep(1)
def launch():return subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=env,stdout=log,stderr=log)
k=launch()
def rpc(method,params=None):
 data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode();r=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18991/jsonrpc',data=data,headers={'Content-Type':'application/json'}),timeout=5))
 if 'error' in r:raise RuntimeError((method,params,r['error']))
 return r['result']
def wait(fn,t=45):
 end=time.monotonic()+t
 while time.monotonic()<end:
  try:
   if fn():return
  except Exception:pass
  time.sleep(.25)
 raise AssertionError('timeout')
def cond(c):return rpc('XBMC.GetInfoBooleans',{'booleans':[c]})[c]
def act(a):rpc('Input.ExecuteAction',{'action':a});time.sleep(.3)
def drive(body):
 # Wait for both a result receipt and the same native interpreter teardown.
 import re
 receipt=out/('driver-'+str(time.time_ns())+'.json')
 logpath=profile/'temp/kodi.log'
 offset=logpath.stat().st_size if logpath.exists() else 0
 source='import xbmc,xbmcgui,json,traceback\nfrom pathlib import Path\nresult={"ok":False}\ntry:\n'
 source+='\n'.join(' '+line for line in body.splitlines())
 source+='\n result["ok"]=True\nexcept Exception:\n result["error"]=traceback.format_exc()\nfinally:\n Path('+repr(str(receipt))+').write_text(json.dumps(result))\n'
 (driver/'default.py').write_text(source)
 rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.searchdriver','wait':False})
 wait(receipt.exists)
 def stopped():
  with logpath.open('rb') as f:f.seek(offset);tail=f.read().decode('utf-8',errors='replace')
  match=re.search(r'T:(\d+)\s+.*CPythonInvoker.*script\.foundry\.searchdriver/default\.py.*script successfully run',tail)
  return bool(match and re.search(r'T:'+match.group(1)+r'\s+.*Python interpreter stopped',tail[match.end():]))
 wait(stopped)
 result=json.loads(receipt.read_text())
 assert result['ok'], result.get('error')
def focus_yes(expected):
 state=out/'dialog-focus.json'
 def observe():
  drive('w=xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())\nPath('+repr(str(state))+').write_text(json.dumps({"id":w.getFocusId(),"yes":xbmc.getInfoLabel("Control.GetLabel(11)")}))')
  return json.loads(state.read_text())
 current=observe()
 assert current['yes']==expected, current
 for _ in range(2):
  if current['id']==11:return
  act('left');current=observe()
 assert current['id']==11, current
def snap(n):
 dest=out/(n+'.png')
 if dest.exists():dest.unlink()
 drive('xbmc.executebuiltin('+repr('TakeScreenshot('+str(dest)+')')+',True)\nxbmc.sleep(700)')
 wait(dest.exists)
"""Offline AVI fixture: 640x360 MJPEG + actual 48kHz stereo signed PCM."""
import struct,math
from io import BytesIO
from PIL import Image
def chunk(name,data):return name+struct.pack('<I',len(data))+data+(b'\0' if len(data)%2 else b'')
def video(path):
 width,height,fps,count,rate=640,360,2,120,48000
 buf=BytesIO();Image.new('RGB',(width,height),(85,100,120)).save(buf,'JPEG');frame=buf.getvalue()
 # A quiet actual sine signal avoids treating an empty track as metadata-only.
 sound=b''.join(struct.pack('<hh',int(1000*math.sin(2*math.pi*440*i/rate)),int(1000*math.sin(2*math.pi*660*i/rate))) for i in range(rate//fps))
 avih=struct.pack('<14I',1000000//fps,len(frame)*fps+rate*4,0,16,count,0,2,max(len(frame),len(sound)),width,height,0,0,0,0)
 vh=struct.pack('<4s4sIHH8I4h',b'vids',b'MJPG',0,0,0,0,1,fps,0,count,len(frame),0xffffffff,0,0,0,width,height)
 vf=struct.pack('<IiiHH4sIiiII',40,width,height,1,24,b'MJPG',width*height*3,0,0,0,0)
 ah=struct.pack('<4s4sIHH8I4h',b'auds',b'\0'*4,0,0,0,0,4,rate*4,0,count*rate//fps,len(sound),0xffffffff,4,0,0,0,0)
 af=struct.pack('<HHIIHH',1,2,rate,rate*4,4,16)
 header=chunk(b'LIST',b'hdrl'+chunk(b'avih',avih)+chunk(b'LIST',b'strl'+chunk(b'strh',vh)+chunk(b'strf',vf))+chunk(b'LIST',b'strl'+chunk(b'strh',ah)+chunk(b'strf',af)))
 # Relative offsets from 'movi' fourcc, with actual per-chunk index.
 frames=[];index=[];offset=4
 for _ in range(count):
  for name,data in ((b'00dc',frame),(b'01wb',sound)):
   entry=chunk(name,data);frames.append(entry);index.append(struct.pack('<4sIII',name,16,offset,len(data)));offset+=len(entry)
 path.write_bytes(chunk(b'RIFF',b'AVI '+header+chunk(b'LIST',b'movi'+b''.join(frames))+chunk(b'idx1',b''.join(index))))

video(base/"fixture.avi")
def info(label):return rpc('XBMC.GetInfoLabels',{'labels':[label]})[label]
def selected():return info('Skin.String(MediaIconPack)')
def quiet():
 start=time.monotonic();stable=None
 while time.monotonic()-start<90:
  if cond('System.HasActiveModalDialog'):act('back');stable=None
  elif stable is None:stable=time.monotonic()
  elif time.monotonic()-stable>2:return
 raise AssertionError('Startup modal never settled')
def identity(skin):
 dest=out/'identity.json';drive('Path('+repr(str(dest))+').write_text(json.dumps({"skin":xbmc.getSkinDir()}))')
 assert json.loads(dest.read_text())['skin']==skin
def start_monitor():
 if (out/'stop-monitor').exists():(out/'stop-monitor').unlink()
 for qaid in SERVICE_QA:rpc('Addons.ExecuteAddon',{'addonid':qaid,'wait':False})
def open_settings():
 drive('xbmc.executebuiltin("ActivateWindow(skinsettings)",False)')
 trace=[]
 def record(step):
  labels=['System.CurrentControl','Container(9000).ListItem.Label']
  trace.append({'step':step,'labels':rpc('XBMC.GetInfoLabels',{'labels':labels}),'category6':cond('Container(9000).HasFocus(6)'),'category_focused':cond('Control.HasFocus(9000)'),'target_focused':cond('Control.HasFocus(6098)')})
 try:
  wait(lambda:cond('Window.IsActive(skinsettings)'))
  if cond('Control.HasFocus(6098)'):
   assert cond('Container(9000).HasFocus(6)'), 'Remembered target in wrong category'
   record('remembered-target');snap(skin+'-media-pack-control');return
  if not cond('Control.HasFocus(9000)'):
   act('left');record('return-to-sidebar')
  wait(lambda:cond('Control.HasFocus(9000)'));record('opened');snap(skin+'-settings-opened')
  for _ in range(20):
   if cond('Container(9000).HasFocus(6)'):break
   act('down');record('category-down')
  assert cond('Container(9000).HasFocus(6)'), 'Artwork category not selected'
  wait(lambda:cond('Control.IsVisible(600)') and cond('Control.IsVisible(6098)') and cond('Control.IsEnabled(6098)'))
  time.sleep(.8);snap(skin+'-artwork-category');act('right')
  wait(lambda:not cond('Control.HasFocus(9000)'),t=5);record('entered-artwork')
  for _ in range(50):
   if cond('Control.HasFocus(6098)'):break
   act('down');record('control-down')
  assert cond('Control.HasFocus(6098)'), 'Actual settings button unreachable'
  snap(skin+'-media-pack-control')
 except Exception:
  snap(skin+'-settings-failure')
  target=out/(skin+'-settings-focus.json')
  drive('Path('+repr(str(target))+').write_text(json.dumps({"skin":xbmc.getSkinDir(),"window":xbmcgui.getCurrentWindowId(),"dialog":xbmcgui.getCurrentWindowDialogId(),"focus":xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocusId(),"label":xbmc.getInfoLabel("System.CurrentControl")}))')
  raise
 finally:(out/(skin+'-settings-trace.json')).write_text(json.dumps(trace,indent=2))
def choose(expected):
 rows=inspect_module();ids=['']+[r['id'] for r in rows];index=ids.index(expected)
 report.setdefault('picker_choices',[]).append({'skin':skin,'id':expected,'index':index,'ids':ids,'names':['Built-in icons']+[r['name'] for r in rows]})
 open_settings();act('select');wait(lambda:cond('Window.IsVisible(selectdialog)'))
 # Real picker selection, not setting injection. Home resets native select list.
 act('firstpage')
 for _ in range(index):act('down')
 snap(skin+'-picker-'+str(index));act('select')
 wait(lambda:not cond('System.HasActiveModalDialog'))
 wait(lambda:selected()==expected)
def scheduler_evidence(label,paused):
 tag='original' if skin=='skin.foundry' else 'slate'
 path=out/(tag+'-scheduler.json')
 cutoff=time.monotonic()
 def ready():
  data=json.loads(path.read_text());sample=data['samples'][-1]
  return sample['at']>=cutoff and sample['skin']==skin and sample['paused']==paused and sample['setting']==selected() and (2 if paused else .2) in data['waits']
 wait(ready,t=12)
 data=json.loads(path.read_text());dest=out/(skin+'-'+label+'-scheduler.json');dest.write_text(json.dumps(data,indent=2))
 assert data['source']['service']==hashlib.sha256((addons/helper/'resources/lib/service.py').read_bytes()).hexdigest()
 report['scheduler_evidence'].append({'phase':label,'skin':skin,'file':dest.name,'paused':paused})
def inspect_module():
 dest=out/(skin+'-inventory.json')
 drive('import sys\nsys.path.insert(0,'+repr(str(addons/helper/'resources/lib'))+')\nfrom modules import media_pack\nrows=media_pack.discover()\nassert set(r["id"] for r in rows)=='+repr(set(PACKS[:2]+['resource.images.foundry.media.puremarks']))+'\nPath('+repr(str(dest))+').write_text(json.dumps(rows))')
 return json.loads(dest.read_text())
def show_fixture():
 # Custom content window invokes shipped MediaFlags include, unchanged; selected
 # metadata comes from real ListItem stream details, never injected Home values.
 folder=qa/'resources/skins/default/1080i';folder.mkdir(parents=True,exist_ok=True)
 (folder/'mediaqa.xml').write_text('''<window><defaultcontrol always="true">900</defaultcontrol><controls>
 <control type="list" id="900"><left>50</left><top>60</top><width>900</width><height>180</height><onup>900</onup><ondown>900</ondown><itemlayout height="60"><control type="label"><width>850</width><height>60</height><label>$INFO[ListItem.Label]</label><font>font13</font></control></itemlayout><focusedlayout height="60"><control type="label"><width>850</width><height>60</height><label>$INFO[ListItem.Label]</label><font>font13</font></control></focusedlayout></control>
 <control type="group"><top>350</top><include content="MediaFlags"/></control>
 <control type="group"><left>100</left><top>650</top><include content="StreamPilotFormatBadges"/></control>
 </controls></window>''')
 source='''import xbmc,xbmcgui,json,traceback
from pathlib import Path
OUT=Path('''+repr(str(out))+''')
class Fixture(xbmcgui.WindowXML):
 def onInit(self):
  a=xbmcgui.ListItem('QA full video');a.setInfo('video',{'title':'QA full video','mediatype':'movie'})
  a.getVideoInfoTag().addVideoStream(xbmc.VideoStreamDetail(1920,1080,1.78,60,'h264','','','hdr10'))
  a.addStreamInfo('audio',{'codec':'ac3','channels':6})
  b=xbmcgui.ListItem('QA no stream metadata');b.setInfo('video',{'title':'QA no stream metadata'})
  self.getControl(900).addItems([a,b]);self.setFocusId(900)
try:
 w=Fixture('mediaqa.xml','''+repr(str(qa))+''','default','1080i');w.show()
 (OUT/'fixture-ready').write_text('true')
 while not xbmc.Monitor().abortRequested() and not (OUT/'close-fixture').exists():xbmc.sleep(100)
 w.close()
except Exception:
 (OUT/'fixture-error.txt').write_text(traceback.format_exc());raise
finally:(OUT/'fixture-stopped').write_text('true')
'''
 for p in ('fixture-ready','fixture-stopped','close-fixture'):
  if (out/p).exists():(out/p).unlink()
 (qa/'default.py').write_text(source)
 rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.searchqa','wait':False});wait(lambda:(out/'fixture-ready').exists())
 try:wait(lambda:cond('Control.HasFocus(900)'))
 except Exception:
  snap(skin+'-fixture-focus-failure')
  evidence=out/(skin+'-fixture-focus-failure.json')
  drive('Path('+repr(str(evidence))+').write_text(json.dumps({"skin":xbmc.getSkinDir(),"window":xbmcgui.getCurrentWindowId(),"dialog":xbmcgui.getCurrentWindowDialogId(),"focus":xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocusId(),"video":xbmc.getCondVisibility("Player.HasVideo")}))')
  raise
def close_fixture():
 (out/'close-fixture').write_text('true');wait(lambda:(out/'fixture-stopped').exists());time.sleep(1)
def snapshot(name,expect_pack):
 started=time.monotonic()
 labels=['ListItem.'+x for x in ('VideoCodec','VideoResolution','HdrType','VideoAspect','AudioCodec','AudioChannels')]
 labels+=['Window(Home).Property('+prefix+'.list.'+c+'.'+field+')' for c in CATS for field in ('path','value')]
 current=[{}]
 fields=dict(zip(CATS,('VideoCodec','VideoResolution','HdrType','VideoAspect','AudioCodec','AudioChannels')))
 def fresh():
  values=rpc('XBMC.GetInfoLabels',{'labels':labels});current[0]=values
  if info('Window(Home).Property('+prefix+'.pack)')!=expect_pack:return False
  for category,field in fields.items():
   value=values['ListItem.'+field]
   expected_file=addons/expect_pack/'resources/flags'/category/(value.lower()+'.png') if expect_pack and value else None
   expected=bool(expected_file and expected_file.is_file())
   actual=values['Window(Home).Property('+prefix+'.list.'+category+'.path)']
   guard=values['Window(Home).Property('+prefix+'.list.'+category+'.value)']
   if expected:
    if actual!=str(expected_file) or guard!=value:return False
   elif actual or guard:return False
  return True
 # Service may be paused in Settings/custom window: 2s cadence plus 3s inventory
 # refresh. Poll native outputs, never call process() or mutate properties here.
 try:wait(fresh,t=8)
 finally:
  (out/(skin+'-'+name+'-freshness.json')).write_text(json.dumps({'elapsed_seconds':time.monotonic()-started,'bound_seconds':8,'last_values':current[0]},indent=2))
 time.sleep(.8)
 values=rpc('XBMC.GetInfoLabels',{'labels':labels})
 (out/(skin+'-'+name+'.json')).write_text(json.dumps(values,indent=2));snap(skin+'-'+name)
 row=[]
 with Image.open(out/(skin+'-'+name+'.png')).convert('RGB') as im:
  for index,category in enumerate(CATS):
   pixels=list(im.crop((1160+125*index,350,1275+125*index,415)).getdata())
   a=sum(r>210 and g<65 and b>120 for r,g,b in pixels)
   b=sum(r<65 and g>200 and b<130 for r,g,b in pixels)
   path=values['Window(Home).Property('+prefix+'.list.'+category+'.path)']
   expected=bool(expect_pack and path)
   row.append({'category':category,'a_pixels':a,'b_pixels':b,'expected':expected})
   if expected:
    assert (a if expect_pack==PACKS[0] else b)>2000,('Missing rendered category',category,row)
   else:assert a+b<100,('Unexpected/stale rendered category',category,row)
 (out/(skin+'-'+name+'-row-pixels.json')).write_text(json.dumps(row,indent=2))
 assert not (out/'monitor-error.txt').exists()
 return values
def colour_count(name,which):
 with Image.open(out/(skin+'-'+name+'.png')).convert('RGB') as im:
  return sum(1 for r,g,b in im.crop((0,320,1920,450)).getdata() if (r>210 and g<65 and b>120) if which=='a') if which=='a' else sum(1 for r,g,b in im.crop((0,320,1920,450)).getdata() if r<65 and g>200 and b<130)
import xml.etree.ElementTree as E
import hashlib
def card_geometry(path):
 root=E.parse(path).getroot()
 def number(node,tag,default=0):return int(node.findtext(tag,str(default)))
 def include(name):return root.find("include[@name='%s']"%name)
 def row(group):return any(n.text=='StreamPilotFormatBadges' for n in group.findall('include'))
 badges=include('StreamPilotFormatBadges').find('control')
 images=badges.findall("control[@type='image']")
 audio=[n for n in images if n.findtext('texture')=='$VAR[StreamPilotOSDAudio]']
 assert sorted(number(n,'width') for n in audio)==[76,160]
 assert all(number(n,'height')==54 and n.findtext('aspectratio')=='keep' for n in audio)
 assert [number(n,'width') for n in images[:2]]==[76,76]
 gap=number(badges,'itemgap');assert gap==10
 wide=next(n for n in audio if number(n,'width')==160)
 guard=next(n.text for n in wide.findall('visible') if '.audiocodec.wide' in n.text)
 assert all(token in guard for token in ('.audiocodec.wide),true)','.audiocodec.path))','Skin.String(MediaIconPack)','.audiocodec.value))'))
 narrow=next(n for n in audio if number(n,'width')==76)
 assert '!['+guard+']' in [n.text for n in narrow.findall('visible')]
 result={'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'wide_guard':guard,'cards':{}}
 for name in ('StreamPilotVODCard','StreamPilotLiveCard'):
  outer=include(name).find('control');left=number(outer,'left');height=number(outer,'height');top=1080-number(outer,'bottom')-height;width=1920-left-number(outer,'right')
  assert left==60 and width==1800
  variants={}
  for enabled in (False,True):
   audio_width=160 if enabled else 76;total=152+audio_width+2*gap
   if name=='StreamPilotLiveCard':
    details=next(n for n in outer.findall("control[@type='group']") if number(n,'left')==228 and number(n,'right')==(536 if enabled else 452))
    band=next(n for n in outer.findall("control[@type='group']") if row(n) and number(n,'width')==total)
    expected=guard if enabled else '!['+guard+']'
    assert details.findtext('visible')==expected and band.findtext('visible')==expected
    assert number(band,'right')==164 and number(band,'top')==115 and number(band,'height')==54
    bx=left+width-number(band,'right')-number(band,'width');by=top+number(band,'top')
   else:
    details=next(n for n in outer.findall("control[@type='group']") if number(n,'left')==272 and number(n,'right')==508)
    band=next(n for n in details.findall("control[@type='group']") if row(n))
    assert number(details,'top')==9 and number(band,'top')==74 and number(band,'height')==54
    bx=left+number(details,'left')+number(band,'left');by=top+number(details,'top')+number(band,'top')
   text_left=left+number(details,'left');text_right=left+width-number(details,'right')
   if name=='StreamPilotLiveCard':assert bx-text_right==40
   variants['wide' if enabled else 'narrow']={'audio':[bx+152+2*gap,by,audio_width,54],'row':[bx,by,total,54],'text':[text_left,top+number(details,'top'),text_right-text_left,number(details,'height')],'gap':bx-text_right if name=='StreamPilotLiveCard' else None}
  result['cards'][name]=variants
 return result

LONG_TITLE='A Very Long Film and Live Programme Title: The Remarkable Journey Across the Northern Mountains and Beyond'
LONG_PLOT='A long programme description verifies that enlarged audio badges remain separated from programme text, timing and seek status. The title and description must remain readable inside their own bounds.'
def show_card(card):
 folder=qa/'resources/skins/default/1080i'
 (folder/'cardqa.xml').write_text('<window><defaultcontrol always="true">900</defaultcontrol><controls><control type="button" id="900"><left>0</left><top>0</top><width>1</width><height>1</height><label /></control><include>'+card+'</include></controls></window>')
 for marker in ('fixture-ready','fixture-stopped','close-fixture'):(out/marker).unlink(missing_ok=True)
 source='''import xbmc,xbmcgui
from pathlib import Path
OUT=Path('''+repr(str(out))+''')
w=xbmcgui.WindowXML('cardqa.xml','''+repr(str(qa))+''','default','1080i')
try:
 w.show();(OUT/'fixture-ready').write_text('true')
 while not xbmc.Monitor().abortRequested() and not (OUT/'close-fixture').exists():xbmc.sleep(100)
finally:w.close();(OUT/'fixture-stopped').write_text('true')
'''
 (qa/'default.py').write_text(source);rpc('Addons.ExecuteAddon',{'addonid':qa.name,'wait':False})
 wait(lambda:(out/'fixture-ready').exists());wait(lambda:cond('Control.HasFocus(900)'))
def geometry_phase():
 geometry=card_geometry(addons/skin/'xml/Includes_StreamPilotOSD.xml')
 # First suite completed; no parallel rewritten QA script remains.
 rpc('Addons.SetAddonEnabled',{'addonid':ACTUAL_QA,'enabled':True});quiet()
 drive('xbmc.executebuiltin("Skin.SetString(MediaIconPack,'+ACTUAL_QA+')",True)\nxbmcgui.Window(10000).clearProperty("pause_services")')
 drive('item=xbmcgui.ListItem(label='+repr(LONG_TITLE)+',path='+repr(str(base/'geometry-ac3.mkv'))+')\nitem.setInfo("video",{"title":'+repr(LONG_TITLE)+',"plot":'+repr(LONG_PLOT)+',"mediatype":"movie"})\nxbmc.Player().play('+repr(str(base/'geometry-ac3.mkv'))+',item)')
 wait(lambda:cond('Window.IsActive(12005)') and not cond('System.HasActiveModalDialog'))
 wait(lambda:info('VideoPlayer.AudioCodec')=='ac3' and info('VideoPlayer.AudioChannels')=='2')
 wait(lambda:info('Window(Home).Property('+prefix+'.player.audiocodec.wide)')=='true')
 assert info('VideoPlayer.Title')==LONG_TITLE
 pages=[]
 for card in ('StreamPilotVODCard','StreamPilotLiveCard'):
  show_card(card)
  for variant in ('wide','builtin','missing-derivative','wide-restored'):
   derived=actual_qa/'resources/flags-osd/audiocodec/ac3.png'
   if variant=='builtin':drive('xbmc.executebuiltin("Skin.Reset(MediaIconPack)",True)')
   elif variant=='missing-derivative':
    held=derived.read_bytes();derived.unlink();drive('xbmc.executebuiltin("Skin.SetString(MediaIconPack,'+ACTUAL_QA+')",True)')
   elif variant=='wide-restored':derived.write_bytes(held)
   want=variant in ('wide','wide-restored')
   wait(lambda:(info('Window(Home).Property('+prefix+'.player.audiocodec.wide)')=='true')==want,t=8)
   time.sleep(.8);name=skin+'-'+card+'-'+variant;snap(name)
   path=info('Window(Home).Property('+prefix+'.player.audiocodec.path)')
   if want:assert path==str(derived)
   elif variant=='missing-derivative':assert path==str(actual_qa/'resources/flags/audiocodec/ac3.png')
   pages.append({'card':card,'variant':variant,'file':name+'.png','codec':info('VideoPlayer.AudioCodec'),'channels':info('VideoPlayer.AudioChannels'),'title':info('VideoPlayer.Title'),'path':path,'wide':want})
  close_fixture()
 act('stop');wait(lambda:not cond('Player.HasVideo'))
 receipts=[]
 for p in pages:
  im=Image.open(out/p['file']).convert('RGB');assert im.size==(1920,1080)
  islive=p['card']=='StreamPilotLiveCard';wide=p['wide'];width=160 if wide else 76
  # Shipped coordinates: Live right-anchored expanding row, VOD left-anchored.
  derived_geometry=geometry['cards'][p['card']]['wide' if wide else 'narrow']
  x,y,parsed_width,parsed_height=derived_geometry['audio'];assert parsed_width==width and parsed_height==54
  if p['variant']!='builtin':
   src=Image.open(Path(p['path'])).convert('RGBA');scale=min(width/src.width,54/src.height);w=round(src.width*scale);h=round(src.height*scale)
   mask=src.getchannel('A').resize((w,h),Image.Resampling.BILINEAR)
   region=im.crop((x+(width-w)//2,y+(54-h)//2,x+(width-w)//2+w,y+(54-h)//2+h))
   ink=[min(rgb)>170 for rgb,a in zip(region.getdata(),mask.getdata()) if a>180]
   assert ink and sum(ink)/len(ink)>.75,('Audio badge not rendered at expected bounds',p)
   p['visible_ink_recall']=sum(ink)/len(ink)
  # Source controls remain clipped to disjoint title/plot and badge rectangles.
  p['derived_xml_geometry']=derived_geometry
  p['text_right']=derived_geometry['text'][0]+derived_geometry['text'][2]
  p['badges_left']=derived_geometry['row'][0]
  if islive:assert p['badges_left']-p['text_right']==40
  p['screenshot_sha256']=hashlib.sha256((out/p['file']).read_bytes()).hexdigest();receipts.append(p)
 (out/(skin+'-audio-geometry.json')).write_text(json.dumps({'passed':True,'pages':receipts,'geometry_source':geometry,'scope':'Actual shipped card includes with native AC3/real title metadata, synthetic Live layout not PVR; visual title/time/status review required','original_pack_status':original_status,'source_receipts':actual_source_receipts,'derivative_receipts':derivative_receipts},indent=2))
 report['skins'][skin]['audio_geometry']=receipts
 rpc('Addons.SetAddonEnabled',{'addonid':ACTUAL_QA,'enabled':True})


def channel_phase():
 geometry=card_geometry(addons/skin/'xml/Includes_StreamPilotOSD.xml')
 tree=E.parse(addons/skin/'xml/Includes_StreamPilotOSD.xml')
 images=tree.getroot().find("include[@name='StreamPilotFormatBadges']").find('control').findall("control[@type='image']")
 control=next(n for n in images if n.findtext('texture')=='$VAR[StreamPilotOSDChannels]')
 assert control.findtext('width')=='76' and control.findtext('height')=='54' and control.findtext('aspectratio')=='keep'
 visibility=control.findtext('visible');assert all(x in visibility for x in ('.audiochannel.path','.audiochannel.value','Skin.String(MediaIconPack)','AudioChannels,2)','AudioChannels,6)','AudioChannels,8)'))
 rpc('Addons.SetAddonEnabled',{'addonid':ACTUAL_QA,'enabled':True});quiet()
 rows=[]
 for fixture in sorted(channel_fixture_receipts,key=lambda r:r['channels']):
  n=fixture['channels'];media=base/fixture['file']
  drive('xbmc.executebuiltin("Skin.SetString(MediaIconPack,'+ACTUAL_QA+')",True)\nxbmcgui.Window(10000).clearProperty("pause_services")')
  rpc('Player.Open',{'item':{'file':str(media)}})
  wait(lambda:cond('Window.IsActive(12005)') and not cond('System.HasActiveModalDialog'))
  wait(lambda:info('VideoPlayer.AudioChannels')==str(n))
  assert info('VideoPlayer.AudioCodec').startswith('pcm')
  wait(lambda:info('Window(Home).Property('+prefix+'.player.audiochannel.value)')==str(n) and bool(info('Window(Home).Property('+prefix+'.player.audiochannel.path)')),t=8)
  for card in ('StreamPilotVODCard','StreamPilotLiveCard'):
   show_card(card)
   for selected in (True,False):
    drive('xbmc.executebuiltin('+repr('Skin.SetString(MediaIconPack,'+ACTUAL_QA+')' if selected else 'Skin.Reset(MediaIconPack)')+',True)')
    wait(lambda:bool(info('Window(Home).Property('+prefix+'.player.audiochannel.path)'))==selected,t=8)
    wait(lambda:cond(visibility)==selected,t=8)
    wide=info('Window(Home).Property('+prefix+'.player.audiocodec.wide)')=='true'
    name=skin+'-'+card+'-channels-'+str(n)+('-selected' if selected else '-builtin');time.sleep(.8);snap(name)
    path=info('Window(Home).Property('+prefix+'.player.audiochannel.path)')
    row={'card':card,'channels':n,'actual_channels':info('VideoPlayer.AudioChannels'),'actual_codec':info('VideoPlayer.AudioCodec'),'selected':selected,'channel_control_visible':cond(visibility),'path':path,'file':name+'.png','fixture':fixture,'screenshot_sha256':hashlib.sha256((out/(name+'.png')).read_bytes()).hexdigest()}
    assert row['actual_channels']==str(n)
    if selected:
     assert path==str(actual_qa/'resources/flags/audiochannel'/f'{n}.png')
     src=Image.open(path).convert('RGBA');scale=min(76/src.width,54/src.height);w=round(src.width*scale);h=round(src.height*scale)
     gx,gy,_,_=geometry['cards'][card]['wide' if wide else 'narrow']['row'];x=gx+86+(76-w)//2;y=gy+(54-h)//2
     expected=src.resize((w,h),Image.Resampling.BILINEAR);cap=Image.open(out/(name+'.png')).convert('RGB');region=cap.crop((x,y,x+w,y+h))
     ink=[min(rgb)>170 for rgb,a in zip(region.getdata(),expected.getchannel('A').getdata()) if a>180]
     assert ink and sum(ink)/len(ink)>.75,('Channel glyph absent/clipped',row)
     row.update(visible_ink_recall=sum(ink)/len(ink),channel_rectangle=[x,y,w,h],source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
    else:assert not path and not row['channel_control_visible']
    rows.append(row)
   close_fixture()
  act('stop');wait(lambda:not cond('Player.HasVideo'))
 (out/(skin+'-channel-geometry.json')).write_text(json.dumps({'passed':True,'pages':rows,'geometry_source':geometry,'scope':'Actual native PCM channel metadata 1/3/4/5/7/10, shipped full cards in synthetic window; selected glyph pixels and unchanged builtin channel absence. Not PVR/hardware decoding.'},indent=2))
 report['skins'][skin]['channel_geometry']=rows
 rpc('Addons.SetAddonEnabled',{'addonid':ACTUAL_QA,'enabled':True})

report={'passed':False,'skins':{},'scheduler_evidence':[],'scope':'Geometry phase uses exact approved packaged artwork, unchanged add-on ID and manifest; synthetic Live card not PVR. Actual settings button/picker; unchanged production Service loop with actual media monitor; unrelated worker dependencies stubbed; shipped MediaFlags/StreamPilotFormatBadges includes in custom window, real ListItem metadata and offline native video. Catalog window, physical device, codecs other than native PCM/AC3 and unrelated service workers NOT certified by this runner.'}
try:
 wait(lambda:rpc('JSONRPC.Ping')=='pong');quiet()
 for aid in ['resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','resource.images.foundry.slate.icons','script.foundry.helper','script.foundry.slate.helper','skin.foundry','skin.foundry.slate','script.foundry.searchqa','script.foundry.searchdriver','script.foundry.mediapackmonitor','script.foundry.mediapackmonitorslate']+PACKS:
  rpc('Addons.SetAddonEnabled',{'addonid':aid,'enabled':True})
 rpc('Addons.SetAddonEnabled',{'addonid':PACKS[3],'enabled':False});rpc('Addons.SetAddonEnabled',{'addonid':ACTUAL_QA,'enabled':True});quiet();start_monitor()
 for skin,helper,prefix in [('skin.foundry','script.foundry.helper','foundry.media'),('skin.foundry.slate','script.foundry.slate.helper','foundry.slate.media')]:
  quiet();assert rpc('Settings.SetSettingValue',{'setting':'lookandfeel.skin','value':skin})
  wait(lambda:cond('Window.IsVisible(yesnodialog)'));focus_yes('Yes');act('select');quiet();identity(skin)
  report['skins'][skin]={'inventory':inspect_module()}
  open_settings();act('select');wait(lambda:cond('Window.IsVisible(selectdialog)'));act('back');assert selected()==''
  drive('xbmcgui.Window(10000).setProperty("pause_services","true")')
  choose(PACKS[0]);scheduler_evidence('paused-setting-selection',True);show_fixture();v=snapshot('pack-a',PACKS[0])
  for c in CATS:
   assert v['Window(Home).Property('+prefix+'.list.'+c+'.path)'],('Missing true metadata/category',c,v)
  assert colour_count('pack-a','a')>2000,'Actual include did not render A pixels'
  act('down');wait(lambda:info('ListItem.Label')=='QA no stream metadata');v=snapshot('empty',PACKS[0])
  assert all(not v['Window(Home).Property('+prefix+'.list.'+c+'.path)'] for c in CATS),'Stale empty-item art'
  close_fixture();choose(PACKS[1]);show_fixture();snapshot('pack-b',PACKS[1]);assert colour_count('pack-b','b')>2000
  close_fixture();choose('');show_fixture();snapshot('builtin','');assert colour_count('builtin','a')<100 and colour_count('builtin','b')<100;close_fixture()
  choose(PACKS[0]);show_fixture();snapshot('before-disable',PACKS[0])
  rpc('Addons.SetAddonEnabled',{'addonid':PACKS[0],'enabled':False});snapshot('disabled','');assert selected()==PACKS[0]
  assert colour_count('disabled','a')<100;rpc('Addons.SetAddonEnabled',{'addonid':PACKS[0],'enabled':True});snapshot('reenabled',PACKS[0])
  asset=addons/PACKS[0]/'resources/flags/videocodec/h264.png';asset_bytes=asset.read_bytes();asset.unlink()
  time.sleep(.5);v=snapshot('missing-file',PACKS[0]);assert not v['Window(Home).Property('+prefix+'.list.videocodec.path)']
  asset.write_bytes(asset_bytes);time.sleep(.5);v=snapshot('file-restored',PACKS[0]);assert v['Window(Home).Property('+prefix+'.list.videocodec.path)'];close_fixture()
  drive('xbmcgui.Window(10000).clearProperty("pause_services")')
  rpc('Player.Open',{'item':{'file':str(base/'fixture.avi')}});wait(lambda:cond('Player.HasVideo'))
  wait(lambda:cond('Window.IsActive(12005)') and not cond('System.HasActiveModalDialog'))
  snap(skin+'-playback-ready');show_fixture()
  wait(lambda:bool(info('Window(Home).Property('+prefix+'.player.videoresolution.path)')))
  snapshot('player-resolution',PACKS[0])
  resolution=info('VideoPlayer.VideoResolution');assert resolution
  assert info('Window(Home).Property('+prefix+'.player.videoresolution.value)')==resolution
  with Image.open(out/(skin+'-player-resolution.png')).convert('RGB') as im:
   assert sum(1 for r,g,b in im.crop((80,630,400,740)).getdata() if r>210 and g<65 and b>120)>300,'Shipped OSD include did not render pack resolution'
  report['skins'][skin]['actual_player_resolution']=resolution
  scheduler_evidence('active-video',False)
  wait(lambda:info('VideoPlayer.AudioChannels')=='2')
  codec=info('VideoPlayer.AudioCodec');assert codec.startswith('pcm'),codec
  for cat,field in [('audiocodec','AudioCodec'),('audiochannel','AudioChannels')]:
   assert info('Window(Home).Property('+prefix+'.player.'+cat+'.value)')==info('VideoPlayer.'+field)
   assert info('Window(Home).Property('+prefix+'.player.'+cat+'.path)')
  with Image.open(out/(skin+'-player-resolution.png')).convert('RGB') as im:
   for x0 in (100,186,272):
    assert sum(1 for r,g,b in im.crop((x0,650,x0+76,704)).getdata() if r>210 and g<65 and b>120)>300,'Actual OSD resolution/channel/PCM badge missing'
  report['skins'][skin]['actual_player_audio']={'codec':codec,'channels':2}
  close_fixture();act('stop');wait(lambda:not cond('Player.HasVideo'))
  # Same profile, no prepare/reseed; restarting demonstrates persisted Skin.String.
  drive('xbmc.executebuiltin("ActivateWindow(home)",False)');rpc('Application.Quit');k.wait(timeout=20)
  settings=userdata/'addon_data'/skin/'settings.xml';shutil.copy2(settings,out/(skin+'-saved-settings.xml'))
  assert any(n.get('id','').casefold()=='mediaiconpack' and n.text==PACKS[0] for n in E.parse(settings).getroot())
  k=launch();wait(lambda:rpc('JSONRPC.Ping')=='pong');quiet();identity(skin);assert selected()==PACKS[0];start_monitor()
  show_fixture();snapshot('after-restart',PACKS[0]);assert colour_count('after-restart','a')>2000;close_fixture()
  rpc('Application.Quit');k.wait(timeout=20)
  quarantine=base/(skin+'-removed-resource');(addons/PACKS[0]).rename(quarantine)
  k=launch();wait(lambda:rpc('JSONRPC.Ping')=='pong');quiet();identity(skin);start_monitor()
  assert selected()==PACKS[0];show_fixture();snapshot('missing-pack','')
  assert colour_count('missing-pack','a')<100
  report['skins'][skin]['missing_pack_enabled_state']=cond('System.AddonIsEnabled('+PACKS[0]+')')
  close_fixture();rpc('Application.Quit');k.wait(timeout=20)
  quarantine.rename(addons/PACKS[0]);k=launch();wait(lambda:rpc('JSONRPC.Ping')=='pong');quiet();identity(skin)
  rpc('Addons.SetAddonEnabled',{'addonid':PACKS[0],'enabled':True});start_monitor()
  geometry_phase()
  channel_phase()
  report['skins'][skin]['passed']=True
 report['passed']=True
except Exception:
 report['error']=traceback.format_exc();raise
finally:
 for f in (profile/'temp').glob('kodi*.log'):shutil.copy2(f,out/f.name)
 report['screenshots']=[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in out.glob('*.png')]
 report['source_receipts']=[]
 for aid in ('script.foundry.helper','script.foundry.slate.helper','skin.foundry','skin.foundry.slate'):
  paths=['resources/lib/modules/media_pack.py','resources/lib/modules/router.py','resources/lib/service.py'] if aid.startswith('script.') else ['xml/'+n+'.xml' for n in ('Home','Custom_1121_SearchResults','Includes','Includes_StreamPilotOSD','SkinSettings','Variables')]
  for relative in paths:
   f=addons/aid/relative
   report['source_receipts'].append({'file':aid+'/'+relative,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 report.update(release_source_mode='packaged-no-overlay' if not args.stage and not args.audio_stage else 'overlay-candidate',actual_pack_id=ACTUAL_QA,actual_pack_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
 (out/'native-report.json').write_text(json.dumps(report,indent=2))
 try:rpc('Application.Quit');k.wait(timeout=15)
 except Exception:
  k.terminate()
  try:k.wait(timeout=5)
  except Exception:k.kill();k.wait(timeout=5)
 x.terminate();x.wait(timeout=5);log.close()
print(json.dumps(report,indent=2))
