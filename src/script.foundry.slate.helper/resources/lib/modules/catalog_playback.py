"""Preserve the execution contract of known action-style video providers.

FenSkeleton owns xbmc.Player.play and does not return setResolvedUrl. Asking
Kodi to resolve its action URL leaves an unresolved outer play request that
can report failure after the inner player stops. Never mask an error dialog.
"""
import xbmc
from .catalog_source import rpc

ACTION_PREFIX = 'plugin://plugin.video.fenskeleton/'


def action_provider(item):
    return (isinstance(item, dict) and item.get('filetype') != 'directory'
            and item.get('type') in ('movie', 'episode', 'video')
            and isinstance(item.get('file'), str)
            and item['file'].startswith(ACTION_PREFIX))


def run_action(path):
    # Quote the argument without decoding or rewriting the provider URL.
    # Reject literal control/quote characters; valid provider values are encoded.
    if not path.startswith(ACTION_PREFIX) or any(c in path for c in ('"', '\r', '\n', '\x00')):
        raise ValueError('Invalid action-provider URL')
    xbmc.executebuiltin('RunPlugin("%s")' % path)


def play_item(item):
    if action_provider(item):
        run_action(item['file'])
    else:
        rpc('Player.Open', {'item': {'file': item.get('file', '')}})


def play_info_action():
    # Capture the native video-info item before closing its dialog.
    if not xbmc.getCondVisibility('Window.IsActive(videoinfo)'):
        return False
    item = {'file': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'type': xbmc.getInfoLabel('ListItem.DBTYPE').lower()}
    if not action_provider(item):
        return False
    path = item['file']
    if any(c in path for c in ('"', '\r', '\n', '\x00')):
        return False
    xbmc.executebuiltin('Dialog.Close(videoinfo)')
    run_action(path)
    return True
