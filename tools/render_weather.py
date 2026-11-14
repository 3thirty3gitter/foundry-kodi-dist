"""Native weather/Home QA in a disposable Kodi 21+/X11 portable profile.

Requires Linux Kodi, Xvfb, Pillow; xdotool/requests may share the CI environment
but this runner uses loopback JSON-RPC. No installation or real profile is used.
All source XML remains unchanged. Only fixture copies of Python entrypoints are
wrapped/no-oped to prohibit live provider, helper setup and update requests.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
import xml.etree.ElementTree as E

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / 'skin.foundry-nimbus'
HELPER = ROOT.parent / 'script.foundry.helper'
PROVIDER = 'weather.foundry.canada'
ALTERNATE = 'weather.foundry.fixtureother'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8', newline='\n')


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    write(temporary, json.dumps(value, ensure_ascii=False))
    temporary.replace(path)


def output_directory(explicit=None, root=ROOT):
    if explicit:
        return Path(explicit).resolve()
    release = json.loads((root / 'release.json').read_text(encoding='utf-8'))['release']
    if not isinstance(release, str) or not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z._-]*', release):
        raise ValueError('release.json contains an unsafe release identifier')
    return root / 'releases' / (release + '-qa')


def scenario(kind='fresh', now=None):
    """Public synthetic fixture only; dates stay meaningful on any CI day."""
    now = now or datetime.now(timezone.utc)
    bi = lambda value: {'en': value, 'fr': value}
    stamp = lambda delta: (now + timedelta(hours=delta)).isoformat()
    forecasts = []
    for index in range(7):
        day = (now + timedelta(days=index)).strftime('%A')
        for title, classification, temperature in ((day, 'high', index), (day + ' night', 'low', -8 + index)):
            forecasts.append({'period': {'value': bi(title), 'textForecastName': bi(title)},
                'temperatures': {'temperature': [{'class': bi(classification), 'value': bi(temperature)}]},
                'abbreviatedForecast': {'textSummary': bi('Synthetic snow'), 'icon': {'value': 16}},
                'textSummary': bi('Synthetic forecast for offline interface verification.')})
    properties = {'identifier': 'on-118', 'name': bi('Ottawa'), 'lastUpdated': stamp(0),
        'currentConditions': {'timestamp': bi(stamp(-0.25)), 'temperature': {'value': bi(0)},
            'windChill': {'value': bi(-7)}, 'condition': bi('Synthetic snow'), 'iconCode': {'value': 16},
            'relativeHumidity': {'value': bi(70)}, 'wind': {'speed': {'value': bi(12)}, 'direction': {'value': bi('N')}}},
        'forecastGroup': {'forecasts': forecasts},
        'hourlyForecastGroup': {'hourlyForecasts': [{'timestamp': stamp(i), 'temperature': {'value': bi(-i)},
            'condition': bi('Synthetic snow'), 'iconCode': {'value': 16}, 'lop': {'value': bi(60)}} for i in range(1, 25)]},
        'warnings': [{'description': bi('SYNTHETIC TEST ADVISORY - not a real warning'),
            'type': bi('warning'), 'alertColourLevel': bi('yellow'), 'eventIssue': stamp(-1),
            'expiryTime': stamp(6), 'url': bi('https://weather.gc.ca/warnings/index_e.html')}]}
    if kind == 'missing':
        properties['currentConditions'] = {}
        properties['forecastGroup'] = {}
        properties['hourlyForecastGroup'] = {}
        properties['warnings'] = []
    if kind == 'stale':
        properties['lastUpdated'] = stamp(-4)
        properties['currentConditions']['timestamp'] = bi(stamp(-4))
    return {'kind': kind, 'payload': {'type': 'Feature', 'id': 'on-118', 'properties': properties},
            'fetched': now.timestamp(), 'stale': kind == 'stale'}


PROVIDER_WRAPPER = r'''
import json,runpy,sys,traceback,uuid
from pathlib import Path
from resources.lib import client
class SyntheticClient:
    def __init__(self,*args,**kwargs):pass
    def get(self,path,validator,**kwargs):
        data=json.loads((BASE/'scenario.json').read_text(encoding='utf-8'))
        locations={'on-118':'Ottawa','bc-74':'Vancouver'}
        if path == client.CATALOGUE:
            catalogue={'type':'FeatureCollection','features':[
                {'id':key,'properties':{'name':{'en':name,'fr':name}}}
                for key,name in locations.items()]}
            validator(catalogue)
            return catalogue,data['fetched'],False,'fresh'
        identifier=path.removeprefix(client.COLLECTION+'/items/').removesuffix('?f=json')
        if identifier not in locations or path != client.COLLECTION+'/items/'+identifier+'?f=json':
            raise AssertionError('Unexpected fixture endpoint: '+path)
        data['payload']['id']=identifier
        data['payload']['properties']['identifier']=identifier
        data['payload']['properties']['name']={lang:locations[identifier] for lang in ('en','fr')}
        validator(data['payload'])
        return data['payload'],data['fetched'],data['stale'],'offline' if data['stale'] else 'fresh'
def forbid(*args,**kwargs):raise AssertionError('Live weather transport forbidden in native QA')
client.transport=forbid
client.Client=SyntheticClient
try:
    # Kodi's Addon() reads identity from the current __main__ module, which
    # runpy replaces. Carry genuine invoker values into the shipped script.
    original_main=vars(sys.modules['__main__'])
    keys=('__xbmcaddonid__','__xbmcapiversion__','__xbmcinvokerid__')
    context={key:original_main[key] for key in keys if key in original_main}
    if context.get('__xbmcaddonid__')!='weather.foundry.canada':
        raise RuntimeError('Weather wrapper must be launched through its Kodi add-on context')
    invocation=uuid.uuid4().hex
    kind=json.loads((BASE/'scenario.json').read_text(encoding='utf-8'))['kind']
    runpy.run_path(str(Path(__file__).with_name('shipped_default.py')),init_globals=context,run_name='__main__')
    receipt=BASE/('provider-complete-'+invocation+'.tmp')
    receipt.write_text(json.dumps({'invocation':invocation,'kind':kind,
        'argument':sys.argv[1] if len(sys.argv)>1 else '1'}),encoding='utf-8')
    receipt.replace(BASE/'provider-complete.json')
except Exception:
    (BASE/'provider-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
    raise
'''

FIXTURE = r'''
import json,time,traceback
import xbmc,xbmcgui,xbmcvfs
def phase(stage,**values):
    temporary=BASE/'fixture-phase.tmp'
    temporary.write_text(json.dumps(dict(values,stage=stage,observed=time.monotonic())),encoding='utf-8')
    temporary.replace(BASE/'fixture-phase.json')
try:
    phase('observer-started')
    runtime_skin_path=xbmcvfs.translatePath('special://skin/')
    phase('runtime-skin-observed',runtime_skin_path=runtime_skin_path)
    normalize=lambda value:str(value).replace('\\','/').rstrip('/')
    if normalize(runtime_skin_path)!=normalize(EXPECTED_SKIN_PATH):
        raise AssertionError('Observer is not running in the copied Foundry skin: '+runtime_skin_path)
    home=xbmcgui.Window(10000)
    def focus_menu():
        # Native XML lists are not Python ControlList.vecItems. Use Kodi's
        # native focus action and info labels, never borrowed control wrappers.
        count=int(xbmc.getInfoLabel('Container(9000).NumItems') or '0')
        for index in range(count):
            xbmc.executebuiltin('SetFocus(9000,%d,absolute)'%index,True)
            xbmc.sleep(75)
            if xbmc.getInfoLabel('Container(9000).ListItem.Property(id)')=='weather':return
        raise AssertionError('Weather menu item is missing')
    first_state=True
    deadline=time.monotonic()+360
    while not (BASE/'complete').exists() and time.monotonic()<deadline:
        weather=xbmcgui.Window(12600)
        try:focus=home.getFocusId()
        except RuntimeError:focus=0
        dialog=xbmc.getCondVisibility('Window.IsVisible(textviewer)')
        body=''
        if dialog:
            body=xbmc.getInfoLabel('Control.GetLabel(5)')
        values={key:weather.getProperty('Foundry.Weather.'+key) for key in
            ['Status','HasCurrent','Temperature','Location','AlertCount','AlertStatus','DayCount','HourCount','Stale']}
        child_visible=xbmc.getCondVisibility('Control.IsVisible(15150)')
        parent_visible=xbmc.getCondVisibility(CARD_PARENT_VISIBLE)
        values.update(window=xbmcgui.getCurrentWindowId(),focus=focus,dialog=dialog,body=body,
            runtime_skin_path=xbmcvfs.translatePath('special://skin/'),home_count=xbmc.getInfoLabel('Container(9000).NumItems'),
            modal_active=xbmc.getCondVisibility('System.HasActiveModalDialog'),
            modal_visible=xbmc.getCondVisibility('System.HasVisibleModalDialog'),
            startup_visible=xbmc.getCondVisibility('Window.IsVisible(startup)'),
            updating=xbmc.getCondVisibility('Container.IsUpdating'),
            provider=xbmc.getInfoLabel('Weather.Plugin'),category=xbmc.getInfoLabel('Container(9000).ListItem.Property(id)'),
            card_control_visible=child_visible,card_parent_visible=parent_visible,
            card_visible=child_visible and parent_visible,
            legacy_visible=xbmc.getCondVisibility('Control.IsVisible(15001)'),
            legacy_focused=xbmc.getCondVisibility('ControlGroup(15001).HasFocus'))
        (BASE/'state.tmp').write_text(json.dumps(values),encoding='utf-8');(BASE/'state.tmp').replace(BASE/'state.json')
        if first_state:
            phase('first-state-published',state=values);first_state=False
        command=BASE/'command.json'
        if command.exists():
            value=json.loads(command.read_text(encoding='utf-8'))
            phase('command-started',command=value)
            if value['action']=='focus-menu':focus_menu()
            elif value['action']=='open-provider-settings':
                # Asynchronous: modal settings must not block the observer acknowledgment.
                xbmc.executebuiltin('Addon.OpenSettings(weather.foundry.canada)')
            elif value['action']=='capture':xbmc.executebuiltin('TakeScreenshot('+str(OUTPUT/(value['name']+'.png'))+')')
            # Consumption is the host's completion acknowledgment, not merely
            # receipt. Never let host input race the menu-selection loop.
            phase('command-completed',command=value)
            command.unlink()
        xbmc.sleep(50)
    if not (BASE/'complete').exists():raise AssertionError('Native weather QA timed out')
except Exception:
    error=traceback.format_exc()
    phase('observer-failed',error=error)
    (BASE/'error.txt').write_text(error,encoding='utf-8')
'''


def prepare(base, kodi_root=Path('/usr/share/kodi'), skin_source=SKIN, helper_source=HELPER):
    home = base / 'kodi'
    shutil.copytree(kodi_root, home, ignore_dangling_symlinks=True)
    profile = home / 'portable_data'
    userdata = profile / 'userdata'
    addons = profile / 'addons'
    addons.mkdir(parents=True)
    sources = [ROOT / 'src/resource.images.foundry.wallpapers', ROOT / 'src/resource.images.foundry.osd',
               ROOT / 'src/resource.uisounds.foundry.pulse', helper_source,
               ROOT / ('src/' + PROVIDER), skin_source]
    identifiers = []
    for source in sources:
        identifier = E.parse(source / 'addon.xml').getroot().get('id')
        shutil.copytree(source, addons / identifier, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        identifiers.append(identifier)
    # Disable services in this private copy, including bundled version-check services.
    for manifest_path in list((home / 'addons').glob('*/addon.xml')) + list(addons.glob('*/addon.xml')):
        tree = E.parse(manifest_path)
        services = tree.getroot().findall("extension[@point='xbmc.service']")
        for extension in services:
            tree.getroot().remove(extension)
        if services:
            tree.write(manifest_path, encoding='UTF-8', xml_declaration=True)
    helper = addons / 'script.foundry.helper'
    manifest = E.parse(helper / 'addon.xml')
    for dependency in list(manifest.getroot().find('requires')):
        if dependency.get('addon') != 'xbmc.python':
            manifest.getroot().find('requires').remove(dependency)
    for extension in manifest.getroot().findall('extension'):
        library = extension.get('library')
        if library:
            write(helper / library, '# Offline QA: helper setup/network actions intentionally disabled.\n')
    manifest.write(helper / 'addon.xml', encoding='UTF-8', xml_declaration=True)
    skin = addons / 'skin.foundry'
    # These exact source files, including Home navigation, must never be replaced by a mock.
    hashes = {}
    for name in ('Home.xml', 'Includes.xml', 'Includes_FoundryCanadaWeather.xml', 'Font.xml'):
        source = skin_source / 'xml' / name
        copied = skin / 'xml' / name
        assert source.read_bytes() == copied.read_bytes(), name
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    write(userdata / 'addon_data/skin.foundry/settings.xml', '<settings><setting id="firsttimerun" type="bool">true</setting></settings>')
    write(userdata / ('addon_data/' + PROVIDER + '/settings.xml'), '<settings version="2"><setting id="language">en</setting><setting id="location1_id">on-118</setting><setting id="location1_label">Ottawa, ON</setting><setting id="location2_id">bc-74</setting><setting id="location2_label">Vancouver, BC</setting></settings>')
    provider = addons / PROVIDER
    shutil.copyfile(provider / 'default.py', provider / 'shipped_default.py')
    hashes['weather_default.py'] = hashlib.sha256((provider / 'shipped_default.py').read_bytes()).hexdigest()
    write(provider / 'default.py', 'from pathlib import Path\nBASE=Path(%r)\n' % str(base) + PROVIDER_WRAPPER)
    other = addons / ALTERNATE
    write(other / 'addon.xml', '<addon id="%s" name="Synthetic Other Weather" version="1.0.0" provider-name="Foundry QA"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.weather" library="default.py"/><extension point="xbmc.addon.metadata"><platform>all</platform><license>Private test fixture</license></extension></addon>' % ALTERNATE)
    write(other / 'default.py', '# No network or weather-property writes.\n')
    identifiers.append(ALTERNATE)
    atomic_json(base / 'scenario.json', scenario())
    return home, profile, identifiers, hashes


def wait_for(predicate, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError('Native weather fixture did not reach the expected state')


def weather_menu_ready(values):
    return (values.get('window') == 10000 and values.get('focus') == 9000
            and values.get('category') == 'weather' and not values.get('dialog'))


def card_parent_visibility(skin):
    # Omega Control.IsVisible reports only the child, not hidden ancestors.
    # Read the actual shipped group expression without changing its XML/IDs.
    root = E.parse(skin / 'xml/Includes_FoundryCanadaWeather.xml').getroot()
    value = root.findtext("include[@name='FoundryCanadaWeatherWidget']/definition/control/visible")
    if not value or not value.strip():
        raise ValueError('Shipped weather card parent visibility is missing')
    return value.strip()


def card_title_pixels(picture):
    # Independent rendered evidence: the cyan CANADA WEATHER title sits here
    # on the shipped card. Fresh capture supplies a positive control.
    return sum(g > 150 and b > 170 and r < 130
               for y in range(318, 352) for x in range(338, 638)
               for r, g, b in [picture.getpixel((x, y))[:3]])


def available_port(requested=0):
    """Fail on a busy explicit port, or allocate a separate ephemeral endpoint."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', requested))
        return listener.getsockname()[1]


