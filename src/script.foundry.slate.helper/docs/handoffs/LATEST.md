# Helper 1.3.5: ten additional Movies categories, 2026-11-12

Local development candidate only. Added exact-label Genres, Providers, Languages, Years, Decades, Certifications, Because You Watched..., Watched, Recently Watched and In Progress routing. Ten new metallic icon/title wallpapers retain the exact approved Trending background outside their right-side foregrounds. Original 45 approved frames, old provenance, Home geometry, custom-background and selected-title fanart precedence remain unchanged. Owner explicitly approved deterministic composition.

Source and packaged/native checks are pending; final results are in the distribution handoff. No dev push, production publication, physical phone or Shield verification is claimed. Work is isolated under Documents/Codex/foundry-category-wallpapers-20261112/apps.

---

# Foundry Helper 1.3.4 local candidate, 2026-11-11

QR phone entry discovers a physical Android/Linux LAN IPv4, fails closed for ambiguous/unavailable discovery, and retains revoked QR imagery only for exit animation. Password/PIN exclusions, temporary token-protected plaintext trusted-LAN service and explicit TV OK remain enforced.

Unpublished local dev candidate only. No push, production merge, release or published artifact changes authorized. Physical phone/Wi-Fi and Shield remain unverified. 35 focused phone tests and exact latest-source Kodi 21.3 phone-evidence-08 passed, including HTTP entry, TV OK, Cancel/Back, hidden-field exclusions and pixel-identical restored keyboard. The missing-fcntl fail-closed regression is included; evidence08 supersedes evidence06 for exact latest code. Final combined validation is pending. Working tree: C:/Users/TrentTimmerman/Documents/Codex/foundry-phone-fix-20261111/apps.

---

# QR phone connection repair, 2026-11-11

Unpublished local work under C:/Users/TrentTimmerman/Documents/Codex/foundry-phone-fix-20261111/apps. Published helper 1.3.3 / Foundry 1.5.2 remain unchanged.

Phone entry now selects a discoverable physical Wi-Fi/Ethernet IPv4 on Android/Linux instead of blindly advertising a VPN-selected Kodi IP. Ambiguous or unavailable physical discovery fails closed with a TV status. Unsupported platforms preserve the validated-Kodi-IP fallback. No routing, firewall, VPN, credentials or server-exposure settings change. See docs/PHONE-ENTRY.md for selection and limitations.

Keyboard full-size/QR animation work retains a revoked QR image for 350 ms only after session/listener closure, guarding newer-session cleanup. Ten network and five lifecycle/layout regression tests plus all 19 prior phone security tests pass together (34 total). Native Kodi 21.3 focused tests passed physical-interface discovery despite a simulated VPN-reported Kodi IP, HTTP delivery, explicit TV OK, Cancel, Back and hidden-input exclusion. Final native evidence is in project-root/phone-evidence-06; independent PNG verification confirms full-size restoration and intact controls. Real phone/Shield remains unverified. Full integrated source/extracted/native release gates must run after the simultaneous wallpaper redesign.

No commit, push, version bump or production publication by this repair task. Current task handoff: project-root/QR-REPAIR-HANDOFF.md. Prior release/candidate records below are historical.

---
# Foundry Helper 1.3.3 local candidate, 2026-11-11

Studio-logo resolution now uses actual installed white/coloured pack entries and explicit/parent artwork aliases. Native keyboard Phone entry is temporary, token-protected trusted-LAN HTTP, excludes hidden/password/PIN fields, requires TV OK and cancels with the dialog. See docs/PHONE-ENTRY.md for security limitations.

Local dev candidate only. No production publication or push authorized. Source integration passed 722 Linux tests before versioning; final versioned source/extracted and native release gates are pending. The distribution handoff is authoritative for final validation. Real phone browser/Wi-Fi and Shield remain unverified. Source checkouts are under C:/Users/TrentTimmerman/Documents/Codex/foundry-wallpaper-20261111/apps.

---
# Helper 1.3.2 navigation/widget repair candidate, 2026-11-11

