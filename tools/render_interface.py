"""Verify widget metadata, OSD frames and system icons in native Foundry/Kodi."""
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
from PIL import Image,ImageGrab,ImageChops,ImageStat

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'
HELPER=ROOT.parent/'script.foundry.helper'

FIXTURE=r'''
import json,sys,time,traceback
from pathlib import Path
import xbmc,xbmcgui
def require(condition,message):
    if not condition:raise AssertionError(message)
sys.path.insert(0,str(HELPER/'resources/lib'))
from modules.monitors.metadata import MetadataMonitor
from modules.vod import CatalogArtworkMonitor
from modules.catalog_window import CatalogWindow
class Provider:
    def enrich(self,item,section):
        item=dict(item);item['art']=dict(item.get('art') or {},studiologo=STUDIO)
        item['ratings']={'tmdb':{'rating':7.2},'imdb':{'rating':7.8}}
        return item,{'tmdb':'ready','omdb':'ready'}
try:
    # JSON-RPC can change the setting before the active skin is reloaded.
    # ReloadSkin without parameters uses that setting and asks no confirmation.
    xbmc.executebuiltin('ReloadSkin()',True)
    xbmc.executebuiltin('ActivateWindow(Home)',True)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if xbmc.getSkinDir()=='skin.foundry':
            try:
                window=xbmcgui.Window(10000);row=window.getControl(19011)
                break
            except RuntimeError:pass
        xbmc.sleep(100)
    else:raise AssertionError('Foundry fixture Home did not load; active skin: '+xbmc.getSkinDir())
    from modules.experience import configure_experience
    def setting(method,**params):
        result=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params})))
        require('error' not in result,result)
        return result['result']
    sounds=[]
    for selected,expected in [('resource.uisounds.kodi','resource.uisounds.foundry.pulse'),('',''),('resource.uisounds.foundry.qacustom','resource.uisounds.foundry.qacustom')]:
        xbmc.executebuiltin('Skin.Reset(foundry.sounds.pulse.v1)',True)
        xbmc.executebuiltin('Skin.Reset(foundry.sounds.default.v1)',True)
        changed=setting('Settings.SetSettingValue',setting='lookandfeel.soundskin',value=selected)
        require(changed,('Could not select sound fixture',selected))
        configure_experience()
        actual=setting('Settings.GetSettingValue',setting='lookandfeel.soundskin')['value']
        require(actual==expected,(selected,expected,actual))
        sounds.append({'before':selected,'after':actual})
    changed=setting('Settings.SetSettingValue',setting='lookandfeel.soundskin',value='resource.uisounds.foundry.pulse')
    require(changed,'Could not restore Pulse fixture selection')
    (BASE/'sounds.json').write_text(json.dumps(sounds))
    metadata=MetadataMonitor(window,provider=Provider());artwork=CatalogArtworkMonitor()
    for title,kind,season,episode in [('Widget Film','movie',None,None),('The Signal','episode',1,2)]:
        item=xbmcgui.ListItem(title,path='fixture://'+kind)
        info={'title':title,'year':2026,'mediatype':kind,'plot':'A complete focused widget item shows the same metadata stack as the library.','genre':['Mystery'],'studio':['Fixture Studio'],'premiered':'2026-11-01'}
        if kind=='episode':info.update(tvshowtitle='Fixture Series',season=season,episode=episode)
        item.setInfo('video',info);item.setArt({'poster':POSTER,'fanart':FANART,'studiologo':STUDIO})
        row.addItem(item)
    window.setFocusId(19011)
    playback_catalog=None;playback_command=0;playback_parent=None;playback_closed_parent=None;command_sequence=0
    deadline=time.monotonic()+360
    while not (BASE/'complete').exists() and time.monotonic()<deadline:
        if playback_catalog is not None:
            if playback_catalog.closed:
                playback_catalog.dispose();playback_catalog=None
                playback_closed_parent=None
            else:playback_catalog.tick()
        if playback_catalog is None and playback_parent is not None and xbmcgui.getCurrentWindowId()==playback_parent:
            playback_closed_parent=playback_parent
        metadata.process_current_item();artwork.process_current_item()
        def label(name):return xbmc.getInfoLabel(name)
        snapshot={'window':xbmcgui.getCurrentWindowId(),'label':label('ListItem.Label'),
                  'details':label('Control.GetLabel(5723)'),
                  'studio':window.getProperty('foundry.vod.studio_logo'),
                  'title':window.getProperty('foundry.metadata.title'),
                  'wallpaper':label('Skin.String(foundry.fixture)'),
                  'focus':window.getFocusId(),'favorites_count':label('Container(14100).NumItems'),
                  'favorite_label':label('Container(14100).ListItem.Label'),
                  'seek_offset':label('Player.SeekOffset'),'seek_step':label('Player.SeekStepSize'),
                  'player_time':label('Player.Time'),'player_duration':label('Player.Duration'),
                  'seek_visible':xbmc.getCondVisibility('Window.IsVisible(seekbar)'),
                  'busy_visible':xbmc.getCondVisibility('Window.IsVisible(busydialognocancel)'),
                  'python_optimize':sys.flags.optimize,'playback_command':playback_command,'command_sequence':command_sequence,
                  'playback_parent':playback_parent,'playback_closed_parent':playback_closed_parent,
                  'catalog':None}
        if playback_catalog is not None:
            snapshot['catalog']={'selected':playback_catalog.state.selected,'source':playback_catalog.source.path,
                'submenu':playback_catalog.getProperty('foundry.movie_submenu_label'),
                'fanart':playback_catalog.getProperty('catalog.fanart'),'native_ready':False,
                'message':playback_catalog.getProperty('catalog.message'),
                'file':playback_catalog.state.items[3]['file']}
            if not xbmc.getCondVisibility('Player.HasVideo'):
                try:
                    snapshot['catalog'].update(native_ready=True,focus=playback_catalog.getFocusId(),
                        position=playback_catalog.getCurrentListPosition(),size=playback_catalog.getListSize())
                except RuntimeError:snapshot['catalog']['native_ready']=False
        (BASE/'state.tmp').write_text(json.dumps(snapshot));(BASE/'state.tmp').replace(BASE/'state.json')
        playback_request=BASE/'playback-command.json'
        if playback_request.exists():
            request=json.loads(playback_request.read_text())
            if request['action']=='open-catalog':
                require(playback_catalog is None,'Previous catalog did not close')
                xbmc.executebuiltin('ActivateWindow(settings)',True);xbmc.sleep(300)
                playback_parent=xbmcgui.getCurrentWindowId();playback_closed_parent=None
                require(playback_parent==10004,('Unexpected catalog parent',playback_parent))
                class Source:
                    scope='fixture';path='fixture://playback-catalog';content='movies'
                    movie_submenu_label='Trending';movie_submenu_verified=False
                    def load(self):raise AssertionError('Playback return reloaded the source')
                source=Source()
                art={'poster':POSTER}
                if request.get('fanart'):art['fanart']=FANART
                source.initial={'items':[{'title':'Playback Movie '+str(index),'type':'movie',
                    'filetype':'file','file':str(BASE/'fixture.avi'),'plot':'Offline playback return fixture.',
                    'art':dict(art)} for index in range(6)]}
                playback_catalog=CatalogWindow('script-foundry-vod.xml',str(HELPER),'default','1080i',True,
                    source=source,section='Movies',breadcrumb='VOD / Movies / Trending')
                playback_catalog.show()
                limit=time.monotonic()+10
                while not playback_catalog.initialized and time.monotonic()<limit:xbmc.sleep(20)
                require(playback_catalog.initialized,'Playback catalog failed to initialize')
            elif request['action']=='begin':xbmc.log('[Foundry playback QA] begin',xbmc.LOGINFO)
            elif request['action']=='end':xbmc.log('[Foundry playback QA] end',xbmc.LOGINFO)
            else:raise AssertionError('Unknown playback command')
            # Acknowledge only a completed action; the next state carries this ID.
            playback_command=request['id'];playback_request.unlink()
        command=BASE/'command'
        if command.exists():
            value=command.read_text()
            if value=='clear-widget':row.reset()
            elif value=='icons':xbmc.executebuiltin('ActivateWindow(11126)')
            elif value=='live-frame':xbmc.executebuiltin('ActivateWindow(11127)')
            elif value=='favorites':
                import shutil
                # BASE is created by TemporaryDirectory, never the source checkout.
                target=BASE/'kodi/portable_data/addons/skin.foundry/xml/Home.xml'
                require(target.resolve().is_relative_to(BASE.resolve()),'Home restoration escaped disposable profile')
                shutil.copyfile(BASE/'shipped-Home.xml',target)
                xbmc.executebuiltin('ReloadSkin()',True);xbmc.executebuiltin('ActivateWindow(Home)',True)
                # Keep the existing Home wrapper alive. Native XML-populated lists
                # do not populate ControlList's Python vecItems; use GUI info/actions.
                favorites_deadline=time.monotonic()+10
                while time.monotonic()<favorites_deadline:
                    count=int(xbmc.getInfoLabel('Container(9000).NumItems') or '0')
                    if count:break
                    xbmc.sleep(50)
                require(count>0,'Shipped Home menu did not populate')
                for index in range(count):
                    xbmc.executebuiltin('SetFocus(9000,%d,absolute)'%index,True)
                    xbmc.sleep(100)
                    if xbmc.getInfoLabel('Container(9000).ListItem.Property(id)')=='favorites':break
                else:raise AssertionError('Shipped Home has no Favorites menu item')
            # Kodi permits the non-cancel busy dialog for addons; both native
            # dialog classes render the unchanged shipped DialogBusy.xml.
            elif value=='busy-open':xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
            elif value=='busy-close':xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
            elif value=='play':
                item=xbmcgui.ListItem('Foundry Playback')
                item.setInfo('video',{'title':'Foundry Playback','mediatype':'movie'})
                item.setArt({'poster':POSTER,'studiologo':STUDIO})
                xbmc.Player().play(str(BASE/'fixture.avi'),item)
            else:raise AssertionError('Unknown interface command')
            # Publish completion only after the requested action returns.
            command_sequence+=1;command.unlink()
        capture=BASE/'capture'
        if capture.exists():
            name=capture.read_text()
            xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+')')
            capture.unlink()
        xbmc.sleep(30)
    metadata.stop()
except Exception:(BASE/'error.txt').write_text(traceback.format_exc())
'''


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


