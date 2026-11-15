# Audio-only readability stage, not published

Four narrow product files only, based on owner canonical local module hardening and OSD XML. delta.json contains exact before/after SHA256. No canonical edits performed by this worker.

Selected approved audio derivative only: width160 x height54, aspectkeep, no tint. Builtin, missing derivative and unavailable pack retain76 x54. Resolution/channel icon sizes unchanged. Live selected row332(right164), text right536; builtin row248, text right452. Both preserve40px gap. VOD has sufficient existing available width; no VOD container expansion. Runtime geometry uses mutually exclusive static controls, not unsupported variable dimensions. Live details duplicate static noninteractive groups; no IDs duplicated.

Derivative contract is explicit resources/media-pack.json osd_asset_root='flags-osd', osd_derivatives mapping audioalias -> source_sha256, bbox[l,t,r,b], sha256. Only player audio resolves it; all legacy/list originals retained. Hash check stat-cached and PNG validation retained. Missing/malformed/hashmismatch derivative returns original and wide=false. Only declared compatible approved packs processed. Current actual asset manifest remains experimental-review-required, not selectable in production.

QA worker's separate resources/flags-osd variants alpha-trim existing genuine originals with every nonzero-alpha pixel retained, no resampling/recolor. Provenance verified there. Source flags and source release status unchanged. Review actual variants and long Live title readability natively before release.

35 unit tests pass, including all original28 plus player-only derivative routing, missing/disable/hash/source mismatch/root/bbox fallback. Both XML parse. Native rendering remains pending independent QA. Requested native comparisons: actualAC3 playback VOD and Live with long title, selectedwide vsBuiltin, imagealpha/RGB integrity, selectedderivedmissing revertslayout, navigation/seek no overlap. No publication authorized by this staging request.
