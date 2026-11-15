"""Installed media flag packs. No downloads, enables or executable pack content."""
import json
import os
import re
import time
import struct
from PIL import Image
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

SKIN_ID = "skin.foundry"
PREFIX = "foundry.media"
SETTING = "MediaIconPack"
CATEGORIES = {
    "videocodec": "VideoCodec", "videoresolution": "VideoResolution",
    "videohdr": "HdrType", "aspectratio": "VideoAspect",
    "audiocodec": "AudioCodec", "audiochannel": "AudioChannels",
}
CONTEXTS = {"list": "ListItem.", "container": "Container.ListItem.", "player": "VideoPlayer."}
_ID = re.compile(r"resource\.images\.[a-z0-9_.-]+$")
_ALIAS = re.compile(r"[a-z0-9_.-]+$")

def read_pack(addon_id):
    if not isinstance(addon_id, str) or not _ID.fullmatch(addon_id):
        return None
    try:
        if not xbmc.getCondVisibility("System.AddonIsEnabled(%s)" % addon_id):
            return None
        addon = xbmcaddon.Addon(addon_id)
        root = os.path.realpath(xbmcvfs.translatePath(addon.getAddonInfo("path")))
        with open(os.path.join(root, "resources", "media-pack.json"), encoding="utf-8") as stream:
            data = json.loads(stream.read(65537))
        if not isinstance(data, dict):
            return None
        flags_root = os.path.realpath(os.path.join(root, "resources", "flags"))
        if os.path.commonpath([root, flags_root]) != root:
            return None
        if (type(data.get("schema_version")) is not int or data["schema_version"] != 1
                or data.get("kind") != "foundry-media-flags"
                or data.get("release_status") != "approved"
                or data.get("asset_root") != "flags"
                or not isinstance(data.get("categories"), list)
                or not data["categories"]
                or any(c not in CATEGORIES for c in data["categories"])):
            return None
        return {"id": addon_id, "name": str(data.get("name") or addon.getAddonInfo("name"))[:100],
                "root": flags_root,
                "categories": data["categories"]}
    except (OSError, ValueError, TypeError, RuntimeError):
        return None

def discover():
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc":"2.0", "id":1,
            "method":"Addons.GetAddons", "params":{"type":"kodi.resource.images", "enabled":True}})))
        if not isinstance(response, dict) or not isinstance(response.get("result"), dict):
            return []
        rows = response["result"].get("addons", [])
        if not isinstance(rows, list):
            return []
        packs = [read_pack(row.get("addonid", "")) for row in rows if isinstance(row, dict)]
        return sorted((p for p in packs if p), key=lambda p:(p["name"].casefold(),p["id"]))
    except (ValueError, TypeError, RuntimeError):
        return []

_PNG_CACHE = {}

def valid_png(path):
    """Validate changed files once; bound memory and decompression, never decode per frame."""
    try:
        stat = os.stat(path)
        stamp = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        cached = _PNG_CACHE.get(path)
        if cached and cached[0] == stamp:
            return cached[1]
        valid = False
        if 45 <= stat.st_size <= 16 * 1024 * 1024:
            with open(path, "rb") as stream:
                header = stream.read(24)
            if header[:16] == b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
                width, height = struct.unpack(">II", header[16:24])
                if 0 < width <= 8192 and 0 < height <= 8192 and width * height <= 16777216:
                    with Image.open(path) as image:
                        image.verify()
                    with Image.open(path) as image:
                        image.load()
                    valid = True
        if len(_PNG_CACHE) >= 512:
            _PNG_CACHE.clear()
        _PNG_CACHE[path] = (stamp, valid)
        return valid
    except (OSError, ValueError, SyntaxError, struct.error, Image.DecompressionBombError):
        if "stamp" in locals():
            if len(_PNG_CACHE) >= 512:
                _PNG_CACHE.clear()
            _PNG_CACHE[path] = (stamp, False)
        else:
            _PNG_CACHE.pop(path, None)
        return False

