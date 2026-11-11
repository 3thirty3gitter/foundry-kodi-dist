"""Native CI changes routing, not repository trust or the validation gates."""
from pathlib import Path
import sys, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from use_direct_ubuntu_sources import configure

class UbuntuNativeSources(unittest.TestCase):
    def test_deb822_preserves_suites_components_and_signed_by(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sources.list.d/ubuntu.sources';path.parent.mkdir()
            original=b'Types: deb\nURIs: mirror+file:/etc/apt/apt-mirrors.txt\nSuites: resolute resolute-updates resolute-security\nComponents: main universe\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n'
            path.write_bytes(original)
            configure(temp)
            self.assertEqual(path.read_bytes(),original.replace(b'mirror+file:/etc/apt/apt-mirrors.txt',b'https://archive.ubuntu.com/ubuntu'))
            configure(temp)
            self.assertNotIn(b'trusted=yes',path.read_bytes())
    def test_legacy_and_unrelated_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sources.list'
            original=b'deb [signed-by=/keys/ubuntu.gpg] http://azure.archive.ubuntu.com/ubuntu resolute main\ndeb https://packages.microsoft.com/repos/code stable main\n'
            path.write_bytes(original)
            configure(temp)
            self.assertEqual(path.read_bytes(),original.replace(b'http://azure.archive.ubuntu.com/ubuntu',b'https://archive.ubuntu.com/ubuntu'))
    def test_unknown_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(RuntimeError):configure(temp)
    def test_both_workflows_keep_native_gates_and_strict_update(self):
        for name in ('dev-validation.yml','release.yml'):
            text=(ROOT/'.github/workflows'/name).read_text()
            self.assertIn('docker build --platform linux/amd64',text)
            self.assertNotIn('sudo apt-get',text)
            for gate in ('library','startup_splash','interface','weather','games'):
                self.assertIn('tools/render_'+gate+'.py',text)
            self.assertNotIn('allow-unsupported-kodi',text)
            self.assertNotIn('allow-unauthenticated',text)

if __name__=='__main__':unittest.main()
