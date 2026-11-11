# Native validation follow-up, 2026-11-11

Dev d38a3a8 passed source/extracted suites and deterministic packaging in both attempts of run 42957974887. Attempt 1 passed Library, Splash, Interface and Games but Kodi 21.3 segfaulted during Weather startup; root cause remains unconfirmed. Attempt 2 passed Weather but Games classified dialog 12002 while progress was still visible and its text was blank. Neither attempt is a full pass.

The QA-only Games correction waits for progress/updating to finish before classifying the modal. Exact emulator heading/body checks, unrelated-dialog rejection, bounded timeout, settled screenshot requirements and cancellation checks remain intact. A regression test covers the observed transition and rejects a settled wrong dialog. Weather now retains native crash reports before removing its disposable profile. No runtime package/source pin is changed. Focused Games/Weather harness tests pass 28/22. A fresh full native run is required before publication.

---

# Quick Relay recovery and publication preparation, 2026-11-11

Trent requested that artwork failures be resolved and the candidate published, and approved safe recovery preserving existing work. After the prior lease expired, canonical startup granted SESSION_READY to Codex-Nova Fix Publish Foundry Artwork in an isolated clean checkout. The original checkout and all thirteen pending files remain untouched; their backup and replay were SHA-256 verified against base c02e6837a41d68295091459a611e3112e322379e.

The earlier Windows artwork failures do not reproduce when TEMP and TMP use a short writable path. All 661 source tests passed (one Windows skip), and all 661 extracted-package tests passed (two expected Windows skips). This points to Windows temporary-path constraints, not a demonstrated artwork runtime regression. No artwork product code was changed. The isolated deterministic rebuild passed and all 125 ZIPs matched the preserved candidate byte-for-byte. All ten selected packages, feed, dependencies and hashes validated.

Final recovered-checkout verification and exact-head development CI are in progress. All five native Kodi gates remain required. Production/main/Pages publication has not occurred; the project production Approval Gate remains pending. Earlier authorization and failure statements below are historical. Shield/Android and audible output checks remain unverified.

Windows validation uses process-local TEMP and TMP set to C:/Users/TrentTimmerman/Documents/Codex, with PYTHONDONTWRITEBYTECODE=1. No system or user environment settings are changed.

---

# Quick Relay sound update, 2026-11-11

Trent selected the third Muted Relay variation and requested a single UI sound integrated directly. Added Quick Relay 1.1.0 under the stable sound add-on ID. Navigation, Select and Back use the identical selected cue; existing error, action mapping, mute/playback/custom sound preferences remain unchanged. Exact regenerated WAV SHA256: bbfab20103bf39a11a66c153807614911ffe8f2f5d7eb24e5ac0d4e681d4b93f.

Verified: 22 focused sound/migration tests pass. All ten packages/manifests/feed/aliases validate. All 124 pre-existing ZIPs are byte-identical after rebuilding from pinned sources. The new sound package is versioned separately at 1.1.0.

Full Windows suites (659 tests before two new sound tests) remain blocked by 2 failures and 2 errors in existing artwork cache/presentation paths, with 1 source / 2 extracted skips. These are not a full pass. Native audible output/Shield testing and current-head CI were not performed. No production/main/Pages publication is authorized or performed. Existing 1.5.0 candidate release gate still applies.

Local evidence: C:/Users/TrentTimmerman/Documents/Codex/quick-relay-20261111/ .

---

# Foundry 1.5.0 development handoff

Updated 2026-11-09 UTC on SPACESHIP. Branch: dev. Runtime development is validated in the recorded run; read the latest dev workflow below for current-head status. Published Kodi main/Pages remains 1.4.0; release authorization is pending. Uncommitted product work: none. This documentation receipt follows the validated runtime candidate.

## Exact candidate

- Validated distribution code: bcd5875b4215bf6e268f05444c096b1a7f0a30ff.
- Skin 1.5.0 runtime pin: 579e84b3fed7e765bc7a0ec3ce30657a979c82af.
- Helper 1.3.1 runtime pin: 8fb2841867a54ce363ef79f05e115305ab1738cf.
- Build/bootstrap: 1.5.0. Games: 0.1.0. Weather, Pulse and other resource/repository versions remain unchanged. Ten candidate packages.
- Source pins/snapshot: releases/1.5.0-sources.json and releases/1.5.0-source-snapshot.json.gz. Independent materialization matched 898 skin and 54 helper Git blobs.

Later skin/helper documentation receipts do not move runtime pins. Reproduce using tools/materialize_sources.py --release 1.5.0 in an isolated layout, as the development workflow does. Preserve the intentional published 1.4.0 source pins and all versioned artifacts.

## Completed behavior

Games restores seventeen catalog systems, local/VFS scanning, favorites/recent/playtime, search/paging, bounded staging and native emulator choice. Asynchronous navigation/refresh waits for fresh completed directory and invoker identities. Only the active Games route displaying its own UUID may select view58; Home widgets cannot change another view.

All thirteen approved Movies submenu PNGs retain original generated bytes. Exact label and verified source-owned Movies context survive paging, Back and playback reinitialization. TV/mixed/unknown contexts are excluded. Custom backgrounds and selected-title fanart keep priority. Home geometry, unrelated artwork, source URLs, profile/history keys and sound choices are preserved.

## Verified evidence

