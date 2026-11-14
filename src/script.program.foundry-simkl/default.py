"""Inert until explicitly run; never enable, restart, link, or modify SIMKL settings."""
import json
import xbmc
import xbmcaddon
import xbmcgui

ADDON = 'script.simkl'
NOTICE = ('Linked profiles may resume tracking and upload queued history.\n'
          "Foundry won't sign you in or change settings.\n")
DISABLED_NOTICE = ('SIMKL is disabled and will stay disabled.\n'
                   'Enable via My add-ons > Services. Linked profiles may\n'
                   'resume tracking and upload queued history.\n'
                   "Foundry won't sign you in or change settings.")


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
                dialog.ok('Foundry SIMKL', DISABLED_NOTICE)
                return
            if dialog.yesno('Foundry SIMKL', NOTICE + 'Open SIMKL settings?', nolabel='Cancel', yeslabel='Settings'):
                xbmcaddon.Addon(ADDON).openSettings()
            return
        if dialog.yesno('Foundry SIMKL', NOTICE + 'Install the official SIMKL tracker?', nolabel='Cancel', yeslabel='Install'):
            xbmc.executebuiltin('InstallAddon(script.simkl)')
            # Kodi owns install/dependencies and any confirmation. No forced enable,
            # polling, login action, account read or automatic settings changes.
    except (RuntimeError, ValueError, KeyError):
        dialog.ok('Foundry SIMKL', 'Could not inspect SIMKL safely. No account changes were requested. Please use Kodi My add-ons.')


if __name__ == '__main__':
    main()
