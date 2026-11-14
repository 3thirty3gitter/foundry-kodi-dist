"""Run isolated Kodi21+ action/resolver playback contracts under BOTH shipped skins."""
import argparse,importlib.util,json,os,shutil,signal,subprocess,tempfile,time,traceback,hashlib,sys,re,xml.etree.ElementTree as E
from PIL import Image,ImageStat
from pathlib import Path
from urllib.request import Request,urlopen
import native_action_fixture as contract

DRIVER=r'''
import sys,json,time,traceback
from pathlib import Path
import xbmc,xbmcgui
sys.path.insert(0,str(HELPER/'resources/lib'))
from modules.catalog_window import CatalogWindow
window=None
try:
 while not (BASE/'driver-done').exists():
  if window and window.closed:window.dispose();window=None
  if window:window.tick()
  snapshot={'catalog':None,'modal':bool(xbmc.getCondVisibility('System.HasActiveModalDialog')),'dialog_id':xbmcgui.getCurrentWindowDialogId()}
  if window:
   try:snapshot['catalog']={'native_ready':True,'focus':window.getFocusId()}
   except RuntimeError:snapshot['catalog']={'native_ready':False}
  p=BASE/'state.tmp';p.write_text(json.dumps(snapshot));p.replace(BASE/'state.json')
  command=BASE/'command.json'
  if command.exists():
   request=json.loads(command.read_text())
   if request['action']=='open-catalog':
    assert window is None
    xbmc.executebuiltin('ActivateWindow(settings)',True);xbmc.sleep(300)
    class Source:
     scope='fixture';path='fixture://contracts';content='movies';movie_submenu_label='Trending';movie_submenu_verified=False
     def load(self):raise AssertionError('Unexpected source reload')
    source=Source();source.initial={'items':[{'title':'Contract Movie','type':'movie','filetype':'file','file':request['file'],'plot':'Offline provider contract','art':{}}]}
    window=CatalogWindow('script-foundry-vod.xml',str(HELPER),'default','1080i',True,source=source,section='Movies',breadcrumb='Movies / Trending');window.show()
   elif request['action']=='capture':xbmc.executebuiltin('TakeScreenshot('+request['path']+')')
   else:raise AssertionError(request)
   command.unlink()
  xbmc.sleep(30)
except Exception:(BASE/'driver-error.txt').write_text(traceback.format_exc())
'''

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--display',default=':97');args=parser.parse_args()
 root=args.root.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
 spec=importlib.util.spec_from_file_location('render_util',root/'tools/render_interface.py');util=importlib.util.module_from_spec(spec);spec.loader.exec_module(util)
 port=util.available_port(0)
 with tempfile.TemporaryDirectory(prefix='foundry-action-contract-') as temp:
  base=Path(temp);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
  profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True);addons=profile/'addons';addons.mkdir()
  sources=[root.parent/'skin.foundry-nimbus',root.parent/'script.foundry.helper']+[root/'src'/x for x in ('skin.foundry.slate','script.foundry.slate.helper','resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','resource.images.foundry.slate.icons')]
  aids=[]
  for source in sources:
   aid=E.parse(source/'addon.xml').getroot().get('id');aids.append(aid);shutil.copytree(source,addons/aid,ignore=shutil.ignore_patterns('.git'))
  for helper in addons.glob('script.*helper'):
   tree=E.parse(helper/'addon.xml');r=tree.getroot()
   for n in list(r.findall("extension[@point='xbmc.service']")):r.remove(n)
   for n in list(r.find('requires')):
    if n.get('addon')!='xbmc.python':r.find('requires').remove(n)
   tree.write(helper/'addon.xml')
   # Isolate out-of-scope first-run installers/rebuilders in this temporary
   # profile only. Retain the actual router and playback modules byte-for-byte.
   (helper/'resources/lib/default.py').write_text("import sys\nfrom urllib.parse import parse_qsl\nmode=dict(parse_qsl(sys.argv[1] if len(sys.argv)>1 else '')).get('mode','check_for_update')\nif mode not in ('check_for_update','check_for_profile_change','configure_experience'):\n from modules.router import routing\n routing()\n",encoding='utf-8')
  for p in (home/'addons').glob('*/addon.xml'):
   tree=E.parse(p)
   for e in tree.getroot().findall("extension[@point='xbmc.service']"):tree.getroot().remove(e)
   tree.write(p)
  for aid in ('skin.foundry','skin.foundry.slate'):
   d=userdata/'addon_data'/aid;d.mkdir(parents=True);(d/'settings.xml').write_text('<settings><setting id="firsttimerun" type="bool">true</setting></settings>')
  (userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">%d</setting><setting id="services.webserverauthentication">false</setting></settings>'%port)
  util.video(base/'fixture.avi');contract.prepare(addons,base)
  driver=addons/'script.foundry.contractqa';driver.mkdir();(driver/'addon.xml').write_text('<addon id="script.foundry.contractqa" version="1.0.0" name="Contract driver" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
  probe_addon=addons/'script.foundry.contractidentity';probe_addon.mkdir()
  (probe_addon/'addon.xml').write_text('<addon id="script.foundry.contractidentity" version="1.0.0" name="Native skin identity probe" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
  env=dict(os.environ,HOME=str(base/'home'),DISPLAY=args.display,KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL');(base/'home').mkdir()
  log=(out/'console.log').open('w');x=subprocess.Popen(['Xvfb',args.display,'-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log);time.sleep(1)
  kodi=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=env,stdout=log,stderr=log,start_new_session=True)
  def rpc(method,params=None):
   data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode()
   with urlopen(Request('http://127.0.0.1:%d/jsonrpc'%port,data=data,headers={'Content-Type':'application/json'}),timeout=5) as r:result=json.load(r)
   if 'error' in result:raise RuntimeError(result['error'])
   return result.get('result')
  def wait(fn,timeout=45):
   deadline=time.monotonic()+timeout
   while time.monotonic()<deadline:
    if (base/'driver-error.txt').exists():raise AssertionError((base/'driver-error.txt').read_text())
    if fn():return
    time.sleep(.1)
   raise AssertionError('Native contract timeout')
  def ready():
   try:return rpc('JSONRPC.Ping')=='pong'
   except Exception:return False
  def cond(name):return rpc('XBMC.GetInfoBooleans',{'booleans':[name]}).get(name,False)
  def drain_modals():
   # A transient gap between queued first-start dialogs is not readiness.
   deadline=time.monotonic()+90;quiet=None
   while time.monotonic()<deadline:
    if cond('System.HasActiveModalDialog'):
     rpc('Input.Back');quiet=None
    elif quiet is None:quiet=time.monotonic()
    elif time.monotonic()-quiet>=2:return
    time.sleep(.2)
   raise AssertionError('Startup dialogs never reached a stable quiet interval')
  identity_sequence=0
  def identity(focus_yes=False):
   nonlocal identity_sequence
   identity_sequence+=1
   marker=base/('identity-%03d.json'%identity_sequence)
   logfile=profile/'temp/kodi.log'
   log_offset=len(logfile.read_text(encoding='utf-8',errors='replace'))
   body="import xbmc,xbmcgui,xbmcvfs,json,hashlib\nfrom pathlib import Path\n"
   if focus_yes:body+='xbmc.executebuiltin("SetFocus(11)",True)\nxbmc.sleep(100)\n'
   body+="skin_path=Path(xbmcvfs.translatePath('special://skin/')).resolve()\n"
   body+="data={'skin_id':xbmc.getSkinDir(),'skin_path':str(skin_path),'dialog_id':xbmcgui.getCurrentWindowDialogId(),'modal':bool(xbmc.getCondVisibility('System.HasActiveModalDialog')),'yesno':bool(xbmc.getCondVisibility('Window.IsActive(yesnodialog)')),'yes_focused':bool(xbmc.getCondVisibility('Control.HasFocus(11)')),'prompt':{str(i):xbmc.getInfoLabel('Control.GetLabel(%d)'%i) for i in (1,9,10,11)},'dialog_info_sha256':hashlib.sha256((skin_path/'xml/DialogVideoInfo.xml').read_bytes()).hexdigest()}\n"
   body+='Path(%r).write_text(json.dumps(data),encoding="utf-8")\n'%str(marker)
   error_marker=marker.with_suffix('.error.json')
   wrapped='import traceback\nfrom pathlib import Path\ntry:\n'+''.join(' '+line+'\n' for line in body.splitlines())+'except BaseException:\n Path(%r).write_text(traceback.format_exc(),encoding="utf-8")\n raise\n'%str(error_marker)
   (probe_addon/'default.py').write_text(wrapped,encoding='utf-8')
   rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.contractidentity','wait':True})
   def marker_ready():
    if error_marker.exists():raise AssertionError(error_marker.read_text(encoding='utf-8'))
    return marker.exists()
   wait(marker_ready)
   # A marker proves the body finished, not that Kodi released this script
   # instance. Wait for its native interpreter teardown before re-executing
   # the same addon; otherwise ExecuteAddon may stop the prior instance.
   def probe_exited():
    tail=logfile.read_text(encoding='utf-8',errors='replace')[log_offset:]
    pattern=r'T:(\d+)\s+debug <general>: CPythonInvoker\(\d+, '+re.escape(str(probe_addon/'default.py'))+r'\): script successfully run'
    matches=list(re.finditer(pattern,tail))
    return bool(matches and re.search(r'T:'+matches[-1].group(1)+r'\s+debug <general>: Python interpreter stopped',tail[matches[-1].end():]))
   wait(probe_exited,15)
   sample=json.loads(marker.read_text(encoding='utf-8'))
   sample['probe_sequence']=identity_sequence;sample['native_interpreter_exited']=True
   return sample
  def assert_identity(sample,skin):
   assert sample['skin_id']==skin,('Setting is not actual loaded skin',sample,skin)
   assert Path(sample['skin_path']).resolve()==(addons/skin).resolve(),('Wrong special skin path',sample)
   assert sample['dialog_info_sha256']==hashlib.sha256((addons/skin/'xml/DialogVideoInfo.xml').read_bytes()).hexdigest(),('Runtime skin XML differs',sample)
  def switch_skin(skin):
   drain_modals();assert not cond('System.HasActiveModalDialog')
   assert rpc('Settings.SetSettingValue',{'setting':'lookandfeel.skin','value':skin})
   wait(lambda:cond('Window.IsActive(yesnodialog)'))
   pending=identity();assert_identity(pending,skin)
   text=' '.join(pending['prompt'].values()).lower()
   assert 'keep' in text and ('skin' in text or 'change' in text),('Unexpected confirmation; refusing to accept',pending)
   assert pending['yesno'] and pending['prompt']['11'].strip().lower()=='yes',('Unexpected Yes control',pending)
   focused=identity(focus_yes=True);assert_identity(focused,skin)
   focused_text=' '.join(focused['prompt'].values()).lower()
   assert focused['yesno'] and focused['yes_focused'] and all(focused['prompt'][i]==pending['prompt'][i] for i in ('1','10','11')) and 'keep' in focused_text and ('skin' in focused_text or 'change' in focused_text),('Confirmation changed before acceptance',focused,pending)
   rpc('Input.Select');wait(lambda:not cond('System.HasActiveModalDialog'));drain_modals()
   loaded=identity();assert_identity(loaded,skin)
   assert not loaded['modal'] and rpc('Settings.GetSettingValue',{'setting':'lookandfeel.skin'})['value']==skin
   return {'skin':skin,'pending_confirmation':pending,'focused_confirmation':focused,'loaded':loaded}
  def state():
   try:return json.loads((base/'state.json').read_text())
   except (OSError,ValueError):return {}
  def command(action,**values):
   path=base/'command.json';tmp=base/'command.tmp';tmp.write_text(json.dumps(dict(values,action=action)));tmp.replace(path);wait(lambda:not path.exists())
  screenshots=[]
  def capture(name):
   path=out/(name+'.png');path.unlink(missing_ok=True);command('capture',path=str(path))
   def valid():
    try:
     with Image.open(path) as im:im.verify()
     return True
    except (OSError,ValueError,SyntaxError):return False
   wait(valid)
   data=path.read_bytes()
   with Image.open(path) as im:
    assert im.format=='PNG',('Not a PNG',path)
    width,height=im.size;stddev=ImageStat.Stat(im.convert('RGB')).stddev
   assert width>=640 and height>=360,('Undersized screenshot',path,width,height)
   assert max(stddev)>2,('Blank screenshot',path,stddev)
   receipt={'file':path.name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'width':width,'height':height,'rgb_stddev':stddev,'nonblank':True}
   screenshots.append(receipt)
   return receipt
  source_receipts=[]
  for skin_id,helper_id,skin_source,helper_source in [
   ('skin.foundry','script.foundry.helper',root.parent/'skin.foundry-nimbus',root.parent/'script.foundry.helper'),
   ('skin.foundry.slate','script.foundry.slate.helper',root/'src/skin.foundry.slate',root/'src/script.foundry.slate.helper')]:
   for aid,source,rel in [(helper_id,helper_source,'resources/lib/modules/'+n) for n in ('catalog_playback.py','catalog_window.py','router.py')]+[(skin_id,skin_source,'xml/DialogVideoInfo.xml')]:
    content=(source/rel).read_bytes();copied=(addons/aid/rel).read_bytes()
    assert content==copied,('Tested source differs from checkout',aid,rel)
    source_receipts.append({'addon':aid,'path':rel,'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),'profile_copy_verified':True})
  report={'schema_version':1,'passed':False,'source_receipts':source_receipts,'screenshots':screenshots,'cases':[],'fixture_isolation':{'disabled_setup_entry_modes':['check_for_update','check_for_profile_change','configure_experience'],'helper_service_disabled':True,'playback_router_source_unmodified':True},'scope':'Disposable native Kodi, both shipped skins and real playback helper entry routes, setup-only entry modes/service disabled; synthetic action and resolver addons/local video; no live FEN service or affected device validation.'}
  try:
   wait(ready,60);version=rpc('Application.GetProperties',{'properties':['version']})['version'];assert version['major']>=21,version;report['kodi']=version
   drain_modals()
   for aid in aids+list(contract.ADDONS)+['script.foundry.contractqa','script.foundry.contractidentity']:rpc('Addons.SetAddonEnabled',{'addonid':aid,'enabled':True})
   drain_modals();report['skin_identity_receipts']=[]
   report['cases']=[]
   for skin,helper in [('skin.foundry','script.foundry.helper'),('skin.foundry.slate','script.foundry.slate.helper')]:
    report['skin_identity_receipts'].append(switch_skin(skin))
    (base/'driver-done').unlink(missing_ok=True);(base/'state.json').unlink(missing_ok=True)
    (driver/'default.py').write_text('from pathlib import Path\nBASE=Path(%r)\nHELPER=Path(%r)\n'%(str(base),str(addons/helper))+DRIVER)
    driver_log_offset=len((profile/'temp/kodi.log').read_text(encoding='utf-8',errors='replace'))
    rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.contractqa','wait':False});wait(lambda:bool(state()))
    report['cases']+=contract.verify(rpc,base,out,command,state,wait,capture,skin)
    completed_identity=identity();assert_identity(completed_identity,skin);assert not completed_identity['modal']
    report['skin_identity_receipts'][-1]['after_cases']=completed_identity
    (base/'driver-done').write_text('done')
    def driver_exited():
     tail=(profile/'temp/kodi.log').read_text(encoding='utf-8',errors='replace')[driver_log_offset:]
     matches=list(re.finditer(r'T:(\d+)\s+debug <general>: CPythonInvoker\(\d+, '+re.escape(str(driver/'default.py'))+r'\): script successfully run',tail))
     return bool(matches and re.search(r'T:'+matches[-1].group(1)+r'\s+debug <general>: Python interpreter stopped',tail[matches[-1].end():]))
    wait(driver_exited,15)
   logs=(profile/'temp/kodi.log').read_text(errors='replace')
   forbidden=['one or more items failed to play','skipping unplayable item','PythonToCppException','Error Contents:','Traceback (most recent call last):']
   errors=[line for line in logs.splitlines() if any(f in line for f in forbidden)];assert not errors,errors
   expected={(skin,provider,route) for skin in ('skin.foundry','skin.foundry.slate') for provider in contract.ADDONS for route in ('info','context')}
   actual=[(case['skin'],case['provider'],case['route']) for case in report['cases']]
   assert len(actual)==8 and len(set(actual))==8 and set(actual)==expected,('Incomplete or duplicate contract cases',actual)
   assert len(source_receipts)==8 and len(screenshots)==12,('Missing evidence',len(source_receipts),len(screenshots))
   assert all(c['stop_without_failure'] and c['screenshots'] for c in report['cases'])
   assert len(report['skin_identity_receipts'])==2
   report['actual_skin_identity_gate']=True;report['exact_eight_cases']=True;report['playback_log_error_gate']=True;report['passed']=True
  except BaseException:
   report['passed']=False;report['error_trace']=traceback.format_exc()
   raise
  finally:
   for p in (profile/'temp').glob('kodi*.log'):shutil.copy2(p,out/p.name)
   (out/'native-contract-report.json').write_text(json.dumps(report,indent=2))
   # Reap both processes before TemporaryDirectory cleanup. A signalled but
   # running Kodi can still create profile files and mask the primary failure.
   try:
    try:rpc('Application.Quit')
    except Exception:pass
    try:kodi.wait(timeout=15)
    except subprocess.TimeoutExpired:
     try:os.killpg(kodi.pid,signal.SIGTERM)
     except ProcessLookupError:pass
     try:kodi.wait(timeout=10)
     except subprocess.TimeoutExpired:
      try:os.killpg(kodi.pid,signal.SIGKILL)
      except ProcessLookupError:pass
      kodi.wait(timeout=10)
   finally:
    x.terminate()
    try:x.wait(timeout=10)
    except subprocess.TimeoutExpired:x.kill();x.wait(timeout=10)
    log.close()
if __name__=='__main__':
 try:main()
 except BaseException:
  # Setup failures also emit an explicit failure receipt, never stale success.
  if '--output' in sys.argv:
   dest=Path(sys.argv[sys.argv.index('--output')+1]);dest.mkdir(parents=True,exist_ok=True);report_file=dest/'native-contract-report.json'
   try:failure=json.loads(report_file.read_text(encoding='utf-8'))
   except (OSError,ValueError):failure={'schema_version':1}
   failure.update(passed=False,error_trace=traceback.format_exc())
   report_file.write_text(json.dumps(failure,indent=2),encoding='utf-8')
  raise
