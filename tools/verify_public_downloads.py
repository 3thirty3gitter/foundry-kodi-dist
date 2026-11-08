"""Verify real public package downloads on both Pages and Kodi's raw feed host."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASES = ('https://3thirty3gitter.github.io/foundry-kodi-dist/',
         'https://raw.githubusercontent.com/3thirty3gitter/foundry-kodi-dist/main/')
COMMIT = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def download(base, path, expected=None):
    last_error = None
    # Package publication precedes the separate Pages deployment. Give the
    # small manifest time to converge before checking the larger ZIP files.
    attempts=18 if base==BASES[0] and path=='release.json' else 6
    for attempt in range(attempts):
        try:
            request = Request(base + path + '?verify=' + COMMIT, headers={'User-Agent': 'Foundry-release-verification'})
            with urlopen(request, timeout=10 if attempts==18 else 30) as response:
                assert response.status == 200, 'HTTP status ' + str(response.status)
                data = response.read()
            if expected is not None:
                assert data == expected, 'Published bytes differ: ' + base + path
            return data
        except Exception as error:
            last_error = error
            if attempt < attempts-1:
                time.sleep(10)
    raise RuntimeError('Public download failed: ' + base + path) from last_error


def package_check(task):
    base, package = task
    data = download(base, package['path'], (ROOT / package['path']).read_bytes())
    assert len(data) == package['size']
    assert hashlib.sha256(data).hexdigest() == package['sha256']
    with zipfile.ZipFile(BytesIO(data)) as bundle:
        assert bundle.testzip() is None, 'Corrupt downloaded ZIP'
    download(base, package['path'] + '.sha256', (ROOT / (package['path'] + '.sha256')).read_bytes())
    print('Verified', base + package['path'], flush=True)
    return dict(package, host=base, status=200, verified=True)


def main():
    manifest = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    release = manifest['release']
    qa = ROOT / 'releases' / (release + '-qa')
    sources = json.loads((ROOT / 'releases' / (release + '-sources.json')).read_text(encoding='utf-8'))
    assert sources['release'] == release
    source_tests = json.loads((qa / 'source-tests.json').read_text(encoding='utf-8'))
    packaged_tests = json.loads((qa / 'packaged-tests.json').read_text(encoding='utf-8'))
    rebuild = json.loads((qa / 'packaged-verification.json').read_text(encoding='utf-8'))
    assert source_tests['successful'] and packaged_tests['successful'] and rebuild['passed']
    assert rebuild['deterministic_rebuild']
    package_count = len(manifest['packages'])
    for base in BASES:
        for path in ('release.json', 'addons.xml', 'addons.xml.md5'):
            download(base, path, (ROOT / path).read_bytes())
    with ThreadPoolExecutor(max_workers=4) as pool:
        checks = list(pool.map(package_check, [(base, p) for base in BASES for p in manifest['packages']]))
    for path in ('index.html', 'skin.html', 'repository.foundry-1.2.0.zip',
                 'script.program.foundry-build.zip', 'script.program.foundry-bootstrap.zip'):
        download(BASES[0], path, (ROOT / path).read_bytes())
    record = {
        'verification_time_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'published_downloads_verified_target_device_checks_pending',
        'release': manifest['release'], 'skin': manifest['skin'], 'helper': sources['helper'],
        'source_url': BASES[0], 'distribution_commit_verified': COMMIT,
        'source_commits': sources['source_commits'],
        'validation': {
            'source_regression_tests': source_tests,
            'packaged_regression_tests': packaged_tests,
            'native_kodi_interface': json.loads((qa / 'native/interface-verification.json').read_text(encoding='utf-8')),
            'native_kodi_startup_splash': json.loads((qa / 'native/startup-splash-verification.json').read_text(encoding='utf-8')),
            'native_kodi_fixture': json.loads((qa / 'native/verification.json').read_text(encoding='utf-8')),
            'native_kodi_games': json.loads((qa / 'native/games/verification.json').read_text(encoding='utf-8')),
            'native_kodi_weather': json.loads((qa / 'native/weather-verification.json').read_text(encoding='utf-8')),
            'test_inputs': 'Pinned source snapshots and extracted package ZIPs; mocked Kodi APIs',
            'deterministic_rebuild': 'All %d package sizes and SHA-256 checksums unchanged' % package_count,
            'public_release_manifest_and_feed': 'Byte-identical on Pages and raw GitHub',
            'public_source_and_root_installers': 'Byte-identical to committed release',
            'public_package_downloads': 'All %d ZIPs and SHA-256 sidecars verified on both hosts' % package_count
        },
        'public_packages': checks,
        'limitations': [
            'Live TMDb/OMDb calls require personal profile keys and remain unverified',
            'No Shield is connected; target-device rendering, navigation and playback remain unverified',
            'Add-on custom windows and unidentified action listings keep their own behavior',
            'Games fixtures use synthetic non-playable files; actual emulator gameplay is unverified',
            'Games does not yet support PSP, direct Drive OAuth, remote metadata or save migration',
            'Weather uses an experimental Canadian API; device-local times, advisory headlines only',
            'Native Pulse checks preserve selection but a null audio sink cannot verify audibility',
            'The reported false error after playback stops has not been reproduced or confirmed fixed'
        ]
    }
    (ROOT / 'releases' / (release + '-verification.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Verified all %d packages on both public hosts, Kodi feed, source listing and root installers.' % package_count)


if __name__ == '__main__':
    main()

