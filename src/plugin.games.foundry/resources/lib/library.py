"""Independent, transactional game index. No Kodi imports or network requests."""
import hashlib
import json
import os
import posixpath
import sqlite3
import time
from urllib.parse import urlsplit

# Ambiguous images require a source's explicit system, never extension guessing.
SYSTEMS = {
    'a2600': ('Atari 2600', '.a26 .zip', 'game.libretro.stella'),
    'a7800': ('Atari 7800', '.a78 .zip', 'game.libretro.prosystem'),
    'lynx': ('Atari Lynx', '.lnx .zip', 'game.libretro.handy'),
    'nes': ('Nintendo Entertainment System', '.nes .unf .unif .zip', 'game.libretro.nestopia'),
    'snes': ('Super Nintendo', '.sfc .smc .zip', 'game.libretro.snes9x'),
    'gb': ('Game Boy', '.gb .zip', 'game.libretro.gambatte'),
    'gbc': ('Game Boy Color', '.gbc .zip', 'game.libretro.gambatte'),
    'gba': ('Game Boy Advance', '.gba .zip', 'game.libretro.mgba'),
    'genesis': ('Sega Genesis', '.md .gen .smd .bin .zip', 'game.libretro.genplus'),
    'sms': ('Sega Master System', '.sms .zip', 'game.libretro.genplus'),
    'gg': ('Sega Game Gear', '.gg .zip', 'game.libretro.genplus'),
    'n64': ('Nintendo 64', '.n64 .z64 .v64 .zip', 'game.libretro.mupen64plus-nx'),
    'psx': ('PlayStation', '.cue .m3u .chd .pbp .iso', 'game.libretro.pcsx-rearmed'),
    'psp': ('PlayStation Portable (unsupported)', '.iso .cso .pbp', ''),
    'nds': ('Nintendo DS', '.nds .zip', 'game.libretro.melonds'),
    'pce': ('PC Engine / TurboGrafx-16', '.pce .cue .m3u .chd .zip', 'game.libretro.beetle-pce-fast'),
    'arcade': ('Arcade', '.zip', 'game.libretro.fbneo'),
}


class Cancelled(Exception):
    pass


class SourceUnavailable(OSError):
    pass


class LocalIO:
    def listdir(self, path):
        dirs, files = [], []
        for entry in os.scandir(path):
            if entry.is_symlink() or os.path.normcase(os.path.realpath(entry.path)) != os.path.normcase(os.path.abspath(entry.path)):
                continue
            (dirs if entry.is_dir() else files).append(entry.name)
        return dirs, files

    def exists(self, path):
        return os.path.exists(path)

    def read(self, path, limit):
        with open(path, 'rb') as stream:
            return stream.read(limit + 1)


def join(root, name):
    return root.rstrip('/\\') + '/' + name


def identity(source, relative):
    return hashlib.sha256((source + '\0' + relative).encode('utf-8')).hexdigest()


def metadata(io, path):
    stem = path.rsplit('.', 1)[0]
    result = {}
    sidecar = stem + '.json'
    if io.exists(sidecar):
        try:
            raw = io.read(sidecar, 65536)
            if len(raw) <= 65536:
                value = json.loads(raw.decode('utf-8-sig'))
                if isinstance(value, dict):
                    for key in ('title', 'overview', 'publisher', 'developer', 'genre', 'year'):
                        if isinstance(value.get(key), (str, int)):
                            result[key] = str(value[key])[:8000]
        except (ValueError, OSError, UnicodeError):
            pass
    art = {}
    for kind, suffix in (('thumb', ''), ('poster', '-boxart'), ('fanart', '-fanart'), ('clearlogo', '-clearlogo')):
        for ext in ('.png', '.jpg', '.webp'):
            candidate = stem + suffix + ext
            if io.exists(candidate):
                art[kind] = candidate
                break
    result['art'] = art
    return result


