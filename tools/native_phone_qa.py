"""Native isolated Kodi phone-entry QA: real keyboard, LAN ioctl, HTTP and TV OK."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import time
from io import BytesIO
from urllib.request import Request,urlopen
import xml.etree.ElementTree as E
from PIL import Image,ImageGrab,ImageChops

ROOT=Path('/work/foundry-kodi-dist')
SKIN=ROOT.parent/'skin.foundry-nimbus'
HELPER=ROOT.parent/'script.foundry.helper'

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


def wait_for(predicate,timeout=45):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.1)
    raise AssertionError('Foundry interface did not reach the expected native state')


def animation_evidence(frames,latencies,elapsed):
    """Coarse native animation/responsiveness gate, not a device FPS benchmark."""
    assert len(frames)>=4 and latencies,'Animation sample is incomplete'
    changed=[sum(max(pixel)>8 for pixel in ImageChops.difference(a,b).getdata()) for a,b in zip(frames,frames[1:])]
    assert sum(n>20 for n in changed)>=3,('Ripple did not animate visibly',changed)
    assert any(sum(max(pixel)>120 for pixel in frame.getdata())>50 for frame in frames),'Ripple has no visible frame'
    assert max(latencies)<2 and elapsed<20,('Native animation responsiveness bound exceeded',latencies,elapsed)
    return changed


def atomic_text(path,value):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(value,encoding='utf-8')
    temporary.replace(path)


def available_port(requested=0):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1',requested))
        return listener.getsockname()[1]


def fixture_ready(rpc,logfile,port,identity):
    try:
        if '<CWebserver[%d]>: Started'%port not in logfile.read_text(encoding='utf-8',errors='replace'):
            return False
        return rpc('JSONRPC.Ping')=='pong' and rpc('Settings.GetSettingValue',{'setting':'services.devicename'}).get('value')==identity
    except (OSError,ValueError,RuntimeError):return False


def playback_log_report(text):
    """Retain complete native traceback context, including swallowed callbacks."""
    begin='[Foundry playback QA] begin';end='[Foundry playback QA] end'
    start=text.find(begin);finish=text.find(end,start+len(begin)) if start>=0 else -1
    segment=text[start:finish+len(end) if finish>=0 else None] if start>=0 else ''
    markers=('PythonToCppException','Error Contents:','Traceback (most recent call last):','[Foundry catalog]')
    failures=[line for line in segment.splitlines() if any(marker in line for marker in markers)]
    return {'complete':start>=0 and finish>=0,'failures':failures,'log':segment}


FIXTURE="\nimport threading,json,time,traceback\nimport xbmc,xbmcgui\nhome=xbmcgui.Window(10000)\ndef keyboard(hidden):\n k=xbmc.Keyboard('', 'Phone entry QA', hidden);k.doModal()\n result=BASE/'keyboard-result.tmp';result.write_text(json.dumps({'confirmed':k.isConfirmed(),'text':k.getText()}));result.replace(BASE/'keyboard-result.json')\ntry:\n threading.Thread(target=keyboard,args=(False,),daemon=True).start()\n while not (BASE/'complete').exists():\n  capture=BASE/'capture'\n  if capture.exists():\n   name=capture.read_text();capture.unlink();xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+',sync)',True)\n  normal=BASE/'normal'\n  if normal.exists():\n   normal.unlink();threading.Thread(target=keyboard,args=(False,),daemon=True).start()\n  command=BASE/'hidden'\n  if command.exists():\n   command.unlink();threading.Thread(target=keyboard,args=(True,),daemon=True).start()\n  state={'window':xbmcgui.getCurrentWindowId(),'dialog':xbmcgui.getCurrentWindowDialogId(),'focus':xbmc.getInfoLabel('System.CurrentControlId'),'phone_visible':xbmc.getCondVisibility('Control.IsVisible(95301)'),'hidden':xbmc.getCondVisibility('System.HasHiddenInput'),'image':home.getProperty('foundry.phone_entry.image'),'active':bool(home.getProperty('foundry.phone_entry.active')),'status':home.getProperty('foundry.phone_entry.status'),'text':xbmc.getInfoLabel('Control.GetLabel(312).index(1)')}\n  temporary=BASE/'state.tmp';temporary.write_text(json.dumps(state));temporary.replace(BASE/'state.json');time.sleep(.05)\nexcept Exception:(BASE/'error.txt').write_text(traceback.format_exc())\n"
PLUGIN=""

def main():
    global ROOT, SKIN, HELPER, FIXTURE
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--skin',type=Path,required=True)
    parser.add_argument('--helper',type=Path,required=True)
    parser.add_argument('--restricted-enumeration',action='store_true')
    parser.add_argument('--native-debugger',action='store_true',help='Diagnostic only: existing gdb records native crash stack, no retry')
    parser.add_argument('--keyboard-xml',type=Path)
    parser.add_argument('--display',default=':98',help='A free private X11 display')
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--allow-unsupported-kodi',action='store_true',help='Diagnostic run only; final release still requires Kodi21+')
    args=parser.parse_args()
    ROOT=args.root.resolve();SKIN=args.skin.resolve();HELPER=args.helper.resolve()
    skin_id=E.parse(SKIN/'addon.xml').getroot().get('id')
    helper_id=E.parse(HELPER/'addon.xml').getroot().get('id')
    assert skin_id in ('skin.foundry','skin.foundry.slate')
    assert helper_id in ('script.foundry.helper','script.foundry.slate.helper')
    namespace='foundry.slate.phone_entry' if skin_id.endswith('.slate') else 'foundry.phone_entry'
    FIXTURE=FIXTURE.replace('foundry.phone_entry',namespace)
    port=available_port(args.port);display=args.display
    release=json.loads((ROOT/'release.json').read_text())['release']
    assert isinstance(release,str) and release and all(c.isalnum() or c in '._-' for c in release)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    (output/'phone-verification.json').write_text(json.dumps({'passed':False,'status':'running or incomplete','qr_decode_verified':False,'physical_phone_verified':False}))
    with tempfile.TemporaryDirectory(prefix='foundry-interface-',ignore_cleanup_errors=True) as temporary:
        base=Path(temporary);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
        profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True)
        # Full redraw avoids Xvfb readback of incomplete dirty-region frames.
        (userdata/'advancedsettings.xml').write_text('<advancedsettings><gui><algorithmdirtyregions>0</algorithmdirtyregions></gui></advancedsettings>')
        addons=profile/'addons';addons.mkdir()
        resources=[ROOT/'src'/node.get('addon') for node in E.parse(SKIN/'addon.xml').getroot().findall('./requires/import') if node.get('addon').startswith('resource.')]
        for source in [SKIN,HELPER]+resources:
            aid=E.parse(source/'addon.xml').getroot().get('id');shutil.copytree(source,addons/aid)
        helper=addons/helper_id;skin=addons/skin_id
        if args.keyboard_xml:shutil.copyfile(args.keyboard_xml,skin/'xml/DialogKeyboard.xml')
        tested={'phone_entry_http.py':helper/'resources/lib/modules/phone_entry_http.py','DialogKeyboard.xml':skin/'xml/DialogKeyboard.xml','phone_entry.py':helper/'resources/lib/modules/phone_entry.py','phone_entry_network.py':helper/'resources/lib/modules/phone_entry_network.py'}
        (output/'tested-source-hashes.json').write_text(json.dumps({name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in tested.items()},indent=2))
        manifest=E.parse(helper/'addon.xml')
        for node in list(manifest.getroot().findall('extension')):
            if node.get('point')=='xbmc.service':manifest.getroot().remove(node)
        for node in list(manifest.getroot().find('requires')):
            if node.get('addon')!='xbmc.python':manifest.getroot().find('requires').remove(node)
        manifest.write(helper/'addon.xml',encoding='UTF-8',xml_declaration=True)
        for path in (home/'addons').glob('*/addon.xml'):
            tree=E.parse(path)
            for extension in tree.getroot().findall("extension[@point='xbmc.service']"):tree.getroot().remove(extension)
            tree.write(path,encoding='UTF-8',xml_declaration=True)
        custom=addons/'resource.uisounds.foundry.qacustom'
        shutil.copytree(addons/'resource.uisounds.foundry.pulse',custom)
        tree=E.parse(custom/'addon.xml');tree.getroot().set('id',custom.name);tree.write(custom/'addon.xml',encoding='UTF-8',xml_declaration=True)
        settings=userdata/'addon_data'/skin_id;settings.mkdir(parents=True)
        (settings/'settings.xml').write_text('<settings><setting id="firsttimerun" type="bool">true</setting></settings>')
        shutil.copyfile(skin/'xml/Home.xml',base/'shipped-Home.xml')
        identity='Foundry Interface QA '+base.name
        (userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">%d</setting><setting id="services.webserverauthentication">false</setting><setting id="services.devicename">%s</setting></settings>'%(port,identity))
        launcher=addons/'script.foundry.interfaceqa';launcher.mkdir()
        (launcher/'addon.xml').write_text('<addon id="script.foundry.interfaceqa" version="1.0.0" name="Foundry Interface QA" provider-name="Foundry"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-2.0-only</license></extension></addon>')
        (launcher/'default.py').write_text('from pathlib import Path\nBASE=Path(%r)\nOUTPUT=Path(%r)\nHELPER=Path(%r)\nPOSTER=%r\nFANART=%r\nSTUDIO=%r\n'%(str(base),str(output),str(helper),'', '', '')+FIXTURE)

        # Suppress unrelated setup/network entrypoints only in this disposable copy.
        (helper/'resources/lib/default.py').write_text('from pathlib import Path\nBASE=Path(%r)\nRESTRICTED=%r\n'%(str(base),args.restricted_enumeration)+"import sys,json,os,socket,fcntl\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).parent))\nif any('mode=phone_entry' in x for x in sys.argv):\n from modules import phone_entry\n original=phone_entry.render_qr\n def capture(url,path):\n  original(url,path)\n  Path(BASE/'phone-url.txt').write_text(url)\n  import shutil\n  shutil.copyfile(path,BASE/'actual-qr.png')\n phone_entry.render_qr=capture\n original_ip=phone_entry.xbmc.getIPAddress\n original_names=socket.if_nameindex\n original_listdir=os.listdir\n original_ioctl=fcntl.ioctl\n events=[]\n def denied_names():\n  events.append('if_nameindex_denied');raise PermissionError('QA Android netlink restriction')\n def denied_sysfs(path):\n  if str(path)=='/sys/class/net':\n   events.append('sysfs_denied');raise PermissionError('QA Android sysfs restriction')\n  return original_listdir(path)\n def real_ioctl(fd,operation,arg=0,*rest):\n  result=original_ioctl(fd,operation,arg,*rest)\n  if operation==0x8912:\n   events.append('real_SIOCGIFCONF')\n   (BASE/'discovery-evidence.json').write_text(json.dumps(events))\n  return result\n phone_entry.xbmc.getIPAddress=lambda:'10.8.0.2'\n if RESTRICTED:\n  socket.if_nameindex=denied_names;os.listdir=denied_sysfs;fcntl.ioctl=real_ioctl\n try: phone_entry.run()\n finally:\n  phone_entry.xbmc.getIPAddress=original_ip\n  socket.if_nameindex=original_names;os.listdir=original_listdir;fcntl.ioctl=original_ioctl\n")

        isolated_home=base/'user-home';isolated_home.mkdir()
        environment=dict(os.environ,HOME=str(isolated_home),XDG_CONFIG_HOME=str(isolated_home/'.config'),XDG_CACHE_HOME=str(isolated_home/'.cache'),DISPLAY=display,KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL')
        kodi=None;log=(output/'interface-console.log').open('w')
        xserver=subprocess.Popen(['Xvfb',display,'-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log)
        try:
            time.sleep(1)
            assert xserver.poll() is None,'Private Xvfb failed to start'
            command=['kodi','-p','-fs','--windowing=x11','--debug']
            if args.native_debugger:
                candidates=list(Path('/usr/lib').glob('*/kodi/kodi.bin'))+[Path('/usr/lib/kodi/kodi.bin')]
                binaries=[p for p in candidates if p.is_file()]
                assert len(binaries)==1 and shutil.which('gdb'),'Expected one installed kodi.bin and existing gdb'
                environment['KODI_BIN_HOME']=str(binaries[0].parent)
                wrapper=Path(shutil.which('kodi'))
                shutil.copyfile(wrapper,output/'installed-kodi-launcher.txt')
                command=['gdb','--batch','--return-child-result','-ex','set pagination off','-ex','set logging file '+str(output/'native-gdb.log'),'-ex','set logging enabled on','-ex','run','-ex','thread apply all bt full','--args',str(binaries[0]),'-p','-fs','--windowing=x11','--debug']
            (output/'native-launch-command.json').write_text(json.dumps({'command':command,'debugger':args.native_debugger,'KODI_HOME':environment.get('KODI_HOME'),'KODI_BIN_HOME':environment.get('KODI_BIN_HOME')},indent=2))
            kodi=subprocess.Popen(command,env=environment,stdout=log,stderr=log,start_new_session=True)
            def rpc(method,params=None):
                data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode()
                with urlopen(Request('http://127.0.0.1:%d/jsonrpc'%port,data=data,headers={'Content-Type':'application/json'}),timeout=5) as response:result=json.loads(response.read())
                if 'error' in result:raise RuntimeError(str(result['error']))
                return result.get('result')
            def ready():
                try:return fixture_ready(rpc,profile/'temp/kodi.log',port,identity)
                except Exception:return False
            wait_for(ready,60)
            kodi_version=rpc('Application.GetProperties',{'properties':['version']})['version']
            assert kodi_version['major']>=21 or args.allow_unsupported_kodi,'Kodi 21+ required; older runtimes are diagnostic only'
            # First-start add-on prompts arrive one at a time. A momentary
            # gap is not initialization completion, so require a quiet interval.
            deadline=time.monotonic()+30;quiet_since=None
            while time.monotonic()<deadline:
                visible=rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']})
                if visible.get('System.HasActiveModalDialog'):
                    rpc('Input.Back');quiet_since=None
                elif quiet_since is None:quiet_since=time.monotonic()
                elif time.monotonic()-quiet_since>=2:break
                time.sleep(.2)
            else:raise AssertionError('Initial add-on dialogs did not settle')
            # Fresh profiles discover manually placed add-ons as disabled.
            # Enable the isolated fixture dependencies before selecting its skin.
            for aid in [path.name for path in resources]+['resource.uisounds.foundry.qacustom',helper_id,skin_id,'script.foundry.interfaceqa']:
                rpc('Addons.SetAddonEnabled',{'addonid':aid,'enabled':True})
            assert rpc('Settings.SetSettingValue',{'setting':'lookandfeel.skin','value':skin_id})
            wait_for(lambda:rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']}).get('System.HasActiveModalDialog'))
            labels=rpc('XBMC.GetInfoLabels',{'labels':['Control.GetLabel(1)','Control.GetLabel(9)']})
            prompt=' '.join(labels.values()).lower()
            assert 'keep' in prompt or 'skin' in prompt,('Unexpected skin-change dialog',labels)
            rpc('Input.Left');rpc('Input.Select')
            wait_for(lambda:not rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']}).get('System.HasActiveModalDialog'))
            wait_for(lambda:rpc('Settings.GetSettingValue',{'setting':'lookandfeel.skin'}).get('value')==skin_id)
            rpc('GUI.ActivateWindow',{'window':'home'})
            rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.interfaceqa'})

            def state():
                if kodi.poll() is not None:
                    raise RuntimeError('Native Kodi exited before phone verification completed (exit %s); inspect retained console/crash logs'%kodi.returncode)
                try:return json.loads((base/'state.json').read_text())
                except (OSError,ValueError):return {}
            wait_for(lambda:state().get('dialog')==10103)
            def captured(path):
                state()  # Detect native exit even while awaiting screenshot I/O.
                return path.exists()
            def capture(name):
                time.sleep(.7);(base/'capture').write_text(name)
                wait_for(lambda:captured(output/(name+'.png')),10)
                time.sleep(.1)
                if name in ('keyboard-normal','keyboard-qr','keyboard-cancelled'):
                    for index in range(6):
                        extra=name+'-repeat-'+str(index)
                        (base/'capture').write_text(extra);wait_for(lambda:captured(output/(extra+'.png')),10);time.sleep(.15)
                    (output/(name+'-state.json')).write_text(json.dumps(state(),indent=2))
            capture('keyboard-normal')
            assert state()['phone_visible'],state()
            # Default focus is Done; up reaches Phone through actual remote navigation.
            rpc('Input.Up');time.sleep(.3)
            assert state()['focus']=='95301',state()
            import threading
            opening_frames=[]
            def record_opening():
                for _ in range(24):
                    opening_frames.append(ImageGrab.grab(xdisplay=display).convert('RGB'));time.sleep(.035)
            recording=threading.Thread(target=record_opening);recording.start()
            rpc('Input.Select')
            wait_for(lambda:bool(state().get('image')),15)
            recording.join()
            for index,frame in enumerate(opening_frames):frame.save(output/('keyboard-opening-%02d.png'%index))
            capture('keyboard-qr')
            url=(base/'phone-url.txt').read_text();origin,token=url.split('/#')
            shutil.copyfile(base/'actual-qr.png',output/'actual-qr.png')
            if args.restricted_enumeration:
                evidence=json.loads((base/'discovery-evidence.json').read_text())
                assert all(x in evidence for x in ('if_nameindex_denied','sysfs_denied','real_SIOCGIFCONF')),evidence
                (output/'discovery-evidence.json').write_text(json.dumps(evidence,indent=2))
            assert not origin.startswith('http://10.8.0.2:'), 'VPN-reported address was not replaced'
            from urllib.request import ProxyHandler,build_opener
            http=build_opener(ProxyHandler({}))
            with http.open(origin+'/',timeout=3) as response:
                page=response.read().decode();assert response.status==200 and '<textarea' in page,page[:200]
            from urllib.error import HTTPError
            for bad_origin,bad_token in [('http://untrusted.invalid',token),(origin,'invalid-token')]:
                bad=Request(origin+'/text',data=b'{"text":"must not arrive"}',headers={'Content-Type':'application/json','Origin':bad_origin,'Authorization':'Bearer '+bad_token})
                try:
                    http.open(bad,timeout=3)
                    raise AssertionError('Unauthorized phone write was accepted')
                except HTTPError as exc:assert exc.code==403,exc.code
            assert state()['dialog']==10103 and not (base/'keyboard-result.json').exists()
            synthetic='Foundry phone QA 27' 
            request=Request(origin+'/text',data=json.dumps({'text':synthetic}).encode(),headers={'Content-Type':'application/json','Origin':origin,'Authorization':'Bearer '+token})
            with http.open(request,timeout=3) as response:assert response.status==200
            time.sleep(.5)
            assert state()['dialog']==10103 and not (base/'keyboard-result.json').exists(),state()
            capture('keyboard-filled')
            wait_for(lambda:not state().get('active'))
            rpc('Input.Down');rpc('Input.Select')
            wait_for(lambda:(base/'keyboard-result.json').exists())
            assert json.loads((base/'keyboard-result.json').read_text())=={'confirmed':True,'text':synthetic}
            wait_for(lambda:state().get('dialog')!=10103)
            (base/'normal').touch();wait_for(lambda:state().get('dialog')==10103)
            time.sleep(.7)
            rpc('Input.Up')
            # New session, explicit Phone cancel leaves keyboard open and listener closes.
            rpc('Input.Select');wait_for(lambda:bool(state().get('image')),15)
            origin2=(base/'phone-url.txt').read_text().split('/#')[0]
            rpc('Input.Select');wait_for(lambda:not state().get('active'))
            ImageGrab.grab(xdisplay=display).convert('RGB').save(output/'keyboard-cancel-transition.png')
            time.sleep(.4)
            try:http.open(origin2+'/',timeout=1);raise AssertionError('Cancelled listener remains open')
            except OSError:pass
            assert state()['dialog']==10103
            capture('keyboard-cancelled')
            # Back also closes a third listener.
            rpc('Input.Select');wait_for(lambda:bool(state().get('image')),15)
            old_image=state()['image']
            rpc('Input.Select');wait_for(lambda:not state().get('active'))
            rpc('Input.Select')
            wait_for(lambda:state().get('active') and state().get('image') and state()['image']!=old_image,15)
            time.sleep(.5)
            assert state().get('active') and state().get('image'), 'Old cleanup cleared restarted session'
            capture('keyboard-reopened')
            origin3=(base/'phone-url.txt').read_text().split('/#')[0]
            rpc('Input.Back');wait_for(lambda:state().get('dialog')!=10103)
            time.sleep(.5)
            try:http.open(origin3+'/',timeout=1);raise AssertionError('Back listener remains open')
            except OSError:pass
            (base/'hidden').touch();wait_for(lambda:state().get('dialog')==10103 and state().get('hidden'))
            capture('keyboard-hidden');assert not state()['phone_visible'],state()
            rpc('Input.Back');(base/'complete').touch()
            (output/'phone-verification.json').write_text(json.dumps({'passed':True,'qr_decode_verified':False,'physical_phone_verified':False,'url_source':'QA render wrapper observes the URL passed to the actual QR renderer; no QR decode performed','source_sha256':json.loads((output/'tested-source-hashes.json').read_text()),'image_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.png'))},'native_kodi':kodi_version,'skin':skin_id,'helper':helper_id,'restricted_enumeration_real_ioctl':args.restricted_enumeration,'remote_reachable':True,'vpn_reported_ip_replaced_by_discovered_interface':True,'http_text_no_auto_confirm':True,'bad_origin_and_token_rejected':True,'cancel_closed_listener':True,'back_closed_listener':True,'rapid_cancel_reopen_retains_new_session':True,'hidden_has_no_phone':True,'scope':'Isolated offline Kodi; actual modules/XML; actual generated QR image retained and hashed, but QR scan/decode and physical phone are unverified. QA dispatcher observes transient URL. HTTP runs on discovered interface within native QA host/container, not an independent phone/LAN test.'},indent=2))

        except Exception:
            import traceback
            (output/'phone-verification.json').write_text(json.dumps({'passed':False,'skin':skin_id,'helper':helper_id,'restricted_enumeration_real_ioctl':args.restricted_enumeration,'qr_decode_verified':False,'physical_phone_verified':False,'failure':traceback.format_exc(),'source_sha256':json.loads((output/'tested-source-hashes.json').read_text()),'image_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.png'))}},indent=2))
            try:ImageGrab.grab(xdisplay=display).save(output/'interface-failure.png')
            except Exception:pass
            raise
        finally:
            # Preserve native crash diagnostics before TemporaryDirectory cleanup.
            # Do not copy core dumps: stack text and process outcome suffice.
            crash_logs=[]
            for label,directory in [('user-home',isolated_home),('profile-temp',profile/'temp')]:
                if directory.exists():
                    for diagnostic in directory.rglob('*.log'):
                        target=output/'native-diagnostics'/label/diagnostic.relative_to(directory)
                        target.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(diagnostic,target)
                        crash_logs.append(str(target.relative_to(output)))
            (output/'native-process-outcome.json').write_text(json.dumps({'exit_before_cleanup':kodi.poll() if kodi else None,'crash_logs':crash_logs},indent=2))
            if kodi:
                try:os.killpg(kodi.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:kodi.wait(timeout=5)
                except subprocess.TimeoutExpired:pass
                # The kodi shell launcher can exit before kodi.bin. Reap only
                # our own start_new_session process group, even after wait succeeds.
                try:os.killpg(kodi.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                kodi.wait(timeout=5)
            xserver.terminate();xserver.wait(timeout=5);log.close()
            if (profile/'temp/kodi.log').exists():shutil.copyfile(profile/'temp/kodi.log',output/'interface-kodi.log')
            if (output/'interface-kodi.log').exists():
                playback=playback_log_report((output/'interface-kodi.log').read_text(encoding='utf-8',errors='replace'))
                (output/'interface-playback-kodi.log').write_text(playback.pop('log'),encoding='utf-8')
                (output/'interface-playback-errors.json').write_text(json.dumps(playback,indent=2)+'\n',encoding='utf-8')
            for name in ['state.json','error.txt','sounds.json','keyboard-result.json','discovery-evidence.json']:
                if (base/name).exists():shutil.copyfile(base/name,output/('interface-'+name))


if __name__=='__main__':main()

