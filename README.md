# Foundry Kodi source

Permanent Kodi File Manager source: https://3thirty3gitter.github.io/foundry-kodi-dist/

Install `repository.foundry-1.2.0.zip`, then open **Install from repository > Foundry Repository > Program add-ons > Foundry Build**.
For an existing installation, check for updates and update Foundry Build to **1.2.6**, then run it once to finish setup. The current Build ZIP is also listed in the File Manager source.
The release installs **Foundry skin 1.1.5**, **Foundry Helper 1.1.1**, and the two required artwork resources.
For the interface update while a provider dependency is failing, install the skin-only `skin.foundry-1.1.5.zip` from the same source listing, with Foundry Repository enabled so Kodi can install its helper and image resources.
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

The Home main menu is fully transparent, with separate space for the logo, action buttons and scrolling menu. Empty-library message overlays are removed from Home. Menus with visible or loading widget rows show one smaller category title at the top right; empty menus keep the full-size wallpaper. Custom menu background folders remain supported. The original artwork files are unchanged; Kodi places the compact texture over a native vector background.
All fourteen original Foundry category wallpapers are included unchanged in `resource.images.foundry.wallpapers` 1.0.0. Their Home layers render independently of background blur and switch between full-size and compact artwork according to the active widget rows, including all fifty configurable rows per custom or movie/TV menu.
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
Validation for 1.2.6: 44 checks pass. These cover the transparent Home menu, removal of empty-state overlays, populated/loading/hidden widget rows, selection changes, custom row 50, mutually exclusive title layouts, original artwork hashes, and the existing SlyGuy/OSD regressions. A reference layout was rendered from the native geometry and original assets. Target-device rendering and playback checks remain pending.

Build 1.2.6 enlarges the Home logo from its existing (60, 40) anchor and removes only its transparent canvas border. The visible artwork is pixel-identical to the original crop. The logo ends at y=155, leaving a 10-unit gap before the unchanged button group at y=165. All other Home control coordinates are unchanged. Shutdown and Search icon focus select matching native-vector wallpaper; their hover label is removed. Home widget focus no longer executes the reset-to-first-item actions, and Back returns directly to the menu while native group memory retains the selected row. The search-results window keeps its prior navigation behavior.
