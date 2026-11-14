"""Inert until explicitly run; never enable, restart, link, or modify SIMKL settings."""
import json
import xbmc
import xbmcaddon
import xbmcgui

ADDON = 'script.simkl'
NOTICE = ('SIMKL can send watched activity and ratings to your account. Installing '
          'or enabling its service may resume tracking and queued history on an '
          'already-linked profile. New accounts link through the official PIN flow. '
          'Foundry will not sign you in or change your tracking settings.')


def details():
    result = json.loads(xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': 'Addons.GetAddonDetails',
        'params': {'addonid': ADDON, 'properties': ['enabled', 'version']}})))
    if 'error' in result:
        if result['error'].get('code') == -32602:
            return None
        raise RuntimeError('Kodi could not inspect SIMKL. No changes made.')
    return result['result']['addon']


def main():
    dialog = xbmcgui.Dialog()
    try:
        installed = details()
        if installed is not None:
            if not installed.get('enabled'):
                dialog.ok('Foundry SIMKL', 'SIMKL is installed but disabled. Foundry will leave it disabled. ' + NOTICE + ' Enable it yourself in My add-ons > Services if desired.')
                return
            if dialog.yesno('Foundry SIMKL', NOTICE + ' Open its settings?', nolabel='Cancel', yeslabel='Settings'):
                xbmcaddon.Addon(ADDON).openSettings()
            return
        if dialog.yesno('Foundry SIMKL', NOTICE + ' Ask Kodi to install the official SIMKL tracker?', nolabel='Cancel', yeslabel='Install'):
            xbmc.executebuiltin('InstallAddon(script.simkl)')
            # Kodi owns install/dependencies and any confirmation. No forced enable,
            # polling, login action, account read or automatic settings changes.
    except (RuntimeError, ValueError, KeyError):
        dialog.ok('Foundry SIMKL', 'Could not inspect SIMKL safely. No account changes were requested. Please use Kodi My add-ons.')


if __name__ == '__main__':
    main()
