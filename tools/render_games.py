"""Native Games UI QA, isolated portable Kodi/X11; no downloads or real profiles.

Linux dependencies: Kodi 21+, Xvfb, Python 3 + Pillow. Run from any directory:
python tools/render_games.py [--output PATH] [--display :98] [--port 18082]
Synthetic bytes deliberately are NOT a playable ROM. This checks UI/launch error
handling only; no optional core installer or gameplay claim is included.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import zipfile
from urllib.request import Request, urlopen
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / 'skin.foundry-nimbus'
ADDON = ROOT / 'src/plugin.games.foundry'
HELPER = ROOT.parent / 'script.foundry.helper'

FIXTURE = r'''
import json,sys,time,traceback
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
import xbmc,xbmcgui,xbmcvfs
sys.path.insert(0,str(ADDON/'resources/lib'))
(OUTPUT/'phase.txt').write_text('fixture importing production library',encoding='utf-8')
from library import Library

def require(condition, message):
    # Kodi may initialize Python with optimization enabled. Never use assert
    # for native checks or put a required operation inside an assert expression.
    if not condition: raise AssertionError(message)

def wait(predicate, timeout=30):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if predicate(): return
        xbmc.sleep(100)
    raise AssertionError('Expected native game state not reached: '+json.dumps(snapshot()))

def info(key): return xbmc.getInfoLabel(key)
def snapshot():
    return {'window':xbmcgui.getCurrentWindowId(),'path':info('Container.FolderPath'),
            'plugin':info('Container.PluginName'),'content':info('Container.Content'),
            'viewmode':info('Container.Viewmode'),
            'directory_id':info('Container.Property(Foundry.Games.DirectoryId)'),
            'games_content':xbmc.getCondVisibility('Container.Content(games)'),
            'foundry_plugin':xbmc.getCondVisibility('String.IsEqual(Container.PluginName,plugin.games.foundry)'),
            'view58_visible':xbmc.getCondVisibility('Control.IsVisible(58)'),
            'current_game_id':info('ListItem.Property(Foundry.Game.Id)'),
            'label':info('ListItem.Label'),'title':info('ListItem.Title'),
            'position':info('Container(58).CurrentItem'),
            'game_id':info('Container(58).ListItem.Property(Foundry.Game.Id)'),
            'platform':info('Container(58).ListItem.Property(Foundry.Game.Platform)'),
            'overview':info('Container(58).ListItem.Property(Foundry.Game.Overview)'),
            'modal':xbmc.getCondVisibility('System.HasActiveModalDialog'),
            'updating':xbmc.getCondVisibility('Container.IsUpdating'),
            'dialog_id':xbmcgui.getCurrentWindowDialogId(),
            'dialog_heading':info('Control.GetLabel(1)'),
            'dialog_message':info('Control.GetLabel(9)')}
def native_core_dialog(state, expected):
    normalize=lambda text:' '.join(text.split()).casefold()
    heading=normalize(state['dialog_heading']);body=normalize(state['dialog_message'])
    if heading==normalize('Foundry Games') or 'unable to complete this operation' in body:
        return False
    if state['dialog_id']==12000:
        return heading==normalize(expected['chooser'])
    return (state['dialog_id']==12002 and heading==normalize(expected['heading']) and
            body in [normalize(value) for value in expected['messages']])
def invocation_complete(records, identifier, action):
    record=records.get(identifier,{})
    return (record.get('id')==identifier and record.get('action')==action and
            record.get('phase')=='completed' and not record.get('error'))
def invocation_records():
    return {path.stem:json.loads(path.read_text(encoding='utf-8')) for path in INVOCATIONS.glob('*.json')}
def new_invocation(action, before):
    matches=[record for identifier,record in invocation_records().items()
             if identifier not in before and record.get('action')==action]
    return matches[0]['id'] if len(matches)==1 else ''
def wait_invocation(action,before):
    wait(lambda:bool(new_invocation(action,before)))
    return new_invocation(action,before)
def wait_invocation_complete(identifier,action,timeout=30):
    wait(lambda:invocation_complete(invocation_records(),identifier,action),timeout)
def shot(name):
    target=OUTPUT/(name+'.png')
    if target.exists():target.unlink()
    xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+')')
    wait(lambda:(OUTPUT/(name+'.png')).exists())
    evidence.append(dict(case=name,**snapshot()))
def directory_id(): return info('Container.Property(Foundry.Games.DirectoryId)')
def directory_ready(query, previous):
    path=info('Container.FolderPath')
    return (path.startswith('plugin://plugin.games.foundry/') and
            parse_qs(urlsplit(path).query)==parse_qs(query) and
            bool(directory_id()) and directory_id()!=previous and
            not xbmc.getCondVisibility('System.HasActiveModalDialog'))
def wait_directory(query, previous):
    # FolderPath and a committed DB row can precede native list replacement.
    # The property is copied with endOfDirectory's completed list, so require
    # an identity never observed before the requested navigation/refresh.
    wait(lambda:directory_ready(query, previous))
    with (OUTPUT/'directory-acks.jsonl').open('a',encoding='utf-8') as acknowledgment:
        acknowledgment.write(json.dumps(snapshot())+'\n')
def open_path(query):
    (OUTPUT/'phase.txt').write_text('open '+query,encoding='utf-8')
    previous=directory_id()
    path='plugin://plugin.games.foundry/?'+query
    if xbmc.getCondVisibility('Window.IsActive(games)'):
        xbmc.executebuiltin('Container.Update('+path+')')
    else:
        xbmc.executebuiltin('ActivateWindow(games,'+path+',return)')
    # A synchronous GUI call can wait for the next plugin invoker while holding
    # this Python interpreter. Post navigation and observe the fresh native list.
    wait_directory(query,previous)
def home_item(index,label):
    xbmc.executebuiltin('Container.SetViewMode(50)')
    wait(lambda:xbmc.getCondVisibility('Control.IsVisible(50)'))
    xbmc.executebuiltin('SetFocus(50,'+str(index)+',absolute)')
    wait(lambda:info('ListItem.Label')==label)
    previous=directory_id()
    action('select')
    return previous
def rail():
    (OUTPUT/'phase.txt').write_text('activate native rail',encoding='utf-8')
    (OUTPUT/'rail-before.json').write_text(json.dumps(snapshot(),indent=2),encoding='utf-8')
    xbmc.executebuiltin('Container.SetViewMode(58)')
    wait(lambda:xbmc.getCondVisibility('Control.IsVisible(58)'))
    xbmc.executebuiltin('SetFocus(58)')
    wait(lambda:xbmc.getCondVisibility('Control.HasFocus(58)'))
    (OUTPUT/'phase.txt').write_text('native rail ready',encoding='utf-8')
def select_item(index):
    # Native built-in posts GUI_MSG_SETFOCUS/absolute selection. Do not return
    # borrowed Python Control wrappers whose owning Window is already disposed.
    xbmc.executebuiltin('SetFocus(58,'+str(index)+',absolute)')
def action(name):
    xbmc.executebuiltin('Action('+name+')');xbmc.sleep(300)

evidence=[]
try:
    (OUTPUT/'phase.txt').write_text('fixture validating skin and seeding catalog',encoding='utf-8')
    require(xbmc.getSkinDir()=='skin.foundry','Games gate requires the Foundry setting')
    require(Path(xbmcvfs.translatePath('special://skin/')).resolve()==(ADDON.parent/'skin.foundry').resolve(),'Actual graphics skin path is not the copied Foundry skin')
    # No game addon is allowed to execute these synthetic fixtures.
    response=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':'Addons.GetAddons','params':{'type':'kodi.gameclient','enabled':True}})))
    if 'error' in response: raise AssertionError('Cannot prove absence of enabled game clients: '+str(response))
    for addon in response.get('result',{}).get('addons',[]):
        result=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':'Addons.SetAddonEnabled','params':{'addonid':addon['addonid'],'enabled':False}})))
        if 'error' in result: raise AssertionError('Could not disable fixture game client')
    profile=Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.games.foundry/'))
    profile.mkdir(parents=True,exist_ok=True)
    db=Library(str(profile/'library-v1.db'))
    sid=db.add_source(str(ROMS),'nes')
    scanned=db.scan(sid)
    require(scanned==45,'Expected 45 synthetic source games; got '+str(scanned))
    first=db.games()[0];gid=first['id'];db.played(gid,60,now=123456)
    db.close()
    open_path('action=home');shot('games-consoles')
    open_path('action=games&system=nes')
    wait(lambda:info('Container.Viewmode')=='Foundry Games' and xbmc.getCondVisibility('Control.IsVisible(58)'))
    shot('games-automatic-view')
    rail()
    wait(lambda:bool(info('Container(58).ListItem.Property(Foundry.Game.Id)')))
    # ControlList.size() reads its Python-owned vecItems, not native GUI items.
    require(int(info('Container(58).NumItems') or '0')==21,'Expected 20 games plus next page')
    select_item(2);wait(lambda:'Fixture 02' in info('ListItem.Label'))
    require('Nintendo' in snapshot()['platform'] and 'Original local' in snapshot()['overview'],'Focused hero metadata is missing')
    shot('games-focused-hero')
    action('right');wait(lambda:'Fixture 03' in info('ListItem.Label'))
    action('left');wait(lambda:'Fixture 02' in info('ListItem.Label'))
    select_item(20);wait(lambda:info('ListItem.Label')=='Next page')
    action('select');wait(lambda:'page=1' in info('Container.FolderPath'))
    rail();shot('games-page-two')
    action('back');wait(lambda:'page=1' not in info('Container.FolderPath') and 'system=nes' in info('Container.FolderPath'))
    rail();wait(lambda:info('ListItem.Label')=='Next page')
    shot('games-page-back-focus')
    # Native RunPlugin context action uses production library transaction.
    before_favorite=directory_id()
    favorite_route=urlsplit(info('Container.FolderPath')).query
    xbmc.executebuiltin('RunPlugin(plugin://plugin.games.foundry/?action=favorite&id='+gid+')')
    def favorite_saved():
        check=Library(str(profile/'library-v1.db'))
        try:return len(check.games(mode='favorites'))==1
        finally:check.close()
    wait(favorite_saved)
    wait_directory(favorite_route,before_favorite)
    rail();require(info('ListItem.Label')=='Next page','Favorite refresh lost the current selection')
    shot('games-favorite-refresh-complete')
    open_path('action=home')
    previous=home_item(1,'Favorites')
    wait_directory('action=games&mode=favorites',previous);rail()
    require(int(info('Container(58).NumItems') or '0')==1,'Expected exactly one favorite')
    wait(lambda:info('ListItem.Label')=='Fixture 00');shot('games-favorites')
    open_path('action=home')
    previous=home_item(0,'Search games')
    wait(lambda:xbmc.getCondVisibility('Window.IsActive(virtualkeyboard)'))
    response=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':'Input.SendText','params':{'text':'Fixture 04','done':True}})))
    require('error' not in response,'Native search keyboard rejected text')
    wait_directory('action=search',previous);rail()
    require(int(info('Container(58).NumItems') or '0')==1,'Search did not filter native items')
    wait(lambda:info('ListItem.Label')=='Fixture 04');shot('games-search-results')
    # Cancellation resolves the pending directory as failed. Kodi retains the
    # original Home items/focus; require that native state, not just a closed UI.
    open_path('action=home')
    before_cancel=snapshot();before_cancel_invocations=set(invocation_records())
    previous=home_item(0,'Search games')
    wait(lambda:xbmc.getCondVisibility('Window.IsActive(virtualkeyboard)'))
    cancel_invocation=wait_invocation('search',before_cancel_invocations)
    action('back');wait(lambda:not xbmc.getCondVisibility('Window.IsActive(virtualkeyboard)'))
    wait_invocation_complete(cancel_invocation,'search')
    wait(lambda:not xbmc.getCondVisibility('Container.IsUpdating'))
    wait(lambda:directory_id()==previous and info('ListItem.Label')=='Search games' and info('Container.FolderPath')==before_cancel['path'])
    shot('games-search-cancel')
    open_path('action=games&system=nes');rail();select_item(2)
    wait(lambda:'Fixture 02' in info('ListItem.Label'))
    before_play_invocations=set(invocation_records())
    xbmc.log('[Foundry Games QA] missing-core begin',xbmc.LOGINFO)
    action('select')
    play_invocation=wait_invocation('play',before_play_invocations)
    # No installer selection or affirmative dialog action is sent. A native
    # missing-emulator chooser/error must appear, and Back must dismiss it.
    expected_core={'chooser':xbmc.getLocalizedString(35258).format('.nes'),
                   'heading':xbmc.getLocalizedString(35210),
                   'messages':[xbmc.getLocalizedString(value) for value in (35212,35214)]}
    def core_ready():
        state=snapshot()
        if not state['modal'] or state['dialog_id'] in (0,10101,10138,10160):return False
        require(native_core_dialog(state,expected_core),'Unexpected game launch dialog: '+json.dumps(state))
        return True
    wait(core_ready)
    shot('games-missing-core')
    for unused in range(4):
        if not xbmc.getCondVisibility('System.HasActiveModalDialog'):break
        action('back')
    wait(lambda:not xbmc.getCondVisibility('System.HasActiveModalDialog'))
    wait_invocation_complete(play_invocation,'play',75)
    xbmc.log('[Foundry Games QA] missing-core end',xbmc.LOGINFO)
    require(not xbmc.Player().isPlaying(),'Synthetic fixture unexpectedly played')
    wait(lambda:'Fixture 02' in info('ListItem.Label'))
    shot('games-launch-cancel-focus')
    # The cancelled core picker must not record a recent successful launch.
    check=Library(str(profile/'library-v1.db'))
    require(len(check.games(mode='recent'))==1,'Cancelled launch incorrectly changed recent games')
    check.close()
    (OUTPUT/'fixture-result.json').write_text(json.dumps({'checks':evidence,'assertions':{'console_listing':True,'automatic_games_view_selected':True,'focused_hero_metadata':True,'remote_navigation':True,'page_back_focus':True,'favorite_persistence':True,'favorite_refresh_complete':True,'favorites_native_route':True,'fresh_directory_acknowledgments':True,'search_results':True,'search_cancel':True,'search_cancel_retains_listing':True,'search_cancel_invoker_completed':True,'launch_cancel_invoker_completed':True,'missing_core_dialog':True,'launch_cancel_focus':True,'cancel_does_not_record_play':True},'invocations':list(invocation_records().values()),'native_core_expected':expected_core,'scope':'Native Kodi UI only. Synthetic non-playable files. No cores/ROMs downloaded. Not Shield or gameplay certification.','limitations':['No actual gameplay or controller/disconnect/multiplayer validation','No Shield or Android emulator compatibility validation','No real VFS provider or Google Drive authorization tested','PSP remains unsupported']},indent=2)+'\n',encoding='utf-8')
    (BASE/'complete').write_text('ok')
except Exception:
    (BASE/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')
'''


def instrument_entrypoint(addon, records):
    records.mkdir()
    path=addon/'default.py'
    original=path.read_text(encoding='utf-8')
    wrapper='''import json as _qa_json,sys as _qa_sys,time as _qa_time,traceback as _qa_traceback
from pathlib import Path as _qa_Path
from uuid import uuid4 as _qa_uuid
from urllib.parse import parse_qs as _qa_parse
_qa_id=_qa_uuid().hex
_qa_action=_qa_parse(_qa_sys.argv[2].lstrip('?')).get('action',['home'])[-1]
_qa_record={'id':_qa_id,'action':_qa_action,'mode':_qa_parse(_qa_sys.argv[2].lstrip('?')).get('mode',[''])[-1],'phase':'started','error':'','started':_qa_time.monotonic()}
_qa_target=_qa_Path(%r)/(_qa_id+'.json')
def _qa_write():
    _qa_temp=_qa_target.with_suffix('.tmp')
    _qa_temp.write_text(_qa_json.dumps(_qa_record),encoding='utf-8')
    _qa_temp.replace(_qa_target)
_qa_write()
try:
    exec(compile(%r,__file__,'exec'),globals())
except BaseException:
    _qa_record['error']=_qa_traceback.format_exc()
    raise
finally:
    _qa_vfs=_qa_sys.modules.get('xbmcvfs');_qa_gui=_qa_sys.modules.get('xbmcgui')
    _qa_record.update(phase='completed',completed=_qa_time.monotonic(),
        runtime_skin_path=_qa_vfs.translatePath('special://skin/') if _qa_vfs is not None else '',
        window_id=_qa_gui.getCurrentWindowId() if _qa_gui is not None else None)
    _qa_write()
''' % (str(records),original)
    path.write_text(wrapper,encoding='utf-8')
    return hashlib.sha256(original.encode('utf-8')).hexdigest()


def native_game_log_report(text):
    begin='[Foundry Games QA] missing-core begin';end='[Foundry Games QA] missing-core end'
    start=text.find(begin);finish=text.find(end,start+len(begin)) if start>=0 else -1
    segment=text[start:finish+len(end)] if start>=0 and finish>=0 else ''
    failures=[line for line in text.splitlines() if any(marker in line for marker in
              ('PythonToCppException','Error Contents:','Traceback (most recent call last):'))]
    return {'complete':bool(segment),'native_gameclient_path':
            'RetroPlayer[PLAYER]: No compatible game client selected, aborting playback' in segment,
            'failures':failures,'log':segment}


def read_invocations(directory):
    return {path.stem: json.loads(path.read_text(encoding='utf-8')) for path in directory.glob('*.json')}


def actual_skin_log_state(text, skin_path):
    lines = text.splitlines()
    loads = [(index, re.search(r'load skin from:\s*(.*?)\s+\(version:', line))
             for index, line in enumerate(lines) if 'load skin from:' in line]
    if not loads: return {'ready': False}
    index, match = loads[-1]
    if match is None: return {'ready': False}
    normalize = lambda path: str(path).replace('\\', '/').rstrip('/')
    path = match.group(1)
    tail = lines[index + 1:]
    loaded = next((offset for offset, line in enumerate(tail) if 'skin loaded...' in line), None)
    transitions = [line for line in tail[loaded + 1:] if 'Window Init (Home.xml)' in line or 'Window Init (Startup.xml)' in line] if loaded is not None else []
    return {'ready': normalize(path) == normalize(skin_path) and bool(transitions) and 'Window Init (Home.xml)' in transitions[-1],
            'loaded_path': path, 'load_event': lines[index],
            'last_transition': transitions[-1] if transitions else ''}


def settle_startup(rpc, records, log_path, alive, output, identity, skin_path, timeout=45, quiet=2):
    """Observe the actual full Home and both real widget invocations to completion."""
    deadline = time.monotonic() + timeout
    quiet_since = None
    last = None
    history = []
    while time.monotonic() < deadline:
        if not alive(): raise RuntimeError('Kodi exited during full Home startup settlement')
        text = log_path.read_text(encoding='utf-8', errors='replace')
        if any(marker in text for marker in ('PythonToCppException', 'Error Contents:', 'Traceback (most recent call last):')):
            raise AssertionError('Python failure during full shipped Home startup')
        gui = rpc('GUI.GetProperties', {'properties': ['currentwindow', 'skin']})
        flags = rpc('XBMC.GetInfoBooleans', {'booleans': ['Window.IsVisible(startup)', 'System.HasActiveModalDialog', 'Container.IsUpdating']})
        labels=rpc('XBMC.GetInfoLabels',{'labels':['Container(9000).NumItems','Container(9000).ListItem.Property(menu_id)','Container(9000).ListItem.Property(id)']})
        log_skin=actual_skin_log_state(text,skin_path)
        owner = rpc('Settings.GetSettingValue', {'setting': 'services.devicename'})['value']
        invocations = read_invocations(records)
        widgets = [record for record in invocations.values() if record['action'] == 'games' and record.get('mode') in ('recent', 'favorites')]
        if any(record.get('error') for record in widgets): raise AssertionError('Production Games startup widget failed')
        normalize=lambda path:str(path).replace('\\','/').rstrip('/')
        complete = ({record['mode'] for record in widgets} == {'recent', 'favorites'} and
                    all(record['phase'] == 'completed' and normalize(record.get('runtime_skin_path',''))==normalize(skin_path) for record in widgets))
        count=labels.get('Container(9000).NumItems','');menu_id=labels.get('Container(9000).ListItem.Property(menu_id)','')
        category=labels.get('Container(9000).ListItem.Property(id)','')
        home_signature=(count.isdigit() and int(count)>0 and menu_id.isdigit() and int(menu_id)>0 and
            category in {'movies','tvshows','music','disc','musicvideos','livetv','radio','games','addons','pictures','video','favorites','weather','settings','custom1','custom2','custom3'})
        state = {'window': gui['currentwindow'], 'skin': gui['skin'], 'flags': flags,
                 'owner': owner, 'actual_skin_log':log_skin,'home_signature':labels, 'widgets': sorted((record['id'], record['mode'], record['phase']) for record in widgets)}
        ready = (gui['currentwindow']['id'] == 10000 and gui['skin']['id'] == 'skin.foundry' and
                 owner == identity and not any(flags.values()) and complete and log_skin['ready'] and home_signature)
        if state != last:
            history.append(state); last = state; quiet_since = None
        if ready:
            if quiet_since is None: quiet_since = time.monotonic()
            elif time.monotonic() - quiet_since >= quiet:
                report = {'passed': True, 'quiet_seconds': quiet, 'observations': history,
                          'completed_game_widgets': widgets, 'owner': identity, 'actual_skin_log':log_skin, 'home_signature':labels}
                (output / 'startup-readiness.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
                return report
        else: quiet_since = None
        (output / 'startup-readiness.json').write_text(json.dumps({'passed': False, 'observations': history}, indent=2) + '\n', encoding='utf-8')
        time.sleep(.1)
    raise AssertionError('Full shipped Home/startup widgets did not settle before the bounded deadline')


def preserve_fixture_evidence(base, profile, output):
    for source, name in ((profile / 'temp/kodi.log', 'kodi.log'), (base / 'error.txt', 'error.txt')):
        if source.exists(): shutil.copyfile(source, output / name)
    for source, name in ((base / 'invocations', 'invocations'),):
        if source.exists(): shutil.copytree(source, output / name, dirs_exist_ok=True)
    for source, name in ((profile / 'addons/plugin.games.foundry/default.py', 'instrumented-games-entrypoint.py'),
                         (profile / 'addons/script.foundry.gamesqa/fixture.py', 'native-fixture.py')):
        if source.exists(): shutil.copyfile(source, output / name)
    for crash in list(base.rglob('kodi_crashlog*.log')):
        target=output/crash.name
        if crash.resolve()!=target.resolve(): shutil.copyfile(crash,target)


KNOWN_TIMER_SHA256 = 'c2c90596e9362a97dc5ad2e79004273fe014954bf0f976cc39f78e7cf2e02614'


def skin_boolean_report(text, timer_sha256):
    if timer_sha256 != KNOWN_TIMER_SHA256:
        raise AssertionError('Known baseline Timer warning requires exact unchanged published bytes')
    known, unexpected = [], []
    marker = 'Error parsing boolean expression'
    for line in text.splitlines():
        if marker in line:
            expression = line.split(marker, 1)[1].strip()
            (known if expression == 'control.hasfocus($param[list_id])' else unexpected).append(line)
    if unexpected: raise AssertionError('New skin boolean parsing failures: ' + str(unexpected))
    return {'passed': True, 'known_baseline_warnings': known, 'new_errors': unexpected,
            'unchanged_timer_sha256': timer_sha256}


def wait_for(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.1)
    raise RuntimeError('Native games fixture timed out')


def stop_process_group(process):
    """Stop only the process group created by this runner's start_new_session.

    Kodi's launcher can exit before kodi.bin. Always finish its original group,
    even when waiting for the launcher itself succeeds.
    """
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def fixture_enable_prompt(labels, name):
    """Match only Kodi's exact request for the currently copied fixture addon."""
    normalize = lambda value: ' '.join(value.split()).casefold()
    return (normalize(labels.get('Control.GetLabel(1)', '')) == 'disabled add-ons' and
            normalize(labels.get('Control.GetLabel(9)', '')) ==
            normalize('Would you like to enable this add-on? ' + name))


