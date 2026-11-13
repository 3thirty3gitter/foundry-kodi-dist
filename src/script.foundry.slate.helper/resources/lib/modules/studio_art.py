"""Shared studio artwork lookup. Never invent paths or fetch artwork on the UI thread."""
import re
import threading
import time
import unicodedata
import xbmc
import xbmcvfs
from .catalog_model import clean

ART_KEYS = ('studiologo', 'studio.logo', 'tvshow.studiologo', 'tvshow.studio.logo')
PACKS = ('resource.images.studios.white', 'resource.images.studios.coloured')
_index = {}
_lock = threading.Lock()


def artwork(art):
    """Keep explicit source/provider artwork, including parent-series aliases."""
    art = art if isinstance(art, dict) else {}
    return next((clean(art.get(key)) for key in ART_KEYS
                 if isinstance(art.get(key), str) and clean(art.get(key)) not in ('', '0', '0.0')), '')


def normalized(name):
    text = unicodedata.normalize('NFKD', name.casefold().replace('&', 'and'))
    return ''.join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def studio_names(value):
    values = value if isinstance(value, (list, tuple)) else [value]
    result = []
    for value in values:
        if not isinstance(value, str):
            continue
        value = clean(value)
        # Try the complete name first: commas can be part of company names.
        for name in [value] + re.split(r'\s+/\s+|\s*;\s*|\s*,\s*', value):
            if name and name not in result:
                result.append(name)
    return result[:64]


def pack_index(pack):
    now = time.monotonic()
    with _lock:
        cached = _index.get(pack)
        if cached and now - cached[0] < 60:
            return cached[1]
        entries = {}
        try:
            _, files = xbmcvfs.listdir('resource://' + pack + '/')
            for filename in files[:20000]:
                if '/' in filename or '\\' in filename or not filename.lower().endswith('.png'):
                    continue
                key = normalized(filename[:-4])
                # Ambiguous normalizations must not silently select the wrong company.
                entries[key] = filename if key not in entries else None
        except (AttributeError, OSError, RuntimeError, TypeError):
            pass
        _index[pack] = (now, entries)
        return entries


def resolve(item):
    explicit = artwork(item.get('art'))
    if explicit:
        return explicit
    names = studio_names(item.get('studio'))
    if not names:
        return ''
    for pack in PACKS:
        if not xbmc.getCondVisibility('System.HasAddon(' + pack + ')'):
            continue
        root = 'resource://' + pack + '/'
        for name in names:
            # Never interpret metadata as a path (or traverse outside the resource).
            if any(c in name for c in ('/', '\\', ':', '\x00')) or name in ('.', '..'):
                continue
            exact = root + name + '.png'
            try:
                if xbmcvfs.exists(exact):
                    return exact
            except (OSError, RuntimeError):
                pass
            filename = pack_index(pack).get(normalized(name))
            if filename:
                return root + filename
    return ''
