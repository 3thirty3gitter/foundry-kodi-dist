"""Kodi 21 Omega directory UI and native RetroPlayer launch bridge."""
import json
import os
import time
from uuid import uuid4
from urllib.parse import parse_qs, urlencode, urlsplit

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from library import Library, SYSTEMS, Cancelled, LocalIO, SourceUnavailable
import staging

ID = 'plugin.games.foundry'
BASE = 'plugin://' + ID + '/'


def url(**values):
    return BASE + '?' + urlencode(values)


class VFS:
    # Some providers silently return an empty listing on access failure. Never
    # hide previous records from a VFS scan; explicit source removal is available.
    authoritative = False
    def exists(self, path):
        return xbmcvfs.exists(path)

    def listdir(self, path):
        if not self.exists(path):
            raise OSError('Source is unavailable; previous library retained')
        return xbmcvfs.listdir(path)

    def open(self, path, mode='rb'):
        # Kodi File.readBytes is necessary: read() is a text API.
        class Stream:
            def __init__(self, filename):
                self.file = xbmcvfs.File(filename)
            def read(self, size):
                return bytes(self.file.readBytes(size))
            def close(self):
                self.file.close()
        return Stream(path)

    def read(self, path, limit):
        stream = self.open(path)
        try:
            return stream.read(limit + 1)
        finally:
            stream.close()


def game_item(game):
    info = json.loads(game['metadata'])
    item = xbmcgui.ListItem(label=game['title'], path=game['path'])
    tag = item.getGameInfoTag()
    tag.setTitle(game['title'])
    tag.setPlatform(SYSTEMS[game['system']][0])
    for key, setter in (('overview', tag.setOverview), ('publisher', tag.setPublisher), ('developer', tag.setDeveloper)):
        if info.get(key): setter(info[key])
    if info.get('genre'): tag.setGenres([info['genre']])
    try:
        if info.get('year'): tag.setYear(int(info['year']))
    except (ValueError, TypeError):
        pass
    item.setArt(info.get('art', {}))
    item.setProperty('Foundry.Game.Id', game['id'])
    item.setProperty('Foundry.Game.System', game['system'])
    item.setProperty('Foundry.Game.Platform', SYSTEMS[game['system']][0])
    item.setProperty('Foundry.Game.Overview', info.get('overview', 'Local game. Kodi manages controllers and saves.'))
    item.setProperty('Foundry.Game.MetadataStatus', 'local')
    # Deliberately no setGameClient: Omega's chooser owns core + savestate resume.
    return item


def launch(db, game, profile):
    if game['system'] == 'psp':
        xbmcgui.Dialog().ok('Foundry Games', 'PSP has no verified native Kodi Omega ARM64 emulator. External emulator integration is not implemented.')
        return
    progress = xbmcgui.DialogProgress()
    progress.create('Foundry Games', 'Preparing game and disc dependencies…')
    monitor = xbmc.Monitor()
    try:
        source_path = xbmcvfs.translatePath(game['path']) if game['path'].startswith('special://') else game['path']
        path = staging.prepare(source_path, game['system'], os.path.join(profile, 'rom-cache'), io=VFS(), cancelled=lambda: progress.iscanceled() or monitor.abortRequested())
    finally:
        progress.close()
    item = game_item(game)
    item.setPath(path)
    class Player(xbmc.Player):
        started = False
        ended = False
        def onPlayBackStarted(self): self.started = True
        def onPlayBackStopped(self): self.ended = True
        def onPlayBackEnded(self): self.ended = True
        def onPlayBackError(self): self.ended = True
    player = Player()
    player.play(path, item)
    # A chooser cancellation is not a recent launch. Keep the Python callback
    # alive during actual gameplay, allowing Kodi's native Back/OSD return path.
    deadline = time.monotonic() + 60
    while not player.started and not player.ended and time.monotonic() < deadline:
        if monitor.waitForAbort(0.2): return
    if not player.started: return
    start = time.monotonic()
    db.played(game['id'])
    while not player.ended and player.isPlaying():
        if monitor.waitForAbort(0.5): break
    db.played(game['id'], time.monotonic() - start)


