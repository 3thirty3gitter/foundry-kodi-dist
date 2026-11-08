"""Native Games UI QA, isolated portable Kodi/X11; no downloads or real profiles.

Linux dependencies: Kodi 21+, Xvfb, Python 3 + Pillow. Run from any directory:
python tools/render_games.py [--output PATH] [--display :98] [--port 18082]
Synthetic bytes deliberately are NOT a playable ROM. This checks UI/launch error
handling only; no optional core installer or gameplay claim is included.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / 'skin.foundry-nimbus'
ADDON = ROOT / 'src/plugin.games.foundry'

FIXTURE = r'''
import json,sys,time,traceback
from pathlib import Path
import xbmc,xbmcgui,xbmcvfs
sys.path.insert(0,str(ADDON/'resources/lib'))
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
            'label':info('ListItem.Label'),'title':info('ListItem.Title'),
            'position':info('Container(58).CurrentItem'),
            'game_id':info('Container(58).ListItem.Property(Foundry.Game.Id)'),
            'platform':info('Container(58).ListItem.Property(Foundry.Game.Platform)'),
            'overview':info('Container(58).ListItem.Property(Foundry.Game.Overview)'),
            'modal':xbmc.getCondVisibility('System.HasActiveModalDialog')}
def shot(name):
    target=OUTPUT/(name+'.png')
    if target.exists():target.unlink()
    xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(name+'.png'))+')')
    wait(lambda:(OUTPUT/(name+'.png')).exists())
    evidence.append(dict(case=name,**snapshot()))
def open_path(query):
    xbmc.executebuiltin('ActivateWindow(games,plugin://plugin.games.foundry/?'+query+',return)')
    wait(lambda:query in info('Container.FolderPath'))
    xbmc.sleep(500)
def rail():
    xbmc.executebuiltin('Container.SetViewMode(58)')
    wait(lambda:xbmc.getCondVisibility('Control.IsVisible(58)'))
    window=xbmcgui.Window(xbmcgui.getCurrentWindowId())
    window.setFocusId(58)
    return window.getControl(58)
def action(name):
    xbmc.executebuiltin('Action('+name+')');xbmc.sleep(300)

evidence=[]
try:
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
    open_path('action=games&system=nes');control=rail()
    wait(lambda:bool(info('Container(58).ListItem.Property(Foundry.Game.Id)')))
    require(control.size()==21,'Expected 20 games plus next page')
    control.selectItem(2);wait(lambda:'Fixture 02' in info('ListItem.Label'))
    require('Nintendo' in snapshot()['platform'] and 'Original local' in snapshot()['overview'],'Focused hero metadata is missing')
    shot('games-focused-hero')
    action('right');wait(lambda:'Fixture 03' in info('ListItem.Label'))
    action('left');wait(lambda:'Fixture 02' in info('ListItem.Label'))
    control.selectItem(20);wait(lambda:info('ListItem.Label')=='Next page')
    action('select');wait(lambda:'page=1' in info('Container.FolderPath'))
    rail();shot('games-page-two')
    action('back');wait(lambda:'page=1' not in info('Container.FolderPath') and 'system=nes' in info('Container.FolderPath'))
    rail();wait(lambda:info('ListItem.Label')=='Next page')
    shot('games-page-back-focus')
    # Native RunPlugin context action uses production library transaction.
    xbmc.executebuiltin('RunPlugin(plugin://plugin.games.foundry/?action=favorite&id='+gid+')')
    def favorite_saved():
        check=Library(str(profile/'library-v1.db'))
        try:return len(check.games(mode='favorites'))==1
        finally:check.close()
    wait(favorite_saved)
    open_path('action=games&mode=favorites');rail()
    wait(lambda:info('ListItem.Label')=='Fixture 00');shot('games-favorites')
    open_path('action=games&query=Fixture+04');rail()
    wait(lambda:info('ListItem.Label')=='Fixture 04');shot('games-search-results')
    # Search cancellation is a real keyboard dialog and returns without scan.
    open_path('action=home')
    xbmc.executebuiltin('ActivateWindow(games,plugin://plugin.games.foundry/?action=search,return)')
    wait(lambda:xbmc.getCondVisibility('Window.IsActive(virtualkeyboard)'))
    action('back');wait(lambda:not xbmc.getCondVisibility('Window.IsActive(virtualkeyboard)'))
    shot('games-search-cancel')
    open_path('action=games&system=nes');control=rail();control.selectItem(2)
    wait(lambda:'Fixture 02' in info('ListItem.Label'))
    action('select')
    # No installer selection or affirmative dialog action is sent. A native
    # missing-emulator chooser/error must appear, and Back must dismiss it.
    wait(lambda:xbmc.getCondVisibility('System.HasActiveModalDialog') and xbmcgui.getCurrentWindowDialogId() not in (0,10101,10138))
    shot('games-missing-core')
    for unused in range(4):
        if not xbmc.getCondVisibility('System.HasActiveModalDialog'):break
        action('back')
    wait(lambda:not xbmc.getCondVisibility('System.HasActiveModalDialog'))
    require(not xbmc.Player().isPlaying(),'Synthetic fixture unexpectedly played')
    wait(lambda:'Fixture 02' in info('ListItem.Label'))
    shot('games-launch-cancel-focus')
    # The cancelled core picker must not record a recent successful launch.
    check=Library(str(profile/'library-v1.db'))
    require(len(check.games(mode='recent'))==1,'Cancelled launch incorrectly changed recent games')
    check.close()
    (OUTPUT/'fixture-result.json').write_text(json.dumps({'checks':evidence,'assertions':{'console_listing':True,'focused_hero_metadata':True,'remote_navigation':True,'page_back_focus':True,'favorite_persistence':True,'search_results':True,'search_cancel':True,'missing_core_dialog':True,'launch_cancel_focus':True,'cancel_does_not_record_play':True},'scope':'Native Kodi UI only. Synthetic non-playable files. No cores/ROMs downloaded. Not Shield or gameplay certification.','limitations':['No actual gameplay or controller/disconnect/multiplayer validation','No Shield or Android emulator compatibility validation','No real VFS provider or Google Drive authorization tested','PSP remains unsupported']},indent=2)+'\n',encoding='utf-8')
    (BASE/'complete').write_text('ok')
except Exception:
    (BASE/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')
'''


def wait_for(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(): return
        time.sleep(.1)
    raise RuntimeError('Native games fixture timed out')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--display', default=':98')
    parser.add_argument('--port', type=int, default=18082)
    args = parser.parse_args()
    release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))['release']
    output = (args.output or ROOT / 'releases' / (str(release) + '-qa') / 'games').resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave a previous pass summary in its evidence set.
    for name in ('verification.json', 'games-verification.json', 'fixture-result.json'):
        target = output / name
        if target.exists(): target.unlink()
    if os.name != 'posix' or not Path('/usr/share/kodi').is_dir():
        raise RuntimeError('Linux Kodi/X11 runner required; no machine setup is performed')
    from PIL import Image, ImageDraw
    with tempfile.TemporaryDirectory(prefix='foundry-games-qa-') as temporary:
        base = Path(temporary)
        home = base / 'kodi'
        shutil.copytree('/usr/share/kodi', home, ignore_dangling_symlinks=True)
        profile = home / 'portable_data'
        userdata = profile / 'userdata'; userdata.mkdir(parents=True)
        addon = profile / 'addons/plugin.games.foundry'
        shutil.copytree(ADDON, addon, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        active = home / 'addons/skin.estuary'
        shutil.copyfile(SKIN / 'xml/View_58_FoundryGames.xml', active / 'xml/View_58_FoundryGames.xml')
        includes = E.parse(active / 'xml/Includes.xml')
        E.SubElement(includes.getroot(), 'include', file='View_58_FoundryGames.xml')
        includes.write(active / 'xml/Includes.xml', encoding='UTF-8', xml_declaration=True)
        games = E.parse(active / 'xml/MyGames.xml')
        views = games.find('views')
        if views is None: views = E.SubElement(games.getroot(), 'views')
        views.text = (views.text or '50') + ',58'
        E.SubElement(games.find('controls'), 'include').text = 'View_58_FoundryGames'
        games.write(active / 'xml/MyGames.xml', encoding='UTF-8', xml_declaration=True)
        fonts = E.parse(active / 'xml/Font.xml')
        source_fonts = E.parse(SKIN / 'xml/Font.xml')
        for fontset in fonts.findall('fontset'):
            for name in ('font27', 'font36_title'):
                for old in list(fontset.findall('font')):
                    if old.findtext('name') == name: fontset.remove(old)
                font = source_fonts.find("fontset/font[name='%s']" % name)
                if font is None: raise RuntimeError('Missing source font: ' + name)
                fontset.append(copy.deepcopy(font))
                shutil.copyfile(SKIN / 'fonts' / font.findtext('filename'), active / 'fonts' / font.findtext('filename'))
        fonts.write(active / 'xml/Font.xml', encoding='UTF-8', xml_declaration=True)
        (active / 'media/streampilot').mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SKIN / 'media/streampilot/catalog-white.png', active / 'media/streampilot/catalog-white.png')
        settings = E.Element('settings', version='2')
        for key, value in {'lookandfeel.skin':'skin.estuary','addons.updatemode':'2','filelists.showparentdiritems':'false','services.webserver':'true','services.webserverport':str(args.port),'services.webserverauthentication':'false'}.items():
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
        prefix = 'from pathlib import Path\nBASE=Path(%r)\nADDON=Path(%r)\nOUTPUT=Path(%r)\nROMS=Path(%r)\n' % tuple(map(str, (base, addon, output, roms)))
        (launcher / 'fixture.py').write_text(prefix + FIXTURE, encoding='utf-8')
        # HOME prevents any fallback user-profile or external account lookup.
        environment = dict(os.environ, HOME=str(base / 'empty-home'), DISPLAY=args.display, KODI_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='1', AE_SINK='NULL')
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
                    try: return rpc('JSONRPC.Ping') == 'pong'
                    except Exception: return False
                wait_for(ready)
                for unused in range(5): rpc('Input.Back'); time.sleep(.2)
                for aid in ('plugin.games.foundry', 'script.foundry.gamesqa'):
                    rpc('Addons.SetAddonEnabled', {'addonid':aid, 'enabled':True})
                rpc('Addons.ExecuteAddon', {'addonid':'script.foundry.gamesqa'})
                def finished():
                    if (base / 'error.txt').exists(): raise AssertionError((base / 'error.txt').read_text())
                    return (base / 'complete').exists()
                wait_for(finished, 240)
                report = json.loads((output / 'fixture-result.json').read_text())
                report['renderer'] = subprocess.check_output(['kodi','--version'], text=True).strip()
                report['release'] = release
                for check in report['checks']:
                    with Image.open(output / (check['case'] + '.png')) as im:
                        assert im.size == (1920,1080), im.size
                        im.verify()
            finally:
                if kodi:
                    try: os.killpg(kodi.pid, signal.SIGTERM); kodi.wait(timeout=10)
                    except ProcessLookupError: pass
                    except subprocess.TimeoutExpired:
                        os.killpg(kodi.pid, signal.SIGKILL); kodi.wait(timeout=5)
                xserver.terminate(); xserver.wait(timeout=10)
                for source, name in ((profile / 'temp/kodi.log','kodi.log'), (base / 'error.txt','error.txt')):
                    if source.exists(): shutil.copyfile(source, output / name)
        kodi_log = output / 'kodi.log'
        if kodi_log.exists():
            assert 'Error parsing boolean expression' not in kodi_log.read_text(errors='replace')
        report['passed'] = True
        report['assertions']['screenshots_verified'] = True
        report['assertions']['skin_boolean_parse_errors_absent'] = True
        for name in ('verification.json', 'games-verification.json'):
            (output / name).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('Native Games UI evidence:', output)


if __name__ == '__main__': main()
