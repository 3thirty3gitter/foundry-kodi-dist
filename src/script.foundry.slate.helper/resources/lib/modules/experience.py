"""Apply the selected Foundry sound default once without resetting user audio settings."""
import json
import xbmc

SOUND_ADDON = "resource.uisounds.foundry.pulse"
MIGRATION = "foundry.slate.sounds.pulse.v1"
LEGACY_MIGRATION = "foundry.slate.sounds.default.v1"


def _rpc(method, params):
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
        })))
        return response.get("result") if isinstance(response, dict) else None
    except (ValueError, TypeError, RuntimeError):
        return None


def _complete():
    xbmc.executebuiltin("Skin.SetBool(" + MIGRATION + ")")


def configure_experience():
    """Optional Slate skin never changes global Kodi configuration."""
    return False
