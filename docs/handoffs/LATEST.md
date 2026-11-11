# Foundry 1.5.2 publication verified, 2026-11-11

Trent explicitly approved production publication after disclosure of immediate updater availability, rollback/manual downgrade risk, trusted-LAN unencrypted QR text entry, and untested physical phone/Shield. Ordinary PR #2 merged the exact validated dev candidate 0029accf61ff1373441ee475f51b2afc6252374b into main as 8dc85df6cd83ce386d9d4928c5b7b47e480c7864. Historical 1.5.1 receipts were preserved; no protection bypass or force push. https://github.com/3thirty3gitter/foundry-kodi-dist/pull/2

Release/skin/build/bootstrap 1.5.2; helper 1.3.3. Source pins: skin 920755f6d90d9d37b6051542b2f6a9215682a13d; helper 597c16da1e67208e7788e563005b5c5a20c07b67. Release manifest SHA256 f96d65e8761106275184e1bfcf5ad77dd0df5df2fee88f7345681c12b1e54073.

Hosted dev run 43101931097 and production release run 43104436614 succeeded: 724 source tests, zero failures/errors/skips; 724 extracted tests, zero failures/errors/one expected skip; deterministic rebuild and all five native Kodi gates passed. Production artifact 13893417185 independently verified against SHA256 38ecbb2e13b404bb9d5593e0d199fd24b459fd2daf7796f7f02831298d2d1123, all 171 extracted files, exact merge/run identity and official read-only evidence() assertions.

Release automation published validation receipt 08ffe19626c28dcbe3983c7e457b17ee44a3c6c2. Public verification run 43105288012 succeeded, creating receipt ba8d38eefca5537ee8c3edbaf6f8b7f3c575f885 (only releases/1.5.2-verification.json changed). Initial Pages43104436190 succeeded; follow-up43105272165 superseded/cancelled by final receipt Pages43105381215, whose final status is recorded separately.

Independent live verification completed 21:43:29UTC: all 10 ZIPs on both Pages and raw GitHub (20 downloads), exact committed bytes/SHA256/ZIP integrity/checksum sidecars, both release manifests/Kodi feeds and five Pages installer/listing aliases passed. Evidence under C:/Users/TrentTimmerman/Documents/Codex/foundry-152-production/production-public-verification/: independent-production-evidence.json and releases/1.5.2-verification.json. No repository edits made by verification worker.

Remaining limitations: physical phone/browser/network and Shield rendering/navigation/playback/controller/gameplay unverified. QR entry is plaintext trusted-LAN HTTP for ordinary text only, excludes hidden/password/PIN dialogs and requires explicit TV OK. Live personal TMDb/OMDb keys unverified; native Games fixtures do not certify gameplay. Production lease closure and dev handoff synchronization remain parent's responsibility. Preserve original dirty shared trees and historical evidence.

Final receipt Pages run 43105381215 completed successfully. All assigned production release, public verification and latest Pages workflows are green.

---

# Foundry 1.5.2 local candidate, 2026-11-11

Unpublished local dev candidate at C:/Users/TrentTimmerman/Documents/Codex/foundry-wallpaper-20261111/apps. Original dirty shared repositories were preserved. All three own leases remain active; no push/main/Pages publication performed or authorized for this candidate.

Skin/build/bootstrap 1.5.2 and Helper 1.3.3 integrate Movies wallpaper layering, wallpaper-backed native catalog adoption/first paint, installed studio-logo resolution and temporary QR phone text entry. Other package versions remain unchanged. Phone entry is trusted-LAN plaintext HTTP for ordinary text only, excludes hidden/password/PIN fields and requires TV OK. Actual phone browser/network and Shield remain unverified; see helper docs/PHONE-ENTRY.md.

Exact source pins: skin 920755f6d90d9d37b6051542b2f6a9215682a13d; helper 597c16da1e67208e7788e563005b5c5a20c07b67. Working packaged bytes were checked against committed Git blobs before recording releases/1.5.2-source-snapshot.json.gz. All 153 previous ZIP/snapshot files retain their original SHA-256 hashes, with hashes and comparison in the project-root candidate-preserved-hashes.json and candidate-preservation-verification.json.

Versioned source suite: 724 tests, zero failures/errors/skips on Linux. Extracted suite: 724 tests, zero failures/errors, one expected preserved-source skip. Deterministic extracted rebuild, all ten package ZIP hashes, manifests/dependencies, feed/checksum and installer/listing aliases pass. Reports: releases/1.5.2-qa/{source-tests,packaged-tests,packaged-verification,release}.json. Exact extracted source workspace: project-root/candidate-packaged-qa-final/apps (prior native-gate extraction retained at candidate-packaged/apps).

