"""Native opt-in program smoke, Linux Docker/Xvfb. No official tracking service.
Three disposable profiles; actual shipped setup code and native dialogs.
Mock script.simkl is deliberately not the official service. No live install/auth claim.
"""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, tempfile, time
import urllib.request
import xml.etree.ElementTree as ET
from PIL import ImageGrab, ImageStat

p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); root=a.root.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
source=root/'src/script.program.foundry-simkl'
report={'passed':False,'scope':'Actual native setup dialogs with empty disposable profiles and nonservice SIMKL fixture. No official install, pairing, tracking, account, Shield or live synchronization validation.','phases':[],'source_sha256':hashlib.sha256((source/'default.py').read_bytes()).hexdigest()}
port=18993; display=':96'

def rpc(method,params=None):
 data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode()
 value=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%d/jsonrpc'%port,data=data,headers={'Content-Type':'application/json'}),timeout=3))
 if 'error' in value: raise RuntimeError(str(value['error']))
 return value['result']
def wait(fn,timeout=40):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   if fn(): return
  except Exception: pass
  time.sleep(.2)
 raise AssertionError('Timed out waiting for native Kodi state')
def modal():
 return rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']})['System.HasActiveModalDialog']
def addon(aid):
 return rpc('Addons.GetAddonDetails',{'addonid':aid,'properties':['enabled','version']})['addon']
def snap(name):
 image=ImageGrab.grab(xdisplay=display).convert('RGB')
 assert image.size==(1920,1080), ('Unexpected native image dimensions',image.size)
 assert max(ImageStat.Stat(image).stddev)>3, 'Screenshot blank or nearly blank'
 path=out/(name+'.png');image.save(path)
 receipt={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'size':list(image.size),'stddev':ImageStat.Stat(image).stddev}
 report.setdefault('screenshots',[]).append(receipt)
 return receipt