def enable_fixture_addons(rpc, identifiers, manifest_names, timeout=30):
    """Enable only the caller's copied fixture list and verify each final state."""
    def details(aid):
        return rpc('Addons.GetAddonDetails', {'addonid':aid,'properties':['enabled','name']})['addon']
    def modal():
        return rpc('XBMC.GetInfoBooleans', {'booleans':['System.HasActiveModalDialog']})['System.HasActiveModalDialog']
    if set(manifest_names) != set(identifiers) or not all(manifest_names.values()):
        raise AssertionError('Fixture enable allowlist does not match copied manifests')
    for aid in identifiers:
        if details(aid)['name'] != manifest_names[aid]:
            raise AssertionError('Kodi addon name differs from copied manifest: ' + aid)
    for aid in identifiers:
        before = details(aid)
        if not before['enabled']:
            rpc('Addons.SetAddonEnabled', {'addonid':aid, 'enabled':True})
        deadline = time.monotonic() + timeout
        quiet_since = None
        while time.monotonic() < deadline:
            if modal():
                labels = rpc('XBMC.GetInfoLabels', {'labels':['Control.GetLabel(1)','Control.GetLabel(9)']})
                # First-run enable prompts can be queued in a different order.
                # Only names verified against every copied fixture manifest count.
                if not any(fixture_enable_prompt(labels, name) for name in manifest_names.values()):
                    raise AssertionError('Unrelated dialog while enabling %s: %s' % (aid, labels))
                rpc('Input.Left'); rpc('Input.Select')
                quiet_since = None
            elif details(aid)['enabled']:
                if quiet_since is None: quiet_since = time.monotonic()
                elif time.monotonic() - quiet_since >= .5: break
            else: quiet_since = None
            time.sleep(.1)
        else: raise AssertionError('Copied fixture dependency did not enable: ' + aid)
    for aid in identifiers:
        if not details(aid)['enabled']: raise AssertionError('Fixture dependency became disabled: ' + aid)