[Development run 42564799165](https://github.com/3thirty3gitter/foundry-kodi-dist/actions/runs/42564799165) succeeded against the exact code above using native Kodi 21.3 on GitHub Ubuntu:

1. Library/catalog, all thirteen Movies wallpapers, custom/fanart precedence, negative contexts, paging/rehydration and pixel/source-hash checks.
2. Actual cold-start splash.
3. Interface/playback: three Play/Stop/Back cycles, retained item/source/file/fanart/submenu/selection/focus and correct parent return; complete traceback segment, no Python failures.
4. Canadian Weather controls, city changes, stale/missing data, provider switching and normal navigation.
5. Games: eleven cases and all twenty-five assertions; automatic view selection, navigation/paging/Back, favorite refresh and actual Favorites route, search/cancel, exact native missing-emulator dialog, canceled invoker completion, retained focus, unchanged launch history, all eleven fully encoded screenshots and shipped-skin hashes.

Both CI suites ran 653 tests, zero failures/errors (source/extracted skips 0/1). The extracted skip intentionally excludes preserved-deferred-source checks from the package workspace. Local Windows suites also passed 653 tests, skips 1/2 due to the additional symbolic-link fixture. All ten ZIPs, manifests, dependencies, hashes, feed/checksum, aliases and deterministic rebuilding passed.

Artifact 13650794181 SHA-256: bfa0eee24cc883e253a8a4f0656770847f61f41f36ace47e0e5b6ed2236b34f8.
Jimmy independently verified the download digest, inspected Favorites/missing-core/return-focus images, verified all eleven PNGs and ran record_release_validation.evidence() read-only against the complete artifact. See [validation receipt](2026-11-09-validation.json).

Local evidence: C:/Users/TrentTimmerman/Documents/Codex/foundry-next-1.5.0-20261109/ci-42564799165/ .
Local full-suite/build records: C:/Users/TrentTimmerman/Documents/Codex/foundry-next-games-20261109/ .

All 92 published 1.4.0 artifacts and thirteen approved original PNGs retain their independently checked hashes. Both exact public update-host release URLs returned 1.4.0/nine packages at 2026-11-09T04:50:54Z.

The unchanged Weather 0.1.0 client fetched/parsed three real Canadian cities at 2026-11-09T03:22:59Z, seven daily/twenty-four hourly entries each, with immediate temporary-cache reuse. Missing fields and advisories were retained; no user profile/config changed.

## Native harness contracts

Captures require native state stable beyond shipped animation bounds, actual 1920x1080 PNG completion acknowledged by the host before further input, and unchanged state after encoding. Library uses completed native action/case-close sequencing, atomic command publication, a free RPC port and unique own-profile readiness.

Only exact proven published Timer and PosterFlow warnings are classified as baseline; every new boolean expression failure remains fatal. No legacy runtime XML was changed to suppress warnings. Exact native emulator-error/chooser state may cover ScriptRunner Busy10138 only under the source-proven Kodi 21.3 topmost-modal/render-suppression rule. Other modal/busy/progress states fail. The report retains source links and separate busy-window bits.

Historical failed runs and diagnoses are preserved in [development diagnostics](2026-11-09-native-development-diagnostics.md). The first exit139 root cause remains unconfirmed; subsequent full runs did not repeat it. No failing historical run is presented as a complete pass.

## Weather observer startup follow-up

The documentation-head run 42565633890 repeated the complete Games pass with the same production entrypoint and shipped-skin hashes, but Weather failed before its first observer state. Its QA invoker started before confirmation deinitialized, then overlapped Startup/Home and another reload; no first state/error file was produced and the failure frame was black. This does not prove a provider or product regression.

The QA-only correction removes the observer's redundant synchronous ReloadSkin/ActivateHome. Host readiness now requires the actual final Foundry load-to-Home event, own profile/webserver/provider, a real Home/menu signature, no active/visible modal or Startup/update, and two stable seconds within the existing deadline. The observer verifies actual special://skin, publishes genuine first state before input, then uses the existing completed focus-menu command. Actual weather buttons, card assertions, synthetic provider behavior and copied source hashes are preserved. Startup observations, phase, pending command and exact observer source are retained on failure.

A fresh local clone materialized the immutable 898/54 skin/helper blobs before rebuilding. All 659 source and 659 extracted-package tests passed (Windows skips 1/2), all 22 direct Weather tests passed, and deterministic rebuilding/source-tree preservation passed. Manifest, feed, aliases and all 112 original candidate/historical artifact hashes remained byte-identical, including the 92 published 1.4.0 artifacts. Runtime packages and source pins did not change.

The completed runtime proof above remains historical evidence. Current-head validation is authoritative in the [latest dev workflow](https://github.com/3thirty3gitter/foundry-kodi-dist/actions/workflows/dev-validation.yml?query=branch%3Adev); all five native gates are required before publication. Follow-up local records: C:/Users/TrentTimmerman/Documents/Codex/foundry-next-games-20261109/weather-cold-home-pinned-source-01/ .

## Remaining scope and next steps

Shield/Android rendering/performance, real VFS providers, gameplay/cores/controllers, disconnect/multiplayer, savestate migration, audible output, device restart and thirty-minute Weather behavior remain unverified. No ROM, BIOS, core binary or credential is bundled or automatically installed. PSP is unsupported; commercial emulator-license clearance remains pending.

The original affected-device playback-stop false error has not been reproduced or confirmed fixed. Controlled native regression success does not establish that device fix.

1. Review the three dev branches and local review packet; explicit authorization is required to open draft PRs after automatic approval review rejected that action. No PR has been posted.
2. Obtain affected-device Kodi logs/ADB access and perform the remaining Shield/provider/playback/audio/Weather checks.
3. Follow the current production Approval Gate before merging/pushing app main or publishing 1.5.0 through the existing Kodi update flow. Prior 1.4.0 approval does not authorize this candidate.
4. At actual session end, run canonical complete-session for this tab's own claims. No close/portable receipt or SESSION COMPLETE is claimed by this task handoff.
