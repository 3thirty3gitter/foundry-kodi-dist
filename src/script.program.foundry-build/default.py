"""Activate the installed Foundry skin; Kodi installs its declared dependencies."""
import json

import xbmc
import xbmcgui

SKIN_ID = "skin.foundry"


def rpc(method, params):
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
    })))
    if "error" in response:
        raise RuntimeError(response["error"].get("message", "Kodi rejected the request"))
    return response.get("result")


def main():
    dialog = xbmcgui.Dialog()
    if xbmc.getSkinDir() == SKIN_ID:
        xbmc.executebuiltin("ReloadSkin()")
        return
    if not dialog.yesno("Foundry", "Use the Foundry skin now?", yeslabel="Use Foundry", nolabel="Cancel"):
        return
    try:
        for addon_id in ("script.foundry.helper", SKIN_ID):
            rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})
        # Open a standard window that exists in both skins before switching.
        xbmc.executebuiltin("ActivateWindow(settings)")
        result = rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": SKIN_ID})
        if result is not True:
            raise RuntimeError("Kodi could not activate Foundry. Select it in Settings > Interface > Skin.")
    except (RuntimeError, ValueError) as error:
        xbmc.log("[Foundry] Skin activation failed: %s" % error, xbmc.LOGERROR)
        dialog.ok("Foundry", str(error))


if __name__ == "__main__":
    main()