class Library:
    def __init__(self, filename):
        self.db = sqlite3.connect(filename, timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1):
            self.db.close()
            raise ValueError('Newer game-library database; refusing to change it')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, path TEXT NOT NULL, system TEXT NOT NULL, label TEXT NOT NULL, scanned REAL);
        CREATE TABLE IF NOT EXISTS games(id TEXT PRIMARY KEY, source TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE, relative TEXT NOT NULL, path TEXT NOT NULL, system TEXT NOT NULL, title TEXT NOT NULL, metadata TEXT NOT NULL, present INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS history(id TEXT PRIMARY KEY, favorite INTEGER NOT NULL DEFAULT 0, launched REAL, seconds REAL NOT NULL DEFAULT 0);
        PRAGMA user_version=1;
        ''')

    def close(self):
        self.db.close()

    def add_source(self, path, system, label='', selected_file=False):
        if system not in SYSTEMS or not path or '\0' in path:
            raise ValueError('Choose a source and its console')
        # Do not accept web download URLs as filesystem sources.
        if urlsplit(path).scheme.lower() in ('http', 'https', 'ftp', 'data', 'plugin'):
            raise ValueError('Choose a local folder or configured Kodi VFS source')
        path = path.rstrip('/\\') + ('' if selected_file else '/')
        sid = identity(system, path)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO sources(id,path,system,label) VALUES(?,?,?,?)', (sid, path, system, label or SYSTEMS[system][0]))
        return sid

    def sources(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM sources ORDER BY label,id')]

    def remove_source(self, sid):
        # Catalog only. History survives re-adding; ROMs and native saves untouched.
        with self.db:
            self.db.execute('DELETE FROM sources WHERE id=?', (sid,))

    def scan(self, sid, io=None, cancelled=lambda: False, max_files=100000, max_depth=32):
        io = io or LocalIO()
        source = self.db.execute('SELECT * FROM sources WHERE id=?', (sid,)).fetchone()
        if source is None:
            raise ValueError('Source no longer exists')
        rows, visited = [], 0
        extensions = SYSTEMS[source['system']][1].split()
        def walk(relative, depth):
            nonlocal visited
            if cancelled():
                raise Cancelled('Scan cancelled; previous library retained')
            if depth > max_depth:
                raise ValueError('Source exceeds folder depth limit')
            dirs, files = io.listdir(join(source['path'], relative))
            for name in sorted(dirs + files):
                if name in ('.', '..') or '/' in name or '\\' in name or ':' in name:
                    raise ValueError('Unsafe source entry')
                visited += 1
                if visited > max_files:
                    raise ValueError('Source exceeds entry limit')
                if cancelled():
                    raise Cancelled('Scan cancelled; previous library retained')
                rel = (relative + '/' + name).lstrip('/')
                if name in dirs:
                    walk(rel, depth + 1)
                elif os.path.splitext(name)[1].lower() in extensions:
                    path = join(source['path'], rel)
                    info = metadata(io, path)
                    rows.append((identity(sid, rel), sid, rel, path, source['system'], info.get('title') or os.path.splitext(name)[0], json.dumps(info)))
        if source['path'].endswith('/'):
            walk('', 0)
        else:
            path = source['path']
            name = path.replace('\\', '/').rsplit('/', 1)[-1]
            if not io.exists(path):
                raise OSError('Selected file is unavailable')
            if os.path.splitext(name)[1].lower() not in extensions:
                raise ValueError('Selected file does not match the chosen system')
            info = metadata(io, path)
            rows.append((identity(sid, name), sid, name, path, source['system'], info.get('title') or os.path.splitext(name)[0], json.dumps(info)))
        if cancelled():
            raise Cancelled('Scan cancelled; previous library retained')
        # A playlist is one library entry, not one entry per disc. Only hide
        # indexed relative children; malformed descriptors remain visible so
        # preparation can explain/reject them without executing anything.
        children = set()
        for row in rows:
            if cancelled():
                raise Cancelled('Scan cancelled; previous library retained')
            if row[2].lower().endswith('.m3u'):
                raw = io.read(row[3], 65536)
                if len(raw) > 65536: continue
                try: lines = raw.decode('utf-8-sig').splitlines()
                except UnicodeError: continue
                for line in lines:
                    ref = line.strip().replace('\\', '/')
                    if not ref or ref.startswith('#') or ref.startswith('/') or ':' in ref or '..' in ref.split('/'):
                        continue
                    children.add(posixpath.join(posixpath.dirname(row[2]), ref))
        rows = [row for row in rows if row[2] not in children or row[2].lower().endswith('.m3u')]
        if cancelled():
            raise Cancelled('Scan cancelled; previous library retained')
        if not rows and not getattr(io, 'authoritative', True):
            raise SourceUnavailable('VFS folder is empty or unavailable. Its previous library was retained; check access before trying again.')
        # Failed/partial traversal never touches the committed index. Missing files
        # are hidden, not deleted, so history/favorites return with removable media.
        with self.db:
            if getattr(io, 'authoritative', True):
                self.db.execute('UPDATE games SET present=0 WHERE source=?', (sid,))
            self.db.executemany('INSERT INTO games(id,source,relative,path,system,title,metadata) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,metadata=excluded.metadata,path=excluded.path,present=1', rows)
            self.db.execute('UPDATE sources SET scanned=? WHERE id=?', (time.time(), sid))
        return len(rows)

    def games(self, system='', query='', mode='', page=0):
        clauses, args = ['g.present=1'], []
        if system:
            clauses.append('g.system=?'); args.append(system)
        if query:
            matches = [key for key, value in SYSTEMS.items() if query.casefold() in value[0].casefold()]
            clauses.append('(g.title LIKE ? ESCAPE "\\" OR g.system LIKE ? ESCAPE "\\"' + (' OR g.system IN (' + ','.join('?' for _ in matches) + ')' if matches else '') + ')')
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            args.extend(['%' + escaped + '%'] * 2)
            args.extend(matches)
        if mode == 'favorites': clauses.append('h.favorite=1')
        if mode == 'recent': clauses.append('h.launched IS NOT NULL')
        order = 'h.launched DESC,g.id' if mode == 'recent' else 'g.title COLLATE NOCASE,g.id'
        sql = 'SELECT g.*,COALESCE(h.favorite,0) AS favorite,h.launched,COALESCE(h.seconds,0) AS seconds FROM games g LEFT JOIN history h ON h.id=g.id WHERE ' + ' AND '.join(clauses)
        return [dict(row) for row in self.db.execute(sql + ' ORDER BY ' + order + ' LIMIT 21 OFFSET ?', args + [max(0, int(page)) * 20])]

    def get(self, gid):
        row = self.db.execute('SELECT * FROM games WHERE id=? AND present=1', (gid,)).fetchone()
        return dict(row) if row else None

    def favorite(self, gid):
        if not self.get(gid): raise ValueError('Game no longer available')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO history(id) VALUES(?)', (gid,))
            self.db.execute('UPDATE history SET favorite=1-favorite WHERE id=?', (gid,))

    def played(self, gid, seconds=0, now=None):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO history(id) VALUES(?)', (gid,))
            self.db.execute('UPDATE history SET launched=?,seconds=seconds+? WHERE id=?', (time.time() if now is None else now, max(0, seconds), gid))
