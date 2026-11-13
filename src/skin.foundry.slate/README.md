# Foundry for Kodi

Unpublished next release candidate: **skin 1.5.0 / Helper 1.3.1 / Build 1.5.0**.

## Movies submenu wallpapers and Games candidate

Thirteen owner-approved Movies submenu PNGs are integrated unchanged at `media/foundry-movie-submenus/`; `SOURCE.json` records each original label, SHA-256, byte count, dimensions and source-manifest hash. Exact provider-neutral labels select folder-focus artwork in native Movies navigation. The current confirmed directory keeps its artwork after opening results or focusing the parent entry. Unknown labels and TV/nonmedia contexts use the existing fallback. Custom backgrounds retain priority.

The dedicated catalog accepts only the helper's verified Movies `foundry.movie_submenu_label` window property. Paging, Back and playback rehydration retain the verified source context; the category image is a background fallback beneath the unchanged selected-title fanart. Home geometry, focus controls and all existing artwork bytes are preserved.

The deferred Games view is restored for this next-version candidate with an installed-add-on Home route, native Games fallback and recent/favorite rows. This is source integration, not a claim of completed Games or Shield gameplay validation. Native Kodi 21 candidate gates and publication remain pending. Published 1.4.0 packages, snapshots and source pins are unchanged.

## Unpublished catalog source-parity candidate

StreamPilot reference is pinned to f26b7f982af2746811155ddbd0949d403014e6f8. This local candidate removes the normal focus frame, pre-tints the original glow alpha mask off the GUI thread and binds the resulting file as native item artwork, and samples cached fanart first (poster fallback) off the GUI thread, with the source-defined white fallback and bounded cache-readiness retries. Focus scale, three existing glow layer geometries and every unrelated control remain unchanged. Android shadow rasterization and Kodi blurred textures are different renderers; equal parameters are not pixel parity.

Metadata enrichment uses native VideoLibrary details for library items and the installed TMDbHelper documented details route for known IDs or an exact title/year match. It preserves playback URLs and native list position, merges nonblank metadata/artwork, and labels the singular rating as TMDb only when it comes from that documented endpoint. Unknown provider ratings are not relabelled. Work is bounded to two concurrent lookups and nearby titles, with window-local bounded caches. No new secrets or credentials are read by Foundry. OMDb remains disabled until the user configures it.

Live Shield/provider success and identical artwork selection remain unverified. The isolated profile has no configured TMDbHelper/provider listing. Native public-film artwork differs from the TMDb variant in the committed reference; those captures verify bindings and focus behavior, not exact end-to-end parity. Native multi-item captures now verify blue and yellow glows with no explicit outline; the list is invalidated 250ms after asynchronous art arrives, using a synchronous width+1/restore because Kodi exposes no Python MarkDirtyRegion. Final rail geometry and selection are unchanged. The approved MEDIA CENTER header is integrated at the original 380x115 footprint. Its SVG icon bytes and FOUNDRY path are unchanged; the 4x export has minor antialiasing differences from the old raster upscale. Live provider/Shield parity remains unverified. Publication is held.

## Main-menu and library error corrections

The unchanged 535-unit Home menu holds seven complete 75-unit rows. Its fixed-list movement is bounded to six so the last focus position stays on the seventh visible row; Weather no longer falls into a clipped eighth row. Native Kodi Home tests cover filtered 3/7/8/16-item menus, a 33-item custom menu, repeated end wrapping, top/action-button return and lower-widget return without losing either selection. Header, action buttons, menu bounds, rich wallpaper pairs, crossfades and OSD controls are unchanged.

The catalog separates source-loading failures from metadata/rendering failures. Optional metadata/color failures retain the loaded poster row and safe title/type/plot fields, do not claim the source failed, and cannot escape on focus changes. Metadata lists/dates are normalized without locale-dependent strptime imports. Empty/error catalogs focus the Back button. Files.GetDirectory no longer requests the unsupported plural ratings property; VideoLibrary search retains its supported richer property set. Sanitized diagnostics include only stage, exception class and code location, never titles, provider URLs, keys or exception values.

The exact partial-load message/clearlogo/navigation error chain was reproduced in the published code by controlled metadata fault injection, and Movies/TV navigation passed with the correction. This verifies the error-handling defect and remedy, not the still-unavailable device traceback identifying the original trigger. Shield/provider validation remains necessary.