def resolve(pack, category, value):
    if not pack or category not in pack["categories"]:
        return ""
    alias = str(value or "").strip().lower()
    if not alias or not _ALIAS.fullmatch(alias) or ".." in alias:
        return ""
    candidates = [alias]
    if category == "videoresolution" and alias in ("4k", "2160"):
        candidates += ["2160" if alias == "4k" else "4k"]
    if category == "audiocodec" and alias.startswith("pcm_"):
        candidates += ["pcm"]
    for item in candidates:
        path = os.path.realpath(os.path.join(pack["root"], category, item + ".png"))
        try:
            if os.path.commonpath([pack["root"], path]) != pack["root"]:
                continue
            if os.path.isfile(path) and xbmcvfs.exists(path) and valid_png(path):
                return path
        except (OSError, ValueError):
            continue
    return ""

def choose():
    if xbmc.getSkinDir() != SKIN_ID:
        return
    packs = discover()
    current = xbmc.getInfoLabel("Skin.String(%s)" % SETTING)
    ids = [""] + [p["id"] for p in packs]
    labels = ["Built-in icons"] + [p["name"] for p in packs]
    index = xbmcgui.Dialog().select("Media icon pack", labels,
                                   preselect=ids.index(current) if current in ids else 0)
    if index < 0 or index >= len(ids):
        return
    # IDs have a strict safe grammar; names are never interpolated in builtins.
    if ids[index]:
        xbmc.executebuiltin("Skin.SetString(%s,%s)" % (SETTING, ids[index]))
    else:
        xbmc.executebuiltin("Skin.Reset(%s)" % SETTING)
    xbmcgui.Window(10000).setProperty(PREFIX + ".invalidate", "true")

class MediaPackMonitor:
    def __init__(self):
        self.window = xbmcgui.Window(10000)
        self.selected = None
        self.pack = None
        self.next_refresh = 0
        self.values = {}
        self.inputs = {}

    def put(self, key, value):
        key = PREFIX + "." + key
        if self.values.get(key) == value:
            return
        self.values[key] = value
        if value:
            self.window.setProperty(key, value)
        else:
            self.window.clearProperty(key)

    def process(self):
        try:
            self._process()
        except Exception:
            # An optional visual resource must not take down metadata/playback services.
            # Clear the pack guard first; native window teardown itself may also fail.
            try:
                self.window.clearProperty(PREFIX + ".pack")
                self.clear()
            except Exception:
                pass
            self.pack = None
            self.selected = None
            self.next_refresh = 0

    def _process(self):
        if xbmc.getSkinDir() != SKIN_ID:
            self.clear()
            self.selected = None
            return
        selected = xbmc.getInfoLabel("Skin.String(%s)" % SETTING)
        now = time.monotonic()
        if (selected != self.selected or now >= self.next_refresh
                or self.window.getProperty(PREFIX + ".invalidate")):
            self.pack = read_pack(selected)
            self.selected = selected
            self.next_refresh = now + 3
            self.window.clearProperty(PREFIX + ".invalidate")
        if self.pack and not xbmc.getCondVisibility("System.AddonIsEnabled(%s)" % self.pack["id"]):
            self.pack = None
        self.put("name", self.pack["name"] if self.pack else "Built-in icons")
        pack_id = self.pack["id"] if self.pack else ""
        if self.values.get(PREFIX + ".pack") != pack_id:
            self.put("pack", "")
        for context, info in CONTEXTS.items():
            for category, label in CATEGORIES.items():
                key = context + "." + category
                value = xbmc.getInfoLabel(info + label)
                stereo = category == "videoresolution" and context != "player" and xbmc.getCondVisibility(info + "IsStereoscopic")
                path = resolve(self.pack, category, "3d" if stereo else value)
                state = (value, path, stereo)
                if self.inputs.get(key) == state:
                    continue
                self.inputs[key] = state
                # Clear source guards before changing texture, so a newly focused item never inherits a previous flag.
                self.put(key + ".value", "")
                self.put(key + ".path", path)
                self.put(key + ".stereo", "true" if stereo else "false")
                self.put(key + ".value", value if path else "")

        self.put("pack", pack_id)

    def clear(self):
        for key in list(self.values):
            self.window.clearProperty(key)
        self.values.clear()
        self.inputs.clear()
        self.pack = None
