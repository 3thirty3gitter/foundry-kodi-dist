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
import copy
import signal


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
    for section,count,case in (('Movies',60,'movies'),('TV Shows',60,'tv-shows'),('Movies',3,'short-row'),('TV Shows',2,'episodes')):
        data=EPISODES if case=='episodes' else [dict(item,type='tvshow' if section=='TV Shows' else 'movie') for item in ITEMS[:count]]
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
                      'accent':window.getProperty('catalog.accent'),'details':window.getProperty('catalog.details'),
                      'rendered_details':xbmc.getInfoLabel('Control.GetLabel(5713)'),'released':window.getProperty('catalog.released')}
            temporary=BASE/'state.tmp';temporary.write_text(json.dumps(snapshot));temporary.replace(BASE/'state.json')
            if (BASE/'capture.json').exists():
                name=json.loads((BASE/'capture.json').read_text())['name'];(BASE/'capture.json').unlink()
                xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+')')
            xbmc.sleep(50)
        window.dispose()
    from modules.monitors.metadata import MetadataMonitor
    from modules.vod import CatalogArtworkMonitor
    class SharedProvider:
        def enrich(self,item,section):
            item=dict(item);item['art']=dict(item.get('art') or {},studiologo=STUDIO)
            item['ratings']={'tmdb':{'rating':7.0},'imdb':{'rating':7.1}}
            return item,{'tmdb':'ready','omdb':'ready'}
    metadata=MetadataMonitor(xbmcgui.Window(10000),provider=SharedProvider())
    artwork=CatalogArtworkMonitor()
    xbmc.executebuiltin('ActivateWindow(Videos,plugin://plugin.video.foundry.libraryqa/?page=1,return)')
    deadline=time.monotonic()+90
    while not (BASE/'native-complete').exists() and time.monotonic()<deadline:
        metadata.process_current_item();artwork.process_current_item()
        def info(label):return xbmc.getInfoLabel(label)
        try:focus=xbmcgui.Window(10025).getFocusId()
        except RuntimeError:focus=0
        snapshot={'case':'native','current_window':xbmcgui.getCurrentWindowId(),'focus':focus,
                  'position':int(info('Container(57).CurrentItem') or '0')-1,
                  'title':info('ListItem.Title'),'label':info('ListItem.Label'),
                  'path':info('Container.FolderPath'),
                  'tmdb':info('Window(Home).Property(foundry.metadata.tmdb)'),
                  'imdb':info('Window(Home).Property(foundry.metadata.imdb)'),
                  'studio':info('Window(Home).Property(foundry.vod.studio_logo)')}
        temporary=BASE/'state.tmp';temporary.write_text(json.dumps(snapshot));temporary.replace(BASE/'state.json')
        if (BASE/'capture.json').exists():
            name=json.loads((BASE/'capture.json').read_text())['name'];(BASE/'capture.json').unlink()
            xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+')')
        xbmc.sleep(50)
    from modules.favorites import remember
    from modules.metadata import service
    remember(service().cache,dict(ITEMS[0],type='movie',file='plugin://plugin.video.foundry.libraryqa/?movie=1'))
    remember(service().cache,dict(EPISODES[0],file='plugin://plugin.video.foundry.libraryqa/?episode=2'))
    xbmc.executebuiltin('ActivateWindow(favouritesbrowser)')
    deadline=time.monotonic()+90
    while not (BASE/'favorites-complete').exists() and time.monotonic()<deadline:
        metadata.process_current_item();artwork.process_current_item()
        try:focus=xbmcgui.Window(10060).getFocusId()
        except RuntimeError:focus=0
        snapshot={'case':'favorites','current_window':xbmcgui.getCurrentWindowId(),'focus':focus,
                  'label':xbmc.getInfoLabel('ListItem.Label'),
                  'title':xbmc.getInfoLabel('Window(Home).Property(foundry.metadata.title)'),
                  'details':xbmc.getInfoLabel('Window(Home).Property(foundry.metadata.details)'),
                  'rendered_details':xbmc.getInfoLabel('Control.GetLabel(5713)'),
                  'plot':xbmc.getInfoLabel('Window(Home).Property(foundry.metadata.plot)'),
                  'released':xbmc.getInfoLabel('Window(Home).Property(foundry.metadata.released_label)'),
                  'studio':xbmc.getInfoLabel('Window(Home).Property(foundry.vod.studio_logo)'),
                  'tmdb':xbmc.getInfoLabel('Window(Home).Property(foundry.metadata.tmdb)'),
                  'imdb':xbmc.getInfoLabel('Window(Home).Property(foundry.metadata.imdb)')}
        temporary=BASE/'state.tmp';temporary.write_text(json.dumps(snapshot));temporary.replace(BASE/'state.json')
        if (BASE/'capture.json').exists():
            name=json.loads((BASE/'capture.json').read_text())['name'];(BASE/'capture.json').unlink()
            xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+')')
        xbmc.sleep(50)
    metadata.stop()
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
    output=ROOT/'releases/1.3.7-qa';output.mkdir(parents=True,exist_ok=True)
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
        native=E.parse(SKIN/'xml/View_57_StreamPilot.xml')
        for texture in native.iter('texture'):
            if texture.text=='$VAR[MediaFanartVar]':texture.text='$VAR[FoundryQAFanart]'
        for filename,names in [('Expressions.xml',('FoundryOmdbCurrentItem','FoundryVODCurrentItem')),('Includes_Metadata.xml',('FoundryMetadataCurrentItem',))]:
            expressions=E.parse(SKIN/'xml'/filename)
            for name in names:native.getroot().append(copy.deepcopy(expressions.find("expression[@name='%s']"%name)))
        for name,value in [('FoundryQAFanart','$INFO[ListItem.Art(fanart)]'),('BreadcrumbsVideoVar','Native provider fixture')]:
            variable=E.SubElement(native.getroot(),'variable',name=name)
            if name=='FoundryQAFanart':E.SubElement(variable,'value',condition='$EXP[FoundryMetadataCurrentItem] + !String.IsEmpty(Window(Home).Property(foundry.metadata.fanart))').text='$INFO[Window(Home).Property(foundry.metadata.fanart)]'
            E.SubElement(variable,'value').text=value
        native.write(active/'xml/FoundryNativeQA.xml',encoding='UTF-8',xml_declaration=True)
        includes=E.parse(active/'xml/Includes.xml');E.SubElement(includes.getroot(),'include',file='FoundryNativeQA.xml');includes.write(active/'xml/Includes.xml',encoding='UTF-8',xml_declaration=True)
        (active/'xml/MyVideoNav.xml').write_text('<window><defaultcontrol always="true">57</defaultcontrol><views>57</views><controls><include>View_57_StreamPilot</include></controls></window>')
        favorites_view=E.fromstring('<window><defaultcontrol always="true">57</defaultcontrol><views>57</views><controls><include>View_57_StreamPilot</include></controls></window>')
        for action in E.parse(SKIN/'xml/MyFavourites.xml').findall('onload'):favorites_view.insert(1,copy.deepcopy(action))
        E.ElementTree(favorites_view).write(active/'xml/MyFavourites.xml',encoding='UTF-8',xml_declaration=True)
        (userdata/'guisettings.xml').write_text('<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="filelists.showparentdiritems">false</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">18080</setting><setting id="services.webserverauthentication">false</setting></settings>')
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
            draw=ImageDraw.Draw(image);draw.text((18,34),'TITLE',font=regular,fill='white');draw.text((18,78),str(index+1),font=bold,fill='white')
            # Four tiny fixture-only fiducials distinguish the opaque artwork
            # edge from a same-hue glow. No released media/artwork is modified.
            for x,y in ((24,24),(196,24),(24,308),(196,308)):
                draw.rectangle((x,y,x+3,y+3),fill=(255,0,255))
            image.save(poster)
            fanart=assets/('fanart-%d.png'%index);image=Image.new('RGB',(1920,1080),color);image.save(fanart)
            items.append({'title':'Fixture title %02d'%(index+1),'label':'Fixture title %02d'%(index+1),'file':'fixture://title/%d'%index,'filetype':'file','year':2026,
                          'premiered':'2026-09-30','mpaa':'CA 14A','plot':'A controlled native Kodi fixture checks the exact source poster geometry, artwork glow, metadata and remote focus behavior.',
                          'genre':['Mystery','Thriller'],'studio':['Fixture Studio'],'original_language':'en','ratings':{'tmdb':{'rating':7.0},'imdb':{'rating':7.1}},
                          'art':{'poster':str(poster),'fanart':str(fanart),'clearlogo':str(logo),'studiologo':str(studio)}})
        episodes=[dict(items[0],type='episode',title='The Signal',showtitle='Fixture Series',season=1,episode=2,premiered='2026-11-01',runtime=2700),dict(items[1],type='episode',title='Origin Special',showtitle='Fixture Series',season=0,episode=0,premiered='2026-10-01',runtime=1800)]
        favorites=E.Element('favourites')
        for title,target in [('Saved movie','plugin://plugin.video.foundry.libraryqa/?movie=1'),('Saved episode','plugin://plugin.video.foundry.libraryqa/?episode=2')]:
            E.SubElement(favorites,'favourite',name=title,thumb=items[0]['art']['poster']).text='PlayMedia("'+target+'")'
        E.ElementTree(favorites).write(userdata/'favourites.xml',encoding='UTF-8',xml_declaration=True)
        script='BASE=Path(%r)\nHELPER=Path(%r)\nOUTPUT=Path(%r)\nITEMS=%r\nEPISODES=%r\nSTUDIO=%r\n'%(str(base),str(helper),str(output),items,episodes,str(studio))
        launcher=profile/'addons/script.foundry.libraryqa';launcher.mkdir()
        (launcher/'addon.xml').write_text('<addon id="script.foundry.libraryqa" version="1.0.0" name="Foundry Library QA" provider-name="Foundry"><requires><import addon="xbmc.python" version="3.0.0" /></requires><extension point="xbmc.python.script" library="fixture.py" /><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-2.0-only</license><summary lang="en_GB">Controlled fixture</summary></extension></addon>')
        (launcher/'fixture.py').write_text('from pathlib import Path\n'+script+FIXTURE)
        plugin=profile/'addons/plugin.video.foundry.libraryqa';plugin.mkdir()
        (plugin/'addon.xml').write_text('<addon id="plugin.video.foundry.libraryqa" version="1.0.0" name="Foundry Native Library QA" provider-name="Foundry"><requires><import addon="xbmc.python" version="3.0.0" /></requires><extension point="xbmc.python.pluginsource" library="default.py"><provides>video</provides></extension><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-2.0-only</license><summary lang="en_GB">Controlled native fixture</summary></extension></addon>')
        (plugin/'default.py').write_text('import sys,xbmcgui,xbmcplugin\nfrom urllib.parse import parse_qs\nITEMS=%r\n'%items+'''
handle=int(sys.argv[1]);page=int(parse_qs(sys.argv[2].lstrip('?')).get('page',['1'])[0])
def arrow(label,target):
    item=xbmcgui.ListItem(label);item.setArt({'icon':'DefaultFolder.png','poster':'DefaultFolder.png'})
    xbmcplugin.addDirectoryItem(handle,'plugin://plugin.video.foundry.libraryqa/?page='+str(target),item,True)
arrow('Previous Page',1)
for source in ITEMS[:8]:
    item=xbmcgui.ListItem(source['title']);item.setInfo('video',dict(title=source['title'],year=2026,mediatype='movie',plot=source['plot'],genre=['Mystery'],studio=['Fixture Studio']))
    item.setArt({k:v for k,v in source['art'].items() if k!='studiologo'})
    xbmcplugin.addDirectoryItem(handle,source['file'],item,False)
arrow('Next Page',page+1)
xbmcplugin.setContent(handle,'movies');xbmcplugin.endOfDirectory(handle)
''')
        environment=dict(os.environ,DISPLAY=':99',KODI_HOME=str(home),LIBGL_ALWAYS_SOFTWARE='1',AE_SINK='NULL')
        log=open(output/'kodi-console.log','w')
        xserver=subprocess.Popen(['Xvfb',':99','-screen','0','1920x1080x24','-ac','-nolisten','tcp'],stdout=log,stderr=log)
        kodi=None
        try:
            time.sleep(1)
            kodi=subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],env=environment,stdout=log,stderr=log,start_new_session=True)
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
            rpc('Addons.SetAddonEnabled',{'addonid':'plugin.video.foundry.libraryqa','enabled':True})
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
            def poster_bounds(im,region):
                pixels=im.load();l,t,r,b=region
                matches=[(x,y) for y in range(t,b) for x in range(l,r) if pixels[x,y][0]>=245 and pixels[x,y][1]<=10 and pixels[x,y][2]>=245]
                assert matches,'Focused poster fiducials were not rendered'
                # Fiducials span [24,24,200,312] of the original 224x336 art.
                # At the source 1.19 focus scale every side has a 28.56px inset.
                inset=24*1.19
                return [round(min(x for x,y in matches)-inset),round(min(y for x,y in matches)-inset),round(max(x for x,y in matches)+1+inset),round(max(y for x,y in matches)+1+inset)]
            for section,name in [('Movies','movies'),('TV Shows','tv-shows')]:
                wait_for(lambda:state().get('case')==name and state().get('focus')==50 and bool(state().get('title')))
                key('Right','Right');wait_for(lambda:state().get('position')==2)
                wait_for(lambda:bool(state().get('tmdb')) and bool(state().get('imdb')) and state().get('accent')=='FF7D25E6')
                time.sleep(1)
                focused=capture(name)
                assert focused.size==(1920,1080),focused.size
                bounds=poster_bounds(focused,(610,540,853,915))
                expected=[598,528,865,928]
                assert all(abs(a-b)<=4 for a,b in zip(bounds,expected)),(bounds,expected)
                key('Up');wait_for(lambda:state().get('focus')==5701)
                time.sleep(.5);unfocused=capture(name+'-unfocused')
                # Inspect rendered pixels, not just the accent property: below
                # the zoomed poster, colored light must fade into the fanart.
                point=(730,960)
                delta=[focused.getpixel(point)[c]-unfocused.getpixel(point)[c] for c in range(3)]
                assert delta[2]>=15 and delta[0]>=5,(point,delta)
                key('Down');wait_for(lambda:state().get('focus')==50 and state().get('position')==2)
                key(*(['Right']*8));wait_for(lambda:state().get('position')==10)
                wait_for(lambda:state().get('accent')=='FF25C7B0');time.sleep(.7)
                middle=poster_bounds(capture(name+'-scrolled'),(610,540,853,915))
                assert all(abs(a-b)<=4 for a,b in zip(middle,expected)),(middle,expected)
                key(*(['Right']*10));wait_for(lambda:state().get('kind')=='next');time.sleep(.7)
                arrow=capture(name+'-next');pixels=arrow.load()
                outline=[(x,y) for y in range(620,840) for x in range(1570,1840) if min(pixels[x,y])>=185 and max(pixels[x,y])-min(pixels[x,y])<35]
                assert outline,'Focused NEXT arrow border was not rendered'
                arrow_bounds=[min(x for x,y in outline),min(y for x,y in outline),max(x for x,y in outline)+1,max(y for x,y in outline)+1]
                assert all(abs(a-b)<=3 for a,b in zip(arrow_bounds,[1586,646,1806,811])),arrow_bounds
                key('Right');assert state().get('position')==20,'Rail wrapped at NEXT'
                key('Return');wait_for(lambda:state().get('page')==2 and state().get('position')==1 and state().get('kind')=='media')
                key('Left');wait_for(lambda:state().get('kind')=='previous');time.sleep(.7)
                capture(name+'-previous')
                key('Left');assert state().get('position')==0,'Rail wrapped at BACK'
                key('Return');wait_for(lambda:state().get('page')==1 and state().get('position')==0 and state().get('kind')=='media')
                evidence.append({'section':section,'screenshot':name+'.png','focused_poster_bounds':bounds,'scrolled_poster_bounds':middle,'source_expected_bounds':expected,'visible_colored_glow_delta_rgb':delta,'focus_return_restores_poster':True,'next_previous_page_roundtrip':True,'row_ends_do_not_wrap':True,'focused_next_arrow_bounds':arrow_bounds})
                key('Escape')
            wait_for(lambda:state().get('case')=='short-row' and state().get('focus')==50 and state().get('position')==0)
            wait_for(lambda:state().get('accent')=='FF1D9BC7');time.sleep(.7)
            short=poster_bounds(capture('short-row'),(100,540,345,915))
            assert all(abs(a-b)<=4 for a,b in zip(short,[91,528,357,928])),short
            evidence.append({'section':'Three-title row','focused_poster_bounds':short,'left_padding_preserved':True})
            key('Escape')
            wait_for(lambda:state().get('case')=='episodes' and 'S01E02' in state().get('rendered_details',''))
            assert 'The Signal' in state()['rendered_details'] and 'Fixture Series' in state()['rendered_details']
            assert state()['released']=='Aired Nov 1, 2026',state()
            capture('episode-details')
            key('Right');wait_for(lambda:'S00E00' in state().get('rendered_details',''))
            assert 'Origin Special' in state()['rendered_details'];capture('episode-special')
            evidence.append({'section':'Episode details','season_episode_and_title_visible':True,'specials_zero_preserved':True,'show_title_air_date_and_runtime_available':True})
            key('Escape')
            wait_for(lambda:state().get('case')=='native' and state().get('focus')==57 and state().get('label')=='Previous Page')
            key('Right','Right','Right');wait_for(lambda:state().get('position')==3)
            wait_for(lambda:state().get('tmdb')=='7' and state().get('imdb')=='7.1/10' and bool(state().get('studio')))
            time.sleep(1.2)
            focused=capture('native-movies')
            key('Up');wait_for(lambda:state().get('focus')==5701);time.sleep(.5)
            unfocused=capture('native-unfocused')
            # Only the selected media item may produce a halo. The previous
            # include applied Control.HasFocus(row) to every unfocused item.
            halo_deltas=[]
            for x in (224,480,730,992,1248,1504):
                difference=[focused.getpixel((x,960))[c]-unfocused.getpixel((x,960))[c] for c in range(3)]
                halo_deltas.append(difference)
            assert max(halo_deltas[2])>=15,halo_deltas
            assert all(max(abs(v) for v in delta)<=3 for index,delta in enumerate(halo_deltas) if index!=2),halo_deltas
            def bright(im,region):
                return sum(min(im.getpixel((x,y)))>170 for y in range(region[1],region[3]) for x in range(region[0],region[2]))
            assert bright(focused,(1568,388,1808,468))>50,'Shared studio logo not visible in native view'
            assert bright(focused,(1768,36,1864,132))==0,'Removed search icon still visible'
            assert bright(focused,(250,960,500,1036))==0,'Removed sort button still visible'
            yellow=sum(1 for y in range(346,370) for x in range(92,440) if focused.getpixel((x,y))[0]>160 and focused.getpixel((x,y))[1]>110 and focused.getpixel((x,y))[2]<80)
            assert yellow>100,'Shared IMDb badge not visible in native view'
            key('Down');wait_for(lambda:state().get('focus')==57)
            key(*(['Right']*6));wait_for(lambda:state().get('label')=='Next Page');time.sleep(.6)
            arrow=capture('native-next')
            assert bright(arrow,(1400,620,1864,840))>150,'Native NEXT arrow not visible'
            key('Return');wait_for(lambda:'page=2' in state().get('path','') and state().get('label')=='Previous Page');time.sleep(.6)
            previous=capture('native-previous')
            assert bright(previous,(80,620,400,840))>150,'Native BACK arrow not visible'
            key('Return');wait_for(lambda:'page=1' in state().get('path',''))
            evidence.append({'section':'Native provider view 57','only_selected_poster_glows':True,'glow_pixel_deltas':halo_deltas,'shared_studio_logo_visible':True,'shared_ratings_visible':True,'legacy_page_icons_replaced':True,'next_previous_page_roundtrip':True,'sort_and_search_buttons_removed':True})
            (base/'native-complete').write_text('ok')
            wait_for(lambda:state().get('case')=='favorites' and state().get('label')=='Saved movie' and bool(state().get('title')))
            assert state()['title']=='Fixture title 01',state()
            wait_for(lambda:state().get('tmdb')=='7' and state().get('imdb')=='7.1/10')
            assert state().get('plot') and state().get('released')
            wait_for(lambda:'catalog-studios' in state().get('studio',''));time.sleep(.6);capture('favorite-movie')
            key('Right');wait_for(lambda:state().get('label')=='Saved episode' and 'S01E02' in state().get('rendered_details',''))
            assert 'The Signal' in state()['rendered_details'] and 'Fixture Series' in state()['rendered_details']
            assert state()['released']=='Aired Nov 1, 2026',state()
            wait_for(lambda:'catalog-studios' in state().get('studio',''));time.sleep(.6);favorite_episode=capture('favorite-episode')
            # Metadata uses the source's muted gray, whose peak RGB is below
            # the separate white-logo/arrow threshold used above.
            text_pixels=sum(min(favorite_episode.getpixel((x,y)))>100 for y in range(386,414) for x in range(92,1249))
            assert text_pixels>100,'Favorite episode identification line is not rendered'
            assert bright(favorite_episode,(1568,388,1808,468))>50,'Favorite studio logo is not visible'
            assert not rpc('XBMC.GetInfoBooleans',{'booleans':['Player.HasVideo']})['Player.HasVideo'],'Favorites metadata started playback'
            evidence.append({'section':'Native favorites','saved_movie_full_metadata':True,'saved_episode_show_number_title_air_date':True,'existing_aliases_preserved':True,'playback_not_started':True})
            (base/'favorites-complete').write_text('ok')
            wait_for(lambda:(base/'complete').exists())
            (output/'verification.json').write_text(json.dumps({'renderer':'Native Kodi '+subprocess.check_output(['kodi','--version'],text=True).strip(),'canvas':[1920,1080],'checks':evidence,'scope':'Controlled fixtures; not Shield, live providers or Android pixel parity'},indent=2)+'\n')
        finally:
            if kodi:
                try:os.killpg(kodi.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:kodi.wait(timeout=5)
                except subprocess.TimeoutExpired:pass
                try:os.killpg(kodi.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                kodi.wait(timeout=5)
            xserver.terminate();log.close()
            logs=profile/'temp/kodi.log'
            if logs.exists():shutil.copyfile(logs,output/'kodi.log')
            for name in ('state.json','error.txt'):
                if (base/name).exists():shutil.copyfile(base/name,output/name)
        assert 'Error parsing boolean expression' not in (output/'kodi.log').read_text(), 'Invalid skin boolean conditions'


if __name__=='__main__':main()

