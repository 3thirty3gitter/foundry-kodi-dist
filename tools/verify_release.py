"""Check the packages, dependency versions, feed, hashes and installer aliases."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def structure(node):
    return node.tag, node.attrib, (node.text or '').strip(), [structure(child) for child in node]


def main():
    root = Path(__file__).resolve().parents[1]
    release = json.loads((root / 'release.json').read_text())
    feed_bytes = (root / 'addons.xml').read_bytes()
    assert hashlib.md5(feed_bytes).hexdigest() == (root / 'addons.xml.md5').read_text().strip(), 'Feed MD5 mismatch'
    feed = {addon.get('id'): addon for addon in ET.fromstring(feed_bytes)}
    versions = {p['id']: p['version'] for p in release['packages']}
    assert release['release'] == versions['script.program.foundry-build']
    assert release['skin'] == versions['skin.foundry']
    for package in release['packages']:
        path = root / package['path']
        data = path.read_bytes()
        assert len(data) == package['size'], str(path) + ': size mismatch'
        digest = hashlib.sha256(data).hexdigest()
        assert digest == package['sha256'], str(path) + ': checksum mismatch'
        assert digest == Path(str(path) + '.sha256').read_text().strip(), str(path) + ': sidecar mismatch'
        with zipfile.ZipFile(path) as bundle:
            assert bundle.testzip() is None, str(path) + ': damaged ZIP'
            manifest = ET.fromstring(bundle.read(package['id'] + '/addon.xml'))
        assert manifest.get('id') == package['id'] and manifest.get('version') == package['version'], str(path) + ': manifest mismatch'
        assert structure(manifest) == structure(feed[package['id']]), str(path) + ': feed mismatch'
        for dependency in manifest.findall('./requires/import'):
            addon = dependency.get('addon')
            if addon in versions:
                installed = tuple(map(int, versions[addon].split('.')))
                minimum = tuple(map(int, dependency.get('version').split('.')))
                assert installed >= minimum, str(path) + ': unmet internal dependency ' + addon
        if package['id'] in ('script.program.foundry-build', 'script.program.foundry-bootstrap'):
            assert (root / (package['id'] + '.zip')).read_bytes() == data, 'Stale root installer alias'
        if package['id'] == 'repository.foundry':
            assert (root / path.name).read_bytes() == data, 'Stale root repository installer'
    print('Verified all %d package ZIPs, hashes, manifests, dependencies, feed and aliases.' % len(release['packages']))


if __name__ == '__main__':
    main()
