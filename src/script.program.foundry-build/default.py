"""Prepare SlyGuy's repository, install trailers, then activate Foundry."""
import importlib.util
import json
import os
import zipfile

import xbmc
import xbmcaddon
import xbmcgui

SKIN_ID = "skin.foundry"
SLYGUY_REPO = "repository.slyguy"
TRAILERS_ID = "slyguy.trailers"


def rpc(method, params):
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
    })))
    if "error" in response:
        raise RuntimeError(response["error"].get("message", "Kodi rejected the request"))
    return response.get("result")


def addon_details(addon_id):
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddonDetails",
        "params": {"addonid": addon_id, "properties": ["enabled", "version"]},
    })))
    error = response.get("error")
    if error:
        # Kodi returns InvalidParams for an add-on that is not installed.
        if error.get("code") == -32602:
            return None
        raise RuntimeError(error.get("message", "Kodi could not inspect " + addon_id))
    return response.get("result", {}).get("addon")


def enable(addon_id):
    if rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True}) != "OK":
        raise RuntimeError("Kodi could not enable " + addon_id)


def version(value):
    return tuple(int(part) for part in value.split("."))


def ensure_trailers():
    """Kodi refuses repository add-ons as dependency installs. Prepare it first.

    Use the original repository ZIP already shipped with Foundry and the helper's
    validated extraction/registration code. Kodi still installs all SlyGuy code.
    """
    repo = addon_details(SLYGUY_REPO)
    if not repo or version(repo["version"]) < (0, 0, 9):
        helper = xbmcaddon.Addon("script.foundry.helper").getAddonInfo("path")
        spec = importlib.util.spec_from_file_location(
            "_foundry_repo_setup", os.path.join(helper, "resources", "lib", "modules", "repo_installer.py"))
        tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tools)
        skin = xbmcaddon.Addon(SKIN_ID).getAddonInfo("path")
        tools._extract_to_addons(os.path.join(skin, "extras", "repos", SLYGUY_REPO + ".zip"), SLYGUY_REPO)
        if tools._register_repos([SLYGUY_REPO]):
            raise RuntimeError("SlyGuy Repository could not be registered. Run Foundry Build again to retry.")
    elif not repo["enabled"]:
        enable(SLYGUY_REPO)

    trailers = addon_details(TRAILERS_ID)
    if not trailers:
        # InstallAddon is modal; wait for Kodi's installer before checking its result.
        xbmc.executebuiltin("InstallAddon(" + TRAILERS_ID + ")", True)
        trailers = addon_details(TRAILERS_ID)
    if not trailers:
        raise RuntimeError("SlyGuy Trailers was not installed. Run Foundry Build again to retry.")
    if version(trailers["version"]) < (0, 2, 2):
        raise RuntimeError("Update SlyGuy Trailers from Install from repository, then run Foundry Build again.")
    if not trailers["enabled"]:
        enable(TRAILERS_ID)


def main():
    dialog = xbmcgui.Dialog()
    try:
        helper = xbmcaddon.Addon("script.foundry.helper").getAddonInfo("path")
        spec = importlib.util.spec_from_file_location(
            "_foundry_startup_splash", os.path.join(helper, "resources", "lib", "modules", "startup_splash.py"))
        startup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(startup)
        startup.install_startup_splash()
        ensure_trailers()
        if xbmc.getSkinDir() == SKIN_ID:
            xbmc.executebuiltin("ReloadSkin()")
            return
        if not dialog.yesno("Foundry", "Use the Foundry skin now?", yeslabel="Use Foundry", nolabel="Cancel"):
            return
        for addon_id in ("script.foundry.helper", SKIN_ID):
            enable(addon_id)
        # Open a standard window that exists in both skins before switching.
        xbmc.executebuiltin("ActivateWindow(settings)")
        result = rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": SKIN_ID})
        if result is not True:
            raise RuntimeError("Kodi could not activate Foundry. Select it in Settings > Interface > Skin.")
    except (RuntimeError, ValueError, OSError, zipfile.BadZipFile, ImportError) as error:
        xbmc.log("[Foundry] Setup failed: %s" % error, xbmc.LOGERROR)
        dialog.ok("Foundry", str(error))


if __name__ == "__main__":
    main()

