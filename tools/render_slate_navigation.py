from pathlib import Path
import os,json,shutil,subprocess,time,urllib.request,xml.etree.ElementTree as E
import argparse,tempfile,hashlib,sys
from PIL import ImageGrab
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();ROOT=args.root.resolve();base=Path(tempfile.mkdtemp(prefix='slate-navigation-'));out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
# Evidence may be copied from an earlier published release. Never accept stale reports.
for stale in out.iterdir():
 if stale.is_file() and (stale.suffix == '.png' or stale.name in ('focus-report.json','focus-progress.json','native-report.json','restored.json')):
  stale.unlink()
profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True);addons=profile/'addons';addons.mkdir()
for source in [ROOT/'src/skin.foundry.slate',ROOT/'src/script.foundry.slate.helper',ROOT.parent/'skin.foundry-nimbus',ROOT.parent/'script.foundry.helper']+[ROOT/'src'/x for x in ('resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse')]:
 aid=E.parse(source/'addon.xml').getroot().get('id');shutil.copytree(source,addons/aid,ignore=shutil.ignore_patterns('.git'))
for helper in addons.glob('script.*helper'):
 t=E.parse(helper/'addon.xml');r=t.getroot()
 for n in list(r.findall("extension[@point='xbmc.service']")):r.remove(n)
 for n in list(r.find('requires')):
  if n.get('addon')!='xbmc.python':r.find('requires').remove(n)
 t.write(helper/'addon.xml');(helper/'resources/lib/default.py').write_text('# offline UI fixture only\n')
for p in (home/'addons').glob('*/addon.xml'):
 t=E.parse(p)
 for e in t.getroot().findall("extension[@point='xbmc.service']"):t.getroot().remove(e)
 t.write(p)
for aid in ('skin.foundry','skin.foundry.slate'):
 d=userdata/'addon_data'/aid;d.mkdir(parents=True);(d/'settings.xml').write_text('<settings><setting id="firsttimerun" type="bool">true</setting></settings>')
(userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">18991</setting><setting id="services.webserverauthentication">false</setting><resolutions/><viewstates/><skinsettings/></settings>')
qa=addons/'script.foundry.slate.navigationqa';qa.mkdir();(qa/'addon.xml').write_text('<addon id="script.foundry.slate.navigationqa" version="1.0.0" name="Slate QA" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>');(qa/'default.py').write_text("\nimport xbmc,xbmcgui,json,time,traceback\nfrom pathlib import Path\nOUT=Path(__OUT__)\nreport={'passed':False,'trace':[],'scope':'Native desktop shipped Home XML with offline helpers suppressed. Search uses configured built-in window1107. No Shield/live-provider/widget population claim.'}\ndef focus():return xbmcgui.Window(10000).getFocusId()\ndef require(ok,msg):\n if not ok:raise AssertionError(msg)\ndef step(action):\n xbmc.executebuiltin('Action('+action+')',False);xbmc.sleep(550)\n report['trace'].append({'action':action,'focus':focus(),'window':xbmcgui.getCurrentWindowId(),'modal':xbmcgui.getCurrentWindowDialogId()})\n (OUT/'focus-progress.json').write_text(json.dumps(report,indent=2))\ndef snap(name):\n xbmc.executebuiltin('TakeScreenshot('+str(OUT/(name+'.png'))+')');xbmc.sleep(700)\ntry:\n require(xbmc.getSkinDir()=='skin.foundry.slate','Wrong active skin')\n xbmc.executebuiltin('Skin.SetString(SearchSetting,1)',True)\n xbmc.executebuiltin('ActivateWindow(Home)',True);xbmc.sleep(700)\n xbmc.executebuiltin('SetFocus(9000,0,absolute)',True);xbmc.sleep(700)\n require(focus()==9000,'Main menu not focused')\n snap('slate-menu')\n for cycle in range(3):\n  for n in range(50):\n   step('Down')\n   if focus()!=9000:break\n  require(focus() in (801,802,803),'Down did not reach footer: '+str(focus()))\n  for _ in range(2):\n   if focus()==801:break\n   step('Left')\n  require(focus()==801,'Footer Left did not reach Power')\n  snap('footer-power-'+str(cycle))\n  step('Right');require(focus()==802,'Right did not reach Settings');snap('footer-settings-'+str(cycle))\n  step('Select');require(xbmcgui.getCurrentWindowId()==10004,'Settings did not activate');snap('settings-window-'+str(cycle))\n  step('Back');require(xbmcgui.getCurrentWindowId()==10000,'Settings Back did not return home')\n  require(focus()==802,'Settings return lost focus')\n  step('Right');require(focus()==803,'Right did not reach Search');snap('footer-search-'+str(cycle))\n  step('Select');require(xbmcgui.getCurrentWindowId()==11107 or xbmcgui.getCurrentWindowDialogId()==11107,'Configured search did not activate');snap('search-window-'+str(cycle))\n  step('Back');require(xbmcgui.getCurrentWindowId()==10000,'Search Back did not return Home')\n  require(focus()==803,'Search return lost focus')\n  step('Up');require(focus()==9000,'Footer Up did not return menu')\n  step('Down');require(focus()==803 or focus()==801,'Menu bottom did not reenter footer')\n  step('Back');require(focus()==9000,'Footer Back did not return menu')\n  xbmc.executebuiltin('SetFocus(9000,0,absolute)',True);xbmc.sleep(500)\n\n def toggle_icons(expected_hidden):\n  xbmc.executebuiltin('ActivateWindow(skinsettings)',False);xbmc.sleep(900)\n  xbmc.executebuiltin('SetFocus(9000,0,absolute)',False);xbmc.sleep(300)\n  xbmc.executebuiltin('SetFocus(6243)',False);xbmc.sleep(300)\n  require(xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocusId()==6243,'Icon setting radio not reachable')\n  snap('icons-setting-before-'+str(expected_hidden))\n  xbmc.executebuiltin('Action(Select)',False);xbmc.sleep(500)\n  require(xbmc.getCondVisibility('Skin.HasSetting(SlateHideMainMenuIcons)')==expected_hidden,'Actual radio did not toggle state')\n  report.setdefault('radio_visual_states',[]).append({'hidden':expected_hidden,'window':xbmcgui.getCurrentWindowId(),'focus':6243})\n  snap('icons-setting-after-'+str(expected_hidden))\n  xbmc.executebuiltin('ActivateWindow(Home)',False);xbmc.sleep(700)\n  xbmc.executebuiltin('SetFocus(9000,0,absolute)',False);xbmc.sleep(500)\n  snap('icons-hidden' if expected_hidden else 'icons-shown')\n require(not xbmc.getCondVisibility('Skin.HasSetting(SlateHideMainMenuIcons)'),'Default icons unexpectedly hidden')\n for state in (True,False,True,False,True):\n  toggle_icons(state)\n  xbmc.executebuiltin('ActivateWindow(skinsettings)',False);xbmc.sleep(500)\n  xbmc.executebuiltin('ActivateWindow(Home)',False);xbmc.sleep(500)\n  require(xbmc.getCondVisibility('Skin.HasSetting(SlateHideMainMenuIcons)')==state,'Setting lost after window reopen')\n report['real_radio_toggles']=5\n report['hidden_before_restart']=True\n report['passed']=True\nexcept Exception:\n report['error']=traceback.format_exc()\nfinally:\n (OUT/'focus-report.json').write_text(json.dumps(report,indent=2))\n".replace('__OUT__',repr(str(out))))
env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'home/.config'),XDG_CACHE_HOME=str(base/'home/.cache'),DISPLAY=':98',KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL');(base/'home').mkdir()
log=(out/'native-console.log').open('w');x=subprocess.Popen(['Xvfb',':98','-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log);time.sleep(1)
k=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=env,stdout=log,stderr=log)
def rpc(method,params=None):
 data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode();r=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18991/jsonrpc',data=data,headers={'Content-Type':'application/json'}),timeout=5))
 if 'error' in r: raise RuntimeError((method,params,r['error']))
 return r['result']
def wait(fn,t=45):
 end=time.monotonic()+t
 while time.monotonic()<end:
  try:
   if fn():return
  except Exception:pass
  time.sleep(.3)
 raise AssertionError('timeout')
def assert_saved_icon_setting(path,expected,phase):
 raw=path.read_bytes()
 (out/('skin-settings-'+phase+'.xml')).write_bytes(raw)
 root=E.fromstring(raw)
 matches=[n for n in root.findall('setting') if n.get('id','').casefold()=='slatehidemainmenuicons']
 assert len(matches)==1,('Missing or duplicate persisted icon setting',[(n.get('id'),n.text) for n in matches])
 n=matches[0]
 assert n.get('type')=='bool',('Wrong saved setting type',n.attrib)
 assert (n.text or '').strip()==expected,('Wrong saved icon preference',n.attrib,n.text,expected)
 report.setdefault('saved_icon_settings',[]).append({'phase':phase,'id':n.get('id'),'value':n.text})

def modal():return rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']}).get('System.HasActiveModalDialog')
report={'scope':'Offline native Home/navigation/switch-back smoke; helper services/setup suppressed in disposable copies only. Not a full runtime/coexistence certification.','passed':False}
try:
 wait(lambda:rpc('JSONRPC.Ping')=='pong');report['kodi']=rpc('Application.GetProperties',{'properties':['version']})
 for _ in range(20):
  if modal():rpc('Input.Back')
  time.sleep(.3)
 for aid in ('resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','script.foundry.helper','script.foundry.slate.helper','skin.foundry','skin.foundry.slate','script.foundry.slate.navigationqa'):rpc('Addons.SetAddonEnabled',{'addonid':aid,'enabled':True})
 for aid,label in [('skin.foundry.slate','slate')]:
  assert rpc('Settings.SetSettingValue',{'setting':'lookandfeel.skin','value':aid})
  wait(modal);rpc('Input.Left');rpc('Input.Select');wait(lambda:not modal());time.sleep(3)
  assert rpc('Settings.GetSettingValue',{'setting':'lookandfeel.skin'})['value']==aid
  rpc('GUI.ActivateWindow',{'window':'home'});time.sleep(1)
  ImageGrab.grab(xdisplay=':98').save(out/(label+'.png'))
  rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.slate.navigationqa','wait':False})
  wait(lambda:(out/'focus-report.json').exists(),180)
  report['navigation']=json.loads((out/'focus-report.json').read_text())
  assert report['navigation']['passed'],report['navigation'].get('error')
  shipped=ROOT/'src/skin.foundry.slate/xml/Home.xml'
  assert (addons/'skin.foundry.slate/xml/Home.xml').read_bytes()==shipped.read_bytes()
  report['home_sha256']=hashlib.sha256(shipped.read_bytes()).hexdigest()
  from PIL import Image,ImageChops,ImageStat
  baseline=Image.open(out/'slate-menu.png').convert('RGB')
  # Assert rendered radio polarity externally: no getControl binding inside Kodi.
  # In shipped focused switch, on knob is right/dark, off knob left/dim.
  report['radio_visual_polarity']={}
  for hidden in (True,False):
   im=Image.open(out/('icons-setting-after-'+str(hidden)+'.png')).convert('RGB')
   assert im.size==(1920,1080),'Fixture coordinates require 1080p native render'
   left=sum(ImageStat.Stat(im.crop((1807,163,1815,171))).mean)
   right=sum(ImageStat.Stat(im.crop((1835,163,1843,171))).mean)
   assert (right-left>5 if hidden else left-right>15),('Rendered radio polarity wrong',hidden,left,right)
   report['radio_visual_polarity'][str(hidden)]={'left_rgb_sum':left,'right_rgb_sum':right}
  on=Image.open(out/'icons-setting-after-False.png').convert('RGB').crop((1790,145,1860,190))
  off=Image.open(out/'icons-setting-after-True.png').convert('RGB').crop((1790,145,1860,190))
  assert sum(ImageStat.Stat(ImageChops.difference(on,off)).sum)>1000,'Radio pixels never changed'
  report['footer_visual_differences']={}
  for i,button in enumerate(('power','settings','search')):
   focused=Image.open(out/('footer-'+button+'-0.png')).convert('RGB')
   box=(55+92*i,885,145+92*i,975)
   diff=ImageChops.difference(baseline.crop(box),focused.crop(box))
   score=sum(ImageStat.Stat(diff).sum)
   assert score>1000,('No visible footer focus effect',button,score)
   report['footer_visual_differences'][button]=score
  # Stop gracefully so skin settings are persisted, then restart exact disposable profile.
  rpc('Application.Quit');k.wait(timeout=30)
  setting=userdata/'addon_data/skin.foundry.slate/settings.xml'
  assert_saved_icon_setting(setting,'true','hidden-before-restart')
  k=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=env,stdout=log,stderr=log)
  wait(lambda:rpc('JSONRPC.Ping')=='pong');time.sleep(4)
  assert rpc('XBMC.GetInfoBooleans',{'booleans':['Skin.HasSetting(SlateHideMainMenuIcons)']})['Skin.HasSetting(SlateHideMainMenuIcons)']
  report['hidden_persisted_after_restart']=True
  # Reset through the actual radio again, NOT via Skin.SetBool/test simulation.
  reset=qa/'restore.py'
  reset.write_text("import xbmc,xbmcgui,json\nfrom pathlib import Path\nxbmc.executebuiltin('ActivateWindow(skinsettings)',False);xbmc.sleep(900)\nxbmc.executebuiltin('SetFocus(9000,0,absolute)',False);xbmc.sleep(300)\nxbmc.executebuiltin('SetFocus(6243)',False);xbmc.sleep(300)\nassert xbmcgui.Window(xbmcgui.getCurrentWindowId()).getFocusId()==6243\nxbmc.executebuiltin('Action(Select)',False);xbmc.sleep(500)\nassert not xbmc.getCondVisibility('Skin.HasSetting(SlateHideMainMenuIcons)')\nxbmc.executebuiltin('ActivateWindow(Home)',False);xbmc.sleep(500)\nPath("+repr(str(out/'restored.json'))+").write_text('true')\n")
  (qa/'default.py').write_text(reset.read_text())
  rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.slate.navigationqa','wait':False})
  wait(lambda:(out/'restored.json').exists())
  rpc('Application.Quit');k.wait(timeout=30)
  assert_saved_icon_setting(setting,'false','shown-before-restart')
  k=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=env,stdout=log,stderr=log)
  wait(lambda:rpc('JSONRPC.Ping')=='pong');time.sleep(4)
  assert not rpc('XBMC.GetInfoBooleans',{'booleans':['Skin.HasSetting(SlateHideMainMenuIcons)']})['Skin.HasSetting(SlateHideMainMenuIcons)']
  report['shown_persisted_after_second_restart']=True

 report['passed']=True
except Exception as e:report['error']=repr(e)
finally:
 
 for logfile in Path('/tmp').rglob('kodi.log'):
  shutil.copy(logfile,out/('diagnostic-'+str(logfile).replace('/','_')))
 ImageGrab.grab(xdisplay=':98').save(out/'final-screen.png')
 (out/'native-report.json').write_text(json.dumps(report,indent=2));k.terminate();x.terminate();time.sleep(1)
 if (profile/'temp/kodi.log').exists():shutil.copy(profile/'temp/kodi.log',out/'kodi.log')
print(json.dumps(report,indent=2))




sys.exit(0 if report['passed'] else 1)
