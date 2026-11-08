"""Package the wallpaper-matched full-color icon artwork for native Kodi menus."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as E

SKIN=Path(__file__).resolve().parents[2]/'skin.foundry-nimbus'
ICON_NAMES=('accessibility', 'add', 'addons', 'audio', 'back', 'calendar', 'check', 'clock', 'debug', 'delete', 'disc', 'display', 'download', 'edit', 'favorite', 'folder', 'fullscreen', 'games', 'help', 'home', 'info', 'interface', 'keyboard', 'language', 'library', 'list', 'lock', 'media', 'music', 'network', 'next', 'pictures', 'player', 'power', 'profiles', 'reload', 'remote', 'remove', 'search', 'settings', 'share', 'skin', 'sleep', 'sliders', 'sort', 'storage', 'subtitles', 'system', 'toggle', 'tv', 'upload', 'weather')
PATHS=dict.fromkeys(ICON_NAMES)

def choose(text, kind='button'):
    text = text.lower()
    rules = [('debug','debug'),('shutdown|powerdown|quit|exit','power'),('reload|reset|restart|reboot','reload'),('sleep|suspend|hibernate','sleep'),('alarm|timer|time|clock','clock'),('subtitle|caption','subtitles'),('sound|audio|volume','audio'),('video|movie|trailer','media'),('tv|pvr|epg|guide','tv'),('music|song|album','music'),('picture|image|photo|fanart|artwork','pictures'),('profile|account|user','profiles'),('file|folder|path|source','folder'),('network|internet|service|web|proxy','network'),('addon|plug-in|plugin|scraper|omdb|tmdb','addons'),('game|controller','games'),('interface|layout|menu|widget','interface'),('skin|theme|colour|color','skin'),('display|screen|resolution|monitor','display'),('lock|password|security','lock'),('language|region|locale','language'),('keyboard|input','keyboard'),('remote|cec','remote'),('database|cache|storage|disc','storage'),('sort|order','sort'),('search|find','search'),('delete|remove|clear','delete'),('add|new|create','add'),('edit|rename|custom','edit'),('favorite|favourite','favorite'),('download|install|update','download'),('help|support','help'),('info|about|version|systeminfo','info'),('weather','weather'),('calibrat','sliders')]
    for pattern, icon in rules:
        if re.search(pattern, text): return icon
    return {'radiobutton':'toggle','spincontrolex':'list','sliderex':'sliders','edit':'edit','colorbutton':'skin'}.get(kind, 'settings')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artwork-map',type=Path,required=True);args=parser.parse_args()
    icons=json.loads(args.artwork_map.read_text())['icons']
    assert set(ICON_NAMES)<=set(icons),'The complete themed icon set is required'
    destination=SKIN/'media/foundry-icons';(destination/'rows').mkdir(parents=True,exist_ok=True)
    templates={'DefaultSettingButton','DefaultAddonSettingsButton','DefaultSystemSettingsButton','DialogSettingButton'}
    heights={70}
    for path in (SKIN/'xml').glob('*.xml'):
        root=E.parse(path).getroot()
        for control in root.iter('control'):
            if (control.findtext('texturefocus') or '').startswith('foundry-icons/rows/'):
                height=control.findtext('height') or ''
                if height.isdigit() and 30<=int(height)<=160:heights.add(int(height))
        for include in root.iter('include'):
            if include.get('content') in templates:
                height=include.find("param[@name='height']")
                value=height.get('value','') if height is not None else ''
                if value.isdigit() and 30<=int(value)<=160:heights.add(int(value))
    provenance={}
    def convert(*values):subprocess.run(['convert',*map(str,values)],check=True)
    for name in ICON_NAMES:
        source=Path(icons[name]['path']);target=destination/(name+'.png')
        convert(source,'-trim','+repage','-resize','220x220','-gravity','center','-background','none','-extent','256x256','-strip',target)
        small=destination/('.'+name+'-small.png')
        convert(target,'-resize','32x32','-strip',small)
        for height in sorted(heights):
            suffix='' if height==70 else '-'+str(height)
            for state in ['normal','focus']:
                output=destination/'rows'/(name+suffix+'-'+state+'.png')
                values=['-size','320x'+str(height),'xc:none']
                if state=='focus':values+=['-fill','#122B42E6','-stroke','#66CCFF80','-strokewidth','1','-draw','roundrectangle 0,0 319,%d 10,10'%(height-1)]
                convert(*values,small,'-geometry','+20+'+str((height-32)//2),'-composite','-strip',output)
        small.unlink()
        provenance[name]={k:v for k,v in icons[name].items() if k!='path'}
        provenance[name].update(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    for path in destination.rglob('*.svg'):path.unlink()
    (destination/'CATALOG.json').write_text(json.dumps({'style':'Foundry wallpaper chrome and original category neon colors','format':'full-color transparent PNG','size':[256,256],'icons':list(ICON_NAMES),'provenance':provenance},indent=2)+'\n')
    for path in (SKIN/'xml').glob('*.xml'):
        text=path.read_text()
        if 'foundry-icons/' not in text:continue
        root=E.fromstring(text)
        for node in root.iter():
            if node.text and node.text.startswith('foundry-icons/'):
                node.text=node.text.replace('.svg','.png');node.attrib.pop('colordiffuse',None)
        for control in root.iter('control'):
            if (control.findtext('texturefocus') or '').startswith('foundry-icons/rows/'):
                height=control.findtext('height') or ''
                if height.isdigit() and int(height)!=70:
                    for tag in ['texturefocus','texturenofocus']:
                        texture=control.find(tag)
                        if texture is not None and texture.text:
                            texture.text=re.sub(r'(?:-\d+)?-(focus|normal)\.png$',r'-'+height+r'-\1.png',texture.text)
                field=control.find('focusedcolor')
                if field is None:field=E.SubElement(control,'focusedcolor')
                field.text='FFFFFFFF'
        for include in root.iter('include'):
            if include.get('name') in templates:
                if include.find("param[@name='system_icon_height']") is None:E.SubElement(include,'param',name='system_icon_height').text=''
                definition=include.find('definition')
                if definition is not None:
                    field=definition.find('focusedcolor')
                    if field is None:field=E.SubElement(definition,'focusedcolor')
                    field.text='FFFFFFFF'
                for texture in include.iter():
                    if texture.tag in ['texturefocus','texturenofocus'] and texture.text and '$PARAM[system_icon]' in texture.text and '$PARAM[system_icon_height]' not in texture.text:
                        texture.text=texture.text.replace('$PARAM[system_icon]','$PARAM[system_icon]$PARAM[system_icon_height]')
            if include.get('content') in templates:
                height=include.find("param[@name='height']")
                value=height.get('value','') if height is not None else ''
                if value.isdigit() and int(value)!=70:
                    param=include.find("param[@name='system_icon_height']")
                    if param is None:param=E.SubElement(include,'param',name='system_icon_height')
                    param.set('value','-'+value)
        E.indent(root,space='  ');path.write_bytes(E.tostring(root,encoding='UTF-8',xml_declaration=True)+b'\n')
    # Keep every chrome/neon bitmap in its original colors in the settings and
    # power-menu layouts. A diffuse tint would recolor the approved artwork.
    for filename,include_name in [('Includes.xml','SettingsPanel'),('Includes_Buttons.xml','ButtonMenuList')]:
        path=SKIN/'xml'/filename;root=E.parse(path).getroot();include=root.find("include[@name='%s']"%include_name)
        for texture in include.iter('texture'):
            if texture.text=='$INFO[ListItem.Icon]':texture.attrib.pop('colordiffuse',None)
        E.indent(root,space='  ');path.write_bytes(E.tostring(root,encoding='UTF-8',xml_declaration=True)+b'\n')
    print('Packaged %d wallpaper-matched icons and %d menu row textures'%(len(ICON_NAMES),2*len(ICON_NAMES)*len(heights)))


if __name__=='__main__':main()

