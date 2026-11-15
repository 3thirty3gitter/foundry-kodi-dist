"""Standalone native resource smoke gate, for tools/run_native_qa.sh.
Fixture controls prove resource decoding/compositing, NOT shipped skin coverage.
"""
import argparse,json,os,shutil,subprocess,tempfile,time,urllib.request,sys,hashlib
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
for marker in ('studio-inner.json','studio-native.png','native-studio-report.json'):
 (out/marker).unlink(missing_ok=True)
base=Path(tempfile.mkdtemp(prefix='studio-native-'));home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
profile=home/'portable_data';addons=profile/'addons';addons.mkdir(parents=True);user=profile/'userdata';user.mkdir()
pack=a.root/'src/resource.images.foundry.studios';shutil.copytree(pack,addons/pack.name)
assets=json.loads((pack/'provenance.json').read_text())['assets']
samples=[]
for mode in ('colour','monochrome'):
 for asset in assets:
  if not asset['alpha'] or asset['width']>300 or asset['height']>200:continue
  with Image.open(pack/'resources'/asset['file']) as im:
   pixels=list(im.convert('RGBA').getdata());ink=[p for p in pixels if p[3]>200]
   if len(ink)<30 or not any(0<p[3]<255 for p in pixels):continue
   coloured=sum(max(p[:3])-min(p[:3])>50 for p in ink)/len(ink)
   dark=sum(max(p[:3])<100 for p in ink)/len(ink)
   if (mode=='colour' and coloured>.15) or (mode=='monochrome' and coloured<.01 and dark>.5):
    samples.append(dict(asset,qa_mode=mode));break
 else:raise AssertionError('No representative '+mode)
qa=addons/'script.foundry.studioqa';qa.mkdir();(qa/'addon.xml').write_text('<addon id="script.foundry.studioqa" name="Studio QA" version="1.0.0" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
fixture_xml=qa/'resources/skins/default/1080i/studioqa.xml';fixture_xml.parent.mkdir(parents=True);fixture_xml.write_text('<window><defaultcontrol always="true">1</defaultcontrol><controls><control type="label" id="1"><left>0</left><top>0</top><width>1</width><height>1</height><label /></control></controls></window>')
payload='''import xbmc,xbmcgui,xbmcvfs,json,hashlib,traceback,time
from pathlib import Path
OUT=Path(OUT_VALUE); SAMPLES=SAMPLES_VALUE; ASSETS=ASSETS_VALUE
r={'passed':False,'scope':'Standalone fixture, not shipped skins'}
w=None
try:
 start=time.monotonic();verified=0
 for asset in ASSETS:
  assert time.monotonic()-start<180,'Resource verification budget exceeded'
  f=xbmcvfs.File('resource://resource.images.foundry.studios/'+asset['file']);data=bytes(f.readBytes());f.close()
  assert hashlib.sha256(data).hexdigest()==asset['sha256'],asset['file']
  verified+=1
 w=xbmcgui.WindowXMLDialog('studioqa.xml',QA_PATH,'default','1080i');w.show()
 # WindowXMLDialog supported constructor loads explicit 1080i skin resolution.
 for index,sample in enumerate(SAMPLES):
  y=150+index*250
  for x,bg in ((100,'FFFFFFFF'),(600,'FF202020')):
   w.addControl(xbmcgui.ControlImage(x,y,400,220,'white.png',colorDiffuse=bg))
   w.addControl(xbmcgui.ControlImage(x,y,sample['width'],sample['height'],'resource://resource.images.foundry.studios/'+sample['file']))
 w.addControl(xbmcgui.ControlLabel(100,700,800,60,'Unknown Studio (text fallback)',textColor='FFFFFFFF'))
 xbmc.sleep(1500);xbmc.executebuiltin('TakeScreenshot('+str(OUT/'studio-native.png')+')');xbmc.sleep(1000)
 r.update(passed=True,samples=SAMPLES,resource_hash_verified=verified,unknown_text_is_fixture_only=True)
except Exception:r['error']=traceback.format_exc()
finally:
 if w:w.close()
 (OUT/'studio-inner.json').write_text(json.dumps(r))
'''.replace('OUT_VALUE',repr(str(out))).replace('SAMPLES_VALUE',repr(samples)).replace('ASSETS_VALUE',repr(assets)).replace('QA_PATH',repr(str(qa)));(qa/'default.py').write_text(payload)
(user/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">18991</setting><setting id="services.webserverauthentication">false</setting></settings>')
env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'home/.config'),XDG_CACHE_HOME=str(base/'home/.cache'),DISPLAY=':98',KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL');(base/'home').mkdir();processes=[];report={'passed':False}
def rpc(method,params={}):
 req=urllib.request.Request('http://127.0.0.1:18991/jsonrpc',data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode(),headers={'Content-Type':'application/json'})
 result=json.load(urllib.request.urlopen(req,timeout=5));assert 'error' not in result,result;return result['result']
log=(out/'native-console.log').open('w')
try:
 processes.append(subprocess.Popen(['Xvfb',':98','-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log));time.sleep(1)
 processes.append(subprocess.Popen(['kodi','-p','-fs','--windowing=x11'],env=env,stdout=log,stderr=log))
 ready=False
 deadline=time.monotonic()+60
 while time.monotonic()<deadline:
  try:
   if rpc('JSONRPC.Ping')=='pong':ready=True;break
  except Exception:time.sleep(.3)
 assert ready,'JSONRPC startup timeout'
 for i in range(10):rpc('Input.Back');time.sleep(.2)
 for addon in (pack.name,qa.name):rpc('Addons.SetAddonEnabled',{'addonid':addon,'enabled':True})
 rpc('Addons.ExecuteAddon',{'addonid':qa.name,'wait':False})
 for i in range(700):
  if (out/'studio-inner.json').exists():break
  time.sleep(.3)
 inner=json.loads((out/'studio-inner.json').read_text());assert inner['passed'],inner
 cap=Image.open(out/'studio-native.png').convert('RGB');assert cap.size==(1920,1080)
 errors=[]
 for index,sample in enumerate(samples):
  src=Image.open(pack/'resources'/sample['file']).convert('RGBA');y=150+index*250
  for x,bg in ((100,(255,255,255)),(600,(32,32,32))):
   expected=Image.new('RGBA',src.size,bg+(255,));expected.alpha_composite(src);expected=expected.convert('RGB')
   observed=cap.crop((x,y,x+src.width,y+src.height))
   error=sum(abs(u-v) for p,q in zip(expected.getdata(),observed.getdata()) for u,v in zip(p,q))/(src.width*src.height*3);errors.append(error)
 assert max(errors)<12,errors
 report.update(passed=True,native=inner,mean_rgb_error_light_dark=errors,screenshot_sha256=hashlib.sha256((out/'studio-native.png').read_bytes()).hexdigest(),scope='Resource fixture only; shipped skin views require separate QA')
except Exception as e:report['error']=repr(e)
finally:
 try:rpc('Application.Quit')
 except Exception:pass
 for proc in reversed(processes):
  try:proc.wait(timeout=10)
  except subprocess.TimeoutExpired:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 for logfile in profile.rglob('kodi.log'):shutil.copyfile(logfile,out/'kodi.log')
 log.close()
 shutil.rmtree(base)

 (out/'native-studio-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report));sys.exit(0 if report['passed'] else 1)