x=k=None
try:
 log=(out/'native-console.log').open('w')
 x=subprocess.Popen(['Xvfb',display,'-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log)
 time.sleep(1)
 for phase in ('missing','disabled','enabled'):
  base=Path(tempfile.mkdtemp(prefix='foundry-simkl-'+phase+'-')); home=base/'kodi'
  shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
  # Suppress unrelated bundled services only in disposable system copy.
  for path in (home/'addons').glob('*/addon.xml'):
   tree=ET.parse(path); node=tree.getroot()
   for ext in list(node.findall("extension[@point='xbmc.service']")): node.remove(ext)
   tree.write(path)
  profile=home/'portable_data'; user=profile/'userdata'; addons=profile/'addons'
  user.mkdir(parents=True); addons.mkdir()
  shutil.copytree(source,addons/'script.program.foundry-simkl',ignore=shutil.ignore_patterns('__pycache__'))
  marker=user/'fixture-executed'
  if phase!='missing':
   mock=addons/'script.simkl'; mock.mkdir()
   (mock/'addon.xml').write_text('<addon id="script.simkl" version="4.0.0" name="SIMKL QA Fixture" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
   (mock/'default.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("unexpected execution")\n')
   (mock/'resources').mkdir()
   (mock/'resources/settings.xml').write_text('<settings><category label="QA only"><setting id="qa" type="bool" label="No account" default="false"/></category></settings>')
  observer=addons/'script.foundry.simkl.observer';observer.mkdir()
  (observer/'addon.xml').write_text('<addon id="script.foundry.simkl.observer" version="1.0.0" name="QA Observer" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
  observation=out/(phase+'-dialog.json')
  if observation.exists():observation.unlink()
  (observer/'default.py').write_text("import xbmc,xbmcgui,json\nfrom pathlib import Path\ndid=xbmcgui.getCurrentWindowDialogId()\nvalues=[]\nfor cid in range(1,31):\n for label in ('Control.GetLabel(%d)'%cid,'Control.GetLabel(%d).index(1)'%cid):\n  try: values.append({'control':cid,'method':label,'text':xbmc.getInfoLabel(label)})\n  except Exception: pass\nPath("+repr(str(observation))+").write_text(json.dumps({'dialog_id':did,'values':values}))\n")
  (user/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">'+str(port)+'</setting><setting id="services.webserverauthentication">false</setting><resolutions/><viewstates/><skinsettings/></settings>')
  (base/'home').mkdir()
  env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'home/.config'),XDG_CACHE_HOME=str(base/'home/.cache'),DISPLAY=display,KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL')
  k=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=env,stdout=log,stderr=log)
  wait(lambda:rpc('JSONRPC.Ping')=='pong')
  for _ in range(20):
   if modal(): rpc('Input.Back')
   time.sleep(.2)
  rpc('Addons.SetAddonEnabled',{'addonid':'script.program.foundry-simkl','enabled':True})
  rpc('Addons.SetAddonEnabled',{'addonid':'script.foundry.simkl.observer','enabled':True})
  if phase!='missing': rpc('Addons.SetAddonEnabled',{'addonid':'script.simkl','enabled':phase=='enabled'})
  time.sleep(1)
  assert not modal(), 'Setup unexpectedly opened without explicit execution'
  assert not marker.exists(), 'SIMKL fixture executed automatically'
  before=None if phase=='missing' else addon('script.simkl')['enabled']
  rpc('Addons.ExecuteAddon',{'addonid':'script.program.foundry-simkl','wait':False})
  wait(modal); time.sleep(.5)
  rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.simkl.observer','wait':False})
  wait(lambda:observation.exists())
  observed=json.loads(observation.read_text())
  expected_id=12002 if phase=='disabled' else 10100
  assert observed['dialog_id']==expected_id, ('Wrong native dialog',phase,observed)
  text=' '.join(' '.join(str(v['text']).split()) for v in observed['values'])
  assert 'Foundry SIMKL' in text, ('Wrong dialog heading',observed)
  assert 'queued history' in text and "Foundry won't sign you in" in text, ('Missing disclosure',observed)
  expected={'missing':'Install the official SIMKL tracker?', 'disabled':'SIMKL is disabled and will stay disabled.', 'enabled':'Open SIMKL settings?'}[phase]
  assert expected in text, ('Wrong phase dialog body',phase,observed)
  consent="Linked profiles may resume tracking and upload queued history. Foundry won't sign you in or change settings. "
  complete=("SIMKL is disabled and will stay disabled. Enable via My add-ons > Services. Linked profiles may resume tracking and upload queued history. Foundry won't sign you in or change settings." if phase=='disabled' else consent+expected)
  assert complete in text, ('Incomplete native disclosure text',phase,observed)
  if phase!='disabled':
   assert 'Cancel' in text, ('Cancel button missing',observed)
   assert ('Install' if phase=='missing' else 'Settings') in text, ('Action button missing',observed)
  snap(phase+'-dialog')
  # Back cancels actual yes/no native prompt (or closes disabled notice).
  rpc('Input.Back'); wait(lambda:not modal()); time.sleep(1)
  if phase=='missing':
   ids=rpc('Addons.GetAddons',{'enabled':'all','properties':['enabled']}).get('addons',[])
   assert not any(item['addonid']=='script.simkl' for item in ids), 'Cancel unexpectedly installed SIMKL'
  else: assert addon('script.simkl')['enabled']==before, 'Setup changed SIMKL enabled state'
  assert not marker.exists(), 'Setup executed SIMKL fixture'
  assert not (user/'addon_data/script.simkl/identity.json').exists(), 'Unexpected identity file'
  assert (addons/'script.program.foundry-simkl/default.py').read_bytes()==(source/'default.py').read_bytes()
  snap(phase+'-cancelled')
  report['phases'].append({'phase':phase,'dialog_id':observed['dialog_id'],'expected_body':expected,'verified_disclosure':True,'observation_file':observation.name,'source_sha256':report['source_sha256'],'native_dialog_opened':True,'cancelled':True,'enabled_before':before,'enabled_unchanged':True,'fixture_executed':False,'shipped_setup_unchanged':True})
  rpc('Application.Quit'); k.wait(timeout=30); k=None
  if (profile/'temp/kodi.log').exists(): shutil.copy(profile/'temp/kodi.log',out/(phase+'-kodi.log'))
 report['passed']=True
except Exception as e:
 report['error']=repr(e)
finally:
 if k is not None: k.terminate()
 if x is not None: x.terminate()
 (out/'native-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)