def fixture_ready(rpc, logfile, port, identity):
    """Ping alone can accidentally reach a previous renderer's orphan process."""
    try:
        if '<CWebserver[%d]>: Started' % port not in logfile.read_text(encoding='utf-8', errors='replace'):
            return False
        if rpc('JSONRPC.Ping') != 'pong':
            return False
        return rpc('Settings.GetSettingValue', {'setting': 'services.devicename'}).get('value') == identity
    except (OSError, ValueError):
        return False


def actual_skin_log_state(text, skin_path):
    lines=text.splitlines()
    loads=[(index,re.search(r'load skin from:\s*(.*?)\s+\(version:',line))
           for index,line in enumerate(lines) if 'load skin from:' in line]
    if not loads:return {'ready':False}
    index,match=loads[-1]
    if match is None:return {'ready':False}
    normalize=lambda value:str(value).replace('\\','/').rstrip('/')
    tail=lines[index+1:]
    loaded=next((offset for offset,line in enumerate(tail) if 'skin loaded...' in line),None)
    transitions=[line for line in tail[loaded+1:] if 'Window Init (Home.xml)' in line or 'Window Init (Startup.xml)' in line] if loaded is not None else []
    return {'ready':normalize(match.group(1))==normalize(skin_path) and bool(transitions) and 'Window Init (Home.xml)' in transitions[-1],
            'loaded_path':match.group(1),'load_event':lines[index],
            'last_transition':transitions[-1] if transitions else ''}


