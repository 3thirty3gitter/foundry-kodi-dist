# Foundry distribution 1.5.0 candidate handoff

Prepared on SPACESHIP for the coordinated dev validation commit. This candidate is unpublished. Supported native Kodi 21 validation and owner approval remain pending; no distribution push or production merge was performed by this task.

## Exact source identity

- Distribution/build/bootstrap and skin: 1.5.0. Helper: 1.3.1. Games: 0.1.0. Canada Weather: 0.1.0. The repository, wallpaper, OSD and Pulse package versions remain unchanged.
- Skin dev commit: `579e84b3fed7e765bc7a0ec3ce30657a979c82af`.
- Helper dev commit: `8fb2841867a54ce363ef79f05e115305ab1738cf`.
- [Source pins](../../releases/1.5.0-sources.json) and [source snapshot](../../releases/1.5.0-source-snapshot.json.gz) use immutable skin 1.4.0 and helper 1.3.0 ZIP baselines. Independent materialization verified all committed Git blob maps: 898 skin files and 54 helper files.

Do not move these runtime source pins merely to add later validation receipts. Record CI outcomes in distribution documentation/evidence separately. Original Games source, tests, harness and skin view remain under `deferred/games`; only its README status note changed.

## Completed local checks

Windows Python 3.13.5 against the exact source pins above:

- Complete source suite: 623 tests run, zero failures/errors, one skipped Windows symbolic-link fixture; successful.
- Complete extracted-package suite: 623 tests run, zero failures/errors, two skips (the same symbolic-link fixture, plus preserved-deferred-source checks intentionally excluded from extracted-package workspaces); successful.
- All ten package ZIPs, sizes, SHA-256 sidecars, manifests, dependencies, feed/checksum and root installer aliases verified.
- Isolated extracted-package deterministic rebuild passed without modifying source trees.
- All 92 published 1.4.0 artifacts were compared byte-for-byte with the pre-candidate committed baseline: nine package ZIPs and sidecars plus 74 source/QA/verification records. All remain unchanged. Generated current feed/installer aliases are working candidate files; the remote existing update flow remains published 1.4.0 until approved publication.

Local evidence directory on SPACESHIP: `C:\Users\TrentTimmerman\Documents\Codex\foundry-next-games-20261109`.

Relevant records: `source-tests-final.json` / `.log`, `packaged-qa-final/packaged-tests.json`, `packaged-qa-final/packaged-verification.json`, `packaged-tests-final.log`, `published-1.4.0-immutability.json`, and `distribution-reviewed-paths.txt`. Local results do not substitute for CI/native results. Existing 1.4.0 native receipts describe that published release only.

## Mandatory next validation

The [development workflow](../../.github/workflows/dev-validation.yml) ([GitHub Actions](https://github.com/3thirty3gitter/foundry-kodi-dist/actions/workflows/dev-validation.yml)) materializes the pinned sources, builds/tests them, then tests and deterministically rebuilds every extracted package. All five native Kodi 21+ gates use that same extracted candidate:

1. Library/catalog and thirteen approved Movies submenu wallpapers: eighteen native cases, all approved routes, custom-background and selected-title-fanart precedence, TV/mixed/unknown negatives, paging/rehydration preservation, pixel comparisons and copied-input hashes.
2. Actual cold-start splash.
3. Interface/playback: three native play-stop-Back cycles, retained source/file/fanart/submenu/count/selection/focus, original parent after Back, complete traceback log segment and no captured Python failures.
4. Canadian Weather.
5. Games: fresh completed native directory identity after favorite refresh; actual Favorites menu route; real search keyboard/cancel; exact localized native emulator selection12000 or missing-core error12002; genuine production invoker completion for canceled search and game launch; marked RetroPlayer game-client log path, no Python traceback, no successful-launch history from cancellation, unchanged shipped skin and verified screenshots.

The [publication workflow](../../.github/workflows/release.yml) and release evidence gate require these complete reports before publication. A file existing, DB persistence, a generic Foundry Games error dialog, a stale prior listing, a Kodi20 diagnostic, or mocked Kodi APIs cannot satisfy Games native validation. Games' disposable copied entrypoint wrapper preserves the genuine invoker globals and production source while recording atomic started/completed-finally acknowledgments; no production test-ack setting was added.

The one local Kodi20 diagnostic failed before running the Games fixture because the unchanged skin requires xbmc.gui5.17. It provides no Games navigation/cancel proof. No further unsupported-runtime attempts are required; use the supported development CI runner.

## Remaining limits and release boundary

No Shield/Android rendering, performance, gameplay, controller/disconnect/multiplayer, real VFS provider, savestate migration or commercial emulator-license clearance is certified. No ROMs, BIOS, cores or credentials are bundled or automatically installed. PSP remains unsupported. Native synthetic catalog/launch checks do not establish playable Shield cores.

The originally reported false error after stopping playback has not been reproduced or confirmed fixed. The new repeated native play-stop-Back gate gathers controlled traceback/state evidence; it does not certify that original device report. Null-audio CI cannot prove audible Pulse output. Weather still requires manual provider/city configuration and carries its existing live-service/device/API limitations.

The existing Kodi repository/update flow remains the delivery route. Published 1.4.0 includes regular Home Favorites, catalog Back/focus and overlay fixes, Pulse/Ripple and Canada Weather, and excludes Games and the thirteen new Movies wallpapers. Do not replace its published ZIPs, snapshots, source pins or evidence. Do not merge/push main or publish 1.5.0 without the current owner approval gate.
