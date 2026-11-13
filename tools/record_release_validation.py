"""Record completed CI evidence and stage only the generated release payload.

The release workflow invokes this after all validation steps pass. It never
pushes, changes branch permissions, or stages source edits or historical ZIPs.
"""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ('verification.json', 'startup-splash-verification.json',
          'interface-verification.json', 'weather-verification.json',
          'games/games-verification.json')
MOVIE_LABELS = ('Trending', 'Trending Recent', 'Popular', 'Popular Today', 'Premieres',
                'Latest Releases', 'Most Watched', 'Most Favorited', 'Top 10 Box Office',
                'Blockbusters', 'In Theaters', 'Up Coming', 'Oscar Winners')
EXTRA_MOVIE_LABELS = ('Genres', 'Providers', 'Languages', 'Years', 'Decades', 'Certifications',
                      'Because You Watched...', 'Watched', 'Recently Watched', 'In Progress')
MOVIE_FLAGS = ('passed', 'custom_background_preserved', 'selected_title_fanart_preserved',
               'tv_mixed_unknown_rejected', 'paging_and_rehydration_context_preserved')
GAMES_ASSERTIONS = ('console_listing', 'capture_state_settled', 'screenshot_encoding_acknowledged', 'automatic_games_view_selected', 'focused_hero_metadata', 'remote_navigation',
                    'page_back_focus', 'favorite_persistence', 'favorite_refresh_complete',
                    'favorites_native_route', 'fresh_directory_acknowledgments',
                    'search_results', 'search_cancel', 'search_cancel_retains_listing',
                    'search_cancel_invoker_completed', 'launch_cancel_invoker_completed',
                    'native_gameclient_path_verified', 'native_tracebacks_absent',
                    'full_home_startup_widgets_completed',
                    'missing_core_dialog', 'launch_cancel_focus',
                    'cancel_does_not_record_play', 'shipped_skin_bytes_unchanged',
                    'screenshots_verified', 'new_skin_boolean_parse_errors_absent')
GAMES_CASES = ('games-consoles', 'games-automatic-view', 'games-focused-hero', 'games-page-two',
               'games-page-back-focus', 'games-favorite-refresh-complete',
               'games-favorites', 'games-search-results', 'games-search-cancel',
               'games-missing-core', 'games-launch-cancel-focus')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require_release_scope(manifest):
    """Keep published 1.4 immutable and require the next release's Games scope."""
    games = [package for package in manifest['packages'] if package['id'] == 'plugin.games.foundry']
    version = tuple(int(part) for part in manifest['release'].split('.'))
    if version < (1, 5, 0):
        if games: raise ValueError('Games is deferred from releases before 1.5.0')
    elif len(games) != 1 or games[0].get('version') != '0.1.0':
        raise ValueError('Foundry 1.5.0+ requires exactly one Games 0.1.0 package and native validation')