def run(argv):
    handle = int(argv[1])
    params = {k: v[-1] for k, v in parse_qs(argv[2].lstrip('?')).items()}
    addon = xbmcaddon.Addon(ID)
    profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    os.makedirs(profile, exist_ok=True)
    db = Library(os.path.join(profile, 'library-v1.db'))
    dialog = xbmcgui.Dialog()
    action = params.get('action', 'home')
    def folder(label, **values):
        xbmcplugin.addDirectoryItem(handle, url(**values), xbmcgui.ListItem(label=label), True)
    def done():
        # This property belongs to Kodi's completed list, rather than the DB
        # transaction or invoker. Consumers can wait for fresh native contents.
        xbmcplugin.setProperty(handle, 'Foundry.Games.DirectoryId', uuid4().hex)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
    try:
        if action == 'home':
            folder('Search games', action='search')
            folder('Favorites', action='games', mode='favorites')
            folder('Recently played', action='games', mode='recent')
            folder('Manage sources', action='sources')
            for key, value in SYSTEMS.items(): folder(value[0], action='games', system=key)
            done()
        elif action in ('games', 'search'):
            query = params.get('query', '')
            if action == 'search':
                keyboard = xbmc.Keyboard('', 'Search title or system')
                keyboard.doModal()
                if not keyboard.isConfirmed():
                    # Failed directory resolution retains the previous native
                    # listing and focus instead of replacing it with an empty page.
                    xbmcplugin.endOfDirectory(handle, succeeded=False)
                    return
                query = keyboard.getText()
            page = max(0, int(params.get('page', '0')))
            games = db.games(params.get('system', ''), query, params.get('mode', ''), page)
            xbmcplugin.setContent(handle, 'games')
            for game in games[:20]:
                item = game_item(game)
                item.addContextMenuItems([
                    ('Remove favorite' if game['favorite'] else 'Add favorite', 'RunPlugin(%s)' % url(action='favorite', id=game['id'])),
                    ('Game details', 'RunPlugin(%s)' % url(action='details', id=game['id']))])
                xbmcplugin.addDirectoryItem(handle, url(action='play', id=game['id']), item, False)
            if len(games) > 20:
                folder('Next page', action='games', system=params.get('system', ''), query=query, mode=params.get('mode', ''), page=page+1)
            if not games: folder('No games here. Add or rescan a source.', action='sources')
            done()
            visible_path = xbmc.getInfoLabel('Container.FolderPath')
            visible_params = {key: values[-1] for key, values in parse_qs(urlsplit(visible_path).query).items()}
            if (xbmc.getSkinDir() == 'skin.foundry' and
                    xbmc.getCondVisibility('Window.IsActive(games)') and
                    visible_path.startswith(BASE) and visible_params == params):
                # Home/widgets may resolve this same route in the background.
                # Only the owning, currently displayed Games directory may
                # change its native view; never mutate Home or another listing.
                xbmc.executebuiltin('Container.SetViewMode(58)')
        elif action == 'sources':
            folder('Add local / configured VFS folder', action='add')
            folder('Add selected game file', action='add', file='1')
            for source in db.sources():
                folder(source['label'] + ' · ' + SYSTEMS[source['system']][0], action='source', id=source['id'])
            folder('Compatibility and connections', action='help')
            done()
        elif action == 'add':
            keys = list(SYSTEMS)
            choice = dialog.select('Choose the source console (required)', [SYSTEMS[key][0] for key in keys])
            if choice < 0: done(); return
            selected_file = params.get('file') == '1'
            path = dialog.browse(1 if selected_file else 0, 'Choose your game file' if selected_file else 'Choose your ROM folder', 'files', '', False, False)
            if path:
                if path.startswith('special://'): path = xbmcvfs.translatePath(path)
                sid = db.add_source(path, keys[choice], selected_file=selected_file)
                scan(db, sid)
            done()
            xbmc.executebuiltin('Container.Refresh')
        elif action == 'source':
            choice = dialog.select('Game source', ['Rescan (preserve library on failure)', 'Remove source from library only'])
            if choice == 0: scan(db, params['id'])
            elif choice == 1 and dialog.yesno('Remove source?', 'This removes catalog entries only. Original games and Kodi saves stay untouched.'):
                db.remove_source(params['id'])
            done()
            xbmc.executebuiltin('Container.Refresh')
        elif action == 'favorite':
            origin = xbmc.getInfoLabel('Container.FolderPath')
            db.favorite(params['id'])
            # A context action can outlive navigation. Refresh only the directory
            # which invoked it. Post the refresh: synchronous GUI dispatch can
            # block a replacement Python directory invoker.
            if origin.startswith(BASE) and xbmc.getInfoLabel('Container.FolderPath') == origin:
                xbmc.executebuiltin('Container.Refresh')
        elif action in ('play', 'details'):
            game = db.get(params.get('id', ''))
            if not game: raise ValueError('Game is no longer in the available library. Rescan its source.')
            if action == 'play': launch(db, game, profile)
            else:
                info = json.loads(game['metadata'])
                dialog.textviewer(game['title'], SYSTEMS[game['system']][0] + '\n\n' + info.get('overview', 'No local description. Add a matching .json sidecar for metadata.') + '\n\nPlay uses Kodi’s emulator and save chooser. Existing StreamPilot savestates are not imported.')
        elif action == 'help':
            dialog.textviewer('Foundry Games compatibility', 'Use rights-cleared ROMs and any required BIOS. Install compatible game add-ons from Kodi’s official repository. No emulator is bundled or installed automatically. Availability does not prove Shield gameplay compatibility. PSP is unsupported. Arcade requires matching sets; N64 rendering and DS touch/dual-screen need device validation.\n\nKodi owns saves, controllers and gameplay controls. StreamPilot savestates and OAuth tokens are not copied. A configured Kodi VFS folder is not direct Google Drive sign-in. Direct Drive authorization and remote metadata are not implemented. Local artwork and JSON metadata work offline.\n\nCache is bounded and never automatically evicts active games. Original ROMs and saves are never deleted.')
            done()
        else: raise ValueError('Unknown Games action')
    except (Cancelled, staging.Cancelled):
        dialog.notification('Foundry Games', 'Cancelled. Existing library and original games retained.')
        if handle >= 0: xbmcplugin.endOfDirectory(handle, succeeded=False)
    except Exception as exc:
        # Do not log source URLs: VFS sources can embed credentials.
        detail = str(exc) if isinstance(exc, (staging.StagingError, SourceUnavailable)) else type(exc).__name__
        dialog.ok('Foundry Games', 'Unable to complete this operation. Check source access, available space and game dependencies.\n' + detail)
        if handle >= 0: xbmcplugin.endOfDirectory(handle, succeeded=False)
    finally:
        db.close()


def scan(db, sid):
    progress = xbmcgui.DialogProgress()
    progress.create('Foundry Games', 'Scanning source. Cancel keeps the previous library.')
    monitor = xbmc.Monitor()
    try:
        source = next((s for s in db.sources() if s['id'] == sid), None)
        if source is None: raise ValueError('Source no longer exists')
        adapter = VFS() if '://' in source['path'] else LocalIO()
        count = db.scan(sid, adapter, lambda: progress.iscanceled() or monitor.abortRequested())
    finally:
        progress.close()
    message = '%d games indexed' % count
    if not getattr(adapter, 'authoritative', True): message += '. Previous VFS entries retained.'
    xbmcgui.Dialog().notification('Foundry Games', message)