def cold_home_ready(observation, identity, provider):
    labels=observation['labels']
    count=labels.get('Container(9000).NumItems','')
    menu=labels.get('Container(9000).ListItem.Property(menu_id)','')
    category=labels.get('Container(9000).ListItem.Property(id)','')
    categories={'movies','tvshows','music','disc','musicvideos','livetv','radio','games','addons',
                'pictures','video','videos','favorites','weather','settings','custom1','custom2','custom3'}
    return (observation['window']['id']==10000 and observation['skin_log']['ready'] and
            observation['own_webserver'] and observation['owner']==identity and
            observation['provider']==provider and labels.get('Weather.Plugin')==provider and
            not any(observation['flags'].values()) and count.isdigit() and int(count)>0 and
            menu.isdigit() and int(menu)>0 and category in categories)


def observer_home_ready(values, skin_path, provider):
    normalize=lambda value:str(value).replace('\\','/').rstrip('/')
    count=values.get('home_count','')
    return (values.get('window')==10000 and values.get('provider')==provider and
            normalize(values.get('runtime_skin_path',''))==normalize(skin_path) and
            count.isdigit() and int(count)>0 and
            not any(values.get(name,True) for name in ('modal_active','modal_visible','startup_visible','updating')))


def settle_cold_home(rpc, log_path, skin_path, port, identity, provider, alive, output, timeout=45, quiet=2):
    deadline=time.monotonic()+timeout;quiet_since=None;last=None;history=[]
    destination=output/'weather-startup-readiness.json'
    while time.monotonic()<deadline:
        if not alive():raise AssertionError('Kodi exited during cold Foundry Home startup')
        text=log_path.read_text(encoding='utf-8',errors='replace')
        if any(marker in text for marker in ('PythonToCppException','Error Contents:','Traceback (most recent call last):')):
            raise AssertionError('Python failure during cold Foundry Home startup')
        observation={'window':rpc('GUI.GetProperties',{'properties':['currentwindow']})['currentwindow'],
            'flags':rpc('XBMC.GetInfoBooleans',{'booleans':['Window.IsVisible(startup)','System.HasActiveModalDialog','System.HasVisibleModalDialog','Container.IsUpdating']}),
            'labels':rpc('XBMC.GetInfoLabels',{'labels':['Container(9000).NumItems','Container(9000).ListItem.Property(menu_id)','Container(9000).ListItem.Property(id)','Weather.Plugin']}),
            'owner':rpc('Settings.GetSettingValue',{'setting':'services.devicename'})['value'],
            'provider':rpc('Settings.GetSettingValue',{'setting':'weather.addon'})['value'],
            'skin_log':actual_skin_log_state(text,skin_path),
            'own_webserver':'<CWebserver[%d]>: Started'%port in text}
        if observation!=last:history.append(observation);last=observation;quiet_since=None
        ready=cold_home_ready(observation,identity,provider)
        if ready:
            if quiet_since is None:quiet_since=time.monotonic()
            elif time.monotonic()-quiet_since>=quiet:
                report={'passed':True,'quiet_seconds':quiet,'observations':history}
                atomic_json(destination,report);return report
        else:quiet_since=None
        atomic_json(destination,{'passed':False,'observations':history})
        time.sleep(.1)
    raise AssertionError('Cold Foundry Home did not settle within the existing startup deadline')


