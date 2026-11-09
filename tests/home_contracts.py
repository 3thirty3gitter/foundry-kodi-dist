"""Legacy Home invariants with explicit, separately tested feature migrations."""
import xml.etree.ElementTree as ET

OURS = 'String.IsEqual(Weather.Plugin,weather.foundry.canada)'
GAMES = 'System.HasAddon(plugin.games.foundry)'


def restore_home_feature_additions(root):
    """Undo only the declared Weather/Games additions for old snapshot tests."""
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag == 'include' and child.get('content') == 'FoundryCanadaWeatherWidget':
                parent.remove(child)
                continue
            if child.tag == 'control' and child.get('type') == 'group' and child.findtext('visible') == '!' + OURS:
                includes = child.findall('include')
                if len(child) == 2 and len(includes) == 1 and (includes[0].text == 'WeatherPanel' or includes[0].get('content') == 'WidgetScrollbar'):
                    index = list(parent).index(child)
                    parent.remove(child)
                    parent.insert(index, includes[0])
                    continue
            if child.tag == 'visible' and parent.get('id') == '15001' and child.text == '!' + OURS:
                parent.remove(child)
                continue
            if child.tag == 'onclick' and ((child.get('condition') == OURS and child.text == 'SetFocus(15150)') or
                                         (child.get('condition') == GAMES and child.text == 'ActivateWindow(games,plugin://plugin.games.foundry/,return)')):
                parent.remove(child)
                continue
            if child.tag == 'onclick' and child.text == 'ActivateWindow(Games)' and child.get('condition') == '!' + GAMES:
                del child.attrib['condition']
            if child.get('condition'):
                child.set('condition', child.get('condition').replace(' + !' + OURS, ''))
            if child.tag == 'visible' and child.text:
                child.text = child.text.replace(' + !' + OURS, '')
            if child.tag == 'label' and child.text == '$VAR[FoundryCanadaHomeWeatherVar]':
                child.text = '$VAR[HomeMenuWeatherVar]'
    return root


def normalized(node):
    return node.tag, node.attrib, (node.text or '').strip(), [normalized(child) for child in node]


def without_home_favorites(data):
    root = restore_home_feature_additions(ET.fromstring(data))
    found = 0
    for parent in root.iter():
        for child in list(parent):
            if child.tag == 'control' and child.get('id') == '14000':
                parent.remove(child)
                found += 1
    if found != 1:
        raise AssertionError('Expected one Home Favorites section')
    return normalized(root)
