"""Offline guardrails for non-publishing development and packaged-source QA."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('foundry_packaged_qa', ROOT / 'tools/verify_packaged_sources.py')
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


class PackagedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'source/foundry-kodi-dist'
        self.root.mkdir(parents=True)
        self.workspace = self.base / 'packaged'
        self.packages = []
        for identifier in ('skin.foundry', 'script.foundry.helper', 'plugin.games.foundry',
                           'weather.foundry.canada', 'resource.uisounds.foundry.pulse'):
            self.add_package(identifier)
        (self.root / 'release.json').write_text(json.dumps({'release': '1.4.0', 'packages': self.packages}))
        self.release = qa.read_release(self.root)

    def add_package(self, identifier):
        manifest = '<addon id="%s" version="1.0.0" />' % identifier
        folder = self.root / identifier
        folder.mkdir()
        archive = folder / (identifier + '-1.0.0.zip')
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.writestr(identifier + '/addon.xml', manifest)
            bundle.writestr(identifier + '/payload.txt', 'exact packaged bytes')
        if identifier not in qa.SIBLINGS:
            source = self.root / 'src' / identifier
            source.mkdir(parents=True)
            (source / 'addon.xml').write_text(manifest)
            (source / 'payload.txt').write_text('different source bytes')
            (source / 'not-packaged.txt').write_text('must never leak into packaged tests')
        data = archive.read_bytes()
        self.packages.append({'id': identifier, 'version': '1.0.0',
                              'path': archive.relative_to(self.root).as_posix(),
                              'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

    def test_every_addon_source_comes_from_its_package(self):
        staged = qa.stage_workspace(self.root, self.workspace, self.release)
        for package in self.packages:
            identifier = package['id']
            target = (self.workspace / qa.SIBLINGS[identifier] if identifier in qa.SIBLINGS
                      else staged / 'src' / identifier)
            self.assertEqual((target / 'payload.txt').read_text(), 'exact packaged bytes')
            self.assertFalse((target / 'not-packaged.txt').exists())
        original = self.root / 'src/plugin.games.foundry'
        self.assertEqual((original / 'payload.txt').read_text(), 'different source bytes')
        self.assertTrue((original / 'not-packaged.txt').exists())

    def test_historical_packages_and_test_fixtures_are_copied_without_hardlinks(self):
        fixture = self.root / 'tests/fixtures/baseline.xml'
        fixture.parent.mkdir(parents=True)
        fixture.write_text('fixture')
        snapshot = self.root / 'releases/1.4.0-source-snapshot.json.gz'
        snapshot.parent.mkdir()
        snapshot.write_bytes(b'pinned snapshot')
        prior_qa = self.root / 'releases/1.4.0-qa/verification.json'
        prior_qa.parent.mkdir()
        prior_qa.write_text('stale pass must not be copied')
        staged = qa.stage_workspace(self.root, self.workspace, self.release)
        self.assertEqual((staged / 'tests/fixtures/baseline.xml').read_text(), 'fixture')
        self.assertEqual((staged / snapshot.relative_to(self.root)).read_bytes(), b'pinned snapshot')
        self.assertFalse((staged / prior_qa.relative_to(self.root)).exists())
        archive = qa.relative_path(self.packages[0]['path'])
        original = (self.root / archive).read_bytes()
        (staged / archive).write_bytes(b'rebuilt copy')
        self.assertEqual((self.root / archive).read_bytes(), original)

    def test_unpublished_source_addon_is_rejected(self):
        missing = self.root / 'src/plugin.missing'
        missing.mkdir()
        (missing / 'addon.xml').write_text('<addon id="plugin.missing" />')
        with self.assertRaisesRegex(ValueError, 'omitted'):
            qa.read_release(self.root)

    def test_modified_package_is_rejected(self):
        (self.root / self.packages[0]['path']).write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            qa.read_release(self.root)

    def test_duplicate_package_id_is_rejected(self):
        self.release['packages'].append(self.release['packages'][0])
        (self.root / 'release.json').write_text(json.dumps(self.release))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            qa.read_release(self.root)

    def test_existing_or_nested_workspace_is_rejected_without_deletion(self):
        for workspace in (self.root, self.root / 'nested', self.base):
            with self.subTest(workspace=workspace), self.assertRaises(ValueError):
                qa.stage_workspace(self.root, workspace, self.release)
        self.assertTrue((self.root / 'release.json').exists())

    def test_path_traversal_and_cross_platform_paths_are_rejected(self):
        for value in ('../escape', '/absolute', 'C:/escape', 'x\\escape', '', 'x/../escape', 'x/./file', 'x//file'):
            with self.subTest(path=value), self.assertRaises(ValueError):
                qa.relative_path(value)

    def test_zip_roots_and_symbolic_links_are_rejected(self):
        package = self.packages[0]
        for number, (name, mode) in enumerate((('wrong/addon.xml', 0),
                                             ('skin.foundry/../escape', 0),
                                             ('skin.foundry/link', stat.S_IFLNK | 0o777))):
            archive = self.base / ('unsafe-%d.zip' % number)
            with zipfile.ZipFile(archive, 'w') as bundle:
                entry = zipfile.ZipInfo(name)
                entry.external_attr = mode << 16
                bundle.writestr(entry, 'unsafe')
            with self.subTest(name=name), self.assertRaises(ValueError):
                qa.extract_package(archive, package, self.base / ('extract-%d' % number))
        self.assertFalse((self.base / 'escape').exists())

    def test_wrong_manifest_version_is_rejected(self):
        package = dict(self.packages[0], version='2.0.0')
        with self.assertRaisesRegex(ValueError, 'manifest differs'):
            qa.extract_package(self.root / package['path'], package, self.base / 'wrong-version')

    def test_success_runs_tests_then_rebuild_and_verification(self):
        output = self.base / 'qa'
        with patch.object(qa.subprocess, 'run') as run:
            staged = qa.verify(self.root, self.workspace, output)
        self.assertEqual([call.args[0][1] for call in run.call_args_list],
                         ['tools/run_tests.py', 'tools/build_release.py', 'tools/verify_release.py'])
        self.assertTrue(all(call.kwargs['cwd'] == staged for call in run.call_args_list))
        self.assertTrue(all(call.kwargs['check'] for call in run.call_args_list))
        result = json.loads((output / 'packaged-verification.json').read_text())
        self.assertTrue(result['passed'])
        self.assertTrue(result['source_trees_preserved'])

    def test_rebuild_change_fails_and_leaves_machine_readable_evidence(self):
        output = self.base / 'qa'
        def rebuild(command, **kwargs):
            if command[1] == 'tools/build_release.py':
                (kwargs['cwd'] / 'release.json').write_text('{}')
        with patch.object(qa.subprocess, 'run', side_effect=rebuild), self.assertRaisesRegex(ValueError, 'changed release.json'):
            qa.verify(self.root, self.workspace, output)
        result = json.loads((output / 'packaged-verification.json').read_text())
        self.assertFalse(result['passed'])
        self.assertEqual(result['stage'], 'deterministic_rebuild')
        self.assertEqual(json.loads((self.root / 'release.json').read_text())['release'], '1.4.0')


class DevelopmentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (ROOT / '.github/workflows/dev-validation.yml').read_text(encoding='utf-8')

    def test_development_validation_cannot_publish(self):
        self.assertIn('branches: [dev]', self.workflow)
        self.assertIn('workflow_dispatch:', self.workflow)
        self.assertIn('contents: read', self.workflow)
        self.assertIn('persist-credentials: false', self.workflow)
        for forbidden in ('contents: write', 'git push', 'git commit', 'gh release', 'deploy-pages'):
            self.assertNotIn(forbidden, self.workflow)

    def test_source_and_packaged_tests_precede_all_native_runners(self):
        self.assertIn('materialize_sources.py --release 1.4.0', self.workflow)
        self.assertLess(self.workflow.index('tools/run_tests.py'), self.workflow.index('tools/verify_packaged_sources.py'))
        for renderer in ('library', 'startup_splash', 'interface', 'games', 'weather'):
            self.assertGreater(self.workflow.index('tools/render_' + renderer + '.py'),
                               self.workflow.index('tools/verify_packaged_sources.py'))
        self.assertEqual(self.workflow.count("steps.packaged.outcome == 'success'"), 5)

    def test_all_evidence_is_retained_without_games_filename_collisions(self):
        self.assertIn('tools/render_games.py --output "$QA/games"', self.workflow)
        self.assertIn('name: Collect all native QA evidence\n        if: always()', self.workflow)
        self.assertIn('uses: actions/upload-artifact@v4\n        if: always()', self.workflow)
        self.assertIn('path: foundry-kodi-dist/releases/1.4.0-qa/', self.workflow)


if __name__ == '__main__':
    unittest.main()