def stop_process_group(process):
    """The launcher exiting does not prove its Kodi child has exited."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # A TERM handler can leave kodi.bin alive after its shell launcher exits.
    # Limit cleanup strictly to the private session created by this runner.
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run(output, display, port):
    from PIL import Image, ImageGrab
    port = available_port(port)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='foundry-weather-', ignore_cleanup_errors=True) as temporary:
        base = Path(temporary)
        home, profile, identifiers, hashes = prepare(base)
        userdata = profile / 'userdata'
        identity = 'Foundry Weather QA ' + base.name
        write(userdata / 'guisettings.xml', '<settings version="2"><setting id="lookandfeel.skin">skin.estuary</setting><setting id="addons.updatemode">2</setting><setting id="services.webserver">true</setting><setting id="services.webserverport">%d</setting><setting id="services.webserverauthentication">false</setting><setting id="services.devicename">%s</setting><setting id="locale.temperatureunit">c</setting></settings>' % (port, identity))
        launcher = profile / 'addons/script.foundry.weatherqa'
        write(launcher / 'addon.xml', '<addon id="script.foundry.weatherqa" name="Foundry Weather QA" version="1.0.0" provider-name="Foundry"><requires><import addon="xbmc.python" version="3.0.0"/></requires><extension point="xbmc.python.script" library="default.py"/><extension point="xbmc.addon.metadata"><platform>all</platform><license>Private test fixture</license></extension></addon>')
        parent_visibility = card_parent_visibility(profile / 'addons/skin.foundry')
        write(launcher / 'default.py', 'from pathlib import Path\nBASE=Path(%r)\nOUTPUT=Path(%r)\nCARD_PARENT_VISIBLE=%r\nEXPECTED_SKIN_PATH=%r\n' % (str(base), str(output), parent_visibility, str(profile/'addons/skin.foundry')) + FIXTURE)
        # Isolate HOME/XDG paths as well as Kodi portable_data. Never inherit a personal profile.
        isolated_home = base / 'user-home'
        isolated_home.mkdir()
        environment = dict(os.environ, HOME=str(isolated_home), XDG_CONFIG_HOME=str(isolated_home / '.config'),
            XDG_CACHE_HOME=str(isolated_home / '.cache'), DISPLAY=display, KODI_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='1', AE_SINK='NULL')
        kodi = None
        with (output / 'weather-console.log').open('w', encoding='utf-8') as log:
            xserver = subprocess.Popen(['Xvfb', display, '-screen', '0', '1920x1080x24', '-ac', '-nolisten', 'tcp'], stdout=log, stderr=log)
            try:
                time.sleep(1)
                if xserver.poll() is not None:
                    raise RuntimeError('Private Xvfb did not start; choose a free --display')
                kodi = subprocess.Popen(['kodi', '-p', '-fs', '--windowing=x11', '--debug'], env=environment, stdout=log, stderr=log, start_new_session=True)
                def rpc(method, params=None):
                    data = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}).encode()
                    with urlopen(Request('http://127.0.0.1:%d/jsonrpc' % port, data=data, headers={'Content-Type': 'application/json'}), timeout=5) as response:
                        result = json.loads(response.read())
                    if 'error' in result:
                        raise RuntimeError(str(result['error']))
                    return result.get('result')
                def ready():
                    return fixture_ready(rpc, profile / 'temp/kodi.log', port, identity)
                wait_for(ready, 75)
                version = rpc('Application.GetProperties', {'properties': ['version']})['version']
                assert version['major'] >= 21, 'Kodi 21+ required'
                quiet = None
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    modal = rpc('XBMC.GetInfoBooleans', {'booleans': ['System.HasActiveModalDialog']})['System.HasActiveModalDialog']
                    if modal:
                        rpc('Input.Back'); quiet = None
                    elif quiet is None:quiet = time.monotonic()
                    elif time.monotonic() - quiet > 2:break
                    time.sleep(.2)
                else:raise AssertionError('First-start dialogs did not settle')
                for identifier in identifiers + ['script.foundry.weatherqa']:
                    rpc('Addons.SetAddonEnabled', {'addonid': identifier, 'enabled': True})
                assert rpc('Settings.SetSettingValue', {'setting': 'weather.addon', 'value': PROVIDER})
                assert rpc('Settings.SetSettingValue', {'setting': 'lookandfeel.skin', 'value': 'skin.foundry'})
                def modal():return rpc('XBMC.GetInfoBooleans', {'booleans': ['System.HasActiveModalDialog']})['System.HasActiveModalDialog']
                wait_for(modal)
                labels = rpc('XBMC.GetInfoLabels', {'labels': ['Control.GetLabel(1)', 'Control.GetLabel(9)']})
                prompt = ' '.join(labels.values()).lower()
                assert 'keep' in prompt or 'skin' in prompt, ('Unexpected skin prompt', labels)
                rpc('Input.Left'); rpc('Input.Select')
                wait_for(lambda: not modal())
                startup=settle_cold_home(rpc,profile/'temp/kodi.log',profile/'addons/skin.foundry',port,identity,PROVIDER,lambda:kodi.poll() is None,output)
                rpc('Addons.ExecuteAddon', {'addonid': 'script.foundry.weatherqa'})
                def state():
                    for name in ('error.txt', 'provider-error.txt'):
                        if (base / name).exists():raise AssertionError((base / name).read_text(encoding='utf-8'))
                    try:return json.loads((base / 'state.json').read_text(encoding='utf-8'))
                    except (OSError, ValueError):return {}
                def command(action, **kwargs):
                    wait_for(lambda: not (base / 'command.json').exists())
                    atomic_json(base / 'command.json', dict(action=action, **kwargs))
                    wait_for(lambda: not (base / 'command.json').exists())
                    if action == 'focus-menu':
                        # The fixture publishes state on its next loop, after
                        # acknowledgment. Do not reuse the previous card focus.
                        wait_for(lambda: weather_menu_ready(state()))
                def capture(name):
                    destination = output / (name + '.png')
                    if destination.exists():destination.unlink()
                    time.sleep(.8)
                    command('capture', name=name)
                    def complete():
                        try:
                            with Image.open(destination) as picture:picture.verify()
                            return True
                        except (OSError, ValueError):return False
                    wait_for(complete)
                    with Image.open(destination) as picture:
                        assert picture.size == (1920, 1080), picture.size
                        return picture.convert('RGB')
                def click_action(identifier):
                    # Navigate to the actual shipped buttons; never initialize
                    # the native Weather window to mask Home-only regressions.
                    command('focus-menu')
                    rpc('Input.Select')
                    wait_for(lambda: state().get('focus') == 15150)
                    rpc('Input.Down')
                    wait_for(lambda: state().get('focus') == 15151)
                    for control in range(15152, identifier + 1):
                        rpc('Input.Right')
                        wait_for(lambda: state().get('focus') == control)
                    rpc('Input.Select')
                def refresh(kind):
                    receipt = base / 'provider-complete.json'
                    before = json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {}
                    atomic_json(base / 'scenario.json', scenario(kind))
                    click_action(15153)
                    def completed():
                        try:after = json.loads(receipt.read_text(encoding='utf-8'))
                        except (OSError, ValueError):return False
                        return (after.get('invocation') != before.get('invocation')
                                and after.get('argument') == 'refresh' and after.get('kind') == kind)
                    wait_for(completed)
                wait_for(lambda: observer_home_ready(state(),profile/'addons/skin.foundry',PROVIDER))
                command('focus-menu')
                wait_for(lambda: state().get('category') == 'weather')
                assert rpc('Settings.GetSettingValue', {'setting': 'weather.currentlocation'})['value'] == 1
                wait_for(lambda: state().get('HasCurrent') == 'true' and state().get('HourCount') == '24')
                assert state()['Temperature'] == '0\u00b0C', state()
                assert state()['DayCount'] == '7' and state()['AlertCount'] == '1', state()
                # Enter through the shipped weather menu's real onclick.
                rpc('Input.Select')
                wait_for(lambda: state().get('focus') == 15150 and state().get('card_visible'))
                fresh = capture('weather-fresh')
                fresh_title = card_title_pixels(fresh)
                assert fresh_title > 100, 'Fresh weather card title is missing from native render'
                bright = sum(min(fresh.getpixel((x, y))) > 100 for y in range(370, 460) for x in range(335, 520))
                assert bright > 50, 'Current temperature appears absent from native card'
                rpc('Input.Select')
                wait_for(lambda: state().get('dialog') and 'Synthetic forecast' in state().get('body', ''))
                capture('weather-forecast')
                rpc('Input.Back'); wait_for(lambda: not state().get('dialog') and state().get('focus') == 15150)
                rpc('Input.Down'); wait_for(lambda: state().get('focus') == 15151)
                rpc('Input.Select'); wait_for(lambda: state().get('dialog') and 'SYNTHETIC TEST ADVISORY' in state().get('body', ''))
                capture('weather-advisories')
                rpc('Input.Back'); wait_for(lambda: not state().get('dialog'))
                rpc('Input.Back'); wait_for(lambda: state().get('focus') == 9000)
                rpc('Input.Select'); wait_for(lambda: state().get('focus') == 15150)
                click_action(15152)
                wait_for(lambda: state().get('Location') == 'Vancouver, BC')
                assert rpc('Settings.GetSettingValue', {'setting': 'weather.currentlocation'})['value'] == 2
                refresh('fresh')
                wait_for(lambda: state().get('Location') == 'Vancouver, BC' and state().get('HasCurrent') == 'true')
                assert rpc('Settings.GetSettingValue', {'setting': 'weather.currentlocation'})['value'] == 2
                capture('weather-next-city')
                click_action(15152)
                wait_for(lambda: state().get('Location') == 'Ottawa, ON')
                assert rpc('Settings.GetSettingValue', {'setting': 'weather.currentlocation'})['value'] == 1
                refresh('missing')
                wait_for(lambda: state().get('HasCurrent') == 'false' and state().get('HourCount') == '0')
                assert state()['Temperature'] == '', state()
                capture('weather-missing')
                refresh('stale')
                wait_for(lambda: state().get('Stale') == 'true' and state().get('AlertStatus') == 'unverified')
                capture('weather-stale')
                command('focus-menu')
                assert rpc('Settings.SetSettingValue', {'setting': 'weather.addon', 'value': ALTERNATE})
                wait_for(lambda: state().get('provider') == ALTERNATE and not state().get('card_visible')
                         and state().get('legacy_visible'))
                other = capture('weather-other-provider')
                alternate_state = state()
                alternate_title = card_title_pixels(other)
                assert alternate_title < fresh_title * .1, 'Canada card title remains rendered with another provider'
                # Normal remote navigation must enter the visible legacy group,
                # never a forced SetFocus call targeting the hidden card itself.
                rpc('Input.Right')
                wait_for(lambda: state().get('legacy_focused'))
                assert state().get('focus') not in range(15150, 15155), state()
                capture('weather-other-provider-navigation')
                assert rpc('Settings.GetSettingValue', {'setting': 'weather.addon'})['value'] == ALTERNATE
                # Real settings action/search selection, not scripted setSetting.
                alternate_navigation_focus = state().get('focus')
                assert rpc('Settings.SetSettingValue', {'setting': 'weather.addon', 'value': PROVIDER})
                rpc('Input.Back')
                atomic_json(base / 'scenario.json', scenario('fresh'))
                def visible(name):
                    key = 'Window.IsVisible(%s)' % name
                    return rpc('XBMC.GetInfoBooleans', {'booleans': [key]})[key]
                def focused_label():
                    return rpc('XBMC.GetInfoLabels', {'labels': ['System.CurrentControl']})['System.CurrentControl']
                saved_path = userdata / 'addon_data' / PROVIDER / 'settings.xml'
                def saved_locations():
                    try:return {x.get('id'):x.text or '' for x in E.parse(saved_path).getroot().findall('setting')}
                    except (OSError,E.ParseError):return {}
                expected_location = {'location1_id':'bc-74','location1_label':'Vancouver, BC'}
                native_index = rpc('Settings.GetSettingValue', {'setting':'weather.currentlocation'})['value']
                command('open-provider-settings')
                wait_for(lambda: visible('addonsettings'))
                if 'Choose location 1' not in focused_label():rpc('Input.Right')
                wait_for(lambda: 'Choose location 1' in focused_label())
                rpc('Input.Select')
                wait_for(lambda: visible('keyboard'))
                assert not visible('addonsettings'), 'Chooser must close settings before writing'
                rpc('Input.SendText', {'text':'Vancouver','done':True})
                wait_for(lambda: visible('select'))
                rpc('Input.Select')
                wait_for(lambda: not visible('select') and not visible('keyboard'))
                wait_for(lambda: all(saved_locations().get(k)==v for k,v in expected_location.items()))
                command('open-provider-settings')
                wait_for(lambda: visible('addonsettings'))
                capture('weather-location-saved-settings')
                rpc('Input.Back')
                wait_for(lambda: not visible('addonsettings'))
                assert all(saved_locations().get(k)==v for k,v in expected_location.items())
                # Clean restart of exactly the same disposable profile. Never reseed.
                write(base / 'complete', 'ok')
                time.sleep(.2)
                rpc('Application.Quit')
                kodi.wait(timeout=30)
                stop_process_group(kodi)
                shutil.copyfile(profile/'temp/kodi.log',output/'weather-before-restart-kodi.log')
                for name in ('complete','state.json','fixture-phase.json'):
                    (base/name).unlink(missing_ok=True)
                kodi = subprocess.Popen(['kodi','-p','-fs','--windowing=x11','--debug'],
                    env=environment,stdout=log,stderr=log,start_new_session=True)
                wait_for(ready,75)
                restart_startup=settle_cold_home(rpc,profile/'temp/kodi.log',profile/'addons/skin.foundry',port,
                    identity,PROVIDER,lambda:kodi.poll() is None,output)
                rpc('Addons.ExecuteAddon', {'addonid':'script.foundry.weatherqa'})
                wait_for(lambda: observer_home_ready(state(),profile/'addons/skin.foundry',PROVIDER))
                assert all(saved_locations().get(k)==v for k,v in expected_location.items())
                assert rpc('Settings.GetSettingValue',{'setting':'weather.currentlocation'})['value']==native_index
                command('open-provider-settings')
                wait_for(lambda: visible('addonsettings'))
                capture('weather-location-after-restart')
                rpc('Input.Back')
                wait_for(lambda: not visible('addonsettings'))
                location_persistence={'passed':True,'actual_gui_selection':True,'saved':expected_location,
                    'native_index':native_index,'restart_same_profile':True,'restart_startup':restart_startup}
                atomic_json(output/'weather-location-persistence.json',location_persistence)
                write(base / 'complete', 'ok')
                atomic_json(output / 'weather-verification.json', {'passed': True, 'kodi_version': version,
                    'checks': ['provider_entrypoint', 'untouched_shipped_home_card', 'current_zero', '24_hourly', '7_daily',
                               'advisory_headline', 'forecast_click_back', 'advisory_click_back', 'menu_back_reentry',
                               'native_home_initial_fetch', 'next_city_native_index', 'refresh_preserves_city',
                               'next_city_wrap', 'missing_values', 'stale_unverified', 'alternate_provider_hides_card',
                               'alternate_card_render_absent', 'alternate_normal_navigation_uses_legacy',
                               'location_actual_settings_search_select', 'location_saved_before_back', 'location_survives_restart'],
                    'location_persistence':location_persistence,
                    'alternate_visibility': {'shipped_parent_condition': parent_visibility,
                        'state': alternate_state, 'fresh_title_pixels': fresh_title,
                        'alternate_title_pixels': alternate_title, 'normal_navigation_focus': alternate_navigation_focus},
                    'source_sha256': hashes, 'data': 'Synthetic only; no live weather or account requests',
                    'fixture_identity': identity, 'fixture_port': port,'cold_home_startup':startup,
                    'isolation': 'Disposable HOME, XDG and Kodi portable profile; copied helper/services disabled',
                    'scope': 'Native Linux desktop only. Shield and live service behavior remain separate QA.'})
            except Exception:
                try:ImageGrab.grab(xdisplay=display).save(output / 'weather-failure.png')
                except Exception:pass
                raise
            finally:
                if kodi:
                    stop_process_group(kodi)
                xserver.terminate()
                try:xserver.wait(timeout=5)
                except subprocess.TimeoutExpired:xserver.kill(); xserver.wait(timeout=5)
                for source, target in [(profile / 'temp/kodi.log', 'weather-kodi.log'),
                                       (base / 'state.json', 'weather-state.json'),
                                       (base / 'provider-complete.json', 'weather-provider-complete.json'),
                                       (base / 'error.txt', 'weather-error.txt'),
                                       (base / 'provider-error.txt', 'weather-provider-error.txt'),
                                       (base / 'fixture-phase.json','weather-fixture-phase.json'),
                                       (base / 'command.json','weather-command.json'),
                                       (base / 'scenario.json','weather-scenario.json'),
                                       (launcher / 'default.py','weather-native-fixture.py')]:
                    if source.exists():shutil.copyfile(source, output / target)
                # Preserve native crash diagnostics before the disposable HOME is removed.
                for crash in isolated_home.glob('kodi_crashlog-*.log'):
                    shutil.copyfile(crash, output / ('weather-' + crash.name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Override release.json-derived QA output directory')
    parser.add_argument('--display', default=':99')
    parser.add_argument('--port', type=int, default=0, help='Private HTTP port; 0 chooses a free ephemeral port')
    args = parser.parse_args()
    if os.name != 'posix':
        parser.error('Native execution requires Linux Kodi/X11; no software will be installed')
    run(output_directory(args.output), args.display, args.port)


if __name__ == '__main__':
    main()
