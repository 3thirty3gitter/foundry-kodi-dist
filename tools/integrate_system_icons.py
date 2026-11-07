"""Apply menu icons to static entries and Kodi's generated control templates."""
import json
from pathlib import Path
import xml.etree.ElementTree as E
from build_system_icons import SKIN, PATHS, choose

XML = SKIN / 'xml'
TEMPLATES = {'DefaultSettingButton','DefaultAddonSettingsButton','DefaultSystemSettingsButton','DialogSettingButton'}


def settext(node, name, value, **attributes):
    child = node.find(name)
    if child is None: child = E.SubElement(node, name)
    child.text = value
    child.attrib.update(attributes)
    return child


def row(control, icon):
    settext(control,'textoffsetx','84')
    settext(control,'texturefocus','foundry-icons/rows/'+icon+'-focus.png',border='72,0,8,0',colordiffuse='FFFFFFFF')
    settext(control,'texturenofocus','foundry-icons/rows/'+icon+'-normal.png',border='72,0,8,0',colordiffuse='FFFFFFFF')


def write(path, root):
    E.indent(root, space='  ')
    path.write_bytes(E.tostring(root,encoding='UTF-8',xml_declaration=True)+b'\n')


def main():
    coverage=[]
    for path in XML.glob('*.xml'):
        system = (path.stem.startswith('Settings') or path.stem in {'SkinSettings','Custom_1101_SettingsList','DialogAddonSettings','DialogSettings','DialogButtonMenu','DialogContextMenu','AddonBrowser'})
        if not system: continue
        root=E.parse(path).getroot();changed=False
        for item in root.iter('item'):
            content=' '.join(n.text or '' for n in item.iter() if n.tag in ('label','onclick','icon'))
            old=item.findtext('icon') or ''
            key=Path(old).stem
            aliases={'filemanager':'folder','sysinfo':'info','livetv':'tv','libreelec':'system'}
            icon=aliases.get(key,key) if aliases.get(key,key) in PATHS else choose(content)
            settext(item,'icon','foundry-icons/'+icon+'.png');changed=True
            coverage.append({'window':path.name,'label':item.findtext('label'),'icon':icon,'kind':'menu item'})
        for control in root.iter('control'):
            kind=control.get('type')
            if kind not in {'button','radiobutton','spincontrolex','sliderex','edit','colorbutton'}:continue
            description=' '.join(n.text or '' for n in control if n.tag in ('label','description','onclick','selected'))
            icon=choose(description,kind)
            includes=[n for n in control.findall('include') if (n.get('content') or (n.text or '').strip()) in TEMPLATES]
            for include in includes:
                name=include.get('content') or include.text.strip();include.text=None;include.set('content',name)
                param=next((n for n in include.findall('param') if n.get('name')=='system_icon'),None)
                if param is None:param=E.SubElement(include,'param',name='system_icon')
                param.set('value',icon)
                # Explicit small label offsets from older callers also reserve
                # the icon slot. Slider values and toggle hit areas stay native.
                for param in include.findall('param'):
                    if param.get('name')=='textoffsetx' and (param.get('value') or '').isdigit():param.set('value',str(max(84,int(param.get('value')))))
            if includes:changed=True
            elif control.find('label') is not None or control.findtext('description') in {'Default Category Button','button template'} or control.get('id')=='10':
                if control.findtext('texturefocus') is not None:row(control,icon);changed=True
            else:continue
            coverage.append({'window':path.name,'id':control.get('id'),'label':control.findtext('label'),'icon':icon,'kind':kind})
        if changed:write(path,root)

    path=XML/'Includes_Buttons.xml';root=E.parse(path).getroot()
    for include in root.findall('include'):
        if include.get('name') not in TEMPLATES:continue
        if not any(n.get('name')=='system_icon' for n in include.findall('param')):E.SubElement(include,'param',name='system_icon').text='settings'
        for param in include.findall('param'):
            if param.get('name')=='textoffsetx':param.text='84'
        definition=include.find('definition')
        row(definition if definition is not None else include,'$PARAM[system_icon]')
        if definition is not None:settext(definition,'textoffsetx','$PARAM[textoffsetx]')
    menu=root.find("include[@name='ButtonMenuList']")
    for layout in [menu.find('itemlayout'),menu.find('focusedlayout')]:
        if not any(n.findtext('texture')=='$INFO[ListItem.Icon]' for n in layout.findall('control')):
            icon=E.SubElement(layout,'control',type='image')
            for k,v in [('left','20'),('top','21'),('width','28'),('height','28'),('aspectratio','keep')]:settext(icon,k,v)
            settext(icon,'texture','$INFO[ListItem.Icon]',fallback='foundry-icons/settings.png',colordiffuse='FFFFFFFF')
        for label in layout.findall("control[@type='label']"):
            settext(label,'left','64');settext(label,'width','370');settext(label,'textoffsetx','0');settext(label,'align','left')
    write(path,root)
    path=XML/'Includes.xml';root=E.parse(path).getroot()
    panel=root.find("include[@name='SettingsPanel']")
    for image in panel.findall('.//control'):
        texture=image.find('texture')
        if texture is not None and texture.text=='$INFO[ListItem.Icon]':
            texture.set('colordiffuse','FFFFFFFF');settext(image,'aspectratio','keep')
    write(path,root)
    path=XML/'Includes_Buttons.xml';root=E.parse(path).getroot()
    for texture in root.findall("include[@name='ButtonMenuList']//texture"):
        if texture.text=='$INFO[ListItem.Icon]':texture.set('colordiffuse','FFFFFFFF')
    write(path,root)
    (SKIN/'media/foundry-icons/COVERAGE.json').write_text(json.dumps({'static_entries_and_templates':coverage,'generated_settings_rows':'Native category, button, toggle, selector, edit, color and slider templates reserve an inline icon for every generated row.','dynamic_context_rows':'Native context template supplies its action icon; power-menu entries use their own icons.'},indent=2)+'\n')
    print('Integrated icons for %d menu entries and control templates' % len(coverage))


if __name__ == '__main__':main()
