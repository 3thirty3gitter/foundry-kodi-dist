"""Native Kodi actions and cached artwork colors for the StreamPilot OSD."""
import colorsys
import json
from pathlib import Path
from urllib.parse import unquote

import xbmc
import xbmcgui
import xbmcvfs
from PIL import Image


def seek(seconds):
    """Use Kodi's relative-seconds API, independent of user seek-step settings."""
    try:
        offset = int(seconds)
        if offset not in (-30, 30):
            return False
        players = json.loads(xbmc.executeJSONRPC(json.dumps({
            'jsonrpc': '2.0', 'id': 1, 'method': 'Player.GetActivePlayers',
        }))).get('result', [])
        player = next((p for p in players if p.get('type') == 'video'), None)
        if player is None:
            return False
        response = json.loads(xbmc.executeJSONRPC(json.dumps({
            'jsonrpc': '2.0', 'id': 2, 'method': 'Player.Seek',
            'params': {'playerid': player['playerid'], 'value': {'seconds': offset}},
        })))
        return 'result' in response and 'error' not in response
    except (ValueError, TypeError, KeyError, StopIteration):
        return False


def dominant_color(image, fallback=(24, 42, 59)):
    """StreamPilot dominantArtworkColor: identical sample grid and bucket score."""
    image = image.convert('RGBA')
    step_x, step_y = max(1, image.width // 36), max(1, image.height // 24)
    buckets = {}
    for y in range(step_y // 2, image.height, step_y):
        for x in range(step_x // 2, image.width, step_x):
            r, g, b, a = image.getpixel((x, y))
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if a <= 180 or s < .18 or not .16 <= v <= .96:
                continue
            key = ((r >> 5) << 6) | ((g >> 5) << 3) | (b >> 5)
            bucket = buckets.setdefault(key, [0., 0, 0, 0, 0])
            bucket[0] += .35 + s * 1.8 + v * .45
            bucket[1] += r; bucket[2] += g; bucket[3] += b; bucket[4] += 1
    if not buckets:
        return fallback
    winner = max(buckets.values(), key=lambda bucket: bucket[0])
    rgb = tuple(int(winner[i] / winner[4]) for i in (1, 2, 3))
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in rgb))
    return tuple(round(x * 255) for x in colorsys.hsv_to_rgb(h, max(.58, s), max(.78, v)))


def _cached_paths(artwork):
    """Never fetch remote artwork or probe a network share from OSD startup."""
    decoded = unquote((artwork[8:] if artwork.startswith('image://') else artwork)).rstrip('/')
    for value in dict.fromkeys((decoded, artwork)):
        hash_fn = getattr(xbmc, 'getCacheThumbName', None)
        if callable(hash_fn):
            thumb = hash_fn(value)
            for ext in ('.jpg', '.png'):
                yield xbmcvfs.translatePath('special://profile/Thumbnails/' + thumb[0] + '/' + thumb[:-4] + ext)
    local = xbmcvfs.translatePath(decoded)
    if local.startswith('/') and not local.startswith('//'):
        yield local


def prepare_artwork():
    home = xbmcgui.Window(10000)
    artwork = next((xbmc.getInfoLabel(label) for label in (
        'Player.Art(poster)', 'Player.Art(tvshow.poster)', 'Player.Icon'
    ) if xbmc.getInfoLabel(label)), '')
    if home.getProperty('foundry.slate.osd.artwork') == artwork and home.getProperty('foundry.slate.osd.accent'):
        return
    color = (24, 42, 59)
    found = False
    if artwork:
        for path in _cached_paths(artwork):
            try:
                if not Path(path).is_file():
                    continue
                with Image.open(path) as image:
                    # Reject oversized/unexpected images before decoding them.
                    if image.width * image.height > 40_000_000:
                        continue
                    color = dominant_color(image)
                found = True
                break
            except (OSError, ValueError, Image.DecompressionBombError):
                continue
    # RunScript is asynchronous; do not apply results from an item already replaced.
    current = next((xbmc.getInfoLabel(label) for label in (
        'Player.Art(poster)', 'Player.Art(tvshow.poster)', 'Player.Icon'
    ) if xbmc.getInfoLabel(label)), '')
    if current != artwork:
        return
    home.setProperty('foundry.slate.osd.accent', 'FF%02X%02X%02X' % color)
    home.setProperty('foundry.slate.osd.shade', 'FF%02X%02X%02X' % tuple(round(c * .30) for c in color))
    if found:
        home.setProperty('foundry.slate.osd.artwork', artwork)
    else:
        # The thumbnail may finish loading before the next OSD opening; allow retry.
        home.clearProperty('foundry.slate.osd.artwork')
