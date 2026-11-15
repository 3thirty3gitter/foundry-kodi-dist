"""Standalone native resource smoke gate, for tools/run_native_qa.sh.
Fixture controls prove resource decoding/compositing, NOT shipped skin coverage.
"""
import argparse,json,os,shutil,subprocess,tempfile,time,urllib.request,sys,hashlib
from pathlib import Path
from PIL import Image
"""Straight-RGBA GL_LINEAR pixel-centre sampling; no downsample prefilter.

Matches non-mipmapped Kodi Omega TextureGL.cpp lines65-85 and
GUITextureGL.cpp lines82-85 SRC_ALPHA compositing. PIL.resize(LANCZOS),
and even PIL.resize(BILINEAR), apply a downsampling prefilter unlike GL.
"""
import math
from PIL import Image
def gl_linear(image,size):
 source=image.convert('RGBA');W,H=source.size;w,h=size;pixels=source.load()
 output=Image.new('RGBA',size);dest=output.load()
 for y in range(h):
  fy=(y+.5)*H/h-.5;y0=math.floor(fy);dy=fy-y0
  for x in range(w):
   fx=(x+.5)*W/w-.5;x0=math.floor(fx);dx=fx-x0
   neighbors=[(pixels[min(W-1,max(0,x0+ix)),min(H-1,max(0,y0+iy))],(dx if ix else 1-dx)*(dy if iy else 1-dy)) for ix in (0,1) for iy in (0,1)]
   dest[x,y]=tuple(round(sum(pixel[c]*weight for pixel,weight in neighbors)) for c in range(4))
 return output

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pack',type=Path);a=p.parse_args()
out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
for prior in out.glob('mediaflags-page-*.png'):prior.unlink()
for marker in ('mediaflags-inner.json','mediaflags-native.png','native-mediaflags-report.json'):
 (out/marker).unlink(missing_ok=True)
base=Path(tempfile.mkdtemp(prefix='mediaflags-native-'));home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
profile=home/'portable_data';addons=profile/'addons';addons.mkdir(parents=True);user=profile/'userdata';user.mkdir()
pack=(a.pack or a.root/'src/resource.images.foundry.media.puremarks').resolve();shutil.copytree(pack,addons/pack.name)
manifest_path=pack/'resources/media-pack.json';manifest=json.loads(manifest_path.read_text())
assets=[]
listed={row['path']:row for row in manifest['assets']}
actual={str(p.relative_to(pack/'resources')).replace('\\','/') for p in (pack/'resources/flags').rglob('*.png')}
assert actual==set(listed),('Manifest/file mismatch',actual-set(listed),set(listed)-actual)
for relative in sorted(actual):
 p=pack/'resources'/relative
 assert p.resolve().is_relative_to((pack/'resources').resolve())
 sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==listed[relative]['sha256'],relative
 with Image.open(p) as im:
  im.load();assert im.format=='PNG';rgba=im.convert('RGBA');assert rgba.getchannel('A').getbbox(),relative
  assets.append({'file':relative,'sha256':sha,'width':im.width,'height':im.height})
