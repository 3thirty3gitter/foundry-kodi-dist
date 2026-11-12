"""Kodi's real splash override and existing-user migration behavior."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_release import HELPER, ROOT, SKIN, xbmc, xbmcaddon, xbmcvfs


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StartupSplash(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.media = self.home / 'media'
        self.source = SKIN / 'media/foundry-backdrops/foundry-loading-splash.png'
        self.module = load('foundry_splash_test', HELPER / 'resources/lib/modules/startup_splash.py')
        addon = lambda aid: type('Addon', (), {'getAddonInfo': lambda _, key: str(SKIN if aid == 'skin.foundry' else HELPER)})()
        self.addCleanup(patch.stopall)
        patch.object(xbmcaddon, 'Addon', addon).start()
        patch.object(xbmcvfs, 'translatePath', lambda value: str(self.media) if value == 'special://home/media/' else value).start()

    def test_fresh_install_preserves_approved_artwork_bytes(self):
        self.assertTrue(self.module.install_startup_splash())
        self.assertEqual((self.media / 'splash.png').read_bytes(), self.source.read_bytes())
        self.assertEqual(list(self.home.iterdir()), [self.media])

    def test_repeat_startup_does_not_rewrite_or_create_backups(self):
        self.module.install_startup_splash()
        destination = self.media / 'splash.png'
        modified = destination.stat().st_mtime_ns
        self.assertFalse(self.module.install_startup_splash())
        self.assertEqual(destination.stat().st_mtime_ns, modified)
        self.assertEqual([p.name for p in self.media.iterdir()], ['splash.png'])

    def test_existing_jpeg_and_png_are_preserved_and_png_wins(self):
        self.media.mkdir()
        (self.media / 'splash.jpg').write_bytes(b'old-jpeg')
        (self.media / 'splash.png').write_bytes(b'old-png')
        self.module.install_startup_splash()
        self.assertFalse((self.media / 'splash.jpg').exists())
        self.assertEqual((self.media / 'splash.jpg.before-foundry').read_bytes(), b'old-jpeg')
        self.assertEqual((self.media / 'splash.png.before-foundry').read_bytes(), b'old-png')
        self.assertEqual((self.media / 'splash.png').read_bytes(), self.source.read_bytes())

    def test_later_custom_override_does_not_replace_earlier_backup(self):
        self.media.mkdir()
        (self.media / 'splash.jpg.before-foundry').write_bytes(b'first')
        (self.media / 'splash.jpg').write_bytes(b'second')
        self.module.install_startup_splash()
        self.assertEqual((self.media / 'splash.jpg.before-foundry').read_bytes(), b'first')
        self.assertEqual((self.media / 'splash.jpg.before-foundry.1').read_bytes(), b'second')

    def test_missing_artwork_leaves_existing_override_untouched(self):
        self.media.mkdir()
        (self.media / 'splash.jpg').write_bytes(b'keep')
        with patch.object(self.module.os.path, 'join', return_value=str(self.home / 'missing.png')):
            with self.assertRaises(OSError): self.module.install_startup_splash()
        self.assertEqual((self.media / 'splash.jpg').read_bytes(), b'keep')
        self.assertFalse((self.media / 'splash.png').exists())

    def test_modified_artwork_is_rejected_before_any_destination_change(self):
        with patch.object(self.module, 'ARTWORK_SHA256', 'invalid'):
            with self.assertRaises(ValueError): self.module.install_startup_splash()
        self.assertFalse(self.media.exists())

    def test_write_failure_keeps_previous_splash_and_removes_temporary_file(self):
        self.module.install_startup_splash()
        (self.media / 'splash.jpg').write_bytes(b'keep')
        with patch.object(self.module.tempfile, 'mkstemp', side_effect=OSError('read-only')):
            (self.media / 'splash.png').write_bytes(b'keep-png')
            with self.assertRaises(OSError): self.module.install_startup_splash()
        self.assertEqual((self.media / 'splash.jpg').read_bytes(), b'keep')
        self.assertEqual((self.media / 'splash.png').read_bytes(), b'keep-png')
        self.assertFalse(list(self.media.glob('.foundry-splash-*')))

    def test_build_installs_splash_before_optional_trailers_setup(self):
        build = load('foundry_build_splash_test', ROOT / 'src/script.program.foundry-build/default.py')
        def trailers():
            self.assertEqual((self.media / 'splash.png').read_bytes(), self.source.read_bytes())
            raise RuntimeError('Fixture stops before changing active skin')
        with patch.object(build, 'ensure_trailers', side_effect=trailers) as setup:
            build.main()
        setup.assert_called_once()

    def test_startup_artwork_is_separate_from_clean_generic_fallbacks(self):
        import hashlib
        expected='9d254d3949ab9dc2690ac285bc8da5a51b42c0644ec48566464a5aaf057c6212'
        self.assertNotEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),expected)
        self.module.install_startup_splash()
        for relative in ('media/foundry-home-backdrop.png','media/foundry-widget-base.png','media/streampilot/catalog-base.png'):
            self.assertEqual(hashlib.sha256((SKIN/relative).read_bytes()).hexdigest(),expected)

    def test_package_contains_dedicated_startup_artwork(self):
        import shutil
        import sys
        import zipfile
        sys.path.insert(0,str(ROOT/'tools'))
        from build_release import package
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            skin=root/'source'
            splash=skin/'media/foundry-backdrops/foundry-loading-splash.png'
            splash.parent.mkdir(parents=True)
            shutil.copyfile(self.source,splash)
            shutil.copyfile(SKIN/'addon.xml',skin/'addon.xml')
            _,record=package(skin,root/'output')
            with zipfile.ZipFile(root/'output'/record['path']) as archive:
                self.assertEqual(archive.read('skin.foundry/media/foundry-backdrops/foundry-loading-splash.png'),self.source.read_bytes())