## Header, Home widget viewport and OSD fixes

The Home header keeps its original graphic, letterforms, spacing and unchanged (60,40), 380x115 control. The owner-approved lettering-only vector trace is rendered in `media/foundry-logo-traced.png` at 3040x920; the graphic is exactly the original resampled with Lanczos. The original 760x230 PNG remains intact. `resources/header-lettering-source.json` records provenance and hashes. Actual perceived sharpness still depends on GUI resolution and display processing.

All fifteen Home category stacks use a 570-unit native grouplist viewport at the existing y=510 anchor. Manual cumulative row translations are removed on Home; Kodi retains each category's scroll offset and last selected item across menu focus. The menu no longer clears the saved row marker. Legacy row fades/translations remain scoped to search. Source item geometry and controls are preserved. This addresses lower-row returns without forcing row/item zero. Regression checks model official Kodi scroll behavior; Shield validation remains required.

VOD and live-TV playback OSDs keep the soft feathered backdrop with 25% lower opacity (effective peak alpha 225 to 169). The backdrop alone is 48 units shorter: VOD 322 to 274; live 368 to 320, with top/bottom fade margin reduced from 60 to 36. Foreground positions, sizes, details, progress, buttons and navigation remain byte-for-byte unchanged. Native Kodi fixtures check both cards against bright and dark scene planes.

## Approved rich wallpaper pairs

All fourteen full-size and widget category images are the exact owner-approved 1672x941 PNGs, with corrected widget revision 1. The widget icon, text and underline were scaled together at 0.55 in the approved artwork; Kodi does not rearrange or regenerate them. Home now reads FOUNDRY / MEDIA CENTER. Foundry Wallpapers 1.1.0 provides full frames, including skin fallback and add-on fanart; widget frames are in the skin. SOURCE.json files record Library identity, exact revision and SHA256. The immutable Wallpapers 1.0.0 ZIP preserves the earlier originals. These are not native 4K images.

The existing stable image control keeps full-frame fit geometry and the 450ms filename crossfade in both directions. The clean plates are visually registered rather than pixel-identical, so slight artwork differences blend during transition; there is no geometry zoom, crop or stretch. Menu/widget focus alone does not restart it. Custom backgrounds and action artwork retain priority, and missing widget images fall back to the matching full frame. Repair patches and runtime title masks remain absent.

Populated/loading Home widgets suppress the focus-driven full-screen fanart and Flix detail panel on first and return entry. The fixed native Home viewport retains selected items and lower-row scroll offsets. Full library navigation is separate.

## StreamPilot VOD catalog

