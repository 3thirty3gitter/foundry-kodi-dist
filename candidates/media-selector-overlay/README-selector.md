# Media icon pack selector: staged implementation

Owner: /root/media_pack_selector. No canonical repository commits or publication performed.

## Scope
Both original Foundry and Slate: Skin Settings artwork section, control 6098, Media icon pack. Uses existing helper router mode choose_media_icon_pack. Built-in icons and installed, enabled compatible approved resource packs only. Never downloads or enables addons. Cancel is a no-op.

Per-skin persistent Skin.String(MediaIconPack) stores only the validated addon ID; missing pack selection is retained so restoring the addon restores the preference. Missing, disabled, malformed, experimental packs and missing individual PNGs fall back to original skin behavior. Selected pack artwork retains RGB/alpha; legacy fallback retains its original artwork_dim tint. Studio, weather, navigation and ratings resources are intentionally unaffected.

## Manifest v1
resources/media-pack.json must be an object with integer schema_version 1, kind foundry-media-flags, release_status approved, asset_root flags, name and nonempty categories drawn from aspectratio/audiochannel/audiocodec/videocodec/videohdr/videoresolution. PNG assets live resources/flags/<category>/<lowercase Kodi alias>.png. No arbitrary root or external paths; realpath confinement rejects traversal and symlink escape. No generic unknown-codec logo. 4k/2160 and pcm_* to pcm are the only semantic aliases.

The current Pure Marks candidate is experimental-review-required and therefore deliberately not selectable. Do not change its status just to exercise this code. Use a clearly named synthetic approved QA-only fixture in a disposable profile. A future approved partial pack must omit unapproved images; missing images preserve original icons.

## Runtime
Service monitor executes before normal metadata-service pause, covering skin settings as well as playback. Existing service loop means typical update <=0.2s active / <=2s paused; compatible manifest refresh <=3s plus next service tick. No Python invoker per frame, network, autoenable or skin reload. Per-file existence checked each tick; enabled state checked each tick. Distinct list/container/player namespaces and source guards avoid stale flags while focus changes. Original and Slate namespaces never collide. Texture and ID publication ordered to prevent cross-pack stale frames. Metadata values unchanged.

Legacy MediaFlags six categories receive alternate untinted image controls. Original builtin controls are shown whenever no validated match exists. Existing layout/visibility rules, including hidden legacy flags on the home/catalog views, are retained. StreamPilot OSD resolution/channels/audio variables gain guarded selected-pack preference and retain all old JPEG and unknown-text fallback. Current helper catalog Python contains rating/studio assets but no media format badge generation; no cache rewrite needed.

## Verification
- 22 unit tests pass via python test_media_pack.py, including selection/cancel/reset, invalid/missing/experimental manifests, disabled addon, missing file, traversal, context separation, stale clearing, simulated restart persistence and original skin switch.
- Both helper modules identical after namespace normalization.
- All XML parses; selector control exactly once per skin.
- compileall passes for both helpers.
- changed-files.json records 18 changed/new product files and SHA256/baseline SHA256.
- Native Kodi rendering, actual remote navigation, physical device and real restart are NOT yet verified. Independent QA worker owns native matrix at ../foundry-media-selector-qa-20261115/NATIVE-QA-CONTRACT.md. No release-ready claim until native proof and owner integration/aggregate gates.

No version bumps made. Release owner should review changes as deltas, preserving independent studio work in shared Includes.xml. Do not replace whole source tree with this snapshot. Source baseline: owner supplied studios integration dev53f0eb5 and original sibling published snapshots042ef8f/7fdeb79. changed-files hashes are authoritative against the read snapshot.
