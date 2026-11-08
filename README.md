# Foundry Kodi source

Release 1.3.9: **Build and Bootstrap 1.3.9 / skin 1.3.9 / Helper 1.2.7 / Wallpapers 1.1.0**.

The pinned source commits are in [releases/1.3.9-sources.json](releases/1.3.9-sources.json). The release workflow builds the packages from those commits, runs all 277 checks against source and extracted ZIPs, verifies deterministic rebuilding, then publishes the ZIPs and feed in one commit. Public download verification is recorded separately in `releases/1.3.9-verification.json` once complete.

Release 1.3.9 adds library-style focused widget metadata and a studio logo above the left side of the row, restores the rounded StreamPilot OSD frame from the pinned Android source, removes page-loading overlays and simplifies page labels. Complete pages remain visible during replacement loads; an independent cached artwork-color path avoids a white placeholder glow. Settings hover uses the small-title wallpaper when the current menu has widgets. All 52 system-menu icons use Foundry chrome/neon artwork, with matching wallpaper categories derived from their approved image and 195 static entries/templates covered. Existing Home icons and logo geometry are preserved. Native interface captures cover widgets, episode details, Settings wallpaper variants, system menus and both OSD frames.

The release also installs the approved Foundry full-frame image unchanged at Kodi's writable startup splash location. The active-skin helper handles existing users automatically, and Foundry Build installs it before optional trailer setup. Kodi displays it on the next full restart. Previous custom PNG/JPEG splashes are preserved as numbered .before-foundry backups; no APK, global Kodi settings, or menu artwork is modified. The new cold-start check captures the real Kodi splash on desktop. Shield restart testing remains pending.

## Shared media catalog

The release uses provider-neutral listing classification and metadata normalization. Supported Movie/TV/Season/Episode listings share the Foundry catalog regardless of add-on name. Ambiguous settings, account actions, source links and mixed action/media screens retain native Kodi navigation; nested non-media folders return to Kodi with their untouched URL. Native Season/Episode details use their own field sets, and library search retains playable file identity and native TV season navigation. See [PROVIDER-CATALOG.md](PROVIDER-CATALOG.md) for the exact adoption contract, tested payload shapes and custom-window/context-menu limitations. These are desktop and payload-contract checks, not a claim that every installed provider has been verified on Shield.

Release 1.3.6 restores Favorites media details and episode identification. Kodi Favorites uses the catalog view with identity-checked shared metadata, and its metadata service remains active while browsing Favorites. Saved native media resolves through Kodi; provider media reuses source metadata captured under a hashed playback target, and known TMDbHelper targets resolve by their explicit IDs. Favorite aliases, ordering and saved actions are unchanged. Unknown provider actions are never executed to scrape details or guessed from an alias. Episodes display the show title, season/episode number, episode title, air date, runtime and available plot/ratings/artwork; specials retain season/episode zero. Both native and dedicated views bind the shared result. The native Kodi check covers real favorite entries and normal/special episode cases as well as the prior glow, page arrows and removed sort/search controls. Evidence is in `releases/1.3.6-qa/`. Shield and live provider verification remain pending.

Metadata enrichment uses native VideoLibrary details and direct TMDb/OMDb clients configured once per Kodi profile. The shared service covers the Foundry catalog, native media views, Home/widgets, details and playback OSD. It supplies artwork, cast, studios, certifications and named ratings, using validated media IDs or an exact title/year match. A bounded SQLite cache and cross-interpreter request leases reuse results across surfaces and restarts. Changes to keys, language, region or the cache invalidate in-flight results. Missing keys, unavailable services and quota errors preserve source data and navigation; playback URLs and watched state remain owned by the source.

Open **Skin settings > Extras > TMDb / OMDb shared metadata settings** (or Foundry Helper settings). Enter your personal TMDb v3 API key or read access token. Enter and enable your personal OMDb key for IMDb ratings; Rotten Tomatoes and Metacritic are optional switches. Choose metadata language and certification country (Canada by default). Keys are masked on screen and stored in the Kodi profile. No keys are embedded or copied from StreamPilot. Existing source metadata remains the fallback. Live API calls with personal keys and Shield rendering/playback remain unverified.

