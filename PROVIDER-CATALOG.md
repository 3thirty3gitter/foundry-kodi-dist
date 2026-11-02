# Provider-neutral Foundry catalog (unpublished candidate)

Foundry uses the same native catalog window, focus scale, artwork-colour glow,
metadata bindings and navigation controller for supported video listings. Routing
does not select a skin by add-on name. TMDbHelper is an optional documented
metadata service, not a required source of playable listings.

## Adoption and safe fallback

The video-window onload hook and service monitor handle initial loads, delayed
loads and folder changes. Adoption waits for Kodi's container to finish updating,
then reuses the probed directory snapshot. A path change during the probe cannot
open the stale directory.

Declared movie, TV show, season and episode records share the catalog. Generic
file directories require actual video type/MIME or title-identifying metadata;
a file, icon or poster alone is insufficient evidence. Native library records
can use their Kodi DB identity and declared content type. Empty declared media
directories retain the catalog's empty state. Pagination links retain their
opaque provider URLs.

Action/configuration/login/source-link listings and ambiguous mixed media/action
listings retain Kodi's browser. A nested catalog folder which resolves to such a
listing returns to Kodi with its exact URL and is not recaptured immediately.
No action URL is reinterpreted as a metadata query or automatically played.

## Metadata and navigation

Directory normalization validates optional art, named ratings, identifiers and
numeric fields. Legacy fanart/thumbnail fields remain available. Anonymous ratings
are not labelled IMDb/TMDb. Missing or malformed optional fields do not supply
fictional scores or unrelated artwork. Playback URLs, authentication parameters,
provider IDs and file/directory identity remain owned by the original listing.

Native Movies, TV Shows, Seasons and Episodes use their own documented detail
methods and supported field sets. Provider IDs are never used as Kodi DB IDs.
Native library search requests the file path so results retain playback identity.
TV-show search results browse Kodi's native season node using the verified
library TV-show ID while retaining the original physical path in metadata.
Optional TMDbHelper enrichment uses valid IMDb/TMDb IDs, otherwise exact
title/year disambiguation; conflicting returned IDs are rejected. No arbitrary
provider URL parameters are parsed. The existing bounded asynchronous jobs,
item-identity guards, metadata debounce and in-place updates preserve selection.

## Platform and data limits

This is not a universal override of an add-on's own custom windows. The monitor
adopts supported listings in Kodi's video window; separately implemented add-on
windows keep their own UI. An add-on that exposes neither a media type nor
identifying metadata cannot safely be distinguished from an action menu. Such
listings retain native navigation instead of receiving invented metadata.

Kodi Files.GetDirectory does not expose provider context-menu commands through
the requested directory schema. The catalog's Open in Kodi action remains the
escape path to the add-on's native context menu and controls. Provider-global
search/sorting APIs are not inferred: provider search/sort covers loaded titles;
native library search queries Kodi's title index. Provider pagination uses only
the links the add-on actually returns.

Artwork and named ratings still require the source or configured metadata
service to supply them. Desktop payload fixtures and native rendering do not
prove live metadata availability across every installed add-on or on Shield.
No add-on installation, credentials or provider-specific configuration is added.

## Primary-source contracts

- Kodi Omega [directory and media field types](https://github.com/xbmc/xbmc/blob/Omega/xbmc/interfaces/json-rpc/schema/types.json): List.Fields.Files supports uniqueid, firstaired, season, episode, mimetype and art; plural ratings belongs to the relevant VideoLibrary fields.
- Kodi Omega [methods](https://github.com/xbmc/xbmc/blob/Omega/xbmc/interfaces/json-rpc/schema/methods.json): native movie/TV/season/episode detail methods and their distinct field types.
- Kodi Omega [TV navigation](https://github.com/xbmc/xbmc/blob/Omega/xbmc/video/VideoDatabase.cpp#L2181): the native TV-show ID selects its season node.
- [TMDbHelper documented details route](https://github.com/jurialmunkey/plugin.video.themoviedb.helper/wiki/Detailed-Item).

Validation uses synthetic representative payload shapes (not claims of real
provider success), the shared regression suite and an isolated Kodi desktop
profile. Target-device/add-on evidence remains a separate validation step.