def wallpaper_evidence(frame,expected_source,other_source):
    """Match foreground art, not isolated pixels shared by both wallpapers."""
    regions=[(1100,140,1780,560),(700,300,1500,580)]
    frame=frame.convert('RGB')
    def errors(source):
        with Image.open(source) as image:expected=image.convert('RGB').resize((1920,1080))
        return [max(ImageStat.Stat(ImageChops.difference(frame.crop(region),expected.crop(region))).mean)
                for region in regions]
    expected_errors=errors(expected_source);other_errors=errors(other_source)
    assert max(expected_errors)<5,('Native wallpaper differs from approved foreground',str(expected_source),expected_errors)
    assert max(other_errors)>max(expected_errors)+3,('Native wallpaper does not distinguish full/widget artwork',expected_errors,other_errors)
    return {'source':str(expected_source),'sha256':hashlib.sha256(Path(expected_source).read_bytes()).hexdigest(),
            'regions':regions,'mean_absolute_errors':expected_errors,'other_variant_errors':other_errors}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    parser.add_argument('--display',default=':98',help='A free private X11 display')
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--allow-unsupported-kodi',action='store_true',help='Diagnostic run only; final release still requires Kodi21+')
    args=parser.parse_args()
    port=available_port(args.port);display=args.display
    release=json.loads((ROOT/'release.json').read_text())['release']
    assert isinstance(release,str) and release and all(c.isalnum() or c in '._-' for c in release)
    output=args.output or ROOT/'releases'/(release+'-qa');output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='foundry-interface-',ignore_cleanup_errors=True) as temporary:
        base=Path(temporary);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
        profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True)
        addons=profile/'addons';addons.mkdir()
        for source in [SKIN,HELPER,ROOT/'src/resource.images.foundry.wallpapers',ROOT/'src/resource.images.foundry.osd',ROOT/'src/resource.uisounds.foundry.pulse']:
            aid=E.parse(source/'addon.xml').getroot().get('id');shutil.copytree(source,addons/aid)
        helper=addons/'script.foundry.helper';skin=addons/'skin.foundry'
        manifest=E.parse(helper/'addon.xml')
        for node in list(manifest.getroot().findall('extension')):
            if node.get('point')=='xbmc.service':manifest.getroot().remove(node)
        for node in list(manifest.getroot().find('requires')):
            if node.get('addon')!='xbmc.python':manifest.getroot().find('requires').remove(node)
        manifest.write(helper/'addon.xml',encoding='UTF-8',xml_declaration=True)
        # Suppress unrelated setup/network entrypoints only in this disposable copy.
        (helper/'resources/lib/default.py').write_text('# Offline native QA: setup/router entrypoint disabled.\n')
        for path in (home/'addons').glob('*/addon.xml'):
            tree=E.parse(path)
            for extension in tree.getroot().findall("extension[@point='xbmc.service']"):tree.getroot().remove(extension)
            tree.write(path,encoding='UTF-8',xml_declaration=True)
        custom=addons/'resource.uisounds.foundry.qacustom'
        shutil.copytree(addons/'resource.uisounds.foundry.pulse',custom)
        tree=E.parse(custom/'addon.xml');tree.getroot().set('id',custom.name);tree.write(custom/'addon.xml',encoding='UTF-8',xml_declaration=True)
        settings=userdata/'addon_data/skin.foundry';settings.mkdir(parents=True)
        (settings/'settings.xml').write_text('<settings><setting id="firsttimerun" type="bool">true</setting></settings>')
        shutil.copyfile(skin/'xml/Home.xml',base/'shipped-Home.xml')
        identity='Foundry Interface QA '+base.name
        (userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">%d</setting><setting id="services.webserverauthentication">false</setting><setting id="services.devicename">%s</setting></settings>'%(port,identity))
        (skin/'xml/Home.xml').write_text('''<window><defaultcontrol always="true">19011</defaultcontrol><controls>
          <control type="image"><width>1920</width><height>1080</height><texture>$VAR[FoundryHomeWallpaper]</texture></control>
          <control type="list" id="9000"><left>-500</left><width>200</width><height>200</height><itemlayout width="200" height="70"><control type="label"><label>$INFO[ListItem.Label]</label></control></itemlayout><focusedlayout width="200" height="70"><control type="label"><label>$INFO[ListItem.Label]</label></control></focusedlayout><content><item><label>Movies</label><property name="id">movies</property></item></content></control>
          <control type="group" id="700"><control type="button" id="802"><left>60</left><top>40</top><width>200</width><height>70</height><label>Settings</label><ondown>19011</ondown><onclick>ActivateWindow(settings)</onclick></control></control>
          <control type="group" id="2000"><control type="list" id="19011"><left>56</left><top>612</top><width>1808</width><height>430</height><orientation>horizontal</orientation><onup>802</onup>
          <itemlayout width="256" height="430"><control type="image"><left>36</left><top>15</top><width>224</width><height>336</height><texture>$INFO[ListItem.Art(poster)]</texture></control></itemlayout>
          <focusedlayout width="256" height="430"><control type="image"><left>36</left><top>15</top><width>224</width><height>336</height><texture>$INFO[ListItem.Art(poster)]</texture></control></focusedlayout>
          </control></control><include>FoundryWidgetMetadata</include></controls></window>''')
        catalog=json.loads((skin/'media/foundry-icons/CATALOG.json').read_text())['icons']
        root=E.fromstring('<window type="window" id="1126"><defaultcontrol>1</defaultcontrol><controls><control type="image"><width>1920</width><height>1080</height><texture colordiffuse="FF081425">colors/white.png</texture></control><control type="button" id="1"><left>8</left><top>8</top><width>150</width><height>50</height><label>Foundry icons</label></control></controls></window>')
        for index,name in enumerate(catalog):
            x=45+(index%10)*186;y=90+(index//10)*164
            node=E.SubElement(root.find('controls'),'control',type='image')
            for key,val in [('left',x),('top',y),('width',128),('height',128),('aspectratio','keep'),('texture','foundry-icons/'+name+'.png')]:E.SubElement(node,key).text=str(val)
        E.ElementTree(root).write(skin/'xml/Custom_11126_IconQA.xml',encoding='UTF-8',xml_declaration=True)
        (skin/'xml/Custom_11127_LiveQA.xml').write_text('<window type="window" id="1127"><defaultcontrol>8802</defaultcontrol><controls><control type="image"><width>1920</width><height>1080</height><texture colordiffuse="FF556478">colors/white.png</texture></control><include>StreamPilotLiveCard</include></controls></window>')
        poster=base/'poster.png';Image.new('RGB',(224,336),'#C8D8E8').save(poster)
        fanart=base/'fanart.png';Image.new('RGB',(1920,1080),'#146B89').save(fanart)
        studio=base/'studio.png';Image.new('RGB',(240,80),'white').save(studio)
        favorites=E.Element('favourites')
        for index in range(3):
            E.SubElement(favorites,'favourite',name='QA Favorite '+str(index+1),thumb=str(poster)).text='PlayMedia("fixture://favorite/%d")'%index
        E.ElementTree(favorites).write(userdata/'favourites.xml',encoding='UTF-8',xml_declaration=True)
        video(base/'fixture.avi')
        launcher=addons/'script.foundry.interfaceqa';launcher.mkdir()
        (launcher/'addon.xml').write_text('<addon id="script.foundry.interfaceqa" version="1.0.0" name="Foundry Interface QA" provider-name="Foundry"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-2.0-only</license></extension></addon>')
        (launcher/'default.py').write_text('from pathlib import Path\nBASE=Path(%r)\nOUTPUT=Path(%r)\nHELPER=Path(%r)\nPOSTER=%r\nFANART=%r\nSTUDIO=%r\n'%(str(base),str(output),str(helper),str(poster),str(fanart),str(studio))+FIXTURE)
        isolated_home=base/'user-home';isolated_home.mkdir()
        environment=dict(os.environ,HOME=str(isolated_home),XDG_CONFIG_HOME=str(isolated_home/'.config'),XDG_CACHE_HOME=str(isolated_home/'.cache'),DISPLAY=display,KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL')
        kodi=None;log=(output/'interface-console.log').open('w')
        xserver=subprocess.Popen(['Xvfb',display,'-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log)
        try:
            time.sleep(1)
            assert xserver.poll() is None,'Private Xvfb failed to start'
            kodi=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=environment,stdout=log,stderr=log,start_new_session=True)
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
            for aid in ('resource.images.foundry.wallpapers','resource.images.foundry.osd','resource.uisounds.foundry.pulse','resource.uisounds.foundry.qacustom','script.foundry.helper','skin.foundry','script.foundry.interfaceqa'):
                rpc('Addons.SetAddonEnabled',{'addonid':aid,'enabled':True})
            assert rpc('Settings.SetSettingValue',{'setting':'lookandfeel.skin','value':'skin.foundry'})
            wait_for(lambda:rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']}).get('System.HasActiveModalDialog'))
            labels=rpc('XBMC.GetInfoLabels',{'labels':['Control.GetLabel(1)','Control.GetLabel(9)']})
            prompt=' '.join(labels.values()).lower()
            assert 'keep' in prompt or 'skin' in prompt,('Unexpected skin-change dialog',labels)
            rpc('Input.Left');rpc('Input.Select')
            wait_for(lambda:not rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']}).get('System.HasActiveModalDialog'))
            wait_for(lambda:rpc('Settings.GetSettingValue',{'setting':'lookandfeel.skin'}).get('value')=='skin.foundry')
            rpc('GUI.ActivateWindow',{'window':'home'})
            rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.interfaceqa'})
            def state():
                if (base/'error.txt').exists():raise AssertionError((base/'error.txt').read_text())
                try:return json.loads((base/'state.json').read_text())
                except (OSError,ValueError):return {}
            playback_serial=0
            def playback_command(action,**values):
                nonlocal playback_serial
                playback_serial+=1
                atomic_text(base/'playback-command.json',json.dumps(dict(values,id=playback_serial,action=action)))
                wait_for(lambda:state().get('playback_command')==playback_serial)
            command_serial=0
            def command(value):
                nonlocal command_serial
                command_serial+=1
                atomic_text(base/'command',value)
                wait_for(lambda:state().get('command_sequence')==command_serial)
            def capture(name):
                destination=output/(name+'.png');destination.unlink(missing_ok=True);atomic_text(base/'capture',name)
                def complete():
                    try:
                        with Image.open(destination) as candidate:candidate.verify()
                        return True
                    except (OSError,ValueError):return False
                wait_for(complete)
                return Image.open(destination).convert('RGB')
            def bright(image,region):return sum(min(image.getpixel((x,y)))>100 for y in range(region[1],region[3]) for x in range(region[0],region[2]))
            wait_for(lambda:state().get('title')=='Widget Film' and bool(state().get('studio')))
            time.sleep(.7);image=capture('widget-film')
            assert bright(image,(92,156,1100,505))>100,'Top-left widget metadata is missing'
            assert bright(image,(92,516,332,580))>100,'Widget studio logo is not above the left side of the row'
            rpc('Input.Right');wait_for(lambda:'S01E02' in state().get('details',''));capture('widget-episode')
            rpc('Input.Up');time.sleep(.8);small=capture('settings-widget-wallpaper')
            widget_source=skin/'media/foundry-widget-wallpapers/settings.png'
            full_source=addons/'resource.images.foundry.wallpapers/resources/settings.png'
            settings_wallpapers={'widget':wallpaper_evidence(small,widget_source,full_source)}
            command('clear-widget');time.sleep(.4);full=capture('settings-full-wallpaper')
            settings_wallpapers['full']=wallpaper_evidence(full,full_source,widget_source)
            (output/'settings-wallpaper-verification.json').write_text(json.dumps(settings_wallpapers,indent=2)+'\n')
            rpc('GUI.ActivateWindow',{'window':'settings'});time.sleep(1);capture('system-settings')
            rpc('GUI.ActivateWindow',{'window':'systemsettings'});time.sleep(1);category=capture('system-setting-rows')
            assert bright(category,(40,145,90,200))>10,'Generated category row has no icon'
            # Options start below Kodi's 50px section heading.
            assert bright(category,(510,200,560,240))>10,'Generated option row has no icon'
            command('play');wait_for(lambda:rpc('Player.GetActivePlayers'))
            time.sleep(.7);rpc('Input.ShowOSD');time.sleep(.8);osd=capture('vod-osd')
            assert bright(osd,(96,742,276,1012))>100,'OSD poster is missing'
            # The rounded card occupies y=834..1036; the retired feather filled
            # y=798..1072. The source panel has a real bottom card edge.
            assert sum(osd.getpixel((900,950)))<sum(osd.getpixel((900,700))),'VOD background frame is missing'
            assert bright(osd,(1540,40,1860,150))>100,'Playback studio logo is missing at top right'
            rpc('Input.Back')
            # IsActive clears before the close animation releases dialog keyboard
            # ownership. Wait for visibility too before sending fullscreen keys.
            wait_for(lambda:not any(rpc('XBMC.GetInfoBooleans',{'booleans':['Window.IsActive(videoosd)','Window.IsVisible(videoosd)']}).values()))
            time.sleep(.35)
            seek_evidence=[]
            for direction in ('Right','Left'):
                # JSON-RPC Input.Right is ACTION_MOVE_RIGHT, not keyboard/remote
                # key mapping. A real key selects Kodi's fullscreen StepForward/Back.
                subprocess.run(['xdotool','key','--clearmodifiers',direction],env=environment,check=True)
                wait_for(lambda:state().get('seek_visible') and bool(state().get('seek_offset') or state().get('seek_step')),5)
                sample=state();seek=capture('vod-seek-'+direction.lower())
                assert sample.get('player_time') and sample.get('player_duration'),sample
                assert bright(seek,(1384,850,1824,886))>20,'Directional seek feedback is not visible'
                assert bright(seek,(1540,40,1860,150))>100,'Seek studio logo is missing'
                seek_evidence.append(sample)
                time.sleep(2.2)
            command('live-frame');wait_for(lambda:state().get('window')==11127);time.sleep(.6);live=capture('live-osd-frame')
            assert sum(live.getpixel((900,900)))+50<sum(live.getpixel((900,700))),'Live background frame is missing'
            assert max(abs(a-b) for a,b in zip(live.getpixel((900,700)),(85,100,120)))<15,'Live preview background is obscured'
            rpc('Player.Stop',{'playerid':1});command('icons');wait_for(lambda:state().get('window')==11126);time.sleep(.8);icons=capture('system-icon-set')
            for index,name in enumerate(catalog):
                x=45+(index%10)*186;y=90+(index//10)*164
                assert bright(icons,(x,y,x+128,y+128))>30,'Missing native icon: '+name
            # Real shipped catalog, native context Play and native Stop/Back.
            # Reopen between cycles so both playback return and navigation cleanup run.
            playback_command('begin');playback_cycles=[]
            for cycle in range(3):
                with_fanart=cycle>0
                playback_command('open-catalog',fanart=with_fanart)
                def catalog_ready():
                    current=state();entry=current.get('catalog') or {}
                    return current.get('window')!=12005 and entry.get('native_ready') and entry.get('focus')==50 and entry.get('size')==6
                wait_for(catalog_ready)
                for position in range(1,4):
                    rpc('Input.Right');wait_for(lambda:(state().get('catalog') or {}).get('position')==position)
                before=state();catalog_window_id=before['window']
                require_label=(before['catalog']['submenu']=='Trending')
                assert require_label,('Movies submenu context missing before playback',before)
                capture('playback-%d-before'%cycle)
                rpc('Input.ContextMenu')
                wait_for(lambda:rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']}).get('System.HasActiveModalDialog'))
                rpc('Input.Select');wait_for(lambda:bool(rpc('Player.GetActivePlayers')))
                wait_for(lambda:state().get('window')==12005)
                time.sleep(.4)
                players=rpc('Player.GetActivePlayers');player=next(item for item in players if item['type']=='video')
                rpc('Player.Stop',{'playerid':player['playerid']})
                wait_for(lambda:not rpc('Player.GetActivePlayers'))
                wait_for(lambda:catalog_ready() and state().get('window')==catalog_window_id)
                after=state();entry=after['catalog']
                assert entry['position']==3 and entry['selected']==3,('Playback lost selection',before,after)
                assert entry['source']==before['catalog']['source'] and entry['file']==before['catalog']['file'],('Playback changed source identity',before,after)
                assert entry['submenu']=='Trending' and entry['fanart']==before['catalog']['fanart'],('Playback changed submenu or item fanart',before,after)
                assert not entry['message'],('Playback return displayed a false source error',after)
                capture('playback-%d-stopped'%cycle)
                rpc('Input.Back')
                wait_for(lambda:state().get('catalog') is None and state().get('playback_closed_parent')==before['playback_parent'])
                assert state()['window']==before['playback_parent'],('Back popped the restored parent',state())
                playback_cycles.append({'cycle':cycle+1,'with_item_fanart':with_fanart,'before':before,'after_stop':after,'after_back':state()})
            playback_command('end')
            report=playback_log_report((profile/'temp/kodi.log').read_text(encoding='utf-8',errors='replace'))
            assert report['complete'] and not report['failures'],('Native playback traceback or diagnostic',report['failures'])
            # Exercise the unchanged shipped Home, not the earlier metadata harness.
            command('favorites')
            wait_for(lambda:state().get('window')==10000 and state().get('favorites_count')=='3')
            assert (skin/'xml/Home.xml').read_bytes()==(SKIN/'xml/Home.xml').read_bytes()
            rpc('Input.Right');wait_for(lambda:state().get('focus')==14100)
            first=state().get('favorite_label');capture('home-favorites-first')
            rpc('Input.Right');wait_for(lambda:state().get('favorite_label')!=first)
            capture('home-favorites-second');rpc('Input.Left');wait_for(lambda:state().get('favorite_label')==first)
            rpc('Input.Back');wait_for(lambda:state().get('focus')==9000)
            assert not rpc('Player.GetActivePlayers'),'Favorites focus started playback'
            # Actual DialogBusy and selected GIF, with native animation and bounded responsiveness.
            rpc('GUI.ActivateWindow',{'window':'settings'});time.sleep(.5)
            command('busy-open');wait_for(lambda:state().get('busy_visible'))
            time.sleep(.8);frames=[];latencies=[];started=time.monotonic()
            for index in range(12):
                frame=ImageGrab.grab(xdisplay=display).convert('RGB');frame.save(output/('ripple-%02d.png'%index))
                frames.append(frame.crop((793,373,1127,707)))
                ping=time.monotonic();assert rpc('JSONRPC.Ping')=='pong';latencies.append(time.monotonic()-ping)
                time.sleep(.13)
            elapsed=time.monotonic()-started
            changed=animation_evidence(frames,latencies,elapsed)
            command('busy-close');wait_for(lambda:not state().get('busy_visible'))
            (base/'complete').write_text('ok')
            (output/'interface-verification.json').write_text(json.dumps({'kodi_version':kodi_version,'diagnostic_only':kodi_version['major']<21,'playback_stop_back_cycles':playback_cycles,'playback_traceback_gate':True,'reported_device_error_reproduced':False,'fixture_identity':identity,'fixture_port':port,'home_favorites_shipped_xml_sha256':hashlib.sha256((SKIN/'xml/Home.xml').read_bytes()).hexdigest(),'home_favorites_row_focus_and_horizontal_navigation':True,'home_favorites_back_returns_menu':True,'preference_migration':json.loads((base/'sounds.json').read_text()),'pulse_native_resource_selected':rpc('Settings.GetSettingValue',{'setting':'lookandfeel.soundskin'})['value'],'audible_output_verified':False,'directional_seek':seek_evidence,'playback_studio_logo_top_right':True,'ripple_native_dialog':'busydialognocancel (shipped DialogBusy.xml)','ripple_changed_pixels':changed,'ripple_capture_elapsed_seconds':elapsed,'ripple_rpc_max_seconds':max(latencies),'widget_metadata_top_left':True,'widget_episode_number_title':True,'studio_logo_above_left_row':True,'settings_hover_uses_widget_wallpaper':True,'empty_widget_restores_full_wallpaper':True,'system_menu_icons':len(catalog),'generated_category_and_option_icons':True,'vod_rounded_frame':True,'live_rounded_frame_preview':True,'scope':'Isolated native desktop Kodi; synthetic metadata/video/Favorites; initial widget harness only, restored shipped Home for Favorites, helper setup/service disabled, null audio sink. Live providers, audible sound, device FPS and Shield remain unverified'},indent=2)+'\n')
        except Exception:
            try:ImageGrab.grab(xdisplay=display).save(output/'interface-failure.png')
            except Exception:pass
            raise
        finally:
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
            for name in ['state.json','error.txt','sounds.json']:
                if (base/name).exists():shutil.copyfile(base/name,output/('interface-'+name))


if __name__=='__main__':main()
