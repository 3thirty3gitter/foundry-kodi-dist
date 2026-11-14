# -*- coding: utf-8 -*-
"""Discover Kodi video sources; keep supported native search routes compatible."""
import json
import re
import xbmc
import xbmcgui
from modules.repo_installer import show_repos

PROVIDERS = [
    {"slot": "0", "id": "plugin.video.fen", "label": "FEN"},
    {"slot": "1", "id": "plugin.video.fenlight", "label": "FEN Light"},
    {"slot": "2", "id": "plugin.video.umbrella", "label": "Umbrella"},
    {"slot": "3", "id": "plugin.video.pov", "label": "POV"},
    {"slot": "4", "id": "plugin.video.seren", "label": "Seren"},
]
_ID = re.compile(r'^[A-Za-z0-9_.-]+$')


def _is_installed(addon_id):
    return bool(xbmc.getCondVisibility(
        'System.HasAddon(%s) + System.AddonIsEnabled(%s)' % (addon_id, addon_id)))


def installed_video_providers():
    # Ask Kodi for its video-source inventory, not a plugin.video.* naming guess.
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.GetAddons',
               'params': {'type': 'xbmc.addon.video', 'enabled': 'all',
                          'installed': True, 'properties': ['name', 'enabled']}}
    data = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if 'error' in data:
        raise RuntimeError('Kodi add-on inventory unavailable')
    supported = {p['id']: p for p in PROVIDERS}
    result = {}
    for addon in data.get('result', {}).get('addons', []):
        addon_id = addon.get('addonid', '')
        if not _ID.fullmatch(addon_id):
            continue
        known = supported.get(addon_id)
        result[addon_id] = {'id': addon_id,
            'slot': known['slot'] if known else addon_id,
            'label': str(addon.get('name') or addon_id),
            'enabled': addon.get('enabled') is True,
            'native': known is not None}
    return sorted(result.values(), key=lambda p: (p['label'].casefold(), p['id']))


def _set_string(key, value):
    # Quote commas and parentheses in add-on display names, never execute them.
    value = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
    xbmc.executebuiltin('Skin.SetString(%s,"%s")' % (key, value))


def choose_search_provider():
    try:
        installed = installed_video_providers()
    except (ValueError, TypeError, RuntimeError):
        xbmcgui.Dialog().ok('Foundry Search', 'Unable to read installed video add-ons. Please try again.')
        return
    if not installed:
        if xbmcgui.Dialog().yesno('Foundry Search',
                'No video add-ons installed.[CR][CR]Open the repository installer?',
                nolabel='Not now', yeslabel='Install add-ons'):
            show_repos()
        return
    current = xbmc.getInfoLabel('Skin.String(current_search_provider)')
    labels = [p['label'] + (' (disabled)' if not p['enabled'] else
              ' - integrated search' if p['native'] else ' - open add-on (no integrated search)')
              for p in installed]
    preselect = next((i for i, p in enumerate(installed) if p['slot'] == current), -1)
    idx = xbmcgui.Dialog().select('Choose video search provider', labels, preselect=preselect)
    if idx is None or not 0 <= idx < len(installed):
        return
    selected = installed[idx]
    # Recheck after modal: add-on may have been disabled/uninstalled meanwhile.
    if not selected['enabled'] or not _is_installed(selected['id']):
        xbmcgui.Dialog().ok('Foundry Search', 'This add-on is disabled or no longer installed. Enable it in My add-ons, then try again.')
        return
    if not selected['native'] and not xbmcgui.Dialog().yesno('Foundry Search',
            'This video add-on has no integrated Foundry search route. The Search button will open the add-on, where you can use its own search if available.',
            nolabel='Cancel', yeslabel='Use add-on'):
        return
    _set_string('foundry.search.provider.id', selected['id'])
    _set_string('foundry.search.provider.label', selected['label'])
    _set_string('current_search_provider', selected['slot'])


def open_selected_video_provider():
    addon_id = xbmc.getInfoLabel('Skin.String(current_search_provider)')
    if addon_id in {p['slot'] for p in PROVIDERS}:
        return
    if not _ID.fullmatch(addon_id or '') or not _is_installed(addon_id):
        xbmcgui.Dialog().ok('Foundry Search', 'Selected video add-on is unavailable. Choose another search provider in Skin settings.')
        return
    # No universal add-on search API exists. Never fabricate a query endpoint.
    xbmc.executebuiltin('ActivateWindow(Videos,"plugin://%s/",return)' % addon_id)


def use_external_video_provider():
    """True when the selected source uses its own UI, not native result widgets."""
    value = xbmc.getInfoLabel('Skin.String(current_search_provider)')
    if not value or value in {p['slot'] for p in PROVIDERS}:
        return False
    open_selected_video_provider()
    return True