Live Shield/provider success and identical artwork selection remain unverified. The earlier isolated desktop profile had no configured TMDbHelper/provider listing. Native public-film artwork differs from the TMDb variant in the committed reference; those captures verify bindings and focus behavior, not exact end-to-end parity. Prior native multi-item pixel checks verified the corrected colored glow; deferred container invalidation prevents stale white pixels without a list reset or focus change. Final rail geometry is unchanged. The approved MEDIA CENTER header is integrated at the original footprint. SVG icon bytes/main path are unchanged; raster sampling differs slightly from the prior upscale.


Permanent Kodi File Manager source: https://3thirty3gitter.github.io/foundry-kodi-dist/

Install `repository.foundry-1.2.0.zip`, then install/run Foundry Build. Existing installations can check for updates and run Build **1.3.9**. The skin-only `skin.foundry-1.3.9.zip` is available when a provider dependency blocks setup; its dependency requires Wallpapers **1.1.0**.

The release retains the 1.2.42 corrections that bound Home menu movement to six so Weather stays visible, and isolate optional library metadata/color errors from source loading and navigation. It preserves every unrelated Home control, all approved rich images, transitions, OSD sizes and foreground controls. The exact device metadata trigger remains unconfirmed without its traceback; native controlled failure tests reproduce and fix the reported partial-load/error chain.

The release retains all fourteen approved rich full/widget wallpaper pairs. The OSD now restores the rounded StreamPilot background frame using the dimensions and gradient geometry recorded in skin resources/streampilot-osd-source.json. Every image is copied unchanged at 1672x941. All widget images are corrected revision 1, retaining the approved 55% uniform icon/text/underline group. Home artwork reads FOUNDRY / MEDIA CENTER. Full images, the skin fallback and add-on fanart use the complete frames. The historical Wallpapers 1.0.0 ZIP remains unchanged.

The 450ms full-frame crossfade, fixed widget viewport, lower-row selection retention, Umbrella visibility fix, traced header and dedicated library remain unchanged. Clean plates are visually registered, not pixel-identical. The restored OSD uses the source rounded card instead of the interim feather backdrop; foreground controls retain their size, position and action.

Native Kodi 21.3 Windows fixtures check all wallpaper pairs, both transition directions, menu returns, rapid toggles and bright/dark OSD scenes. These are controlled fixtures, not Shield captures or proof of exact StreamPilot parity. The library layout remains from 1.2.40, with the metadata/error corrections above; OMDb stays optional and disabled without a user key. FenSkeleton and Forge Releases remain URL bookmarks only, with no repository installation or activation.

    python tools/build_release.py --skin ../skin.foundry-nimbus --helper ../script.foundry.helper
    python -m unittest discover -s tests -v

Packaging rejects missing/modified approved pairs, stale widget revisions and mismatched dimensions. `release.json` records versions, sizes and SHA256 checksums. The OSD resource and repository package bytes are unchanged; the Helper is version 1.2.7.

Kodi installs the following core add-ons using its dependency manager. SlyGuy Trailers installs when Foundry Build runs, after its repository has been prepared:

| Add-on | Purpose |
| --- | --- |
| CocoScrapers Module | External scraper module for compatible providers |
| SlyGuy Trailers | Default trailer provider, with its own playback dependencies |
| TMDb Helper | Discovery, lists, metadata, artwork and supported ratings APIs |
| The Movie Database Python | Movie-library metadata and IMDb ratings |
| TMDb TV Shows | TV-library metadata, artwork and ratings |
| Android TV UI Sounds | Default navigation sounds |
| InputStream Adaptive and InputStream Helper | Adaptive playback and stream support |

IMDb, OMDb, MDbList and Fanart.tv are data services used by the metadata tools; separate add-ons for each are not required.
Personal API keys and accounts remain user-specific. Trakt scrobbling, subtitle services and Artwork Dump are optional additions.

Foundry Repository includes the upstream SlyGuy and CocoScrapers feeds. Foundry Build registers and enables the original bundled SlyGuy Repository before asking Kodi to install Trailers and its dependencies.
Their original ZIPs are downloaded directly from upstream, without repackaging. No YouTube/Tubed replacement add-ons are installed.