Full five-gate native candidate validation is in progress against the extracted packages. No final native release-gate pass or hosted CI success is claimed here. Earlier focused native category, studio and phone fixtures passed, but are not a substitute for complete release gates. Once completed, consult the later validation receipt. Production publication requires the current approval gate; previous 1.5.1 approval does not cover this candidate.

QA-only follow-up: Games cancellation now verifies the complete menu and focus, accepting a new directory UUID only when it belongs to an exact completed fresh Home invocation. Runtime packages/source pins unchanged. Correction commit 4cf6147ae8783fb87f0adf66bdffab7fcd2db205; 30 focused Games checks passed. Full source/extracted suites and deterministic rebuild passed again; log project-root/candidate-source-extracted-qa-final.log. The original failed native Games log is retained by the native validation worker.

---
# Approved 1.5.1 publication, 2026-11-11

Trent explicitly approved publishing 1.5.1 using the successful local Kodi 21.3 native validation as an exception to hosted DNS failure, with immediate availability, rollback/manual-downgrade risk and untested Shield disclosed. Exact response: "Yes publish". The guarded production push fast-forwarded main from 02c4a4b to bfd9c7c07ee86349946f439bd66cc1524b4b4163. Hosted gates, signing keys, security settings and locked protocols remain unchanged. This is not a green hosted native validation claim.

Hosted dev run 43058235384 passed source/extracted testing and packaging but failed all four official Ubuntu archive suites resolving archive.ubuntu.com, exit 100. All five unchanged native harnesses previously passed in isolated Ubuntu 26.04 / Kodi 21.3 on Spaceship; 93 screenshots verified. Full Windows source suite: 682 passed, zero failures/errors, two environment skips.

Publication verified successfully: both public manifests and feeds match; all ten package ZIPs on both Pages and raw GitHub (20 downloads) pass exact bytes, SHA-256, ZIP integrity and checksum sidecars; all five Pages root installer/listing aliases match. Report: C:/Users/TrentTimmerman/Documents/Codex/foundry-navigation-20261111/combined-evidence/PUBLICATION-VERIFIED.json. Pages run 43069822304 and release run 43069821764 belong to bfd9c7c. Hosted release native validation remains separate and may retain the disclosed DNS failure. Earlier sections below are historical, not current blockers.

A fresh normal lease d4961d21-262f-4a01-ab56-371195ce2409 was acquired for repair-foundry-navigation-20261111 after expiry; no token override was needed for publication. Shared active-repos registration publication and canonical session close remain pending because the brain checkout contains preserved unrelated work.

---
# Native validation and hosted setup repair, 2026-11-11

All five unchanged native harnesses passed in a disposable Ubuntu 26.04 Docker container on Spaceship running Kodi 21.3, against the exact extracted f06ed5512dde2451561c7098348c42b3223fd51e packages. Independent evidence() assertions pass; 93 full 1920x1080 PNGs verified and representative catalog/Home/splash/Games captures visually reviewed. Combined evidence and explicit split provenance: C:/Users/TrentTimmerman/Documents/Codex/foundry-navigation-20261111/combined-evidence/PROVENANCE.json. Docker image digest: sha256:82a932795ad13cebee5562e30c0c113ef0ca4b3aa06187afd75b4d71b1f8952e.

Hosted run 43049658155 attempts 1 and 2 passed all 678 source tests (zero skips), all 678 extracted tests (one expected skip) and deterministic packaging. Both failed installing Kodi because Ubuntu package-server DNS resolution failed; hosted native gates never ran. This is not green hosted CI.

Trent approved all three dev pushes, then explicitly authorized the documented session-token override after this task's ephemeral cache token disappeared. Own authoritative identity was verified, existing wrappers used, and override removed. Source and distribution dev SHAs were verified remotely. Production remains 1.5.0.

The narrow CI follow-up replaces only failing mirror-list/official HTTP Ubuntu URIs with direct HTTPS official archive routing. Suites, components, signing keys and all five native gates remain unchanged. Update now fails on repository errors rather than proceeding on stale indexes. Four routing tests and all fourteen existing development/package-validation tests pass. New exact-head hosted validation is pending. Runtime package bytes/source pins are unchanged.

Next: verify new hosted run, then present current production Approval Gate. Pages serves main/root immediately, so do not push main while the gate is unresolved. Shared registry publication and canonical session close remain pending.

---
# Foundry 1.5.1 repair candidate, 2026-11-11