assert assets,'No assets to verify'
samples=assets
for sample in samples:
 sample['cases']=[]
 for box_w,box_h,y in ((115,60,150),(76,54,330)):
  scale=min(box_w/sample['width'],box_h/sample['height'])
  width=round(sample['width']*scale);height=round(sample['height']*scale)
  sample['cases'].append({'box_width':box_w,'box_height':box_h,'width':width,'height':height,'y':y,'offset_x':(box_w-width)//2,'offset_y':(box_h-height)//2})
source_receipts=[{'file':str(p.relative_to(pack)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(pack.rglob('*')) if p.is_file()]
manifest_sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
qa=addons/'script.foundry.mediaflagsqa';qa.mkdir();Image.new('RGBA',(4,4),'white').save(qa/'qa-white.png');(qa/'addon.xml').write_text('<addon id="script.foundry.mediaflagsqa" name="Media flags QA" version="1.0.0" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
fixture_xml=qa/'resources/skins/default/1080i/mediaflagsqa.xml';fixture_xml.parent.mkdir(parents=True);fixture_xml.write_text('<window><defaultcontrol always="true">1</defaultcontrol><controls><control type="label" id="1"><left>0</left><top>0</top><width>1</width><height>1</height><label /></control></controls></window>')
payload='''import xbmc,xbmcgui,xbmcvfs,json,hashlib,traceback,time
from pathlib import Path
OUT=Path(OUT_VALUE); SAMPLES=SAMPLES_VALUE; ASSETS=ASSETS_VALUE
r={'passed':False,'scope':'Standalone fixture, not shipped skins'}
w=None
try:
 start=time.monotonic();verified=0
 for asset in ASSETS:
  assert time.monotonic()-start<180,'Resource verification budget exceeded'
  f=xbmcvfs.File('resource://resource.images.foundry.media.puremarks/'+asset['file']);data=bytes(f.readBytes());f.close()
  assert hashlib.sha256(data).hexdigest()==asset['sha256'],asset['file']
  verified+=1
 w=xbmcgui.WindowXMLDialog('mediaflagsqa.xml',QA_PATH,'default','1080i');w.show()
 # WindowXMLDialog supported constructor loads explicit 1080i skin resolution.
 pages=[]
 for index,sample in enumerate(SAMPLES):
  controls=[]
  for case in sample['cases']:
   for x,bg in ((100,'FFFFFFFF'),(600,'FF202020')):
    controls.append(xbmcgui.ControlImage(x,case['y'],case['box_width'],case['box_height'],str(Path(QA_VALUE)/'qa-white.png'),colorDiffuse=bg))
    controls.append(xbmcgui.ControlImage(x+case['offset_x'],case['y']+case['offset_y'],case['width'],case['height'],'resource://resource.images.foundry.media.puremarks/'+sample['file']))
   controls.append(xbmcgui.ControlLabel(100,case['y']+70,1000,40,str(case['box_width'])+' x '+str(case['box_height'])+' native control',textColor='FFFFFFFF'))
  controls.append(xbmcgui.ControlLabel(100,500,1600,60,sample['file'],textColor='FFFFFFFF'))
  for control in controls:w.addControl(control)
  name='mediaflags-page-%03d.png'%index
  xbmc.sleep(1000);xbmc.executebuiltin('TakeScreenshot('+str(OUT/name)+')');xbmc.sleep(1000)
  pages.append(name)
  for control in controls:w.removeControl(control)
 r.update(passed=True,samples=SAMPLES,pages=pages,resource_hash_verified=verified,full_format_coverage=False)
except Exception:r['error']=traceback.format_exc()
finally:
 if w:w.close()
 (OUT/'mediaflags-inner.json').write_text(json.dumps(r))
'''.replace('QA_VALUE',repr(str(qa))).replace('OUT_VALUE',repr(str(out))).replace('SAMPLES_VALUE',repr(samples)).replace('ASSETS_VALUE',repr(assets)).replace('QA_PATH',repr(str(qa)));(qa/'default.py').write_text(payload)
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
 for i in range(max(700,len(samples)*12)):
  if (out/'mediaflags-inner.json').exists():break
  time.sleep(.3)
 inner=json.loads((out/'mediaflags-inner.json').read_text());assert inner['passed'],inner
 assert len(inner['pages'])==len(samples);page_results=[]
 errors=[]
 for index,sample in enumerate(samples):
  cap=Image.open(out/inner['pages'][index]).convert('RGB');assert cap.size==(1920,1080)
  asset_errors=[];case_results=[]
  for case in sample['cases']:
   src=gl_linear(Image.open(pack/'resources'/sample['file']),(case['width'],case['height']))
   for x,bg in ((100,(255,255,255)),(600,(32,32,32))):
    expected=Image.new('RGBA',src.size,bg+(255,));expected.alpha_composite(src);expected=expected.convert('RGB')
    x+=case['offset_x'];y=case['y']+case['offset_y'];observed=cap.crop((x,y,x+src.width,y+src.height))
    deltas=[sum(abs(u-v) for u,v in zip(p,q))/3 for p,q in zip(expected.getdata(),observed.getdata())]
    alpha=list(src.getchannel('A').getdata());ink=[d for d,a in zip(deltas,alpha) if a>=128]
    assert ink,('No native-size ink',sample['file'],case)
    mean=sum(deltas)/len(deltas);ink_mean=sum(ink)/len(ink)
    case_results.append({'box':[case['box_width'],case['box_height']],'background':list(bg),'mean_rgb_error':mean,'ink_rgb_error':ink_mean,'visible_pixels':len(ink)})
    errors.append(mean);asset_errors.append(mean)
    assert mean<12 and ink_mean<30,('RGB/alpha rendering mismatch',sample['file'],case_results)
  page_results.append({'file':sample['file'],'source_dimensions':[sample['width'],sample['height']],'cases':case_results,'screenshot_sha256':hashlib.sha256((out/inner['pages'][index]).read_bytes()).hexdigest()})
 assert inner['resource_hash_verified']==len(assets)
 assert hashlib.sha256(manifest_path.read_bytes()).hexdigest()==manifest_sha,'Source manifest changed during QA'
 assert all(hashlib.sha256((pack/r['file']).read_bytes()).hexdigest()==r['sha256'] for r in source_receipts),'Source bytes changed during QA'
 report.update(passed=True,native=inner,pages=page_results,reference_sampling='GL_LINEAR pixel-centre straight-RGBA, no prefilter',source_receipts=source_receipts,manifest_sha256=manifest_sha,manifest_release_status=manifest.get('release_status'),asset_count=len(assets),scope='All included resource files decoded and composited in standalone Estuary fixture at115x60 and76x54 controls, light/dark. Not all format coverage, licensing approval, selector installation, or physical device proof. Manifest is unchanged.')
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

 (out/'native-mediaflags-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report));sys.exit(0 if report['passed'] else 1)
