"""Verify widget metadata, OSD frames and system icons in native Foundry/Kodi."""
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import tempfile
import time
from io import BytesIO
from urllib.request import Request,urlopen
import xml.etree.ElementTree as E
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'
HELPER=ROOT.parent/'script.foundry.helper'

FIXTURE=r'''
import json,sys,time,traceback
from pathlib import Path
import xbmc,xbmcgui
sys.path.insert(0,str(HELPER/'resources/lib'))
from modules.monitors.metadata import MetadataMonitor
from modules.vod import CatalogArtworkMonitor
class Provider:
    def enrich(self,item,section):
        item=dict(item);item['art']=dict(item.get('art') or {},studiologo=STUDIO)
        item['ratings']={'tmdb':{'rating':7.2},'imdb':{'rating':7.8}}
        return item,{'tmdb':'ready','omdb':'ready'}
try:
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if xbmc.getSkinDir()=='skin.foundry':
            try:
                window=xbmcgui.Window(10000);row=window.getControl(19011)
                break
            except RuntimeError:pass
        xbmc.sleep(100)
    else:raise AssertionError('Foundry fixture Home did not load; active skin: '+xbmc.getSkinDir())
    metadata=MetadataMonitor(window,provider=Provider());artwork=CatalogArtworkMonitor()
    for title,kind,season,episode in [('Widget Film','movie',None,None),('The Signal','episode',1,2)]:
        item=xbmcgui.ListItem(title,path='fixture://'+kind)
        info={'title':title,'year':2026,'mediatype':kind,'plot':'A complete focused widget item shows the same metadata stack as the library.','genre':['Mystery'],'studio':['Fixture Studio'],'premiered':'2026-11-01'}
        if kind=='episode':info.update(tvshowtitle='Fixture Series',season=season,episode=episode)
        item.setInfo('video',info);item.setArt({'poster':POSTER,'fanart':FANART,'studiologo':STUDIO})
        row.addItem(item)
    window.setFocusId(19011)
    deadline=time.monotonic()+180
    while not (BASE/'complete').exists() and time.monotonic()<deadline:
        metadata.process_current_item();artwork.process_current_item()
        def label(name):return xbmc.getInfoLabel(name)
        snapshot={'window':xbmcgui.getCurrentWindowId(),'label':label('ListItem.Label'),
                  'details':label('Control.GetLabel(5723)'),
                  'studio':window.getProperty('foundry.vod.studio_logo'),
                  'title':window.getProperty('foundry.metadata.title'),
                  'wallpaper':label('Skin.String(foundry.fixture)')}
        (BASE/'state.tmp').write_text(json.dumps(snapshot));(BASE/'state.tmp').replace(BASE/'state.json')
        command=BASE/'command'
        if command.exists():
            value=command.read_text();command.unlink()
            if value=='clear-widget':row.reset()
            elif value=='icons':xbmc.executebuiltin('ActivateWindow(11126)')
            elif value=='live-frame':xbmc.executebuiltin('ActivateWindow(11127)')
            elif value=='play':
                item=xbmcgui.ListItem('Foundry Playback')
                item.setInfo('video',{'title':'Foundry Playback','mediatype':'movie'})
                item.setArt({'poster':POSTER})
                xbmc.Player().play(str(BASE/'fixture.avi'),item)
        capture=BASE/'capture'
        if capture.exists():
            name=capture.read_text();capture.unlink()
            xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+')')
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


def main():
    output=ROOT/'releases/1.3.9-qa';output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='foundry-interface-') as temporary:
        base=Path(temporary);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
        profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True)
        addons=profile/'addons';addons.mkdir()
        for source in [SKIN,HELPER,ROOT/'src/resource.images.foundry.wallpapers',ROOT/'src/resource.images.foundry.osd']:
            aid=E.parse(source/'addon.xml').getroot().get('id');shutil.copytree(source,addons/aid)
        helper=addons/'script.foundry.helper';skin=addons/'skin.foundry'
        manifest=E.parse(helper/'addon.xml')
        for node in list(manifest.getroot().findall('extension')):
            if node.get('point')=='xbmc.service':manifest.getroot().remove(node)
        for node in list(manifest.getroot().find('requires')):
            if node.get('addon')!='xbmc.python':manifest.getroot().find('requires').remove(node)
        manifest.write(helper/'addon.xml',encoding='UTF-8',xml_declaration=True)
        (userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">18081</setting><setting id="services.webserverauthentication">false</setting></settings>')
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
        video(base/'fixture.avi')
        launcher=addons/'script.foundry.interfaceqa';launcher.mkdir()
        (launcher/'addon.xml').write_text('<addon id="script.foundry.interfaceqa" version="1.0.0" name="Foundry Interface QA" provider-name="Foundry"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-2.0-only</license></extension></addon>')
        (launcher/'default.py').write_text('from pathlib import Path\nBASE=Path(%r)\nOUTPUT=Path(%r)\nHELPER=Path(%r)\nPOSTER=%r\nFANART=%r\nSTUDIO=%r\n'%(str(base),str(output),str(helper),str(poster),str(fanart),str(studio))+FIXTURE)
        environment=dict(os.environ,DISPLAY=':99',KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL')
        kodi=None;log=(output/'interface-console.log').open('w')
        xserver=subprocess.Popen(['Xvfb',':99','-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log)
        try:
            time.sleep(1);kodi=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=environment,stdout=log,stderr=log,start_new_session=True)
            def rpc(method,params=None):
                data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode()
                with urlopen(Request('http://127.0.0.1:18081/jsonrpc',data=data,headers={'Content-Type':'application/json'}),timeout=5) as response:result=json.loads(response.read())
                if 'error' in result:raise RuntimeError(str(result['error']))
                return result.get('result')
            def ready():
                try:return rpc('JSONRPC.Ping')=='pong'
                except Exception:return False
            wait_for(ready,60)
            for _ in range(5):
                visible=rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']})
                if not visible.get('System.HasActiveModalDialog'):break
                rpc('Input.Back');time.sleep(.2)
            # Fresh profiles discover manually placed add-ons as disabled.
            # Enable the isolated fixture dependencies before selecting its skin.
            for aid in ('resource.images.foundry.wallpapers','resource.images.foundry.osd','script.foundry.helper','skin.foundry','script.foundry.interfaceqa'):
                rpc('Addons.SetAddonEnabled',{'addonid':aid,'enabled':True})
            assert rpc('Settings.SetSettingValue',{'setting':'lookandfeel.skin','value':'skin.foundry'})
            time.sleep(1)
            if rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog']}).get('System.HasActiveModalDialog'):
                rpc('Input.Left');rpc('Input.Select')
            wait_for(lambda:rpc('Settings.GetSettingValue',{'setting':'lookandfeel.skin'}).get('value')=='skin.foundry')
            rpc('GUI.ActivateWindow',{'window':'home'})
            rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.interfaceqa'})
            def state():
                if (base/'error.txt').exists():raise AssertionError((base/'error.txt').read_text())
                try:return json.loads((base/'state.json').read_text())
                except (OSError,ValueError):return {}
            def capture(name):
                destination=output/(name+'.png');destination.unlink(missing_ok=True);(base/'capture').write_text(name)
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
            expected=Image.open(skin/'media/foundry-widget-wallpapers/settings.png').convert('RGB').resize((1920,1080))
            for point in [(1400,230),(1550,400),(600,720)]:assert max(abs(a-b) for a,b in zip(small.getpixel(point),expected.getpixel(point)))<25,'Settings hover did not select the widget wallpaper'
            (base/'command').write_text('clear-widget');time.sleep(.4);full=capture('settings-full-wallpaper')
            assert sum(abs(a-b) for a,b in zip(full.getpixel((1400,230)),small.getpixel((1400,230))))>20,'Empty widgets did not restore the full Settings wallpaper'
            rpc('GUI.ActivateWindow',{'window':'settings'});time.sleep(1);capture('system-settings')
            rpc('GUI.ActivateWindow',{'window':'systemsettings'});time.sleep(1);category=capture('system-setting-rows')
            assert bright(category,(40,145,90,200))>10,'Generated category row has no icon'
            assert bright(category,(510,145,560,195))>10,'Generated option row has no icon'
            (base/'command').write_text('play');wait_for(lambda:rpc('Player.GetActivePlayers'))
            time.sleep(.7);rpc('Input.ShowOSD');time.sleep(.8);osd=capture('vod-osd')
            assert bright(osd,(96,742,276,1012))>100,'OSD poster is missing'
            # The rounded card occupies y=834..1036; the retired feather filled
            # y=798..1072. The source panel has a real bottom card edge.
            assert sum(osd.getpixel((900,950)))<sum(osd.getpixel((900,700))),'VOD background frame is missing'
            rpc('Input.Back')
            wait_for(lambda:not rpc('XBMC.GetInfoBooleans',{'booleans':['Window.IsActive(videoosd)']}).get('Window.IsActive(videoosd)'))
            (base/'command').write_text('live-frame');wait_for(lambda:state().get('window')==11127);time.sleep(.6);live=capture('live-osd-frame')
            assert sum(live.getpixel((900,900)))+50<sum(live.getpixel((900,700))),'Live background frame is missing'
            assert max(abs(a-b) for a,b in zip(live.getpixel((900,700)),(85,100,120)))<15,'Live preview background is obscured'
            rpc('Player.Stop',{'playerid':1});(base/'command').write_text('icons');wait_for(lambda:state().get('window')==11126);time.sleep(.8);icons=capture('system-icon-set')
            for index,name in enumerate(catalog):
                x=45+(index%10)*186;y=90+(index//10)*164
                assert bright(icons,(x,y,x+128,y+128))>30,'Missing native icon: '+name
            (base/'complete').write_text('ok')
            (output/'interface-verification.json').write_text(json.dumps({'widget_metadata_top_left':True,'widget_episode_number_title':True,'studio_logo_above_left_row':True,'settings_hover_uses_widget_wallpaper':True,'empty_widget_restores_full_wallpaper':True,'system_menu_icons':len(catalog),'generated_category_and_option_icons':True,'vod_rounded_frame':True,'live_rounded_frame_preview':True,'scope':'Isolated native desktop Kodi; live providers and Shield remain unverified'},indent=2)+'\n')
        finally:
            if kodi:
                try:os.killpg(kodi.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:kodi.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(kodi.pid,signal.SIGKILL);kodi.wait(timeout=5)
            xserver.terminate();xserver.wait(timeout=5);log.close()
            if (profile/'temp/kodi.log').exists():shutil.copyfile(profile/'temp/kodi.log',output/'interface-kodi.log')
            for name in ['state.json','error.txt']:
                if (base/name).exists():shutil.copyfile(base/name,output/('interface-'+name))


if __name__=='__main__':main()
