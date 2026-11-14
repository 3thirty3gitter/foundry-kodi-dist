"""Pinned QA host must not weaken product/native/publish gates."""
from pathlib import Path
import re
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATES = ('library', 'startup_splash', 'interface', 'weather', 'games', 'slate_navigation', 'slate_weather')


class NativeQARuntimeTests(unittest.TestCase):
    def test_official_base_and_complete_validated_runtime_are_locked(self):
        recipe = (ROOT / 'tools/native-qa/Dockerfile').read_text()
        self.assertRegex(recipe, r'FROM debian@sha256:[a-f0-9]{64}\n')
        locked = (ROOT / 'tools/native-qa/packages.lock').read_text().splitlines()
        packages = dict(line.split() for line in locked)
        self.assertEqual(len(packages), 414)
        for name in ('kodi', 'kodi-bin', 'kodi-data'):
            self.assertEqual(packages[name], '2:21.2+dfsg-4')
        self.assertEqual(packages['python3'], '3.13.5-1')
        self.assertIn('awk', recipe)
        self.assertIn('APT::Update::Error-Mode=any', recipe)
        self.assertIn('diff -u /qa-packages.lock /qa-package-versions.txt', recipe)
        for forbidden in ('allow-unauthenticated', 'trusted=yes', 'add-apt-repository'):
            self.assertNotIn(forbidden, recipe)

    def test_extracted_sources_read_only_and_only_qa_output_is_overlaid(self):
        wrapper = (ROOT / 'tools/run_native_qa.sh').read_text()
        self.assertIn('set -euo pipefail', wrapper)
        self.assertLess(wrapper.index('mkdir -p "$QA"'), wrapper.index('exec docker run'))
        self.assertIn('source=$apps,target=/work,readonly', wrapper)
        self.assertIn('source=$output,target=/work/foundry-kodi-dist/$QA', wrapper)
        self.assertEqual(wrapper.count('--mount '), 2)
        self.assertIn('--user "$(id -u):$(id -g)"', wrapper)
        self.assertIn('exec python3 "$@"', wrapper)
        self.assertIn('--rm --init --platform linux/amd64', wrapper)
        self.assertNotIn('--privileged', wrapper)

    def test_both_workflows_run_exact_seven_gates_and_preserve_evidence_and_timeouts(self):
        for name in ('dev-validation.yml', 'release.yml'):
            workflow = (ROOT / '.github/workflows' / name).read_text()
            with self.subTest(workflow=name):
                self.assertIn('docker build --platform linux/amd64', workflow)
                self.assertNotIn('sudo apt-get', workflow)
                self.assertEqual(workflow.count('run: bash tools/run_native_qa.sh tools/render_'), 7)
                self.assertEqual(workflow.count("steps.packaged.outcome == 'success'"), 7)
                self.assertEqual(workflow.count("steps.kodi.outcome == 'success'"), 7)
                blocks = re.findall(r'      - name: Render .*?(?=      - name:|      - uses:)', workflow, re.S)
                self.assertEqual(len(blocks), 7)
                for block, gate, timeout in zip(blocks, GATES, (6, 3, 8, 6, 6, 6, 6)):
                    self.assertIn('tools/render_' + gate + '.py', block)
                    self.assertIn('timeout-minutes: ' + str(timeout), block)
                    self.assertIn('!cancelled()', block)
                    self.assertIn('foundry-packaged-validation/foundry-kodi-dist', block)
                    self.assertIn('2>&1 | tee', block)
                self.assertIn('tools/render_weather.py --output "$QA"', workflow)
                self.assertIn('tools/render_games.py --output "$QA/games"', workflow)
                for evidence in ('native-image-inspect.json', 'native-package-versions.txt', 'kodi-version.txt', 'native-python-version.txt'):
                    self.assertIn(evidence, workflow)
                self.assertIn('name: Collect all native QA evidence\n        if: always()', workflow)
                self.assertIn('uses: actions/upload-artifact@v4\n        if: always()', workflow)
                self.assertNotIn('allow-unsupported-kodi', workflow)
                self.assertNotIn('continue-on-error', workflow)

    @unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'Linux CI shell contract')
    def test_wrapper_preserves_arguments_exit_code_and_precreates_output(self):
        with tempfile.TemporaryDirectory(prefix='native qa ') as temp:
            base = Path(temp)
            dist = base / 'apps/foundry-kodi-dist'
            dist.mkdir(parents=True)
            bin_dir = base / 'bin'
            bin_dir.mkdir()
            docker = bin_dir / 'docker'
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nexit 17\n')
            docker.chmod(0o755)
            environment = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                               QA='releases/1.5.3-qa', NATIVE_QA_IMAGE='locked-test-runtime')
            result = subprocess.run(['bash', str(ROOT / 'tools/run_native_qa.sh'),
                                     'tools/render_games.py', '--output', 'output with spaces'],
                                    cwd=dist, env=environment, text=True, capture_output=True)
            self.assertEqual(result.returncode, 17, result.stderr)
            arguments = result.stdout.splitlines()
            self.assertEqual(arguments[-3:], ['tools/render_games.py', '--output', 'output with spaces'])
            self.assertIn('type=bind,source=' + str(base / 'apps') + ',target=/work,readonly', arguments)
            self.assertIn('locked-test-runtime', arguments)
            self.assertTrue((dist / 'releases/1.5.3-qa').is_dir())

    def test_release_still_publishes_only_after_success_on_main(self):
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        self.assertIn("if: success() && github.ref == 'refs/heads/main'", workflow)
        self.assertIn('python tools/record_release_validation.py', workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)


if __name__ == '__main__':
    unittest.main()
