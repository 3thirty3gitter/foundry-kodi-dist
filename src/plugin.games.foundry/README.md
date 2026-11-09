# Foundry Games 0.1.0 (integration candidate)

Independent Python 3.8+ Kodi 21 Omega plugin. Original implementation; no
StreamPilot Android/LibretroDroid code, binaries, credentials, ROMs or BIOS copied.

## Implemented

- All 17 StreamPilot console categories, explicit source-to-console assignment,
  selected files or recursive local/configured Kodi VFS folders.
- Versioned SQLite profile catalog, atomic source scans, cancel/error rollback,
  explicit rescans (never startup scanning), 20-game pages, title/system search.
- Stable source/relative-file identities, favorites, recent successful launches,
  gameplay duration, catalog-only source removal. History survives reimport.
- Local metadata and artwork, detail dialog, game-native InfoTagGame fields.
- Bounded staging, safe ZIP extraction, intact standalone Arcade ZIPs, recursive
  CUE/M3U dependencies. Relative layout is preserved; missing/traversing/ambiguous
  files fail. Multi-disc playlist children are hidden in the library.
- Kodi RetroPlayer launch with core unset, retaining Omega emulator/savestate
  chooser. Kodi owns controller ports, saves, reset and gameplay OSD.
- New dedicated skin include View_58_FoundryGames.xml has focused hero metadata
  and horizontal box-art row, bounded text and standard directory Back behavior.

## Local metadata

For Game.nes, optional Game.json accepts title, overview, publisher, developer,
genre and year. Maximum sidecar size is 64 KiB. Artwork: Game.png (thumb),
Game-boxart.png, Game-fanart.png and Game-clearlogo.png. JPG/WebP also work.
No remote scraping or metadata service requests occur.

## Integration (1.5.0 candidate, canonical owner only)

1. This source folder is restored in the next-release deterministic packaging; published 1.4.0 remains unchanged.
2. Add plugin.games.foundry 0.1.0 as a build dependency if installation is desired.
3. Skin Includes.xml: include file="View_58_FoundryGames.xml".
4. Skin MyGames.xml: add 58 to views and include View_58_FoundryGames among views.
5. Home Games action: ActivateWindow(games,plugin://plugin.games.foundry/,return).
6. Widgets: plugin://plugin.games.foundry/?action=games&mode=recent or favorites.
7. Run full source and extracted-package tests, deterministic rebuild and all five native Kodi 21+ gates before publishing. Games is mandatory in both development and publication; restoration alone is not a pass.

Do not pass game entries through the shared movie/TV metadata resolver. Namespaced
Foundry.Game.Id/System/Platform/Overview/MetadataStatus properties are available.
Each completed directory has a fresh Container.Property(Foundry.Games.DirectoryId);
native automation must wait for that identity after refresh/navigation, not only
a committed database favorite or an updated FolderPath. Search cancellation
retains the preceding native listing and focus.

## Deliberate boundaries and validation gates

- PSP is explicitly unsupported: no verified native Omega ARM64 core. No external
  Android emulator bridge exists. Other systems have catalog candidates, not
  claims of tested Shield compatibility. N64 render path and DS touch/dual-screen
  especially require device testing. Missing cores use native Kodi selection.
- No core is downloaded or installed automatically. Non-commercial core license
  restrictions still need review for customer/commercial use. No binaries bundled.
- Only standalone Arcade ZIP sets are staged. Dependent/merged sets and .7z are
  not established compatible. Supported extensions are intentionally conservative.
- No direct Google Drive OAuth. A user-configured VFS provider is separate and
  must actually support listing and binary reads. Because some VFS providers
  silently report empty folders on failure, VFS scans only add/update records,
  never hide previously indexed records. Explicit source removal is available.
  Local scans hide missing games but retain history. Provider QA remains required.
- No savestate or SRAM migration, forced Start Over, custom emulator controls,
  multiplayer/controller replacement, shader implementation or save deletion.
- Native controller/Back/launch/resume focus needs real Kodi and Shield validation.
  Python tests mock Kodi APIs and synthetic bytes; they are not gameplay tests.
- Cache limit 8 GiB, per-job bytes 4 GiB, 2,048 archive entries. Cache is immutable
  and never auto-evicted, so active games stay pinned. Full cache fails safely;
  a managed cache-cleanup UI is not yet implemented. Sources are reread to verify
  content identity, then completed cache paths are reused. UTF-8 disc descriptors
  only. Real filesystem symlink creation may be unavailable in Windows test hosts.
- Game sessions >60 seconds in the native chooser before actual playback are not
  recorded in recent/playtime by this first callback bridge; launch remains native.
- No install, profile changes, package build, publish, commit or release is done by
  these files. Packaging/device approval belongs to the integration owner.

Verified native contracts (Omega branch):
- https://github.com/xbmc/xbmc/blob/Omega/xbmc/addons/PluginSource.cpp (game provides)
- https://github.com/xbmc/xbmc/blob/Omega/xbmc/interfaces/legacy/InfoTagGame.h
- https://github.com/xbmc/xbmc/blob/Omega/xbmc/games/GameUtils.cpp (native chooser)

Tests: python -m unittest discover -s tests -p "test_games*.py" -v