Local development candidate; not published. Public release remains 1.5.0. Canonical distribution checkout is C:/Users/TrentTimmerman/Documents/Codex/foundry-publish-recovery-20261111/apps/foundry-kodi-dist, owned by Codex-repair-foundry-navigation-20261111. New skin/helper clones are under C:/Users/TrentTimmerman/Documents/Codex/foundry-navigation-20261111/apps; their labels are repair-foundry-skin-20261111 and repair-foundry-helper-20261111. Original stale dirty checkout is untouched.

## Changes

- Add-ons launcher's left category menu background removed without changing control geometry/actions or shared search panels.
- Helper restores widget/menu XML after cold update, same-version reinstall or profile changes using persistent version/file fingerprints, one complete batch and one reload. SQLite serializes concurrent startup. Failed writes remain retryable. Normal edits update only their fingerprint to avoid an extra rebuild. Existing custom-path database/provider URLs are preserved.
- Videos content remains visible with loading feedback during metadata loading. Late provider results are rejected after Home/new folder/update/abort; nonmedia native menus avoid a redundant monitor probe. Eligible media still needs an additional metadata request; this does not establish real provider/Shield latency improvement.

## Exact source pins and evidence

- Skin 1.5.1: 908df9a394913b468d46899ea9bb351131035331.
- Helper 1.3.2: ab6517232b1ebfb23ebcbb6ff971509df7707554.
- Build/Bootstrap 1.5.1; other package versions unchanged. Ten packages.
- Source and extracted-package suites each pass 678 tests on Windows, 0 failures/errors, 2 skips (host symlink privilege and preserved-original check excluded in disposable layout).
- Deterministic extracted rebuild and all ten package ZIPs/manifests/dependencies/feed/aliases pass.
- All 115 pre-existing versioned ZIPs retain their SHA-256 hashes. Existing 1.5.0 source snapshot and pins are unchanged.
- Evidence root: C:/Users/TrentTimmerman/Documents/Codex/foundry-navigation-20261111/, final-source-tests.json/log, package-evidence/packaged-tests.json and packaged-verification.json, published-artifact-hashes.json.
- 140 XML and 46 helper Python files parsed. Focused tests include transparent Add-ons menu, widget recovery/failure/profile/edit and delayed navigation ownership.

## Blockers and next steps

1. Explicit permission to push all three dev branches is pending. Automatic review denied the attempted source dev push before execution; no push occurred. Source commits are local; this distribution handoff accompanies the local candidate commit. Do not retry without new relevant authorization.
2. Once approved, push source commits, commit/push this distribution candidate, and verify all five native Kodi development gates for that exact head. No native visual/Shield/provider claim is made from Windows tests.
3. Obtain affected-device logs/timings and test saved widgets, Back/Home/repeated navigation, provider slow/error cases and visual Add-ons menu.
4. Only after validation and the current production Approval Gate may main/Pages be changed. 1.5.0 approval does not authorize this release.
5. Registration of skin/helper was approved and added to the shared local active-repos.json under brain-only claim Codex-register-foundry-sources-20261111. Registry publication and canonical session close remain pending; preserve existing unrelated brain work.

---
# Foundry 1.5.0 published, 2026-11-11

Trent confirmed YES to the current production Approval Gate for Foundry 1.5.0, including Quick Relay, Games and Movies wallpaper work. Validated code 41afbf69151df874b96c80e9c3838059b0cc95d9 was fast-forwarded to main. Package release run 42960198717 passed all five native Kodi gates again and published QA evidence. Public-download run 42960835218 passed on both Pages and raw GitHub: ten packages, feed/checksum, hashes, ZIP integrity and aliases. Both exact public release.json URLs independently returned 1.5.0 with Quick Relay 1.1.0.

Development run 42959433883 passed 662 source and 662 extracted tests (Linux skips 0/1), deterministic rebuild and all five native gates. Independent evidence() validation passed, including all eleven complete Games PNGs. The earlier Weather crash remains an unconfirmed intermittent failure; it did not recur in the next two full Weather runs. The Games progress-transition race was corrected in QA only without weakening settled-dialog or capture assertions. Device audio, Shield, gameplay/controllers and other previously documented target-device checks remain unverified.

Public update site: https://3thirty3gitter.github.io/foundry-kodi-dist/ . Workflow receipts: https://github.com/3thirty3gitter/foundry-kodi-dist/actions/runs/42960198717 and https://github.com/3thirty3gitter/foundry-kodi-dist/actions/runs/42960835218 .

The recovery checkout is C:/Users/TrentTimmerman/Documents/Codex/foundry-publish-recovery-20261111/apps/foundry-kodi-dist. The original apps/foundry-kodi-dist dirty checkout was deliberately preserved and is now stale; do not republish or blindly apply it. All thirteen original pending files were backed up and SHA-256 verified before replay. No source package pin or published historical ZIP was overwritten.

---

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
