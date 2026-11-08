"""Record completed CI evidence and stage only the generated release payload.

The release workflow invokes this after all validation steps pass. It never
pushes, changes branch permissions, or stages source edits or historical ZIPs.
"""
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ('verification.json', 'startup-splash-verification.json',
          'interface-verification.json', 'games/verification.json',
          'weather-verification.json')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def evidence(root, release):
    qa = root / 'releases' / (release + '-qa')
    source, packaged = read(qa / 'source-tests.json'), read(qa / 'packaged-tests.json')
    for report in (source, packaged):
        assert report['successful'] and report['tests'] > 0
        assert report['failures'] == report['errors'] == 0
    rebuild = read(qa / 'packaged-verification.json')
    assert rebuild['passed'] and rebuild['deterministic_rebuild']
    manifest = read(root / 'release.json')
    assert manifest['release'] == rebuild['release'] == release
    assert rebuild['packages'] == manifest['packages']
    assert read(qa / 'release.json') == manifest
    native = {name: read(qa / 'native' / name) for name in NATIVE}
    assert native['games/verification.json']['passed']
    assert native['weather-verification.json']['passed']
    assert native['verification.json']['checks']
    assert native['startup-splash-verification.json']['real_kodi_cold_start']
    assert native['interface-verification.json']['home_favorites_row_focus_and_horizontal_navigation']
    return {'status': 'ci_passed_target_device_checks_pending',
            'source_tests': source, 'packaged_tests': packaged,
            'deterministic_rebuild': True,
            'native_reports': list(NATIVE),
            'workflow_run': os.environ.get('GITHUB_RUN_ID'),
            'target_device_verification': 'Shield gameplay and rendering unverified'}


def require_unchanged_packages(root, manifest):
    """Never replace committed versioned bytes during a publication rebuild."""
    for package in manifest['packages']:
        for name in (package['path'], package['path'] + '.sha256'):
            path = Path(name)
            assert not path.is_absolute() and '..' not in path.parts
            tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', name],
                                     cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if tracked.returncode == 0:
                committed = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=root)
                assert (root / path).read_bytes() == committed, 'Refusing changed versioned package: ' + name


def main():
    assert os.environ.get('GITHUB_REF') == 'refs/heads/main', 'Publication requires the approved main branch'
    manifest = read(ROOT / 'release.json')
    require_unchanged_packages(ROOT, manifest)
    release = manifest['release']
    source_path = ROOT / 'releases' / (release + '-sources.json')
    sources = read(source_path)
    assert sources['release'] == release
    sources['validation'] = evidence(ROOT, release)
    source_path.write_text(json.dumps(sources, indent=2) + '\n', encoding='utf-8', newline='\n')
    paths = ['addons.xml', 'addons.xml.md5', 'index.html', 'skin.html', 'release.json',
             'script.program.foundry-build.zip', 'script.program.foundry-bootstrap.zip',
             source_path.relative_to(ROOT).as_posix()]
    for package in manifest['packages']:
        path = Path(package['path'])
        assert not path.is_absolute() and '..' not in path.parts
        paths.extend([path.as_posix(), path.as_posix() + '.sha256'])
        if package['id'] == 'repository.foundry':
            paths.append(path.name)
    qa = ROOT / 'releases' / (release + '-qa')
    paths.extend(path.relative_to(ROOT).as_posix() for path in sorted(qa.rglob('*'))
                 if path.is_file() and path.suffix in ('.json', '.png'))
    subprocess.run(['git', 'add', '--', *paths], cwd=ROOT, check=True)
    print('Staged %d exact release and QA paths.' % len(paths))


if __name__ == '__main__':
    main()
