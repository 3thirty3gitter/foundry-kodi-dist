# Foundry Kodi source

Current release: **Build and Bootstrap 1.2.9 / skin 1.1.8 / Helper 1.1.2**.

Permanent Kodi File Manager source: https://3thirty3gitter.github.io/foundry-kodi-dist/

Install `repository.foundry-1.2.0.zip`, then open **Install from repository > Foundry Repository > Program add-ons > Foundry Build**. Existing installations can check for updates, update Foundry Build to **1.2.9**, and run it once. For an interface update while a provider dependency is blocking setup, install `skin.foundry-1.1.8.zip` from the same source with Foundry Repository enabled.

This release restores the exact original header logo at sufficient 1080p/native-4K pixel density, keeps lower Home widget rows inside a fixed native scrolling viewport when returning to the menu, and replaces playback OSD card edges with a soft fade. All wallpaper assets remain unchanged from 1.2.8. OMDb remains optional, disabled by default, with no user key bundled.

The previous release's fourteen standalone widget wallpapers, 450ms crossfade and native StreamPilot-style VOD catalog remain. Kodi sorting, groups-of-six paging and existing search retain the documented platform differences. Actual Shield rendering, focus/navigation, perceived logo sharpness and playback checks remain pending. See the skin README for details and provider terms.

    python tools/build_release.py --skin ../skin.foundry-nimbus --helper ../script.foundry.helper
    python -m unittest discover -s tests -v

`release.json` records all versions, ZIP sizes and SHA256 checksums. Packaging validates all approved widget image bytes. The original wallpaper, OSD resource, repository and Helper packages retain their existing versions and bytes.

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

The Home main menu is fully transparent, with separate space for the logo, action buttons and scrolling menu. Empty-library message overlays are removed from Home. Menus with visible or loading widget rows keep the full-size wallpaper and show only its isolated title artwork smaller at the top right. A feathered PNG repair layer covers the original title in place. Empty menus keep the original wallpaper. Custom menu background folders remain supported at full size, without category repair overlays.
All fourteen original Foundry category wallpapers are included unchanged in `resource.images.foundry.wallpapers` 1.0.0. Their Home layers render independently of background blur and follow the active widget rows, including all fifty configurable rows per custom or movie/TV menu. The title masks use literal include parameters compatible with Kodi 21.
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

Runtime tests use mocked Kodi APIs; final navigation, rendering and playback are tested in Kodi on the target device.
## Historical release notes

Validation for 1.2.7: 45 checks pass. These cover unchanged Home control positions, vector-outline logo and oversampled PNG, full-screen backdrop geometry, all fourteen title-removal layers, unchanged backdrop pixels outside repair regions, static diffuse paths, custom backgrounds, populated/loading/hidden widget rows, selection changes, custom row 50, original artwork hashes, dependency closure, and the existing SlyGuy/OSD regressions. Reference layouts are rendered from the native geometry and original assets. Target-device rendering, navigation and playback checks on Shield remain pending.

Build 1.2.7 packages skin 1.1.6 from `skin.foundry-nimbus` commit `94e7f537003c2078d33d070f801c6028ce9b0570` and unchanged Helper 1.1.1 from commit `44ed58036a7ee2dffafcc9b90a4248aae656d871`. The Home logo now uses clean vector outlines and a 2280-pixel PNG at the unchanged (60,40), 380x115 control. Only the category title moves and shrinks when widgets are shown; the surrounding wallpaper retains its full-screen scale. ZIP metadata is fixed across Windows and Linux so unchanged package versions keep their existing checksums.

Build 1.2.6 enlarges the Home logo from its existing (60, 40) anchor and removes only its transparent canvas border. The visible artwork is pixel-identical to the original crop. The logo ends at y=155, leaving a 10-unit gap before the unchanged button group at y=165. All other Home control coordinates are unchanged. Shutdown and Search icon focus select matching native-vector wallpaper; their hover label is removed. Home widget focus no longer executes the reset-to-first-item actions, and Back returns directly to the menu while native group memory retains the selected row. The search-results window keeps its prior navigation behavior.
