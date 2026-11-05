"""Restore committed release sources without credentials to private repositories.

Unchanged binary assets come from immutable public baseline ZIPs. Changed text
and the complete expected Git blob map were verified against the pinned private
source commits before this snapshot was committed.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import zipfile


def relative_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Invalid snapshot path')
    return Path(*path.parts)


def git_hash(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=root.parent)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    snapshots = json.loads(gzip.decompress((root / 'releases/1.3.0-source-snapshot.json.gz').read_bytes()))
    sources = json.loads((root / 'releases/1.3.0-sources.json').read_text())['source_commits']
    for addon, snapshot in snapshots.items():
        directory = 'skin.foundry-nimbus' if addon == 'skin.foundry' else addon
        assert snapshot['source_commit'] == sources[directory], 'Source pin mismatch'
        destination = output / directory
        if destination.exists():
            raise FileExistsError('Source directory already exists: ' + str(destination))
        archive = root / relative_path(snapshot['baseline'])
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == snapshot['baseline_sha256'], 'Baseline ZIP was modified'
        with tempfile.TemporaryDirectory(dir=output) as temporary:
            work = Path(temporary) / directory
            work.mkdir()
            with zipfile.ZipFile(archive) as bundle:
                for name in bundle.namelist():
                    prefix, path = name.split('/', 1)
                    assert prefix == addon, 'Unexpected add-on in baseline ZIP'
                    target = work / relative_path(path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bundle.read(name))
            for path in snapshot['removed']:
                (work / relative_path(path)).unlink()
            for path, content in snapshot['files'].items():
                target = work / relative_path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content.encode('utf-8'))
            actual = {path.relative_to(work).as_posix(): git_hash(path.read_bytes())
                      for path in work.rglob('*') if path.is_file()}
            assert actual == snapshot['packaged_git_blobs'], 'Restored source differs from verified source commit'
            work.rename(destination)
        print('Restored %s from verified commit %s (%d files)' % (directory, snapshot['source_commit'], len(actual)))


if __name__ == '__main__':
    main()