Unpublished development work. Source: C:/Users/TrentTimmerman/Documents/Codex/foundry-navigation-20261111/apps/script.foundry.slate.helper. Own canonical claim: Codex-repair-foundry-helper-20261111.

Widget generation now has persistent per-profile version/file fingerprints. Cold update, same-version reinstall and profile switches restore all ten includes from the existing custom-path database before one skin reload. A shared-masterprofile SQLite transaction guards simultaneous startup invocations. Failed writes do not stamp completion. Normal individual edits update their own fingerprint, avoiding an extra rebuild/reload without masking corruption elsewhere. Database rows and provider paths are preserved.

Catalog routing now rejects provider results after Home/new folder/updating/abort and marks native onload probes handled so nonmedia menus are not fetched redundantly by the monitor. Eligible media still needs a separate metadata probe after Kodi's original provider load. This is not a measured Shield latency fix.

Eleven focused widget and three navigation tests pass; final full and packaged/native candidate results belong in the distribution handoff. No production publication occurred.

Next steps:
1. Complete source/extracted tests and five native gates for distribution 1.5.1.
2. Verify cold update with real saved widgets and affected-device provider performance.
3. Preserve 1.5.0 artifacts and obtain current production approval before publication.

---
# Foundry Helper 1.3.1 development handoff

Updated 2026-11-09 UTC. Branch: dev. Intended distribution: Foundry 1.5.0, unpublished. Uncommitted product work: none. This documentation receipt follows validated runtime pin 8fb2841867a54ce363ef79f05e115305ab1738cf; do not move the distribution pin merely for documentation.

## Completed

- resources/lib/modules/movie_submenu.py defines thirteen exact canonical Movies submenu labels and complete-label/terminal-breadcrumb matching.
- vod.activate_catalog captures explicit category/folder context. Catalog publication requires verified movie classification. Mixed, TV, nonmedia and unrelated child contexts clear the Window property foundry.movie_submenu_label.
- Each DirectorySource owns its context. Server paging carries it, Back restores the retained parent, playback reinitialization retains it, and search is classified before returning to library context.
- Item art, opaque source URLs, profile keys/history, optional metadata failure isolation and sound choices are preserved. Custom and selected-title fanart keep precedence in the skin.

## Verification

[Distribution run 42564799165](https://github.com/3thirty3gitter/foundry-kodi-dist/actions/runs/42564799165), candidate bcd5875b4215bf6e268f05444c096b1a7f0a30ff, passed source/extracted suites of 653 tests, deterministic rebuilding and all five native Kodi 21.3 gates. CI source/extracted skips 0/1; local Windows skips 1/2. Ten packages/feed/hash/dependency checks and all 92 published 1.4.0 hashes passed.

The native interface gate exercised three real catalog context-Play / native Stop / Back cycles: preserved source/file/fanart/submenu/count/selection/focus, no false source message, exact parent return, and complete traceback evidence with no Python failures. It uses a private profile/free RPC port/own-log identity. Library wallpaper tests proved all thirteen approved routes, custom/fanart precedence, TV/mixed/unknown negatives and paging/native-list rehydration.

Jimmy independently verified the downloaded artifact digest and the complete publication evidence gate read-only. Integration details and artifact identity: sibling foundry-kodi-dist/docs/handoffs/LATEST.md and 2026-11-09-validation.json. Local Kodi 20.5 was diagnostic only; its rejected GUI dependency establishes no native success.

## Playback boundary and next steps

The original device false error after stopping playback has not been reproduced or confirmed fixed. No speculative playback behavior patch was made. Existing native-list rehydration, idempotent closes, optional-metadata isolation and original Videos parent contracts remain intact.

1. Obtain the affected-device full Kodi traceback/ADB access and repeat its actual provider/playback/Stop/Back sequence.
2. Review the dev changes and explicitly authorize draft PR posting if desired. Automatic approval review rejected that action without explicit authorization; no PR exists.
3. Validate Shield/provider/audio/restart behavior, then follow the current production Approval Gate before main/publication. Published 1.4.0/helper 1.3.0 stays immutable.
4. Close only this tab's own claim at actual session end. This task receipt is not a session-close receipt.
