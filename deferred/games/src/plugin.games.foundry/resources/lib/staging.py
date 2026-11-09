"""Bounded, read-only ROM materialization. No ROM, firmware or save deletion.

Adapters implement open(path, 'rb') returning a binary file object and exists(path).
Kodi adapters must expose read(size), close(), and return bytes. Sources must be
explicitly selected by the user. Cache entries are immutable and never evicted,
so an in-use game stays pinned until the user explicitly manages the cache.
"""
import hashlib
import os
import posixpath
import re
import shutil
import stat
import tempfile
import zipfile

MAX_ENTRIES = 2048
MAX_BYTES = 4 * 1024 ** 3
MAX_CACHE_BYTES = 8 * 1024 ** 3
CHUNK = 1024 * 1024
DISC_LIMIT = 1024 * 1024
EXTENSIONS = {
    'a2600': ('.a26',), 'atari2600': ('.a26',),
    'a7800': ('.a78',), 'atari7800': ('.a78',),
    'lynx': ('.lnx',), 'atarilynx': ('.lnx',),
    'nes': ('.nes', '.unf', '.unif'), 'snes': ('.sfc', '.smc'),
    'gb': ('.gb',), 'gbc': ('.gbc',), 'gba': ('.gba',),
    'genesis': ('.md', '.gen', '.smd', '.bin'),
    'megadrive': ('.md', '.gen', '.smd', '.bin'),
    'mastersystem': ('.sms',), 'sms': ('.sms',),
    'gamegear': ('.gg',), 'gg': ('.gg',),
    'n64': ('.z64', '.n64', '.v64'), 'psx': ('.cue', '.chd', '.iso', '.pbp'),
    'ps1': ('.cue', '.chd', '.iso', '.pbp'),
    'playstation': ('.cue', '.chd', '.iso', '.pbp'),
    'nds': ('.nds',), 'ds': ('.nds',),
    'pce': ('.pce', '.cue', '.chd'), 'pcengine': ('.pce', '.cue', '.chd'),
}


class StagingError(ValueError):
    pass


class Cancelled(StagingError):
    pass


class LocalIO:
    def open(self, path, mode='rb'):
        return open(path, mode)

    def exists(self, path):
        return os.path.isfile(path)


def safe_relative(name):
    """Reject Windows and POSIX escapes regardless of the host platform."""
    name = name.replace('\\', '/')
    if not name or name.startswith('/') or ':' in name or '\x00' in name:
        raise StagingError('Unsafe relative path')
    parts = name.split('/')
    if any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in parts):
        raise StagingError('Unsafe relative path')
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {
        prefix + str(i) for prefix in ('COM', 'LPT') for i in range(1, 10)}
    if any(p.split('.')[0].upper() in reserved or
           any(c in p for c in '<>"|?*') or any(ord(c) < 32 for c in p)
           for p in parts):
        raise StagingError('Unsafe filename')
    return '/'.join(parts)


def _check(cancelled):
    if cancelled():
        raise Cancelled('Game preparation cancelled')


def _join_source(root, relative):
    # Never urljoin: it can replace a provider/authority with an input reference.
    return root.rstrip('/\\') + '/' + relative


def _local_safe(path, root):
    root = os.path.abspath(root)
    path = os.path.abspath(path)
    if os.path.commonpath([root, path]) != root:
        raise StagingError('Source escaped its selected folder')
    if os.path.normcase(os.path.realpath(path)) != os.path.normcase(path):
        raise StagingError('Symbolic links or redirected paths are not accepted')
    current = path
    while True:
        if os.path.islink(current):
            raise StagingError('Symbolic links are not accepted')
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent


def _references(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in ('.cue', '.m3u'):
        return []
    if os.path.getsize(path) > DISC_LIMIT:
        raise StagingError('Disc descriptor exceeds size limit')
    with open(path, 'rb') as stream:
        raw = stream.read(DISC_LIMIT + 1)
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise StagingError('Disc descriptors must use UTF-8')
    if ext == '.m3u':
        refs = [line.strip() for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith('#')]
    else:
        refs = []
        for line in text.splitlines():
            if re.match(r'^\s*FILE\b', line, re.I):
                match = re.match(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+\S+\s*$', line, re.I)
                if not match:
                    raise StagingError('Malformed CUE FILE directive')
                refs.append(match.group(1) or match.group(2))
    if not refs:
        raise StagingError('Disc descriptor has no files')
    return [safe_relative(ref) for ref in refs]


def _tree_bytes(root):
    total = 0
    if not os.path.exists(root):
        return total
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            if os.path.islink(os.path.join(directory, name)):
                raise StagingError('Cache contains a symbolic link')
        total += sum(os.path.getsize(os.path.join(directory, name)) for name in files)
    return total


def _digest_tree(root, system, launch, cancelled):
    digest = hashlib.sha256()
    def field(value):
        data = str(value).encode('utf-8')
        digest.update(str(len(data)).encode('ascii') + b':' + data)
    field(system)
    field(launch)
    for directory, folders, filenames in os.walk(root):
        folders.sort()
        for filename in sorted(filenames):
            path = os.path.join(directory, filename)
            field(os.path.relpath(path, root).replace('\\', '/'))
            field(os.path.getsize(path))
            with open(path, 'rb') as stream:
                while True:
                    _check(cancelled)
                    block = stream.read(CHUNK)
                    if not block:
                        break
                    digest.update(block)
    return digest.hexdigest()


def prepare(source, system, cache_dir, io=None, cancelled=lambda: False,
            max_bytes=MAX_BYTES, max_entries=MAX_ENTRIES,
            max_cache_bytes=MAX_CACHE_BYTES):
    """Return an atomic local launch path or raise StagingError/Cancelled.

    No partial output is reused. The selected system is required for ZIP launch
    selection; ambiguous multi-game archives fail rather than guessing a ROM.
    Cache budget includes temporary copies and extraction. Completed entries are
    content-addressed, reused, and never automatically deleted (active-session pin).
    """
    _check(cancelled)
    if system == 'psp':
        raise StagingError('PSP has no verified native Omega ARM64 emulator')
    if system not in EXTENSIONS and system != 'arcade':
        raise StagingError('Select a supported system before preparing a game')
    adapter = io if io is not None else LocalIO()
    source = str(source)
    normalized = source.replace('\\', '/')
    root, name = normalized.rsplit('/', 1) if '/' in normalized else ('.', normalized)
    name = safe_relative(name)
    extension = os.path.splitext(name)[1].lower()
    if system == 'arcade' and extension != '.zip':
        raise StagingError('Arcade preparation supports standalone ZIP sets only; 7z and dependent sets need separate validation')
    if system != 'arcade' and extension not in EXTENSIONS[system] + ('.m3u', '.zip'):
        raise StagingError('File extension is not supported for the selected system')
    cache_dir = os.path.abspath(cache_dir)
    _local_safe(cache_dir, cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    # One writer per cache prevents concurrent scans from exceeding the budget.
    # A crash releases the OS lock; the zero-byte lock file is harmless.
    lock = open(os.path.join(cache_dir, '.prepare.lock'), 'a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        raise StagingError('Another game is being prepared; try again when it finishes')
    try:
        existing_bytes = _tree_bytes(cache_dir)
        workspace = tempfile.mkdtemp(prefix='.preparing-', dir=cache_dir)
    except BaseException:
        lock.close()
        raise
    payload = os.path.join(workspace, 'payload')
    os.mkdir(payload)
    used = [0]
    copied = {}
    visiting = set()

    def write_stream(stream, target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'xb') as output:
            while True:
                _check(cancelled)
                block = stream.read(CHUNK)
                if not block:
                    break
                if not isinstance(block, (bytes, bytearray)):
                    raise StagingError('Source adapter must return binary data')
                used[0] += len(block)
                if used[0] > max_bytes or existing_bytes + used[0] > max_cache_bytes:
                    raise StagingError('Game or cache size limit exceeded')
                output.write(block)

    def copy(relative):
        relative = safe_relative(relative)
        key = relative.casefold()
        if key in visiting:
            raise StagingError('Cyclic disc playlist')
        if key in copied:
            if copied[key] != relative:
                raise StagingError('Disc companion paths differ only in case')
            return
        if len(copied) + len(visiting) >= max_entries:
            raise StagingError('Too many game files')
        if len(visiting) >= 64:
            raise StagingError('Disc playlist nesting limit exceeded')
        visiting.add(key)
        remote = _join_source(root, relative)
        if '://' not in remote:
            _local_safe(remote, root)
        if not adapter.exists(remote):
            raise StagingError('Missing ROM or disc companion')
        target = os.path.join(payload, *relative.split('/'))
        stream = adapter.open(remote, 'rb')
        try:
            write_stream(stream, target)
        finally:
            stream.close()
        for ref in _references(target):
            copy(posixpath.join(posixpath.dirname(relative), ref))
        visiting.remove(key)
        copied[key] = relative

    def validate_disc(relative, seen=None):
        seen = set() if seen is None else seen
        if len(seen) >= 64:
            raise StagingError('Disc playlist nesting limit exceeded')
        if relative.casefold() in seen:
            raise StagingError('Cyclic disc playlist')
        seen = seen | {relative.casefold()}
        target = os.path.join(payload, *relative.split('/'))
        if not os.path.isfile(target):
            raise StagingError('Missing archive disc companion')
        for ref in _references(target):
            validate_disc(posixpath.join(posixpath.dirname(relative), ref), seen)

    try:
        copy(name)
        launch = name
        if name.lower().endswith('.zip') and system != 'arcade':
            archive_path = os.path.join(payload, name)
            unpacked = os.path.join(workspace, 'unpacked')
            os.mkdir(unpacked)
            names = set()
            files = []
            expanded = 0
            with zipfile.ZipFile(archive_path) as archive:
                infos = archive.infolist()
                if len(infos) > max_entries:
                    raise StagingError('Archive entry limit exceeded')
                directory_entries = []
                for info in infos:
                    _check(cancelled)
                    relative = safe_relative(info.filename.rstrip('/') if info.is_dir() else info.filename)
                    key = relative.casefold()
                    mode = info.external_attr >> 16
                    if key in names or stat.S_ISLNK(mode):
                        raise StagingError('Duplicate archive path or symbolic link')
                    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                        raise StagingError('Archive contains a special file')
                    if info.flag_bits & 1:
                        raise StagingError('Encrypted archives are unsupported')
                    names.add(key)
                    expanded += info.file_size
                    if expanded > max_bytes:
                        raise StagingError('Expanded archive size limit exceeded')
                    if not info.is_dir():
                        files.append((relative, info))
                    else:
                        directory_entries.append(relative)
                # Reject case aliases in every directory component, and file/dir conflicts.
                prefixes = {}
                for relative in directory_entries:
                    parts = relative.split('/')
                    for index in range(1, len(parts) + 1):
                        prefix = '/'.join(parts[:index])
                        key = prefix.casefold()
                        if key in prefixes and prefixes[key] != (prefix, 'dir'):
                            raise StagingError('Archive path collision')
                        prefixes[key] = (prefix, 'dir')
                for relative, _ in files:
                    parts = relative.split('/')
                    for index in range(1, len(parts) + 1):
                        prefix = '/'.join(parts[:index])
                        key = prefix.casefold()
                        kind = 'file' if index == len(parts) else 'dir'
                        if key in prefixes and prefixes[key] != (prefix, kind):
                            raise StagingError('Archive path collision')
                        prefixes[key] = (prefix, kind)
                for relative, info in files:
                    with archive.open(info) as stream:
                        write_stream(stream, os.path.join(unpacked, *relative.split('/')))
            payload = unpacked
            candidates = [n for n, _ in files if n.lower().endswith('.m3u')]
            if not candidates:
                candidates = [n for n, _ in files if n.lower().endswith(EXTENSIONS[system])]
            if len(candidates) != 1:
                raise StagingError('Archive must contain one unambiguous game or playlist')
            launch = candidates[0]
            validate_disc(launch)
        _check(cancelled)
        digest = _digest_tree(payload, system, launch, cancelled)
        destination = os.path.join(cache_dir, digest)
        if not os.path.exists(destination):
            try:
                os.rename(payload, destination)
            except OSError:
                if not os.path.isdir(destination):
                    raise
        if _digest_tree(destination, system, launch, cancelled) != digest:
            raise StagingError('Cached game is incomplete or changed; manage this cache entry before trying again')
        result = os.path.join(destination, *launch.split('/'))
        if not os.path.isfile(result):
            raise StagingError('Incomplete cache entry')
        return result
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise StagingError('Unable to prepare game: ' + str(exc)) from exc
    finally:
        # Only remove our freshly-created temporary directory, never source/cache entries.
        try:
            shutil.rmtree(workspace)
        finally:
            lock.close()