The Home main menu is fully transparent, with separate space for the logo, action buttons and scrolling menu. Empty-library message overlays are removed from Home. Menus with visible or loading widget rows keep the full-size wallpaper and show only its isolated title artwork smaller at the top right. Widget mode uses its separately approved complete image, without repair layers. Empty menus keep the original wallpaper. Custom menu background folders remain supported at full size, without category repair overlays.
All fourteen original Foundry category wallpapers are included unchanged in `resource.images.foundry.wallpapers` 1.0.0. Their Home layers render independently of background blur and follow the active widget rows, including all fifty configurable rows per custom or movie/TV menu. No runtime title masks are used.
The playback OSD ports StreamPilot's VOD poster panel and live-TV card, with original format badges, artwork-based colors, five-second idle hiding, Back-to-dismiss, and fixed 30-second seek buttons. Native Kodi audio, subtitle and playback settings remain accessible. Source selection is handled by the video provider.
`resource.images.foundry.osd` 1.0.0 contains the original StreamPilot badges. Both artwork resources are included in the repository feed and installed as skin dependencies; they no longer depend on an unpublished package.
Build 1.2.4 fixes an installation-order defect: SlyGuy Common requires `repository.slyguy`, but Kodi refuses to install repositories as dependencies ([Kodi Omega resolver](https://github.com/xbmc/xbmc/blob/Omega/xbmc/addons/AddonRepos.cpp#L456-L463)). The repository is now prepared before the native trailer installation. Existing disabled SlyGuy components are enabled; completed setup is not repeated. Cancellation or a setup failure produces a retry message before skin activation. Skin installation is also available independently of SlyGuy.
SlyGuy and Android sound defaults migrate once per profile; later user changes are preserved.
Run Foundry Build to activate the skin. Requires Kodi 21 Omega or newer.

`release.json` records ZIP versions and SHA-256 checksums. The repository feed and downloads are public and require no login.
Each resource's `SOURCE.json` records its original repository, commit and asset Git hashes. Wallpaper source: `skin.foundry` commit `7aeaf147cf0e37ad7c6408acf4d349dc1ae187ed`; OSD badge source: `StreamPilot` commit `9f746fc90af40128e5fcfba60056ada99770b796`.
Historical ZIPs remain available; the source listing always shows the current repository installer.

Build with sibling checkouts of `skin.foundry-nimbus` and `script.foundry.helper`:

    python3 tools/build_release.py --skin ../skin.foundry-nimbus --helper ../script.foundry.helper
    python3 tests/test_release.py -v

Runtime tests use mocked Kodi APIs; final navigation, rendering and playback still require verification in Kodi on Shield.
## Historical release notes

Validation for 1.2.7: 45 checks pass. These cover unchanged Home control positions, vector-outline logo and oversampled PNG, full-screen backdrop geometry, all fourteen title-removal layers, unchanged backdrop pixels outside repair regions, static diffuse paths, custom backgrounds, populated/loading/hidden widget rows, selection changes, custom row 50, original artwork hashes, dependency closure, and the existing SlyGuy/OSD regressions. Reference layouts are rendered from the native geometry and original assets. Target-device rendering, navigation and playback checks on Shield remain pending.

Build 1.2.7 packages skin 1.1.6 from `skin.foundry-nimbus` commit `94e7f537003c2078d33d070f801c6028ce9b0570` and unchanged Helper 1.1.1 from commit `44ed58036a7ee2dffafcc9b90a4248aae656d871`. The Home logo now uses clean vector outlines and a 2280-pixel PNG at the unchanged (60,40), 380x115 control. Only the category title moves and shrinks when widgets are shown; the surrounding wallpaper retains its full-screen scale. ZIP metadata is fixed across Windows and Linux so unchanged package versions keep their existing checksums.

Build 1.2.6 enlarges the Home logo from its existing (60, 40) anchor and removes only its transparent canvas border. The visible artwork is pixel-identical to the original crop. The logo ends at y=155, leaving a 10-unit gap before the unchanged button group at y=165. All other Home control coordinates are unchanged. Shutdown and Search icon focus select matching native-vector wallpaper; their hover label is removed. Home widget focus no longer executes the reset-to-first-item actions, and Back returns directly to the menu while native group memory retains the selected row. The search-results window keeps its prior navigation behavior.

