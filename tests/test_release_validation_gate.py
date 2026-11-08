"""Publication guard tests using disposable files and mocked Git calls only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('foundry_release_gate', ROOT / 'tools/record_release_validation.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.qa = self.root / 'releases/1.4.0-qa'
        self.packages = [{'id': 'skin.foundry', 'version': '1.4.0',
                          'path': 'skin.foundry/skin.foundry-1.4.0.zip',
                          'size': 10, 'sha256': 'a' * 64},
                         {'id': 'repository.foundry', 'version': '1.2.0',
                          'path': 'repository.foundry/repository.foundry-1.2.0.zip',
                          'size': 12, 'sha256': 'b' * 64}]
        self.manifest = {'release': '1.4.0', 'packages': self.packages}
        self.write(self.root / 'release.json', self.manifest)
        self.write(self.qa / 'release.json', self.manifest)
        self.committed = {}
        for package in self.packages:
            for name, data in ((package['path'], b'fixture package bytes'),
                               (package['path'] + '.sha256', (package['sha256'] + '\n').encode())):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                self.committed[name] = data
        self.write(self.root / 'releases/1.4.0-sources.json', {'release': '1.4.0', 'validation': {'status': 'pending'}})
        summary = {'successful': True, 'tests': 650, 'errors': 0, 'failures': 0, 'skipped': 0}
        for name in ('source-tests.json', 'packaged-tests.json'):
            self.write(self.qa / name, summary)
        self.write(self.qa / 'packaged-verification.json', {
            'passed': True, 'release': '1.4.0', 'stage': 'complete',
            'deterministic_rebuild': True, 'source_trees_preserved': True,
            'packages': self.packages})
        reports = {
            'verification.json': {'renderer': 'Native Kodi 21.3', 'canvas': [1920, 1080],
                                  'checks': [{'section': 'Native favorites', 'playback_not_started': True}]},
            'startup-splash-verification.json': {'real_kodi_cold_start': True,
                                                'writable_home_override_selected': True,
                                                'approved_artwork_unchanged': True},
            'interface-verification.json': {'home_favorites_row_focus_and_horizontal_navigation': True,
                                            'home_favorites_back_returns_menu': True,
                                            'pulse_native_resource_selected': True,
                                            'audible_output_verified': False,
                                            'widget_metadata_top_left': True,
                                            'vod_rounded_frame': True, 'live_rounded_frame_preview': True},
            'games/verification.json': {'passed': True, 'release': '1.4.0',
                                        'checks': [{'case': 'games-console-listing'}],
                                        'assertions': {'screenshots_verified': True,
                                                       'skin_boolean_parse_errors_absent': True}},
            'weather-verification.json': {'passed': True, 'checks': ['provider_entrypoint']}}
        for name, report in reports.items():
            self.write(self.qa / 'native' / name, report)
        environment = patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main',
                                              'GITHUB_SHA': 'c' * 40,
                                              'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_ATTEMPT': '2'})
        environment.start()
        self.addCleanup(environment.stop)
        (self.qa / 'source-commit.txt').write_text('c' * 40 + '\n')
        (self.qa / 'workflow-run.txt').write_text('12345/2\n')

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def update(self, relative, **changes):
        path = self.qa / relative
        value = json.loads(path.read_text())
        value.update(changes)
        self.write(path, value)

    def test_complete_evidence_keeps_target_device_limits_explicit(self):
        record = gate.evidence(self.root, '1.4.0')
        self.assertEqual(record['status'], 'ci_passed_target_device_checks_pending')
        self.assertIn('unverified', record['target_device_verification'])
        self.assertEqual(set(record['native_reports']), set(gate.NATIVE))

    def test_failed_source_or_packaged_suite_is_rejected(self):
        for name in ('source-tests.json', 'packaged-tests.json'):
            original = (self.qa / name).read_bytes()
            for changes in ({'successful': False}, {'errors': 1}, {'failures': 1}, {'tests': 0}):
                with self.subTest(report=name, changes=changes):
                    self.update(name, **changes)
                    with self.assertRaises((AssertionError, ValueError)):
                        gate.evidence(self.root, '1.4.0')
                    (self.qa / name).write_bytes(original)

    def test_failed_deterministic_rebuild_is_rejected(self):
        for changes in ({'passed': False}, {'deterministic_rebuild': False}):
            with self.subTest(changes=changes):
                original = (self.qa / 'packaged-verification.json').read_bytes()
                self.update('packaged-verification.json', **changes)
                with self.assertRaises((AssertionError, ValueError)):
                    gate.evidence(self.root, '1.4.0')
                (self.qa / 'packaged-verification.json').write_bytes(original)

    def test_each_missing_native_report_is_rejected(self):
        for name in gate.NATIVE:
            path = self.qa / 'native' / name
            original = path.read_bytes()
            with self.subTest(report=name):
                path.unlink()
                with self.assertRaises((FileNotFoundError, AssertionError, ValueError)):
                    gate.evidence(self.root, '1.4.0')
                path.write_bytes(original)

    def test_false_weather_or_games_pass_flag_is_rejected(self):
        for name in ('weather-verification.json', 'games/verification.json'):
            path = 'native/' + name
            original = (self.qa / path).read_bytes()
            with self.subTest(report=name):
                self.update(path, passed=False)
                with self.assertRaises((AssertionError, ValueError)):
                    gate.evidence(self.root, '1.4.0')
                (self.qa / path).write_bytes(original)

    def test_packaged_evidence_for_another_release_is_rejected(self):
        self.update('packaged-verification.json', release='1.3.9')
        with self.assertRaises((AssertionError, ValueError)):
            gate.evidence(self.root, '1.4.0')

    def test_packaged_evidence_for_other_bytes_is_rejected(self):
        packages = [dict(package) for package in self.packages]
        packages[0]['sha256'] = 'd' * 64
        self.update('packaged-verification.json', packages=packages)
        with self.assertRaises((AssertionError, ValueError)):
            gate.evidence(self.root, '1.4.0')

    def test_qa_manifest_for_other_bytes_is_rejected(self):
        value = dict(self.manifest, packages=[])
        self.write(self.qa / 'release.json', value)
        with self.assertRaises((AssertionError, ValueError)):
            gate.evidence(self.root, '1.4.0')

    def test_empty_library_or_failed_native_contract_is_rejected(self):
        cases = [('native/verification.json', {'checks': []}),
                 ('native/startup-splash-verification.json', {'real_kodi_cold_start': False}),
                 ('native/interface-verification.json', {'home_favorites_row_focus_and_horizontal_navigation': False})]
        for name, changes in cases:
            original = (self.qa / name).read_bytes()
            with self.subTest(report=name):
                self.update(name, **changes)
                with self.assertRaises((AssertionError, ValueError)):
                    gate.evidence(self.root, '1.4.0')
                (self.qa / name).write_bytes(original)

    def committed_bytes(self, command, **kwargs):
        self.assertEqual(command[:2], ['git', 'show'])
        return self.committed[command[2].removeprefix('HEAD:')]

    def test_unchanged_versioned_zip_and_sidecar_bytes_are_accepted(self):
        with patch.object(gate.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as git, \
                patch.object(gate.subprocess, 'check_output', side_effect=self.committed_bytes) as show:
            gate.require_unchanged_packages(self.root, self.manifest)
        self.assertEqual(git.call_count, 2 * len(self.packages))
        self.assertEqual(show.call_count, 2 * len(self.packages))

    def test_changed_versioned_zip_or_sidecar_is_rejected_before_any_staging(self):
        for name in (self.packages[0]['path'], self.packages[0]['path'] + '.sha256'):
            with self.subTest(path=name):
                (self.root / name).write_bytes(b'changed same-version bytes')
                with patch.object(gate, 'ROOT', self.root), \
                        patch.object(gate.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as git, \
                        patch.object(gate.subprocess, 'check_output', side_effect=self.committed_bytes):
                    with self.assertRaisesRegex(AssertionError, 'Refusing changed versioned package'):
                        gate.main()
                self.assertFalse(any(call.args[0][:2] == ['git', 'add'] for call in git.call_args_list))
                self.assertEqual(json.loads((self.root / 'releases/1.4.0-sources.json').read_text())['validation'],
                                 {'status': 'pending'})
                (self.root / name).write_bytes(self.committed[name])

    def test_new_untracked_versioned_packages_do_not_require_head_bytes(self):
        with patch.object(gate.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), \
                patch.object(gate.subprocess, 'check_output') as show:
            gate.require_unchanged_packages(self.root, self.manifest)
        show.assert_not_called()

    def test_package_path_traversal_is_rejected_before_git(self):
        manifest = dict(self.manifest, packages=[dict(self.packages[0], path='../escape.zip')])
        with patch.object(gate.subprocess, 'run') as git:
            with self.assertRaises((AssertionError, ValueError)):
                gate.require_unchanged_packages(self.root, manifest)
        git.assert_not_called()

    def test_non_main_or_unset_ref_cannot_stage_or_rewrite_evidence(self):
        source = self.root / 'releases/1.4.0-sources.json'
        original = source.read_bytes()
        for ref in ('refs/heads/dev', 'refs/tags/1.4.0', ''):
            with self.subTest(ref=ref), patch.dict(os.environ, {'GITHUB_REF': ref}), \
                    patch.object(gate, 'ROOT', self.root), patch.object(gate.subprocess, 'run') as git:
                with self.assertRaises((AssertionError, ValueError)):
                    gate.main()
                git.assert_not_called()
                self.assertEqual(source.read_bytes(), original)

    def test_staging_names_only_current_packages_metadata_and_qa(self):
        for name in ('native/new-screen.png', 'native/kodi.log'):
            path = self.qa / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        unrelated = self.root / 'src/example/default.py'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('source must not be staged')
        historical = self.root / 'skin.foundry/skin.foundry-1.3.9.zip'
        historical.parent.mkdir(exist_ok=True)
        historical.write_bytes(b'history must not be staged')
        with patch.object(gate, 'ROOT', self.root), \
                patch.object(gate, 'evidence', return_value={'status': 'test-only'}), \
                patch.object(gate.subprocess, 'check_output', side_effect=self.committed_bytes), \
                patch.object(gate.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='')) as git:
            gate.main()
        adds = [call.args[0] for call in git.call_args_list if call.args[0][:2] == ['git', 'add']]
        self.assertEqual(len(adds), 1)
        self.assertEqual(adds[0][:3], ['git', 'add', '--'])
        paths = set(adds[0][3:])
        self.assertIn('releases/1.4.0-sources.json', paths)
        self.assertIn('releases/1.4.0-qa/native/new-screen.png', paths)
        self.assertIn('repository.foundry-1.2.0.zip', paths)
        for package in self.packages:
            self.assertIn(package['path'], paths)
            self.assertIn(package['path'] + '.sha256', paths)
        self.assertNotIn('src/example/default.py', paths)
        self.assertNotIn('skin.foundry/skin.foundry-1.3.9.zip', paths)
        self.assertNotIn('releases/1.4.0-qa/native/kodi.log', paths)
        self.assertFalse(any('*' in path or path in ('.', 'src', 'releases') for path in paths))


class ReleaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (ROOT / '.github/workflows/release.yml').read_text(encoding='utf-8')

    def test_job_and_publish_step_both_require_main(self):
        self.assertIn("validate:\n    if: github.ref == 'refs/heads/main'", self.workflow)
        publish = self.workflow.split('name: Publish verified packages and repository feed together', 1)[1]
        self.assertIn("if: success() && github.ref == 'refs/heads/main'", publish)

    def test_failed_validation_cannot_be_downgraded_to_success(self):
        self.assertNotIn('continue-on-error:', self.workflow)
        self.assertIn('shell: bash', self.workflow)  # Actions runs explicit bash with -e -o pipefail.
        self.assertEqual(self.workflow.count("steps.packaged.outcome == 'success'"), 5)
        self.assertEqual(self.workflow.count("steps.kodi.outcome == 'success'"), 5)

    def test_failure_artifacts_and_games_evidence_are_preserved(self):
        self.assertIn('name: Collect all native QA evidence\n        if: always()', self.workflow)
        self.assertIn('uses: actions/upload-artifact@v4\n        if: always()', self.workflow)
        self.assertIn('tools/render_games.py --output "$QA/games"', self.workflow)
        self.assertLess(self.workflow.index('actions/upload-artifact@v4'),
                        self.workflow.index('name: Publish verified packages'))

    def test_immutable_resource_guard_precedes_publication(self):
        guard = 'git diff --exit-code -- repository.foundry resource.images.foundry.wallpapers resource.images.foundry.osd'
        self.assertIn(guard, self.workflow)
        self.assertLess(self.workflow.index(guard), self.workflow.index('python tools/record_release_validation.py'))


if __name__ == '__main__':
    unittest.main()
