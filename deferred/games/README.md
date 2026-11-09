# Deferred Foundry Games port

This work is not part of the 1.4.0 release, installer dependencies, repository feed, or packaged validation tree. Native Kodi Games navigation remains unchanged in that release.

The original add-on, five test modules, native harness, and skin view are retained here. Run 42536731571 verified the actual Games rail, hero metadata, navigation, pagination, Back focus and favorite database persistence. Its transition to Favorites failed during overlapping native navigation/refresh, so complete integration validation remains outstanding. No gameplay or Shield compatibility has been certified.

Before reintroducing this feature, restore the intended integration paths, complete Favorites/search/cancel/missing-core native checks, and require a Games native report in both development and publication gates. Do not add the package or dependency without that validation. The 1.4.0 release explicitly rejects an unexpected Games package.

The separate unit suites can be run here with `python -m unittest discover -s deferred/games/tests -p test_games_library.py`, and likewise for `test_games_staging.py` and `test_games_kodi.py`. Integration/renderer tests require restored source and sibling-skin layout. The existing limitations in the add-on README still apply.

## Next release working integration

The original files below remain preserved. The active 1.5.0 candidate now lives at src/plugin.games.foundry, tests/test_games*.py and tools/render_games.py. Publication requires all five native gates, including real Favorites, search/cancel and missing-core completion checks on the extracted candidate. This restoration does not change published 1.4.0 artifacts. Native Kodi 21+ and target-device validation remain required; a restored source tree alone is not verification.
