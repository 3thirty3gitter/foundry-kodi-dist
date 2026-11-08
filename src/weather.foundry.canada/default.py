"""Foundry Canada weather prototype for Kodi 21/Omega."""
import os
import json
import sys
import uuid
from datetime import datetime, timezone
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from resources.lib.client import Client, COLLECTION, CATALOGUE, WeatherError
from resources.lib.model import locations, normalize, valid_id, validate_catalogue, validate_feature
from resources.lib.kodi_bridge import PREFIX, build_properties, clear_properties, publish

ADDON = xbmcaddon.Addon()
WINDOW = xbmcgui.Window(12600)


def is_active_provider():
    """Never overwrite native weather state after the user changes providers."""
    return xbmc.getInfoLabel('Weather.Plugin') == 'weather.foundry.canada'


def current_slot():
    """Share Kodi's authoritative location with its native/periodic jobs.

    Omega Weather.Refresh/LocationNext depend on an initialized native weather
    window. Its integer setting is accessible through the supported JSON-RPC
    Settings API even when the user has only opened the Home card.
    """
    try:
        reply = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1,
            'method': 'Settings.GetSettingValue', 'params': {'setting': 'weather.currentlocation'}})))
        value = reply.get('result', {}).get('value')
        return value if type(value) is int and value > 0 else None
    except (ValueError, TypeError, AttributeError):
        return None


def refresh_current(next_location=False):
    """Explicit Home actions never change the selected weather provider."""
    if not is_active_provider():
        return
    selected = configured_locations()
    if not selected:
        update(1)
        return
    previous = current_slot()
    if previous is None:
        xbmc.log('Foundry Canada Weather: current location could not be read.', xbmc.LOGWARNING)
        return
    slot = (previous % len(selected) + 1) if next_location else min(previous, len(selected))
    if slot != previous:
        if not is_active_provider():
            return
        try:
            reply = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1,
                'method': 'Settings.SetSettingValue',
                'params': {'setting': 'weather.currentlocation', 'value': slot}})))
            if reply.get('result') is not True or current_slot() != slot:
                return
        except (ValueError, TypeError, AttributeError):
            return
    update(slot)


def language():
    configured = ADDON.getSetting('language')
    return 'fr' if configured == 'fr' or (configured == 'auto' and xbmc.getLanguage(xbmc.ISO_639_1) == 'fr') else 'en'


def client():
    return Client(os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo('profile')), 'cache'))


def configured_locations():
    result = []
    for slot in range(1,4):
        identifier = ADDON.getSetting('location'+str(slot)+'_id')
        label = ADDON.getSetting('location'+str(slot)+'_label')
        if valid_id(identifier):
            result.append((identifier,label))
    return result


def refresh_locations():
    selected = configured_locations()
    WINDOW.setProperty('Locations',str(len(selected)))
    for slot in range(1,4):
        WINDOW.setProperty('Location'+str(slot), selected[slot-1][1] if slot <= len(selected) else '')
    return selected


def choose_location(slot):
    if slot not in (1,2,3):
        return
    lang = language()
    query = xbmcgui.Dialog().input('Ville canadienne' if lang=='fr' else 'Canadian city')
    if not query.strip():
        return
    try:
        data, _, _, _ = client().get(CATALOGUE,validate_catalogue,ttl=604800,max_stale=2592000)
        choices = locations(data,lang,query)
        if not choices:
            xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'),'Aucune ville correspondante.' if lang=='fr' else 'No matching forecast location. Try a nearby city.')
            return
        selected = xbmcgui.Dialog().select('Choisir une ville' if lang=='fr' else 'Choose a forecast location',[x['label'] for x in choices])
        if selected < 0:
            return
        item=choices[selected]
        WINDOW.setProperty(PREFIX+'RequestToken',uuid.uuid4().hex)
        # Keep slots contiguous even if a user chooses the second slot first.
        slot=min(slot,len(configured_locations())+1)
        ADDON.setSetting('location'+str(slot)+'_id',item['id'])
        ADDON.setSetting('location'+str(slot)+'_label',item['label'])
        if is_active_provider():
            refresh_locations()
            refresh_current()
    except WeatherError:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'),'Le catalogue est indisponible.' if lang=='fr' else 'The location catalogue is unavailable. Please try again later.')