def evidence(root, release):
    manifest = read(root / 'release.json')
    require_release_scope(manifest)
    qa = root / 'releases' / (release + '-qa')
    source, packaged = read(qa / 'source-tests.json'), read(qa / 'packaged-tests.json')
    for report in (source, packaged):
        assert report['successful'] and report['tests'] > 0
        assert report['failures'] == report['errors'] == 0
    rebuild = read(qa / 'packaged-verification.json')
    assert rebuild['passed'] and rebuild['deterministic_rebuild']
    assert manifest['release'] == rebuild['release'] == release
    assert rebuild['packages'] == manifest['packages']
    assert read(qa / 'release.json') == manifest
    names = NATIVE if any(p['id'] == 'plugin.games.foundry' for p in manifest['packages']) else NATIVE[:-1]
    native = {name: read(qa / 'native' / name) for name in names}
    assert native['weather-verification.json']['passed']
    assert native['verification.json']['checks']
    assert native['startup-splash-verification.json']['real_kodi_cold_start']
    assert native['interface-verification.json']['home_favorites_row_focus_and_horizontal_navigation']
    if 'games/games-verification.json' in native:
        games = native['games/games-verification.json']
        assert games['passed'] is True
        assert games['release'] == release and games['packages'] == manifest['packages']
        version = re.search(r'\b(\d+)\.\d+', games['renderer'])
        assert version and int(version[1]) >= 21, 'Games requires native Kodi 21+'
        assert all(games['assertions'].get(name) is True for name in GAMES_ASSERTIONS)
        assert set(GAMES_CASES) <= {check['case'] for check in games['checks']}
        assert all(check['capture_state_stable_seconds'] >= .5 and check['png_completion_ack'] is True for check in games['checks'])
        expected_core=games['native_core_expected']
        normalize=lambda text:' '.join(text.casefold().split())
        for check in games['checks']:
            assert check['progress_visible'] is False
            assert check['busy_visible']==(check['busy_dialog_visible'] or check['busy_nocancel_visible'])
            if check['case']=='games-missing-core':
                assert check['modal'] is True and check['dialog_id'] in (12000,12002)
                if check['dialog_id']==12000: assert normalize(check['dialog_heading'])==normalize(expected_core['chooser'])
                else:
                    assert normalize(check['dialog_heading'])==normalize(expected_core['heading'])
                    assert normalize(check['dialog_message']) in {normalize(value) for value in expected_core['messages']}
                if check['busy_visible']:
                    assert check['busy_dialog_visible'] is True and check['busy_nocancel_visible'] is False
                    assert check['buried_busy_render_suppressed'] is True
                    assert check['busy_suppression_source']=='Kodi21.3 GUIDialogBusy.cpp118-132: Render only when topmost'
            else: assert check['modal'] is False and check['busy_visible'] is False
        captures=games['capture_acknowledgments']
        assert len(captures)==len(games['checks'])
        for index,(capture,check) in enumerate(zip(captures,games['checks'])):
            assert capture['sequence']==index+1 and capture['case']==check['case']
            assert capture['passed'] is True and capture['dimensions']==[1920,1080] and capture['stable_seconds']>=.5
        assert games['shipped_skin_hashes'], 'Games requires unchanged shipped-skin proof'
        game_log = games['native_gameclient_log']
        assert game_log['complete'] is True and game_log['native_gameclient_path'] is True
        assert game_log['failures'] == []
        assert re.fullmatch(r'[a-f0-9]{64}', games['production_entrypoint_sha256'])
        assert games['skin_boolean_errors']['new_errors'] == []
        assert games['skin_boolean_errors']['unchanged_timer_sha256'] == 'c2c90596e9362a97dc5ad2e79004273fe014954bf0f976cc39f78e7cf2e02614'
        poster=games['skin_boolean_errors']['posterflow_proof']
        assert poster['current_sha256']==poster['published_140_sha256']=='ebcdc5840651253eb0bae2d1241578624d3ee132c5a63ad53a7d58aa2e8c2993'
        assert poster['bytes_equal'] is True
        baseline_inputs={name:'String.IsEqual(ListItem.DBType,'+kind+')' for name,kind in (('isMovie','movie'),('isTVShow','tvshow'),('isSeason','season'),('isEpisode','episode'))}
        assert poster['current_inputs']==poster['published_140_inputs']==baseline_inputs
        startup = games['startup_readiness']
        assert startup['passed'] is True and startup['quiet_seconds'] >= 2
        assert startup['actual_skin_log']['ready'] is True and startup['home_signature']
        assert {record['mode'] for record in startup['completed_game_widgets']} == {'recent', 'favorites'}
        assert all(record['phase'] == 'completed' and not record['error'] for record in startup['completed_game_widgets'])
        movies = native['verification.json']['movie_submenu_wallpapers']
        assert all(movies.get(name) is True for name in MOVIE_FLAGS)
        movie_labels = MOVIE_LABELS + (EXTRA_MOVIE_LABELS if tuple(int(v) for v in release.split('.')) >= (1, 5, 4) else ())
        assert movies['approved_count'] == movies['rendered_approved_count'] == len(movie_labels)
        cases = movies['cases']
        expected = {'movie-wallpaper-' + label.lower().rstrip('.').replace(' ', '-'): label for label in movie_labels}
        expected.update({'movie-wallpaper-unknown': '', 'movie-wallpaper-tv': '',
                         'movie-wallpaper-mixed': '', 'movie-wallpaper-custom': 'Trending',
                         'movie-wallpaper-title-fanart': 'Trending'})
        assert len(cases) == len(movie_labels) + 5 and {case['case'] for case in cases} == set(expected)
        for case in cases:
            assert case['canonical_label'] == expected[case['case']]
            assert case['screenshot'] == case['case'] + '.png'
            errors = case['pixel_mean_max_errors']
            assert len(errors) == 3 and all(isinstance(error, (int, float)) and 0 <= error < 12 for error in errors)
        first = next(case for case in cases if case['case'] == 'movie-wallpaper-trending')
        assert first['paging_roundtrip_retains_context'] is True
        assert first['native_list_loss_rehydration_retains_context'] is True
        hashes = movies['copied_skin_inputs_sha256']
        assert hashes and all(re.fullmatch(r'[a-f0-9]{64}', value) for value in hashes.values())
        interface = native['interface-verification.json']
        assert interface['kodi_version']['major'] >= 21 and interface['diagnostic_only'] is False
        assert interface['playback_traceback_gate'] is True
        assert interface['reported_device_error_reproduced'] is False
        cycles = interface['playback_stop_back_cycles']
        assert len(cycles) == 3
        for index, cycle in enumerate(cycles):
            assert cycle['cycle'] == index + 1 and cycle['with_item_fanart'] is (index > 0)
            before, stopped, back = cycle['before'], cycle['after_stop'], cycle['after_back']
            entry = stopped['catalog']
            assert stopped['window'] == before['window']
            assert entry['native_ready'] is True and entry['size'] == 6 and entry['focus'] == 50
            assert entry['position'] == entry['selected'] == 3 and entry['submenu'] == 'Trending'
            assert entry['message'] == ''
            for name in ('source', 'file', 'fanart'):
                assert entry[name] == before['catalog'][name]
            assert back['catalog'] is None and back['window'] == before['playback_parent']
        playback_errors = read(qa / 'native/interface-playback-errors.json')
        assert playback_errors['complete'] is True and playback_errors['failures'] == []
    return {'status': 'ci_passed_target_device_checks_pending',
            'source_tests': source, 'packaged_tests': packaged,
            'deterministic_rebuild': True,
            'native_reports': list(names),
            'workflow_run': os.environ.get('GITHUB_RUN_ID'),
            'target_device_verification': 'Shield rendering, navigation, controllers and gameplay unverified; native synthetic Games checks do not certify gameplay'}


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
    require_release_scope(manifest)
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-scope', action='store_true', help='Check package scope without staging or requiring main')
    args = parser.parse_args()
    if args.check_scope:
        require_release_scope(read(ROOT / 'release.json'))
    else:
        main()
