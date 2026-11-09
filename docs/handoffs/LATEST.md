# Foundry distribution 1.5.0 candidate handoff

Prepared on SPACESHIP for the coordinated development candidate. This candidate is unpublished. Development commits have been pushed to dev for validation; supported native Kodi 21 validation and owner approval remain pending. Production main remains unchanged.

## Exact source identity

- Distribution/build/bootstrap and skin: 1.5.0. Helper: 1.3.1. Games: 0.1.0. Canada Weather: 0.1.0. The repository, wallpaper, OSD and Pulse package versions remain unchanged.
- Skin dev commit: `579e84b3fed7e765bc7a0ec3ce30657a979c82af`.
- Helper dev commit: `8fb2841867a54ce363ef79f05e115305ab1738cf`.
- [Source pins](../../releases/1.5.0-sources.json) and [source snapshot](../../releases/1.5.0-source-snapshot.json.gz) use immutable skin 1.4.0 and helper 1.3.0 ZIP baselines. Independent materialization verified all committed Git blob maps: 898 skin files and 54 helper files.

Do not move these runtime source pins merely to add later validation receipts. Record CI outcomes in distribution documentation/evidence separately. Original Games source, tests, harness and skin view remain under `deferred/games`; only its README status note changed.

## Completed local checks

Windows Python 3.13.5 against the exact source pins above:

- Complete source suite: 640 tests run, zero failures/errors, one skipped Windows symbolic-link fixture; successful.
- Complete extracted-package suite: 640 tests run, zero failures/errors, two skips (the same symbolic-link fixture, plus preserved-deferred-source checks intentionally excluded from extracted-package workspaces); successful.
- All ten package ZIPs, sizes, SHA-256 sidecars, manifests, dependencies, feed/checksum and root installer aliases verified.
- Isolated extracted-package deterministic rebuild passed without modifying source trees.
- All 92 published 1.4.0 artifacts were compared byte-for-byte with the pre-candidate committed baseline: nine package ZIPs and sidecars plus 74 source/QA/verification records. All remain unchanged. Generated current feed/installer aliases are working candidate files; the remote existing update flow remains published 1.4.0 until approved publication.

Local evidence directory on SPACESHIP: `C:\Users\TrentTimmerman\Documents\Codex\foundry-next-games-20261109`.

Relevant records: `source-tests-final-combined.json` / `.log`, `packaged-qa-final-combined/packaged-tests.json`, `packaged-qa-final-combined/packaged-verification.json`, `packaged-tests-final-combined.log`, `published-1.4.0-immutability.json`, and `distribution-reviewed-paths.txt`. Local results do not substitute for CI/native results. Existing 1.4.0 native receipts describe that published release only.

## First native run and bounded corrections

[Development run42555313989](https://github.com/3thirty3gitter/foundry-kodi-dist/actions/runs/42555313989), distribution721e5daebef6b88b4f117322f623cbc6c1a18599, passed source/extracted checks and the library, splash, interface and Weather native gates. Games exited139 during full Home startup before the first fixture phase. Its crash report lacked a backtrace because gdb was absent. The native crash root cause remains unconfirmed; those four passing reports are provisional for that prior candidate, and every gate must rerun for the correction.

A separate confirmed issue is corrected: background Games widget listings no longer request a global view change in Home/Videos or a different Games route. The native fixture must observe automatic Games view58 before forcing any rail focus/view control. Startup readiness now retains all real Home Games widgets and requires their genuine invokers to finish, actual `special://skin/` graphics paths to match the copied skin, the last real skin-load/Home transitions and Foundry menu signature, fixture identity, no modal/startup/update, and two stable seconds. A later Startup/Home cycle resets settlement. Failure paths preserve phase, invocation records and genuine source wrappers; CI installs gdb for a recurring native crash backtrace.

Only the exact existing Timer warning `control.hasfocus($param[list_id])` is classified as baseline, with byte-equality against the published1.4 Timer and SHA-256c2c90596e9362a97dc5ad2e79004273fe014954bf0f976cc39f78e7cf2e02614. Every new skin boolean parse expression still fails. No native success is claimed for these corrections. Diagnosis: `games-crash-42555313989-diagnosis.json` in the local evidence directory.

The [second development run42557830873](https://github.com/3thirty3gitter/foundry-kodi-dist/actions/runs/42557830873), candidatee9cd14567c743dc94b1dd9bd480acc0a75428330, again passed the other four native gates. Games startup settlement proved the actual Foundry graphics path, full Home signature and completed real recent/favorites widgets; its first Home directory also completed. The subsequent NES `Container.Update` synchronous call stalled: the native directory operation started a new Python invoker which never initialized, while the controller never reached its fresh-directory wait. The host timed out240seconds with Kodi alive.

The minimal correction posts plugin `ActivateWindow`, `Container.Update` and favorite `Container.Refresh` asynchronously, then retains the exact route/fresh DirectoryId/invoker-completion acknowledgments. No timeout or runtime check was relaxed. A semantic fake-GUI regression exposes the requested route immediately but completes its native listing only when the Python controller yields, requiring a genuinely fresh UUID. Its dispatch signature rejects synchronous waiting. Current supported Games native success remains pending a complete rerun. The original exit139 root cause remains unconfirmed. Detailed timeout evidence: `games-timeout-42557830873-diagnosis.json` in the local evidence directory.

The [third development run42559245662](https://github.com/3thirty3gitter/foundry-kodi-dist/actions/runs/42559245662), candidate5e070c61d80645929b0bfbd1bf8b804e3828e844, cleared the synchronous directory stall. Games reached the fresh NES catalog in native window10821 but stayed in List view. The immediate post-endOfDirectory owner check could run before Kodi published the new native list. The correction returns the invocation UUID from done(), then yields through Monitor.waitForAbort(.05), bounded to two seconds, until the exact Games route and that UUID are actually displayed before posting view58. Home/Videos, a different background widget UUID, navigation away or abort cannot change another view. The native automatic58 assertion remains before any fixture-forced rail control. Evidence: `games-view-42559245662-diagnosis.json`.

That third run also exposed a separate short-row library fixture transition race (native position1 versus required0). Its owner added explicit parent-close acknowledgment, host-controlled case release, sequence acknowledgments and input journaling; capture and rehydrate command publication is also atomic. All original position and pixel assertions remain. The combined corrected candidate is locally verified above; both fixes require the next complete native run, with no supported Games pass claimed yet. Skin/helper runtime source pins remain unchanged.

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
