# Combined Foundry 1.5.5 / Slate 0.1.4 development candidate

User first authorized development pushes and hosted tests, then explicitly authorized publication of the Kodi update. Publication still requires all native gates and visual review to pass.

Original source pins: skin 21f1353f44d2155270d995f2bb5118414c84c656 (1.5.5), helper 05b38cf11a00df03216c0a8f969962989fb30d73 (1.3.6). These owned source commits were pushed only after explicit approval. Prior 1.5.4 snapshots and every historical package remain preserved.

Scope:
- Original Foundry: twelve new wallpaper-matching metallic Settings icons, no tile frames/background layers; scoped visible Foundry branding, legal credits/internal IDs retained.
- Both skins: all installed video sources listed. Existing five integrated routes preserved; other sources honestly disclosed as open-only, disabled sources never enabled. Android interface enumeration fallback retains all phone security checks and TV confirmation.
- Slate: independent line resource pack, settings focus aspect/contrast fixes, optional helper 0.1.1. No Slate art is used in original Foundry.
- SIMKL: inert optional Program add-on offered to all skins through repository. No required official service dependency, implicit enable, credential access or history sync. User must explicitly install/open setup. Existing linked official service may resume tracking if user later installs/enables it; disclosure retained.

Eight-gate icon development run 43635695523 passed 824 tests and native checks. Manual review then required additional real folder/file and video-OSD captures plus focus aspect correction. Combined validation adds three native gates: SIMKL disclosure/cancel, actual skin-settings search picker for both skins, and four real phone-input cases (original/Slate normal/restricted discovery). Existing original interface gate additionally traverses actual Settings tiles. All new reports are publication-gated; incomplete reports fail.

No physical Shield, actual QR scan, live SIMKL install/PIN/account/history sync, or live search-provider endpoint claim. Phone fixture observes generated URL to exercise HTTP and TV confirmation, and explicitly records QR decoding/physical-phone as unverified.

Status: final combined source/extracted and native validation pending. No production push, merge or publication.

Fresh combined run 43637837846 passed nine of eleven gates. Interface/catalog readiness and search consent probes failed; active-instance readiness and explicit consent checks are being rerun in 43639921513. Phone four-case matrix passed with independent image/hash review. Slate Settings and actual video OSD reviewed; blank inherited local-file preview is not icon-render evidence, so a supported native icon-wall test now checks visible default glyph strokes. SIMKL long consent text was visually found scrolling and shortened without removing its linked-profile/history warning. Source suite now 864 tests, two expected Windows skips. Production not yet published.

Owner additionally approved verified FENskeleton action-provider correction in this release: exact namespace and media kinds only, Info/context Play route action execution without resolver expectation; generic resolver behavior unchanged, no error suppression. New original pins skin042ef8f3380fb12ee89bc37ea1dccaaace2143ee/helperce31ce6048e38b49b3d06e5752df4ea2f87a26d4. Dedicated native proof pending.

Fresh run 43643207623 passed original Settings traversal/visual review and concise SIMKL consent. Three failures remained: Slate packed textures overrode loose line defaults (now surgical XBTF index correction with all retained payloads byte-identical); search fixture was rendering Estuary despite saved skin setting (now actual native skin identity and specific switch confirmation); Slate phone native process segfaulted before keyboard (diagnostic preservation/early process failure added, no retry or product workaround). FEN action native proof now also verifies actual skin identity. Full twelve-gate fresh run required; no publication yet.
