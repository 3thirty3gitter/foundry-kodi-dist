"""Publication guard tests using disposable files and mocked Git calls only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
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
        self.qa = self.root / 'releases/1.5.0-qa'
        self.packages = [{'id': 'skin.foundry', 'version': '1.5.0',
                          'path': 'skin.foundry/skin.foundry-1.5.0.zip',
                          'size': 10, 'sha256': 'a' * 64},
                         {'id': 'repository.foundry', 'version': '1.2.0',
                          'path': 'repository.foundry/repository.foundry-1.2.0.zip',
                          'size': 12, 'sha256': 'b' * 64},
                         {'id': 'plugin.games.foundry', 'version': '0.1.0',
                          'path': 'plugin.games.foundry/plugin.games.foundry-0.1.0.zip',
                          'size': 10, 'sha256': 'e' * 64}]
        self.manifest = {'release': '1.5.0', 'skin': '1.5.0', 'packages': self.packages}
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
        self.write(self.root / 'releases/1.5.0-sources.json', {
            'release': '1.5.0', 'helper': '1.3.0', 'source_commits': {'skin.foundry-nimbus': 'c' * 40},
            'validation': {'status': 'pending'}})
        summary = {'successful': True, 'tests': 650, 'errors': 0, 'failures': 0, 'skipped': 0}
        for name in ('source-tests.json', 'packaged-tests.json'):
            self.write(self.qa / name, summary)
        self.write(self.qa / 'packaged-verification.json', {
            'passed': True, 'release': '1.5.0', 'stage': 'complete',
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
            'weather-verification.json': {'passed': True, 'checks': ['provider_entrypoint']},
            'games/games-verification.json': {'passed': True, 'release': '1.5.0',
                'packages': self.packages, 'renderer': 'Native Kodi 21.3',
                'native_gameclient_log': {'complete': True, 'native_gameclient_path': True, 'failures': []},
                'production_entrypoint_sha256': 'a' * 64,
                'skin_boolean_errors': {'new_errors': [], 'unchanged_timer_sha256': 'c2c90596e9362a97dc5ad2e79004273fe014954bf0f976cc39f78e7cf2e02614',
                    'posterflow_proof': {'current_sha256':'ebcdc5840651253eb0bae2d1241578624d3ee132c5a63ad53a7d58aa2e8c2993','published_140_sha256':'ebcdc5840651253eb0bae2d1241578624d3ee132c5a63ad53a7d58aa2e8c2993','bytes_equal':True,
                        'current_inputs':{name:'String.IsEqual(ListItem.DBType,'+kind+')' for name,kind in (('isMovie','movie'),('isTVShow','tvshow'),('isSeason','season'),('isEpisode','episode'))},
                        'published_140_inputs':{name:'String.IsEqual(ListItem.DBType,'+kind+')' for name,kind in (('isMovie','movie'),('isTVShow','tvshow'),('isSeason','season'),('isEpisode','episode'))}}},
                'startup_readiness': {'passed': True, 'quiet_seconds': 2, 'actual_skin_log': {'ready':True}, 'home_signature': {'category':'music'}, 'completed_game_widgets': [dict(mode=mode, phase='completed', error='') for mode in ('recent', 'favorites')]},
                'shipped_skin_hashes': {'xml/MyGames.xml': 'f' * 64},
                'assertions': {name: True for name in gate.GAMES_ASSERTIONS},
                'checks': [{'case': name,'capture_state_stable_seconds':.5,'png_completion_ack':True} for name in gate.GAMES_CASES],
                'capture_acknowledgments':[dict(sequence=index+1,case=name,passed=True,dimensions=[1920,1080],stable_seconds=.5) for index,name in enumerate(gate.GAMES_CASES)]}}
        movies = dict(approved_count=13, rendered_approved_count=13,
                      copied_skin_inputs_sha256={'xml/Variables_Artwork.xml': 'f' * 64},
                      cases=[])
        movies.update({name: True for name in gate.MOVIE_FLAGS})
        entries = [('movie-wallpaper-' + label.lower().replace(' ', '-'), label) for label in gate.MOVIE_LABELS]
        entries += [('movie-wallpaper-unknown', ''), ('movie-wallpaper-tv', ''),
                    ('movie-wallpaper-mixed', ''), ('movie-wallpaper-custom', 'Trending'),
                    ('movie-wallpaper-title-fanart', 'Trending')]
        for name, label in entries:
            movies['cases'].append(dict(case=name, canonical_label=label,
                screenshot=name + '.png', pixel_mean_max_errors=[0, 1, 2]))
        movies['cases'][0].update(paging_roundtrip_retains_context=True,
                                 native_list_loss_rehydration_retains_context=True)
        reports['verification.json']['movie_submenu_wallpapers'] = movies
        interface = reports['interface-verification.json']
        interface.update(kodi_version={'major': 21}, diagnostic_only=False,
            playback_traceback_gate=True, reported_device_error_reproduced=False,
            playback_stop_back_cycles=[])
        for index in range(3):
            entry = dict(native_ready=True, size=6, focus=50, position=3, selected=3,
                         submenu='Trending', message='', source='fixture://catalog',
                         file='fixture.avi', fanart='art.png' if index else '')
            before = dict(window=13000, playback_parent=10004, catalog=dict(entry))
            interface['playback_stop_back_cycles'].append(dict(cycle=index + 1,
                with_item_fanart=index > 0, before=before,
                after_stop=dict(window=13000, catalog=dict(entry)),
                after_back=dict(window=10004, catalog=None)))
        reports['interface-playback-errors.json'] = {'complete': True, 'failures': []}
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
        record = gate.evidence(self.root, '1.5.0')
        self.assertEqual(record['status'], 'ci_passed_target_device_checks_pending')
        self.assertIn('unverified', record['target_device_verification'])
        self.assertEqual(set(record['native_reports']), set(gate.NATIVE))
        self.assertEqual(len(record['native_reports']), 5)
        self.assertIn('games/games-verification.json', record['native_reports'])
        self.assertTrue((self.qa / 'native/games/games-verification.json').exists())

    def public_verifier(self):
        spec = importlib.util.spec_from_file_location('foundry_public_gate_test', ROOT / 'tools/verify_public_downloads.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'record_release_validation': gate}), \
                patch.object(subprocess, 'check_output', return_value='c' * 40):
            spec.loader.exec_module(module)
        return module

    def test_old_release_rejects_games_and_new_release_requires_exact_package(self):
        for release, packages in (('1.4.0', self.packages), ('1.4.1', self.packages),
                                  ('1.5.0', self.packages[:-1]),
                                  ('1.5.0', self.packages + [self.packages[-1]]),
                                  ('1.5.0', self.packages[:-1] + [dict(self.packages[-1], version='0.0.1')])):
            with self.subTest(release=release, packages=packages), self.assertRaises(ValueError):
                gate.require_release_scope({'release': release, 'packages': packages})
        gate.require_release_scope(self.manifest)

    def test_every_games_completion_contract_and_capture_is_required(self):
        path = self.qa / 'native/games/games-verification.json'
        original = path.read_bytes()
        for name in gate.GAMES_ASSERTIONS:
            report = json.loads(original)
            report['assertions'][name] = False
            self.write(path, report)
            with self.subTest(assertion=name), self.assertRaises(AssertionError):
                gate.evidence(self.root, '1.5.0')
        for name in gate.GAMES_CASES:
            report = json.loads(original)
            report['checks'] = [check for check in report['checks'] if check['case'] != name]
            self.write(path, report)
            with self.subTest(case=name), self.assertRaises(AssertionError):
                gate.evidence(self.root, '1.5.0')
        path.write_bytes(original)
        for changes in ({'passed': False}, {'release': '1.4.0'}, {'packages': []},
                        {'renderer': 'Kodi 20.5'}, {'shipped_skin_hashes': {}},
                        {'native_gameclient_log': {'complete': False, 'native_gameclient_path': True, 'failures': []}},
                        {'native_gameclient_log': {'complete': True, 'native_gameclient_path': False, 'failures': []}},
                        {'native_gameclient_log': {'complete': True, 'native_gameclient_path': True, 'failures': ['traceback']}},
                        {'production_entrypoint_sha256': ''},
                        {'startup_readiness': {'passed': False, 'quiet_seconds': 2, 'completed_game_widgets': []}},
                        {'startup_readiness': {'passed': True, 'quiet_seconds': 0, 'completed_game_widgets': []}},
                        {'startup_readiness': {'passed': True, 'quiet_seconds': 2, 'actual_skin_log': {'ready':True}, 'home_signature': {'category':'music'}, 'completed_game_widgets': [{'mode': 'recent', 'phase': 'started', 'error': ''}]}},
                        {'skin_boolean_errors': {'new_errors': ['bad.games'], 'unchanged_timer_sha256': '0' * 64}}):
            report = json.loads(original); report.update(changes); self.write(path, report)
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                gate.evidence(self.root, '1.5.0')
        path.write_bytes(original)

    def test_capture_and_published_posterflow_proofs_cannot_be_bypassed(self):
        path=self.qa/'native/games/games-verification.json';original=path.read_bytes()
        for failure in ('capture-stability','capture-ack','ack-size','ack-sequence','poster-current','poster-published','poster-bytes','poster-inputs'):
            report=json.loads(original);poster=report['skin_boolean_errors']['posterflow_proof']
            if failure=='capture-stability':report['checks'][0]['capture_state_stable_seconds']=.1
            elif failure=='capture-ack':report['checks'][0]['png_completion_ack']=False
            elif failure=='ack-size':report['capture_acknowledgments'][0]['dimensions']=[100,100]
            elif failure=='ack-sequence':report['capture_acknowledgments'][0]['sequence']=99
            elif failure=='poster-current':poster['current_sha256']='0'*64
            elif failure=='poster-published':poster['published_140_sha256']='0'*64
            elif failure=='poster-bytes':poster['bytes_equal']=False
            elif failure=='poster-inputs':poster['current_inputs']['isMovie']='changed'
            self.write(path,report)
            with self.subTest(failure=failure),self.assertRaises(AssertionError):gate.evidence(self.root,'1.5.0')
        path.write_bytes(original)

    def test_all_thirteen_movies_native_routes_and_negatives_are_required(self):
        path = self.qa / 'native/verification.json'
        original = path.read_bytes()
        mutations = [{name: False} for name in gate.MOVIE_FLAGS]
        mutations += [{'approved_count': 12}, {'rendered_approved_count': 12},
                      {'cases': []}, {'copied_skin_inputs_sha256': {}},
                      {'copied_skin_inputs_sha256': {'xml/file.xml': 'not-a-hash'}}]
        for changes in mutations:
            report = json.loads(original); report['movie_submenu_wallpapers'].update(changes)
            self.write(path, report)
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                gate.evidence(self.root, '1.5.0')
        for key, value in (('canonical_label', 'Wrong'), ('screenshot', 'wrong.png'),
                           ('pixel_mean_max_errors', [0, 1, 12]),
                           ('paging_roundtrip_retains_context', False),
                           ('native_list_loss_rehydration_retains_context', False)):
            report = json.loads(original)
            report['movie_submenu_wallpapers']['cases'][0][key] = value
            self.write(path, report)
            with self.subTest(field=key), self.assertRaises(AssertionError):
                gate.evidence(self.root, '1.5.0')
        path.write_bytes(original)

    def test_playback_stop_back_and_traceback_proofs_cannot_be_omitted(self):
        path = self.qa / 'native/interface-verification.json'
        original = path.read_bytes()
        for changes in ({'kodi_version': {'major': 20}}, {'diagnostic_only': True},
                        {'playback_traceback_gate': False}, {'playback_stop_back_cycles': []}):
            report = json.loads(original); report.update(changes); self.write(path, report)
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                gate.evidence(self.root, '1.5.0')
        for key, value in (('size', 0), ('focus', 51), ('position', 0),
                           ('selected', 0), ('submenu', ''), ('message', 'error'),
                           ('source', 'changed'), ('file', 'changed'), ('fanart', 'changed')):
            report = json.loads(original)
            report['playback_stop_back_cycles'][0]['after_stop']['catalog'][key] = value
            self.write(path, report)
            with self.subTest(invariant=key), self.assertRaises(AssertionError):
                gate.evidence(self.root, '1.5.0')
        report = json.loads(original)
        report['playback_stop_back_cycles'][0]['after_back']['window'] = 10000
        self.write(path, report)
        with self.assertRaises(AssertionError): gate.evidence(self.root, '1.5.0')
        path.write_bytes(original)
        errors = self.qa / 'native/interface-playback-errors.json'
        for value in ({'complete': False, 'failures': []}, {'complete': True, 'failures': ['traceback']}):
            self.write(errors, value)
            with self.subTest(errors=value), self.assertRaises(AssertionError):
                gate.evidence(self.root, '1.5.0')

    def test_public_verification_retains_all_five_native_reports(self):
        public = self.public_verifier()
        for name in ('addons.xml', 'addons.xml.md5', 'index.html', 'skin.html',
                     'repository.foundry-1.2.0.zip', 'script.program.foundry-build.zip',
                     'script.program.foundry-bootstrap.zip'):
            (self.root / name).write_bytes(b'fixture')
        with patch.object(public, 'ROOT', self.root), patch.object(public, 'download'), \
                patch.object(public, 'package_check', side_effect=lambda task: dict(task[1], verified=True)):
            public.main()
        record = json.loads((self.root / 'releases/1.5.0-verification.json').read_text())
        native = {key for key in record['validation'] if key.startswith('native_kodi_')}
        self.assertEqual(native, {'native_kodi_interface', 'native_kodi_startup_splash',
                                  'native_kodi_fixture', 'native_kodi_weather', 'native_kodi_games'})
        self.assertEqual(len(record['public_packages']), 2 * len(self.packages))
        self.assertTrue(any('no Shield gameplay' in item for item in record['limitations']))

    def test_public_verification_rejects_failed_shipped_feature_before_downloads(self):
        self.update('native/weather-verification.json', passed=False)
        public = self.public_verifier()
        with patch.object(public, 'ROOT', self.root), patch.object(public, 'download') as download:
            with self.assertRaises((AssertionError, ValueError)):
                public.main()
            download.assert_not_called()

    def test_failed_source_or_packaged_suite_is_rejected(self):
        for name in ('source-tests.json', 'packaged-tests.json'):
            original = (self.qa / name).read_bytes()
            for changes in ({'successful': False}, {'errors': 1}, {'failures': 1}, {'tests': 0}):
                with self.subTest(report=name, changes=changes):
                    self.update(name, **changes)
                    with self.assertRaises((AssertionError, ValueError)):
                        gate.evidence(self.root, '1.5.0')
                    (self.qa / name).write_bytes(original)

    def test_failed_deterministic_rebuild_is_rejected(self):
        for changes in ({'passed': False}, {'deterministic_rebuild': False}):
            with self.subTest(changes=changes):
                original = (self.qa / 'packaged-verification.json').read_bytes()
                self.update('packaged-verification.json', **changes)
                with self.assertRaises((AssertionError, ValueError)):
                    gate.evidence(self.root, '1.5.0')
                (self.qa / 'packaged-verification.json').write_bytes(original)

    def test_each_missing_native_report_is_rejected(self):
        for name in gate.NATIVE:
            path = self.qa / 'native' / name
            original = path.read_bytes()
            with self.subTest(report=name):
                path.unlink()
                with self.assertRaises((FileNotFoundError, AssertionError, ValueError)):
                    gate.evidence(self.root, '1.5.0')
                path.write_bytes(original)

    def test_false_weather_pass_flag_is_rejected(self):
        for name in ('weather-verification.json',):
            path = 'native/' + name
            original = (self.qa / path).read_bytes()
            with self.subTest(report=name):
                self.update(path, passed=False)
                with self.assertRaises((AssertionError, ValueError)):
                    gate.evidence(self.root, '1.5.0')
                (self.qa / path).write_bytes(original)

    def test_packaged_evidence_for_another_release_is_rejected(self):
        self.update('packaged-verification.json', release='1.3.9')
        with self.assertRaises((AssertionError, ValueError)):
            gate.evidence(self.root, '1.5.0')

    def test_packaged_evidence_for_other_bytes_is_rejected(self):
        packages = [dict(package) for package in self.packages]
        packages[0]['sha256'] = 'd' * 64
        self.update('packaged-verification.json', packages=packages)
        with self.assertRaises((AssertionError, ValueError)):
            gate.evidence(self.root, '1.5.0')

    def test_qa_manifest_for_other_bytes_is_rejected(self):
        value = dict(self.manifest, packages=[])
        self.write(self.qa / 'release.json', value)
        with self.assertRaises((AssertionError, ValueError)):
            gate.evidence(self.root, '1.5.0')

    def test_empty_library_or_failed_native_contract_is_rejected(self):
        cases = [('native/verification.json', {'checks': []}),
                 ('native/startup-splash-verification.json', {'real_kodi_cold_start': False}),
                 ('native/interface-verification.json', {'home_favorites_row_focus_and_horizontal_navigation': False})]
        for name, changes in cases:
            original = (self.qa / name).read_bytes()
            with self.subTest(report=name):
                self.update(name, **changes)
                with self.assertRaises((AssertionError, ValueError)):
                    gate.evidence(self.root, '1.5.0')
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
                self.assertEqual(json.loads((self.root / 'releases/1.5.0-sources.json').read_text())['validation'],
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
        source = self.root / 'releases/1.5.0-sources.json'
        original = source.read_bytes()
        for ref in ('refs/heads/dev', 'refs/tags/1.5.0', ''):
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
        self.assertIn('releases/1.5.0-sources.json', paths)
        self.assertIn('releases/1.5.0-qa/native/new-screen.png', paths)
        self.assertIn('repository.foundry-1.2.0.zip', paths)
        for package in self.packages:
            self.assertIn(package['path'], paths)
            self.assertIn(package['path'] + '.sha256', paths)
        self.assertNotIn('src/example/default.py', paths)
        self.assertNotIn('skin.foundry/skin.foundry-1.3.9.zip', paths)
        self.assertNotIn('releases/1.5.0-qa/native/kodi.log', paths)
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
        self.assertIn('tools/record_release_validation.py --check-scope', self.workflow)

    def test_failure_artifacts_are_preserved_and_games_is_required(self):
        self.assertIn('name: Collect all native QA evidence\n        if: always()', self.workflow)
        self.assertIn('uses: actions/upload-artifact@v4\n        if: always()', self.workflow)
        self.assertIn('tools/render_games.py --output', self.workflow)
        self.assertLess(self.workflow.index('actions/upload-artifact@v4'),
                        self.workflow.index('name: Publish verified packages'))

    def test_immutable_resource_guard_precedes_publication(self):
        guard = 'git diff --exit-code -- repository.foundry resource.images.foundry.wallpapers resource.images.foundry.osd'
        publish = self.workflow.split('name: Publish verified packages and repository feed together', 1)[1]
        self.assertIn(guard, publish)
        self.assertLess(publish.index(guard), publish.index('python tools/record_release_validation.py'))


if __name__ == '__main__':
    unittest.main()
