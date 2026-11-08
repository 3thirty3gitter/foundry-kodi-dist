"""Create deterministic public snapshots of exact committed skin/helper sources.

Unchanged bytes are reused from an immutable prior release ZIP. Every included
working file must match its Git object at the selected commit before snapshotting.
This command never commits, pushes, or reads credentials.
"""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from build_release import package


ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def snapshot(source, baseline):
    manifest = ET.parse(source / 'addon.xml').getroot()
    addon = manifest.get('id')
    commit = git(source, 'rev-parse', 'HEAD').decode().strip()
    with zipfile.ZipFile(baseline) as archive:
        prefix = addon + '/'
        old = {}
        for item in archive.infolist():
            if item.is_dir():
                continue
            if not item.filename.startswith(prefix):
                raise ValueError('Unexpected baseline add-on')
            old[item.filename[len(prefix):]] = archive.read(item)
    with tempfile.TemporaryDirectory(prefix='foundry-snapshot-') as temporary:
        output = Path(temporary)
        _, details = package(source, output)
        with zipfile.ZipFile(output / details['path']) as archive:
            current = {item.filename[len(addon) + 1:]: archive.read(item)
                       for item in archive.infolist() if not item.is_dir()}
    files, binary, hashes = {}, {}, {}
    for name, data in sorted(current.items()):
        committed = git(source, 'show', commit + ':' + name)
        if committed != data:
            raise ValueError('Working bytes differ from committed source: ' + name)
        hashes[name] = blob(data)
        if old.get(name) == data:
            continue
        try:
            text = data.decode('utf-8')
            if '\0' in text:
                raise UnicodeError('Binary content')
            files[name] = text
        except UnicodeError:
            binary[name] = base64.b64encode(data).decode('ascii')
    return addon, {
        'source_commit': commit,
        'baseline': baseline.relative_to(ROOT).as_posix(),
        'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
        'files': files, 'binary_files': binary,
        'removed': sorted(set(old) - set(current)),
        'packaged_git_blobs': hashes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', required=True)
    parser.add_argument('--skin', type=Path, required=True)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--skin-baseline', default='skin.foundry/skin.foundry-1.3.9.zip')
    parser.add_argument('--helper-baseline', default='script.foundry.helper/script.foundry.helper-1.2.7.zip')
    args = parser.parse_args()
    snapshots, commits = {}, {}
    for source, baseline in ((args.skin, args.skin_baseline), (args.helper, args.helper_baseline)):
        addon, data = snapshot(source, ROOT / baseline)
        snapshots[addon] = data
        commits[source.name] = data['source_commit']
    output = ROOT / 'releases'
    output.mkdir(exist_ok=True)
    encoded = json.dumps(snapshots, sort_keys=True, separators=(',', ':')).encode('utf-8')
    (output / (args.release + '-source-snapshot.json.gz')).write_bytes(gzip.compress(encoded, mtime=0))
    record = {
        'release': args.release,
        'skin': ET.parse(args.skin / 'addon.xml').getroot().get('version'),
        'helper': ET.parse(args.helper / 'addon.xml').getroot().get('version'),
        'source_commits': commits,
        'validation': {'status': 'awaiting_final_ci',
                       'target_device_verification': 'Shield gameplay and rendering unverified'},
    }
    (output / (args.release + '-sources.json')).write_text(
        json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
