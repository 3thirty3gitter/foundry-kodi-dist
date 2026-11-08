"""Test and deterministically rebuild ZIP contents without replacing source trees.

The staged repository keeps the normal relative layout used by tests/renderers,
but every add-on source comes only from release.json's checked ZIPs. The caller
may retain --workspace to run native Kodi checks against those same sources.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


SIBLINGS = {'skin.foundry': 'skin.foundry-nimbus',
            'script.foundry.helper': 'script.foundry.helper'}


def relative_path(value):
    if not isinstance(value, str) or '\\' in value or ':' in value:
        raise ValueError('Unsafe package path: ' + repr(value))
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Unsafe package path: ' + repr(value))
    return Path(*path.parts)


def read_release(root):
    release = json.loads((root / 'release.json').read_text(encoding='utf-8'))
    identifiers = set()
    for package in release['packages']:
        identifier = package['id']
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]*', identifier) or identifier in identifiers:
            raise ValueError('Invalid or duplicate add-on ID: ' + repr(identifier))
        identifiers.add(identifier)
        archive = root / relative_path(package['path'])
        data = archive.read_bytes()
        if len(data) != package['size'] or hashlib.sha256(data).hexdigest() != package['sha256']:
            raise ValueError('Package does not match release.json: ' + identifier)
    source_ids = {ET.parse(path).getroot().get('id') for path in (root / 'src').glob('*/addon.xml')}
    missing = (source_ids | set(SIBLINGS)) - identifiers
    if missing:
        raise ValueError('Source add-ons omitted from packages: ' + ', '.join(sorted(missing)))
    return release


def extract_package(archive, package, destination):
    """Reject alternate roots, duplicate entries, links and path traversal."""
    identifier = package['id']
    seen = set()
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            path = relative_path(entry.filename.rstrip('/'))
            if path.parts[0] != identifier or len(path.parts) < 2:
                raise ValueError('Unexpected add-on ZIP root: ' + entry.filename)
            kind = stat.S_IFMT(entry.external_attr >> 16)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('Non-regular ZIP entry: ' + entry.filename)
            key = path.as_posix().casefold()
            if key in seen:
                raise ValueError('Duplicate ZIP entry: ' + entry.filename)
            seen.add(key)
            target = destination.joinpath(*path.parts[1:])
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.read(entry))
    manifest = ET.parse(destination / 'addon.xml').getroot()
    if manifest.get('id') != identifier or manifest.get('version') != package['version']:
        raise ValueError('Extracted manifest differs from release.json: ' + identifier)


def stage_workspace(root, workspace, release):
    root, workspace = root.resolve(), workspace.resolve()
    if workspace.exists() or workspace.is_relative_to(root) or root.is_relative_to(workspace):
        raise ValueError('Use a new workspace outside the source repository: ' + str(workspace))
    workspace.mkdir(parents=True)
    staged = workspace / root.name

    def ignore(directory, names):
        excluded = {name for name in names if name in {'.git', '__pycache__'} or name.endswith(('.pyc', '.pyo'))}
        if Path(directory) == root:
            excluded.add('src')
        if Path(directory) == root / 'releases':
            excluded.update(name for name in names if name.endswith('-qa'))
        return excluded

    # Copies, not hard links: a rebuild must never modify the original ZIPs.
    shutil.copytree(root, staged, ignore=ignore)
    for package in release['packages']:
        identifier = package['id']
        destination = (workspace / SIBLINGS[identifier] if identifier in SIBLINGS
                       else staged / 'src' / identifier)
        extract_package(root / relative_path(package['path']), package, destination)
    return staged


def verify(root, workspace, output):
    output.mkdir(parents=True, exist_ok=True)
    record = {'passed': False, 'stage': 'check_packages'}
    try:
        release = read_release(root)
        expected = (root / 'release.json').read_bytes()
        record.update(release=release['release'], packages=release['packages'])
        record['stage'] = 'extract_packages'
        staged = stage_workspace(root, workspace, release)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')

        def run(*arguments):
            subprocess.run([sys.executable, *arguments], cwd=staged, env=environment, check=True)

        record['stage'] = 'packaged_tests'
        run('tools/run_tests.py', '--output', str(output / 'packaged-tests.json'))
        record['stage'] = 'deterministic_rebuild'
        run('tools/build_release.py', '--skin', '../skin.foundry-nimbus',
            '--helper', '../script.foundry.helper')
        if (staged / 'release.json').read_bytes() != expected:
            raise ValueError('Rebuilding the exact ZIP sources changed release.json')
        # Rehash the rebuilt ZIP bytes, not only the manifest describing them.
        read_release(staged)
        run('tools/verify_release.py')
        record.update(passed=True, stage='complete', deterministic_rebuild=True,
                      source_trees_preserved=True)
        print('Packaged tests and deterministic rebuild passed in ' + str(staged))
        return staged
    except Exception as error:
        record['error'] = str(error)
        raise
    finally:
        (output / 'packaged-verification.json').write_text(
            json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path,
                        help='New, retained staging directory outside the checkout')
    parser.add_argument('--output', required=True, type=Path, help='Directory for QA JSON')
    args = parser.parse_args()
    verify(Path(__file__).resolve().parents[1], args.workspace.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