def prepare_shipped_skin(home, profile, skin_source=SKIN, helper_source=HELPER, root=ROOT):
    """Copy production UI unchanged; suppress only disposable helper/services."""
    addons = profile / 'addons'
    addons.mkdir(parents=True, exist_ok=True)
    identifiers = []
    sources = [root / 'src/resource.images.foundry.wallpapers',
               root / 'src/resource.images.foundry.osd',
               root / 'src/resource.uisounds.foundry.pulse', helper_source, skin_source]
    for source in sources:
        aid = E.parse(source / 'addon.xml').getroot().get('id')
        shutil.copytree(source, addons / aid, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        identifiers.append(aid)
    # No startup services (including system update/version-check services) run.
    for manifest_path in list((home / 'addons').glob('*/addon.xml')) + list(addons.glob('*/addon.xml')):
        tree = E.parse(manifest_path)
        services = tree.getroot().findall("extension[@point='xbmc.service']")
        for service in services: tree.getroot().remove(service)
        if services: tree.write(manifest_path, encoding='UTF-8', xml_declaration=True)
    helper = addons / 'script.foundry.helper'
    manifest = E.parse(helper / 'addon.xml')
    for dependency in list(manifest.getroot().find('requires')):
        if dependency.get('addon') != 'xbmc.python': manifest.getroot().find('requires').remove(dependency)
    for extension in manifest.getroot().findall('extension'):
        library = extension.get('library')
        if library:
            (helper / library).write_text('# Offline Games QA: helper setup/router entrypoint disabled.\n', encoding='utf-8')
    manifest.write(helper / 'addon.xml', encoding='UTF-8', xml_declaration=True)
    skin = addons / 'skin.foundry'
    relative_paths = ['addon.xml', 'xml/Home.xml', 'xml/MyGames.xml', 'xml/Includes.xml',
                      'xml/View_58_FoundryGames.xml', 'xml/Font.xml', 'xml/Timers.xml']
    relative_paths += [str(path.relative_to(skin_source)).replace('\\', '/')
                       for path in (skin_source / 'fonts').rglob('*') if path.is_file()]
    hashes = {}
    for relative in relative_paths:
        original = (skin_source / relative).read_bytes()
        if original != (skin / relative).read_bytes(): raise AssertionError('Shipped skin changed: ' + relative)
        hashes[relative] = hashlib.sha256(original).hexdigest()
    settings = profile / 'userdata/addon_data/skin.foundry'
    settings.mkdir(parents=True, exist_ok=True)
    (settings / 'settings.xml').write_text('<settings><setting id="firsttimerun" type="bool">true</setting></settings>', encoding='utf-8')
    return identifiers, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--display', default=':98')
    parser.add_argument('--port', type=int, default=18082)
    args = parser.parse_args()
    release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))['release']
    output = (args.output or ROOT / 'releases' / (str(release) + '-qa') / 'games').resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output/'phase.txt').write_text('preparing isolated native Games host',encoding='utf-8')
    # A failed rerun must not leave a previous pass summary in its evidence set.
    for name in ('verification.json', 'games-verification.json', 'fixture-result.json'):
        target = output / name
        if target.exists(): target.unlink()
    if os.name != 'posix' or not Path('/usr/share/kodi').is_dir():
        raise RuntimeError('Linux Kodi/X11 runner required; no machine setup is performed')
    version = subprocess.check_output(['kodi', '--version'], text=True).strip()
    import re
    match = re.search(r'\b(\d+)\.\d+', version)
    if not match or int(match[1]) < 21:
        raise RuntimeError('Native Games validation requires Kodi 21 or newer: ' + version)
    from PIL import Image, ImageDraw
    # Never send fixture commands to an existing renderer or personal Kodi.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('127.0.0.1', args.port))
    with tempfile.TemporaryDirectory(prefix='foundry-games-qa-') as temporary:
        base = Path(temporary)
        home = base / 'kodi'
        shutil.copytree('/usr/share/kodi', home, ignore_dangling_symlinks=True)
        profile = home / 'portable_data'
        userdata = profile / 'userdata'; userdata.mkdir(parents=True)
        addon = profile / 'addons/plugin.games.foundry'
        shutil.copytree(ADDON, addon, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        entrypoint_sha256=instrument_entrypoint(addon,base/'invocations')
        identifiers, skin_hashes = prepare_shipped_skin(home, profile)
        (output / 'shipped-skin-hashes.json').write_text(json.dumps(skin_hashes, indent=2)+'\n', encoding='utf-8')
        settings = E.Element('settings', version='2')
        for key, value in {'lookandfeel.skin':'skin.estuary','addons.updatemode':'2','filelists.showparentdiritems':'false','services.webserver':'true','services.webserverport':str(args.port),'services.webserverauthentication':'false','services.devicename':base.name}.items():
            E.SubElement(settings, 'setting', id=key).text = value
        E.ElementTree(settings).write(userdata / 'guisettings.xml', encoding='UTF-8', xml_declaration=True)
        roms = base / 'synthetic-roms'; roms.mkdir()
        for index in range(45):
            stem = roms / ('Fixture %02d' % index)
            stem.with_suffix('.nes').write_bytes(b'Foundry synthetic listing fixture. NOT A ROM.\n')
            stem.with_suffix('.json').write_text(json.dumps({'overview':'Original local metadata fixture with a long description to test bounded hero text.','year':2026,'genre':'UI test'}), encoding='utf-8')
            art = Image.new('RGB', (220, 275), (40, 50 + index * 3, 110))
            ImageDraw.Draw(art).text((20, 100), 'Fixture %02d' % index, fill='white')
            art.save(str(stem) + '-boxart.png')
        launcher = profile / 'addons/script.foundry.gamesqa'; launcher.mkdir()
        (launcher / 'addon.xml').write_text('<addon id="script.foundry.gamesqa" version="1.0.0" name="Foundry Games QA" provider-name="Foundry"><requires><import addon="xbmc.python" version="3.0.0" /></requires><extension point="xbmc.python.script" library="fixture.py" /><extension point="xbmc.addon.metadata"><platform>all</platform><license>GPL-2.0-only</license><summary lang="en_GB">Isolated Games UI fixture</summary></extension></addon>', encoding='utf-8')
        prefix = 'from pathlib import Path\nBASE=Path(%r)\nADDON=Path(%r)\nOUTPUT=Path(%r)\nROMS=Path(%r)\nINVOCATIONS=Path(%r)\n' % tuple(map(str, (base, addon, output, roms,base/'invocations')))
        (launcher / 'fixture.py').write_text(prefix + FIXTURE, encoding='utf-8')
        # HOME prevents any fallback user-profile or external account lookup.
        environment = dict(os.environ, HOME=str(base / 'empty-home'), XDG_CONFIG_HOME=str(base / 'empty-home/.config'), XDG_CACHE_HOME=str(base / 'empty-home/.cache'), DISPLAY=args.display, KODI_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='1', AE_SINK='NULL')
        Path(environment['HOME']).mkdir()
        kodi = None
        with (output / 'kodi-console.log').open('w', encoding='utf-8') as log:
            xserver = subprocess.Popen(['Xvfb', args.display, '-screen', '0', '1920x1080x24', '-ac', '-nolisten', 'tcp'], stdout=log, stderr=log)
            try:
                time.sleep(1)
                kodi = subprocess.Popen(['kodi', '-p', '-fs', '--windowing=x11', '--debug'], env=environment, stdout=log, stderr=log, start_new_session=True)
                def rpc(method, params=None):
                    body = json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}}).encode()
                    with urlopen(Request('http://127.0.0.1:%d/jsonrpc' % args.port, data=body, headers={'Content-Type':'application/json'}), timeout=5) as response:
                        result = json.loads(response.read())
                    if 'error' in result: raise RuntimeError(str(result['error']))
                    return result.get('result')
                def ready():
                    try:
                        logtext = (profile / 'temp/kodi.log').read_text(encoding='utf-8', errors='replace')
                        if '<CWebserver[%d]>: Started' % args.port not in logtext: return False
                        return rpc('JSONRPC.Ping') == 'pong' and rpc('Settings.GetSettingValue', {'setting':'services.devicename'}).get('value') == base.name
                    except Exception: return False
                wait_for(ready)
                for unused in range(5): rpc('Input.Back'); time.sleep(.2)
                fixture_ids = identifiers + ['plugin.games.foundry', 'script.foundry.gamesqa']
                fixture_names = {}
                for aid in fixture_ids:
                    manifest = E.parse(profile / 'addons' / aid / 'addon.xml').getroot()
                    if manifest.get('id') != aid: raise AssertionError('Unexpected copied fixture ID: ' + aid)
                    fixture_names[aid] = manifest.get('name', '')
                enable_fixture_addons(rpc, fixture_ids, fixture_names)
                if not rpc('Settings.SetSettingValue', {'setting':'lookandfeel.skin','value':'skin.foundry'}):
                    raise AssertionError('Could not select shipped Foundry skin')
                def modal():
                    return rpc('XBMC.GetInfoBooleans', {'booleans':['System.HasActiveModalDialog']})['System.HasActiveModalDialog']
                wait_for(modal)
                labels = rpc('XBMC.GetInfoLabels', {'labels':['Control.GetLabel(1)','Control.GetLabel(9)']})
                prompt = ' '.join(labels.values()).lower()
                if 'keep' not in prompt or 'skin' not in prompt:
                    raise AssertionError('Unexpected skin confirmation: ' + str(labels))
                rpc('Input.Left'); rpc('Input.Select')
                (output/'phase.txt').write_text('settling full shipped Home and Games widgets',encoding='utf-8')
                startup = settle_startup(rpc,base/'invocations',profile/'temp/kodi.log',lambda:kodi.poll() is None,output,base.name,profile/'addons/skin.foundry')
                rpc('Addons.ExecuteAddon', {'addonid':'script.foundry.gamesqa'})
                def finished():
                    if (base / 'error.txt').exists(): raise AssertionError((base / 'error.txt').read_text())
                    if kodi.poll() is not None:
                        raise RuntimeError('Kodi exited before Games fixture completion; return code %s. See console/crash logs.' % kodi.returncode)
                    return (base / 'complete').exists()
                wait_for(finished, 240)
                report = json.loads((output / 'fixture-result.json').read_text())
                report['renderer'] = version
                report['packages'] = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))['packages']
                report['release'] = release
                report['shipped_skin_hashes'] = skin_hashes
                report['host'] = 'Actual pinned skin.foundry; Home/MyGames/Includes/view/fonts unchanged; only copied helper/services disabled'
                for check in report['checks']:
                    with Image.open(output / (check['case'] + '.png')) as im:
                        assert im.size == (1920,1080), im.size
                        im.verify()
            finally:
                if kodi:
                    stop_process_group(kodi)
                xserver.terminate(); xserver.wait(timeout=10)
                preserve_fixture_evidence(base,profile,output)
        kodi_log = output / 'kodi.log'
        timer_bytes=(SKIN/'xml/Timers.xml').read_bytes()
        with zipfile.ZipFile(ROOT/'skin.foundry/skin.foundry-1.4.0.zip') as baseline:
            if timer_bytes != baseline.read('skin.foundry/xml/Timers.xml'):
                raise AssertionError('Published baseline Timer bytes differ')
        boolean_errors=skin_boolean_report(kodi_log.read_text(encoding='utf-8',errors='replace'),hashlib.sha256(timer_bytes).hexdigest())
        launch_log=native_game_log_report(kodi_log.read_text(encoding='utf-8',errors='replace'))
        (output/'games-native-errors.json').write_text(json.dumps(launch_log,indent=2)+'\n',encoding='utf-8')
        if not launch_log['complete'] or not launch_log['native_gameclient_path'] or launch_log['failures']:
            raise AssertionError('Native game-client path/traceback evidence failed: '+str(launch_log))
        report['skin_boolean_errors']=boolean_errors
        report['startup_readiness']=startup
        report['assertions']['full_home_startup_widgets_completed']=True
        report['native_gameclient_log']=launch_log
        report['production_entrypoint_sha256']=entrypoint_sha256
        report['assertions']['native_gameclient_path_verified']=True
        report['assertions']['native_tracebacks_absent']=True
        report['passed'] = True
        for relative, expected_hash in skin_hashes.items():
            actual_hash = hashlib.sha256((profile / 'addons/skin.foundry' / relative).read_bytes()).hexdigest()
            if actual_hash != expected_hash: raise AssertionError('Runtime modified shipped skin: ' + relative)
        report['assertions']['shipped_skin_bytes_unchanged'] = True
        report['assertions']['screenshots_verified'] = True
        report['assertions']['new_skin_boolean_parse_errors_absent'] = True
        for name in ('verification.json', 'games-verification.json'):
            (output / name).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Native Games UI evidence:', output)


if __name__ == '__main__': main()
