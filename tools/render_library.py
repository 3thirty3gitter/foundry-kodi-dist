"""Render the shipped catalog in native Kodi/X11 with an isolated fixture profile.

The runner needs Kodi, Xvfb, xdotool, Pillow and requests. No personal media,
accounts, API keys or network providers are loaded. The active Estuary fixture
provides fonts/textures; the window and controller are the shipped Foundry code.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as E
from urllib.request import Request, urlopen
from PIL import Image, ImageDraw, ImageFont


ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT.parent/'skin.foundry-nimbus'
HELPER=ROOT.parent/'script.foundry.helper'


FIXTURE=r'''
import json,sys,time,traceback
from pathlib import Path
import xbmc,xbmcgui
sys.path.insert(0,str(HELPER/'resources/lib'))
from modules.catalog_window import CatalogWindow

class Source:
    scope='fixture'
    path='fixture://library'
    def load(self):
        return {'items':ITEMS,'page':1,'total_pages':500}
    def search(self,query):return None

try:
    for section,count,case in (('Movies',60,'movies'),('TV Shows',60,'tv-shows'),('Movies',3,'short-row')):
        data=[dict(item,type='tvshow' if section=='TV Shows' else 'movie') for item in ITEMS[:count]]
        source=Source();source.load=lambda:{'items':data,'page':1,'total_pages':500}
        window=CatalogWindow('script-foundry-vod.xml',str(HELPER),'default','1080i',True,source=source,section=section,breadcrumb='Trending')
        window.show();deadline=time.monotonic()+90
        while not window.closed and time.monotonic()<deadline:
            window.tick()
            snapshot={'case':case,'initialized':window.initialized,'current_window':xbmcgui.getCurrentWindowId(),'section':section,'focus':window.getFocusId(),'position':window.getCurrentListPosition(),
                      'page':window.state.page,'title':window.getProperty('catalog.title'),
                      'kind':window.rail[window.getCurrentListPosition()].get('kind') if window.rail else '',
                      'sort_open':window.getProperty('catalog.sortopen'),
                      'tmdb':window.getProperty('catalog.tmdb'),'imdb':window.getProperty('catalog.imdb'),
                      'accent':window.getProperty('catalog.accent')}
            temporary=BASE/'state.tmp';temporary.write_text(json.dumps(snapshot));temporary.replace(BASE/'state.json')
            if (BASE/'capture.json').exists():
                name=json.loads((BASE/'capture.json').read_text())['name'];(BASE/'capture.json').unlink()
                xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+')')
            xbmc.sleep(50)
        window.dispose()
    (BASE/'complete').write_text('ok')
except Exception:
    (BASE/'error.txt').write_text(traceback.format_exc())
'''


def wait_for(predicate,timeout=40):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.1)
    raise RuntimeError('Native Kodi fixture did not reach its expected state')


def main():
    output=ROOT/'releases/1.3.2-qa';output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='foundry-kodi-') as temporary:
        base=Path(temporary);home=base/'kodi';shutil.copytree('/usr/share/kodi',home,ignore_dangling_symlinks=True)
        profile=home/'portable_data';userdata=profile/'userdata';userdata.mkdir(parents=True)
        helper=profile/'addons/script.foundry.helper';shutil.copytree(HELPER,helper)
        manifest=E.parse(helper/'addon.xml')
        for node in list(manifest.getroot().findall('extension')):
            if node.get('point')=='xbmc.service':manifest.getroot().remove(node)
        for node in list(manifest.getroot().find('requires')):
            if node.get('addon') != 'xbmc.python':manifest.getroot().find('requires').remove(node)
        manifest.write(helper/'addon.xml',encoding='UTF-8',xml_declaration=True)
        template=helper/'resources/skins/default/1080i';template.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(SKIN/'xml/script-foundry-vod.xml',template/'script-foundry-vod.xml')
        active=home/'addons/skin.estuary'
        shutil.copytree(SKIN/'media/streampilot',active/'media/streampilot',dirs_exist_ok=True)
        for name in ('Roboto-Regular.ttf','Roboto-Bold.ttf','NotoSans-Regular.ttf','NotoMono-Regular.ttf'):
            shutil.copyfile(SKIN/'fonts'/name,active/'fonts'/name)
        fonts=E.parse(active/'xml/Font.xml');source=E.parse(SKIN/'xml/Font.xml')
        for fontset in fonts.findall('fontset'):
            for font in source.find('fontset').findall('font'):
                if (font.findtext('name') or '').startswith('sp_'):
                    fontset.append(E.fromstring(E.tostring(font)))
        fonts.write(active/'xml/Font.xml',encoding='UTF-8',xml_declaration=True)
        (userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">18080</setting><setting id="services.webserverauthentication">false</setting></settings>')
        keymaps=userdata/'keymaps';keymaps.mkdir()
        (keymaps/'fixture.xml').write_text('<keymap><global><keyboard><f12>RunScript('+str(base/'fixture.py')+')</f12></keyboard></global></keymap>')
        assets=base/'assets';assets.mkdir()
        regular=ImageFont.truetype(str(SKIN/'fonts/Roboto-Regular.ttf'),24)
        bold=ImageFont.truetype(str(SKIN/'fonts/Roboto-Bold.ttf'),42)
        logo=assets/'clearlogo.png';image=Image.new('RGBA',(520,132));ImageDraw.Draw(image).text((16,30),'NATIVE TITLE',font=bold,fill='white');image.save(logo)
        studio=assets/'studio.png';image=Image.new('RGBA',(240,140));ImageDraw.Draw(image).text((36,45),'STUDIO',font=regular,fill='black');image.save(studio)
        colors=['#146B89','#D04A2A','#7D25E6','#1B9382','#CA3162','#50851B','#3B6FBD']
        items=[]
        for index in range(60):
            color=colors[index%len(colors)]
            poster=assets/('poster-%d.png'%index);image=Image.new('RGB',(224,336),color)
            draw=ImageDraw.Draw(image);draw.text((18,34),'TITLE',font=regular,fill='white');draw.text((18,78),str(index+1),font=bold,fill='white');image.save(poster)
            fanart=assets/('fanart-%d.png'%index);image=Image.new('RGB',(1920,1080),color);image.save(fanart)
            items.append({'title':'Fixture title %02d'%(index+1),'label':'Fixture title %02d'%(index+1),'file':'fixture://title/%d'%index,'filetype':'file','year':2026,
                          'premiered':'2026-09-30','mpaa':'CA 14A','plot':'A controlled native Kodi fixture checks the exact source poster geometry, artwork glow, metadata and remote focus behavior.',
                          'genre':['Mystery','Thriller'],'studio':['Fixture Studio'],'original_language':'en','ratings':{'tmdb':{'rating':7.0},'imdb':{'rating':7.1}},
                          'art':{'poster':str(poster),'fanart':str(fanart),'clearlogo':str(logo),'studiologo':str(studio)}})
        script='BASE=Path(%r)\nHELPER=Path(%r)\nOUTPUT=Path(%r)\nITEMS=%r\n'%(str(base),str(helper),str(output),items)
        launcher=profile/'addons/script.foundry.libraryqa';launcher.mkdir()
        (launcher/'addon.xml').write_text('<addon id="script.foundry.libraryqa" version="1.0.0" name="Foundry Library QA" provider-name="Foundry"><requires><import addon="xbmc.python" version="3.0.0" /></requires><extension point="xbmc.python.script" library="fixture.py" /><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-2.0-only</license><summary lang="en_GB">Controlled fixture</summary></extension></addon>')
        (launcher/'fixture.py').write_text('from pathlib import Path\n'+script+FIXTURE)
        environment=dict(os.environ,DISPLAY=':99',KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL')
        log=open(output/'kodi-console.log','w')
        xserver=subprocess.Popen(['Xvfb',':99','-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log)
        kodi=None
        try:
            time.sleep(1)
            kodi=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=environment,stdout=log,stderr=log)
            def rpc(method,params=None):
                payload=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode()
                with urlopen(Request('http://127.0.0.1:18080/jsonrpc',data=payload,headers={'Content-Type':'application/json'}),timeout=5) as response:
                    result=json.loads(response.read())
                if 'error' in result:raise RuntimeError(str(result['error']))
                return result.get('result')
            def ready():
                try:return rpc('JSONRPC.Ping')=='pong'
                except Exception:return False
            wait_for(ready,60)
            methods={'Right':'Input.Right','Left':'Input.Left','Down':'Input.Down','Return':'Input.Select','Escape':'Input.Back','Up':'Input.Up'}
            def key(*names):
                for name in names:
                    rpc(methods[name]);time.sleep(.15)
            def state():
                if (base/'error.txt').exists():raise RuntimeError((base/'error.txt').read_text())
                try:return json.loads((base/'state.json').read_text())
                except (OSError,ValueError):return {}
            # A fresh Kodi profile can show its first-run confirmation dialog.
            # It must close before Kodi permits a non-modal WindowXML to open.
            for _ in range(5):
                visible=rpc('XBMC.GetInfoBooleans',{'booleans':['System.HasActiveModalDialog','System.HasVisibleModalDialog']})
                if not any(visible.values()):break
                if visible.get('System.HasActiveModalDialog'):rpc('Input.Back')
                time.sleep(.3)
            rpc('Addons.SetAddonEnabled',{'addonid':'script.foundry.helper','enabled':True})
            rpc('Addons.SetAddonEnabled',{'addonid':'script.foundry.libraryqa','enabled':True})
            rpc('Addons.ExecuteAddon',{'addonid':'script.foundry.libraryqa'})
            evidence=[]
            def capture(name):
                destination=output/(name+'.png')
                destination.unlink(missing_ok=True)
                (base/'capture.json').write_text(json.dumps({'name':name}))
                def complete():
                    try:
                        with Image.open(destination) as im:im.verify()
                        return True
                    except (OSError,ValueError):return False
                wait_for(complete)
                with Image.open(destination) as im:return im.convert('RGB')
            def poster_bounds(im,target,region):
                pixels=im.load();l,t,r,b=region
                matches={(x,y) for y in range(t,b) for x in range(l,r) if max(abs(pixels[x,y][c]-target[c]) for c in range(3))<=3}
                assert matches,'Focused poster was not rendered'
                # Saturation-boosted artwork light can pass through the original
                # poster RGB again in a disconnected halo. Measure the connected
                # poster body containing its center, excluding that outer ring.
                seed=min(matches,key=lambda p:(p[0]-(l+r)/2)**2+(p[1]-(t+b)/2)**2)
                body={seed};pending=[seed]
                while pending:
                    x,y=pending.pop()
                    for point in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                        if point in matches and point not in body:body.add(point);pending.append(point)
                return [min(x for x,y in body),min(y for x,y in body),max(x for x,y in body)+1,max(y for x,y in body)+1]
            for section,name in [('Movies','movies'),('TV Shows','tv-shows')]:
                wait_for(lambda:state().get('case')==name and state().get('focus')==50 and bool(state().get('title')))
                key('Right','Right');wait_for(lambda:state().get('position')==2)
                wait_for(lambda:bool(state().get('tmdb')) and bool(state().get('imdb')) and state().get('accent')=='FF7D25E6')
                time.sleep(1)
                focused=capture(name)
                assert focused.size==(1920,1080),focused.size
                bounds=poster_bounds(focused,(125,37,230),(540,480,940,980))
                expected=[598,528,865,928]
                assert all(abs(a-b)<=4 for a,b in zip(bounds,expected)),(bounds,expected)
                key('Down');wait_for(lambda:state().get('focus')==5703)
                time.sleep(.5);unfocused=capture(name+'-unfocused')
                # Inspect rendered pixels, not just the accent property: below
                # the zoomed poster, colored light must fade into the fanart.
                point=(730,960)
                delta=[focused.getpixel(point)[c]-unfocused.getpixel(point)[c] for c in range(3)]
                assert delta[2]>=15 and delta[0]>=5,(point,delta)
                key('Return');wait_for(lambda:state().get('focus')==5750)
                key('Escape');wait_for(lambda:state().get('focus')==5703)
                key('Up');wait_for(lambda:state().get('focus')==50 and state().get('position')==2)
                key(*(['Right']*8));wait_for(lambda:state().get('position')==10)
                wait_for(lambda:state().get('accent')=='FF25C7B0');time.sleep(.7)
                middle=poster_bounds(capture(name+'-scrolled'),(27,147,130),(540,480,940,980))
                assert all(abs(a-b)<=4 for a,b in zip(middle,expected)),(middle,expected)
                key(*(['Right']*10));wait_for(lambda:state().get('kind')=='next');time.sleep(.7)
                capture(name+'-next')
                key('Right');assert state().get('position')==20,'Rail wrapped at NEXT'
                key('Return');wait_for(lambda:state().get('page')==2 and state().get('position')==1 and state().get('kind')=='media')
                key('Left');wait_for(lambda:state().get('kind')=='previous');time.sleep(.7)
                capture(name+'-previous')
                key('Left');assert state().get('position')==0,'Rail wrapped at BACK'
                key('Return');wait_for(lambda:state().get('page')==1 and state().get('position')==0 and state().get('kind')=='media')
                evidence.append({'section':section,'screenshot':name+'.png','focused_poster_bounds':bounds,'scrolled_poster_bounds':middle,'source_expected_bounds':expected,'visible_colored_glow_delta_rgb':delta,'sort_cancel_restores_poster':True,'next_previous_page_roundtrip':True,'row_ends_do_not_wrap':True})
                key('Escape')
            wait_for(lambda:state().get('case')=='short-row' and state().get('focus')==50 and state().get('position')==0)
            wait_for(lambda:state().get('accent')=='FF1D9BC7');time.sleep(.7)
            short=poster_bounds(capture('short-row'),(20,107,137),(60,480,400,980))
            assert all(abs(a-b)<=4 for a,b in zip(short,[91,528,357,928])),short
            evidence.append({'section':'Three-title row','focused_poster_bounds':short,'left_padding_preserved':True})
            key('Escape')
            wait_for(lambda:(base/'complete').exists())
            (output/'verification.json').write_text(json.dumps({'renderer':'Native Kodi '+subprocess.check_output(['kodi','--version'],text=True).strip(),'canvas':[1920,1080],'checks':evidence,'scope':'Controlled fixtures; not Shield, live providers or Android pixel parity'},indent=2)+'\n')
        finally:
            if kodi:kodi.terminate()
            xserver.terminate();log.close()
            logs=profile/'temp/kodi.log'
            if logs.exists():shutil.copyfile(logs,output/'kodi.log')
            for name in ('state.json','error.txt'):
                if (base/name).exists():shutil.copyfile(base/name,output/name)


if __name__=='__main__':main()
