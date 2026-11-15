from pathlib import Path
import os,json,shutil,subprocess,time,urllib.request,xml.etree.ElementTree as E
import argparse,tempfile,hashlib,sys
from PIL import ImageGrab
parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();ROOT=args.root.resolve();base=Path(tempfile.mkdtemp(prefix='slate-icons-'));out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
# Evidence may be copied from an earlier published release. Never accept stale reports.
for stale in out.iterdir():
 if stale.is_file() and (stale.suffix == '.png' or stale.name in ('focus-report.json','focus-progress.json','native-report.json','restored.json','icon-report.json','native-icon-report.json')):
  stale.unlink()
profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True);addons=profile/'addons';addons.mkdir()
for source in [ROOT/'src/skin.foundry.slate',ROOT/'src/script.foundry.slate.helper',ROOT.parent/'skin.foundry-nimbus',ROOT.parent/'script.foundry.helper']+[ROOT/'src'/x for x in ('resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','resource.images.foundry.slate.icons')]:
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
(userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="myvideos.extractthumb">false</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">18991</setting><setting id="services.webserverauthentication">false</setting><resolutions/><viewstates/><skinsettings/></settings>')
import wave,struct,math,re
qa=addons/'script.foundry.slate.iconqa';qa.mkdir()
(qa/'addon.xml').write_text('<addon id="script.foundry.slate.iconqa" version="1.0.0" name="Slate Icon QA" provider-name="QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/></addon>')
fixture=base/'video-fixture';fixture.mkdir();(fixture/'A folder without artwork').mkdir();(fixture/'B movie without artwork.mp4').write_bytes(b'')
from io import BytesIO
from PIL import Image
# Fixture copied verbatim from tools/render_interface.py: chunk/video
def chunk(name,data):return name+struct.pack('<I',len(data))+data+(b'\0' if len(data)%2 else b'')
def video(path):
    width,height,fps,count=640,360,2,120
    out=BytesIO();Image.new('RGB',(width,height),(85,100,120)).save(out,format='JPEG');frame=out.getvalue()
    avih=struct.pack('<14I',1000000//fps,len(frame)*fps,0,16,count,0,1,len(frame),width,height,0,0,0,0)
    strh=struct.pack('<4s4sIHH8I4h',b'vids',b'MJPG',0,0,0,0,1,fps,0,count,len(frame),0xffffffff,0,0,0,width,height)
    strf=struct.pack('<IiiHH4sIiiII',40,width,height,1,24,b'MJPG',width*height*3,0,0,0,0)
    header=chunk(b'LIST',b'hdrl'+chunk(b'avih',avih)+chunk(b'LIST',b'strl'+chunk(b'strh',strh)+chunk(b'strf',strf)))
    data=b'AVI '+header+chunk(b'LIST',b'movi'+chunk(b'00dc',frame)*count)
    path.write_bytes(chunk(b'RIFF',data))
video_path=base/'offline-video.avi'
video(video_path)
payload="import xbmc,xbmcgui,xbmcvfs,json,threading,traceback\nfrom pathlib import Path\nOUT=Path(__OUT__)\nreport={'passed':False,'surfaces':[],'resolved':0}\ndef snap(name):\n xbmc.sleep(1100)\n xbmc.executebuiltin('TakeScreenshot('+str(OUT/(name+'.png'))+')')\n xbmc.sleep(800)\n report['surfaces'].append({'name':name,'window':xbmcgui.getCurrentWindowId(),'dialog':xbmcgui.getCurrentWindowDialogId()})\ndef activate(name):\n xbmc.executebuiltin('ActivateWindow('+name+')');xbmc.sleep(900)\ntry:\n assert xbmc.getSkinDir()=='skin.foundry.slate'\n report['actual_skin']=xbmc.getSkinDir()\n report['actual_skin_path']=xbmcvfs.translatePath('special://skin/')\n assert 'skin.foundry.slate' in report['actual_skin_path']\n pack='resource://resource.images.foundry.slate.icons/'\n manifest=json.loads(Path(__MANIFEST__).read_text())\n paths=['aliases/'+x for x in manifest['texture_aliases']]+['aliases/'+x for x in manifest['system_rows']]+['weather/'+x for x in manifest['weather']]\n for path in paths:\n  f=xbmcvfs.File(pack+path);raw=f.readBytes();f.close()\n  assert bytes(raw[:8])==bytes([137,80,78,71,13,10,26,10]),'Failed resource URI: '+path\n  report['resolved']+=1\n activate('Home');assert xbmcgui.getCurrentWindowId()==10000;snap('icons-home')\n activate('Settings');assert xbmcgui.getCurrentWindowId()==10004;snap('icons-settings')\n activate('skinsettings');snap('icons-skinsettings')\n activate('Home')\n result={}\n def keyboard():result['value']=xbmcgui.Dialog().input('Slate icon QA',defaultt='Keyboard icon test')\n worker=threading.Thread(target=keyboard);worker.start();xbmc.sleep(1100)\n assert xbmcgui.getCurrentWindowDialogId()==10103,'Actual keyboard not open'\n snap('icons-keyboard');xbmc.executebuiltin('Action(Back)');worker.join(10);assert not worker.is_alive()\n activate('Videos,'+__FIXTURE__+',return')\n assert xbmcgui.getCurrentWindowId() in (10024,10025),'Actual video browser not open'\n for _ in range(100):\n  if int(xbmc.getInfoLabel('Container.NumItems') or '0')>=2:break\n  xbmc.sleep(200)\n assert int(xbmc.getInfoLabel('Container.NumItems') or '0')>=2,'Placeholder list never populated'\n # Offline helper is suppressed; resolve its routing handshake for this local fixture only.\n home=xbmcgui.Window(10000)\n home.clearProperty('foundry.slate.catalog.routing')\n home.setProperty('foundry.slate.catalog.handled_path',xbmc.getInfoLabel('Container.FolderPath'))\n xbmc.sleep(500)\n assert not xbmc.getCondVisibility('Container.IsUpdating'),'Browser still updating'\n report['offline_catalog_handshake']=True\n snap('icons-default-placeholders')\n # Drive shipped native list, no custom test image controls or assigned artwork.\n xbmc.executebuiltin('Container.SetViewMode(52)');xbmc.sleep(700)\n xbmc.executebuiltin('SetFocus(52)');xbmc.sleep(300)\n assert xbmc.getCondVisibility('Control.IsVisible(52)'),'Actual icon wall unavailable for local files'\n assert xbmc.getCondVisibility('Control.HasFocus(52)'),'Icon wall not focused'\n report['placeholder_view']={'id':52,'name':xbmc.getInfoLabel('Container.Viewmode'),'visible':True,'focused':True}\n report['placeholder_items']=[]\n for prefix,name in [('A folder','icons-wall-default-folder'),('B movie','icons-wall-default-file')]:\n  found=False\n  # Remote-style movement through the actual native list, no Python control proxy.\n  for attempt in range(16):\n   current=xbmc.getInfoLabel('ListItem.Label')\n   report.setdefault('placeholder_navigation',[]).append({'target':prefix,'attempt':attempt,'label':current})\n   if current.startswith(prefix):\n    found=True;break\n   xbmc.executebuiltin('Action(Right)');xbmc.sleep(300)\n  assert found,'Missing real fixture item '+prefix\n  xbmc.sleep(1100)\n  label=xbmc.getInfoLabel('ListItem.Label');icon=xbmc.getInfoLabel('ListItem.Icon')\n  assert icon.startswith('Default'),('Fixture did not expose implicit default',label,icon)\n  assert label.startswith(prefix),(prefix,label)\n  assert icon and 'Default' in icon,('Missing Kodi fallback icon',label,icon)\n  # Both implicit media shadow and resource must be present; actual render reviewed below.\n  basename=icon.split('/')[-1]\n  assert xbmcvfs.exists('special://skin/media/'+basename),('Missing shadow',icon)\n  f=xbmcvfs.File(pack+'aliases/'+basename);data=f.readBytes();f.close()\n  assert bytes(data[:8])==bytes([137,80,78,71,13,10,26,10]),('Missing fallback resource',icon)\n  report['placeholder_items'].append({'label':label,'icon':icon,'capture':name,'view':52})\n  snap(name)\n activate('Home')\n player=xbmc.Player();player.play(__VIDEO__)\n for _ in range(30):\n  if player.isPlayingVideo():break\n  xbmc.sleep(200)\n assert player.isPlayingVideo(),'Offline AVI failed to play'\n activate('fullscreenvideo');xbmc.executebuiltin('Action(OSD)');xbmc.sleep(700)\n assert player.isPlayingVideo();assert xbmc.getCondVisibility('Window.IsActive(videoosd)'), 'Video OSD not active';snap('icons-playback-osd')\n report['playback_active']=True\n report['playback_type']='offline MJPG AVI video'\n assert xbmcgui.getCurrentWindowId()==12005,'Not fullscreen video'\n assert xbmcgui.getCurrentWindowDialogId()==12901,'Not actual VideoOSD'\n player.stop();activate('Home')\n report['passed']=True\nexcept Exception:report['error']=traceback.format_exc()\nfinally:(OUT/'icon-report.json').write_text(json.dumps(report,indent=2))\n"
for token,value in [('__OUT__',str(out)),('__MANIFEST__',str(addons/'resource.images.foundry.slate.icons/resources/manifest.json')),('__FIXTURE__',str(fixture)),('__VIDEO__',str(video_path))]:payload=payload.replace(token,repr(value))
(qa/'default.py').write_text(payload)
env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'home/.config'),XDG_CACHE_HOME=str(base/'home/.cache'),DISPLAY=':98',KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL');(base/'home').mkdir()
log=(out/'native-console.log').open('w');x=None;k=None
report={'passed':False,'scope':'Offline actual shipped Slate native windows and resource URI lookup; no live media/provider or Shield certification.'}
def rpc(method,params=None):
 data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode()
 r=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18991/jsonrpc',data=data,headers={'Content-Type':'application/json'}),timeout=5))
 if 'error' in r:raise RuntimeError(r)
 return r['result']
def wait(fn,t=60):
 end=time.monotonic()+t
 while time.monotonic()<end:
  try:
   if fn():return
  except Exception:pass
  time.sleep(.3)
 raise AssertionError('timeout')
def modal():return rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']}).get('System.HasActiveModalDialog')
try:
 from PIL import Image,ImageStat
 # Detect opaque PNG patches before native rendering, including copied row art.
 pack=addons/'resource.images.foundry.slate.icons'
 for f in (pack/'resources/icons').glob('*.png'):
  with Image.open(f) as im:
   assert im.mode=='RGBA',(f,'No alpha')
   assert all(im.getpixel(pt)[3]==0 for pt in [(0,0),(0,255),(255,0),(255,255)]),(f,'Opaque corner')
   assert sum(a>0 for a in im.getchannel('A').getdata()) < 65536*.4,(f,'Opaque patch')
 x=subprocess.Popen(['Xvfb',':98','-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log);time.sleep(1)
 k=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=env,stdout=log,stderr=log)
 wait(lambda:rpc('JSONRPC.Ping')=='pong')
 for _ in range(20):
  if modal():rpc('Input.Back')
  time.sleep(.3)
 for aid in ('resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','resource.images.foundry.slate.icons','script.foundry.helper','script.foundry.slate.helper','skin.foundry','skin.foundry.slate','script.foundry.slate.iconqa'):rpc('Addons.SetAddonEnabled',{'addonid':aid,'enabled':True})
 assert rpc('Settings.SetSettingValue',{'setting':'lookandfeel.skin','value':'skin.foundry.slate'})
 wait(modal);rpc('Input.Left');rpc('Input.Select');wait(lambda:not modal());time.sleep(3)
 rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.slate.iconqa','wait':False})
 wait(lambda:(out/'icon-report.json').exists(),180)
 report['native']=json.loads((out/'icon-report.json').read_text());assert report['native']['passed'],report['native'].get('error')
 report['captures']={}
 for name in ('icons-home','icons-settings','icons-skinsettings','icons-keyboard','icons-default-placeholders','icons-wall-default-folder','icons-wall-default-file','icons-playback-osd'):
  f=out/(name+'.png');assert f.exists(),('Missing screenshot',name)
  with Image.open(f) as im:
   assert im.size==(1920,1080),(name,im.size)
   roi=im.crop((0,0,480,1080)) if name=='icons-home' else im
   assert max(ImageStat.Stat(roi.convert('RGB')).stddev)>10,('Blank screenshot',name)
  report['captures'][name]=hashlib.sha256(f.read_bytes()).hexdigest()
 # Compare native wall glyph pixels against actual implicit shadow source, not labels alone.
 report['placeholder_pixel_matches']=[]
 for item in report['native']['placeholder_items']:
  icon=item['icon'].split('/')[-1]
  with Image.open(addons/'skin.foundry.slate/media'/icon) as src:
   alpha=src.convert('RGBA').resize((120,120),Image.Resampling.LANCZOS).getchannel('A')
   ink=[(x,y) for y in range(120) for x in range(120) if alpha.getpixel((x,y))>100]
  assert len(ink)>30,('Empty glyph template',icon)
  with Image.open(out/(item['capture']+'.png')) as cap:
   cap=cap.convert('RGB');best=0
   # Shipped view52: 92% width centered, 440px cells, image offset160/60, panel top120.
   for column in range(4):
    for dx in range(-5,6):
     for dy in range(-5,6):
      x0=237+440*column+dx;y0=180+dy
      recall=sum(min(cap.getpixel((x0+x,y0+y)))>100 for x,y in ink)/len(ink)
      best=max(best,recall)
  assert best>.65,('Implicit glyph not visibly rendered',icon,best)
  report['placeholder_pixel_matches'].append({'icon':icon,'stroke_recall':best})
 rpc('Application.Quit');k.wait(timeout=30)
 logs=list(profile.rglob('kodi.log'));assert logs,'Missing Kodi log'
 text='\n'.join(f.read_text(errors='replace') for f in logs)
 (out/'kodi.log').write_text(text)
 failures=[line for line in text.splitlines() if re.search(r'(ERROR|WARNING)',line,re.I) and re.search(r'(texture|resource.images.foundry.slate.icons)',line,re.I) and re.search(r'(fail|unable|not found|unknown|error loading)',line,re.I)]
 report['texture_failures']=failures;assert not failures,failures
 report['passed']=True
except Exception as e:report['error']=repr(e)
finally:
 for process in (k,x):
  if process is not None and process.poll() is None:process.terminate()
 if (profile/'temp/kodi.log').exists():shutil.copy(profile/'temp/kodi.log',out/'kodi.log')
 (out/'native-icon-report.json').write_text(json.dumps(report,indent=2))
 log.close()
print(json.dumps(report,indent=2));sys.exit(0 if report['passed'] else 1)
