"""Native action-provider regression hooks for render_interface.py's disposable profile."""
import json
import time
from pathlib import Path

ADDONS=('plugin.video.fenskeleton','plugin.video.foundry.resolverfixture')


def prepare(addons,base):
    """Only call on the harness's fresh TemporaryDirectory addons, never real Kodi."""
    addons,base=Path(addons),Path(base)
    assert addons.resolve().is_relative_to(base.resolve())
    for aid in ADDONS:
        target=addons/aid
        assert not target.exists(), 'Fixture must never replace an installed addon'
        target.mkdir()
        (target/'addon.xml').write_text('<addon id="%s" version="0.0.1" name="Offline playback contract fixture" provider-name="Foundry QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.pluginsource" library="main.py"><provides>video</provides></extension><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-2.0-only</license></extension></addon>'%aid)
        body='''import json,sys,time
from pathlib import Path
import xbmc,xbmcgui,xbmcplugin
base=Path(%r)
aid=%r
record={'url':sys.argv[0]+sys.argv[2],'args':sys.argv,'provider':aid}
def write(phase):
 record['phase']=phase
 p=base/(aid+'.json');q=p.with_suffix('.tmp');q.write_text(json.dumps(record));q.replace(p)
write('entered')
item=xbmcgui.ListItem('Offline provider fixture',path=str(base/'fixture.avi'))
item.setInfo('video',{'title':'Offline provider fixture','mediatype':'movie'})
item.setContentLookup(False)
if aid=='plugin.video.fenskeleton':
 player=xbmc.Player();player.play(str(base/'fixture.avi'),item)
 deadline=time.monotonic()+15
 while not player.isPlayingVideo() and time.monotonic()<deadline:xbmc.sleep(50)
 if not player.isPlayingVideo():raise RuntimeError('Offline action fixture did not start')
 write('playing')
 while player.isPlayingVideo():xbmc.sleep(50)
 write('stopped')
else:
 xbmcplugin.setResolvedUrl(int(sys.argv[1]),True,item)
 write('resolved')
'''%(str(base),aid)
        (target/'main.py').write_text(body)


def verify(rpc,base,output,playback_command,state,wait_for,capture,skin_label='original'):
    base,output=Path(base),Path(output)
    rows=[]
    def boolean(name):return rpc('XBMC.GetInfoBooleans',{'booleans':[name]}).get(name,False)
    def record(aid):
        try:return json.loads((base/(aid+'.json')).read_text())
        except (OSError,ValueError):return {}
    for aid in ADDONS:
        for route in ('info','context'):
            path='plugin://'+aid+'/?mode=play_media&title=Encoded%20%26%20comma%2C%28paren%29&token=fixture-only'
            receipt=base/(aid+'.json');receipt.unlink(missing_ok=True)
            playback_command('open-catalog',fanart=True,file=path)
            wait_for(lambda:(state().get('catalog') or {}).get('native_ready') and (state().get('catalog') or {}).get('focus')==50 and not state().get('modal'))
            time.sleep(.4)
            captures=[]
            if route=='info':
                rpc('Input.Select')
                wait_for(lambda:boolean('Window.IsActive(videoinfo)'))
                labels=rpc('XBMC.GetInfoLabels',{'labels':['ListItem.FileNameAndPath','ListItem.DBTYPE']})
                assert labels['ListItem.FileNameAndPath']==path,('Info path changed',labels)
                assert labels['ListItem.DBTYPE']=='movie',('Info type unavailable',labels)
                captures.append(capture('contract-'+skin_label+'-'+aid+'-info'))
                # Native shipped DialogVideoInfo first menu item is Play.
                rpc('Input.Select')
            else:
                labels={}
                rpc('Input.ContextMenu');wait_for(lambda:boolean('Window.IsActive(contextmenu)'))
                rpc('Input.Select')
            wait_for(lambda:bool(rpc('Player.GetActivePlayers')),20)
            wait_for(lambda:record(aid).get('phase') in ('playing','resolved'),20)
            assert record(aid)['url']==path,('Provider URL changed',record(aid))
            players=rpc('Player.GetActivePlayers');playerid=next(p['playerid'] for p in players if p['type']=='video')
            time.sleep(.5)
            rpc('Player.Stop',{'playerid':playerid})
            wait_for(lambda:not rpc('Player.GetActivePlayers'))
            if aid==ADDONS[0]:wait_for(lambda:record(aid).get('phase')=='stopped')
            # An unresolved outer request only fails after provider returns.
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                assert not boolean('Window.IsActive(okdialog)'), 'False failure dialog after successful stop'
                time.sleep(.1)
            wait_for(lambda:(state().get('catalog') or {}).get('native_ready') and not state().get('modal'))
            captures.append(capture('contract-'+skin_label+'-'+aid+'-'+route+'-stopped'))
            rows.append({'skin':skin_label,'provider':aid,'route':route,'info_labels':labels,'receipt':record(aid),'stop_without_failure':True,'screenshots':captures,'after_stop_dialog_id':state().get('dialog_id'),'after_stop_modal':state().get('modal')})
            rpc('Input.Back');wait_for(lambda:state().get('catalog') is None)
    (output/('action-contract-'+skin_label+'.json')).write_text(json.dumps(rows,indent=2))
    return rows