The dedicated catalog and native fallback view 57 follow StreamPilot commit `cf98b292cbf6cf91d9d79ce34fe5f780263b7956`, `VodCatalogScreen.kt`, and the [actual Movies Trending reference](https://streampilot.ca/images/streampilot-movies-trending.webp), blob `a4c2d396eb3602846e537369db634638112e5f5a`. Component geometry is normalized to Kodi 1920x1080 against that 1672x941 reference, using a 240x360 poster anchor with 32px spacing; Android dp are not copied as Kodi pixels.

The view supplies cinematic fanart/shade; Back, title, breadcrumb and Search; clearlogo/title and native metadata; a separate ratings row; 2:3 posters, artwork-color glow, 1.19 focus scale and protected overflow; studio logo above the rail; and Page / Sort By below it. Roboto and its license are included. Existing text autoscroll preference is respected. There is no active global reduced-motion preference in the existing skin; wallpaper transitions contain no slide/zoom animation.

The dedicated native WindowXML catalog owns 20-title pages, in-rail previous/next controls, four date/alphabetical sorts and a separate 32/68 search layout with 250ms debounce and ten recent queries. Local Kodi library searches query the full index. Provider directories retain their original folder/playback URLs; where a provider exposes no search or global-order API, filtering/sorting is limited to the loaded directory and an unavailable page total displays `?`. There is no invented TMDB provider API. Missing studio/clearlogo artwork remains absent. Native Kodi information, playback and source-selection behavior are preserved; playback return rehydrates the catalog's selected item.

Native Kodi 21.3 Windows fixtures verify delayed loading, sorting, search focus, stale-query rejection, 20-item pages, information return and actual local-video playback return. Home fixtures verify lower-row item retention over five category switches and hide preceding row visuals without resizing the 570-unit viewport. These captures use controlled metadata and generated fanart; they are not Shield captures or proof of pixel-identical StreamPilot rendering. Reference: StreamPilot `cf98b292cbf6cf91d9d79ce34fe5f780263b7956`. Shield, real-provider global search/pagination and artwork availability remain device/provider checks.

## Optional OMDb / IMDb ratings

Open Skin settings > Extras > OMDb / IMDb ratings settings, or Foundry Helper settings. The provider is disabled and its key blank by default. A user can enter their own OMDb key and explicitly enable it. No key is shipped or configured. Kodi masks the key on screen but stores profile settings unencrypted; this is not Android Keystore security.

IMDb ratings are fetched through OMDb; Rotten Tomatoes/Metacritic are optional. Native Kodi IMDb values remain a fallback. Missing/N/A values are omitted. Lookup prefers IMDb ID, otherwise title/year/type; updates debounce 200 ms. Cache TTL is seven days, bounded stale use thirty days, misses fifteen minutes, and disk cache at most 2000 entries. Global quota/auth/offline backoff persists across titles/restarts. Key change/removal invalidates cache and in-flight responses, including while browsing is paused. HTTP timeouts are bounded; errors do not log keys or request URLs.

[OMDb documentation](https://www.omdbapi.com/) specifies CC BY-NC 4.0 content terms and non-affiliation with IMDb; its [free key page](https://www.omdbapi.com/apikey.aspx) lists 1000 requests/day. Confirm suitable usage rights before activation, particularly for commercial use. No provider data is redistributed. The [official IMDb GraphQL API](https://data.imdb.com/documentation/api-documentation/) is separately licensed through AWS Data Exchange and is not implemented, purchased or activated here. Existing TMDB/Kodi metadata provide artwork/descriptions when OMDb is unavailable.

## Earlier release notes

Foundry 1.1.3 is the 3Thirty3 Kodi skin based on Nimbus 0.1.43 by Ivar Brandt.
Requires Kodi 21 Omega or newer and Foundry Helper 1.1.1.
Foundry Build 1.2.3 installs the standard add-ons together, including CocoScrapers, SlyGuy Trailers, TMDb metadata tools, Android TV UI Sounds and adaptive playback support.
Message dialogs use a translucent dark card with a soft shadow, theme accent and readable text, including the first skin confirmation before Home initializes its settings.
The sidebar reserves separate space for its logo, action buttons and menu. All 14 original 4K Foundry wallpapers are restored unchanged in the Foundry Wallpapers image resource, installed automatically with the skin. The selected category renders full-screen in both home layouts, including with background blur enabled. Widget artwork takes over only when entering a widget; returning to the sidebar restores the category wallpaper.

Add this source in Kodi File Manager:

https://3thirty3gitter.github.io/foundry-kodi-dist/

Install the repository ZIP, then select **Install from repository > Foundry Repository > Program add-ons > Foundry Build**.
Kodi resolves the skin and helper dependencies. Run Foundry Build to activate the skin.
The skin can also be selected directly under **Look and feel > Skin > Foundry**.

Release packages and checksums are maintained in `3thirty3gitter/foundry-kodi-dist`.
Code is GPLv2; artwork is CC BY-SA 4.0. Original Nimbus attribution is retained in LICENSE.txt.


The video OSD ports StreamPilot’s compact VOD poster panel and unified live-TV card, including the original audio/resolution badges, five-second idle hide, Back-to-dismiss, and fixed 30-second seek controls. Layout and badge source: StreamPilot commit `9f746fc90af40128e5fcfba60056ada99770b796`. Native Kodi playback/audio/subtitle settings are accessible from the VOD settings button; source selection remains the responsibility of the video add-on.


## File Manager bookmarks

FenSkeleton (`https://fenskeleton.github.io/zips/repository.fenskeleton/`) and Forge Releases (`https://silencebob2.github.io/forge-releases/`) are merged idempotently into profile File Manager sources when Foundry starts. Existing sources are preserved, and an existing valid file is backed up before the first merge. Restart Kodi once after updating for its source list to reload. This does not download, install, enable or update either repository or its add-ons. Invalid source XML is left untouched.