def show_alerts():
    lang=language()
    heading='Avis météo' if lang=='fr' else 'Weather advisories'
    count=int(WINDOW.getProperty(PREFIX+'AlertCount') or 0)
    parts=[WINDOW.getProperty(PREFIX+'Location')]
    for i in range(1,min(count,20)+1):
        key=PREFIX+'Alert.'+str(i)+'.'
        issue_label='Émis (UTC) : ' if lang=='fr' else 'Issued (UTC): '
        expiry_label='Expiration (UTC) : ' if lang=='fr' else 'Expires (UTC): '
        parts.append(WINDOW.getProperty(key+'Headline')+'\n'+issue_label+WINDOW.getProperty(key+'Issued')+'\n'+expiry_label+WINDOW.getProperty(key+'Expires')+'\n'+WINDOW.getProperty(key+'Url'))
    caution='Titres seulement. Consultez le bulletin officiel complet. Ne remplace pas les alertes d’urgence.' if lang=='fr' else 'Headlines only. Consult the complete official bulletin. This is not an emergency-alert service.'
    if WINDOW.getProperty(PREFIX+'AlertStatus')=='unverified':
        caution=('Données en cache, état non vérifié. ' if lang=='fr' else 'Cached data; current alert status is unverified. ')+caution
    elif WINDOW.getProperty(PREFIX+'AlertStatus') not in ('reported',):
        caution=('État actuel des avis indisponible. ' if lang=='fr' else 'Current advisory status is unavailable. ')+caution
    xbmcgui.Dialog().textviewer(heading,'\n\n'.join(parts+[caution]))


def show_forecast():
    lang=language()
    parts=[WINDOW.getProperty(PREFIX+'Location')]
    if WINDOW.getProperty(PREFIX+'Stale')=='true':
        parts.append('Données en cache ou retardées.' if lang=='fr' else 'Cached or delayed weather data.')
    for i in range(1,8):
        key=PREFIX+'Day.'+str(i)+'.'
        title=WINDOW.getProperty(key+'Title')
        if title:
            parts.append(title+'  '+WINDOW.getProperty(key+'Range')+'\n'+WINDOW.getProperty(key+'Summary'))
    if len(parts)==1:
        parts.append('Prévisions indisponibles.' if lang=='fr' else 'Forecast unavailable.')
    parts.append(WINDOW.getProperty(PREFIX+'Attribution'))
    xbmcgui.Dialog().textviewer('Prévisions météo' if lang=='fr' else 'Weather forecast','\n\n'.join(parts))


def update(slot):
    if not is_active_provider():
        return
    selected=refresh_locations()
    if not selected:
        # Clearing locations must supersede an older in-flight request too.
        WINDOW.setProperty(PREFIX+'RequestToken',uuid.uuid4().hex)
        clear_properties(WINDOW)
        WINDOW.setProperty(PREFIX+'Status','needs_location')
        WINDOW.setProperty(PREFIX+'HasCurrent','false')
        return
    slot=min(max(slot,1),len(selected))
    authoritative_slot = current_slot()
    if authoritative_slot is None or min(authoritative_slot, len(selected)) != slot:
        return
    token=uuid.uuid4().hex
    WINDOW.setProperty(PREFIX+'RequestToken',token)
    identifier,_=selected[slot-1]
    def request_is_current():
        if not is_active_provider() or current_slot()!=authoritative_slot or WINDOW.getProperty(PREFIX+'RequestToken')!=token:
            return False
        current = configured_locations()
        return slot <= len(current) and current[slot-1][0] == identifier
    try:
        payload,fetched,stale,reason=client().get(COLLECTION+'/items/'+identifier+'?f=json',lambda data:validate_feature(data,identifier))
        model=normalize(payload,language(),datetime.now(timezone.utc))
        properties=build_properties(model,fetched,stale,reason,xbmc.getRegion('tempunit'),xbmc.getRegion('time'))
        if request_is_current():
            publish(WINDOW,properties)
    except (WeatherError,ValueError,TypeError,AttributeError):
        if not request_is_current():
            return
        clear_properties(WINDOW)
        WINDOW.setProperty(PREFIX+'Status','unavailable')
        WINDOW.setProperty(PREFIX+'HasCurrent','false')
        WINDOW.setProperty(PREFIX+'AlertStatus','unknown')
        xbmc.log('Foundry Canada Weather: refresh unavailable; no location or response data logged.',xbmc.LOGWARNING)


if __name__=='__main__':
    argument=sys.argv[1] if len(sys.argv)>1 else '1'
    if argument=='alerts':
        show_alerts()
    elif argument=='forecast':
        show_forecast()
    elif argument=='refresh':
        refresh_current()
    elif argument=='next':
        refresh_current(next_location=True)
    elif argument.startswith('choose:'):
        try:choose_location(int(argument.split(':',1)[1]))
        except ValueError:pass
    else:
        try:update(int(argument))
        except ValueError:update(1)
