# Foundry Helper

Kodi helper services, native catalog navigation and shared metadata for the Foundry skin. App changes use `dev`; published package versions and their release source pins are immutable.

## Helper 1.3.1 candidate

The next Foundry 1.5.0 candidate carries an explicit Movies submenu label into the native catalog. `Window.Property(foundry.movie_submenu_label)` contains one of the thirteen approved canonical labels, or an empty value. The skin uses this context for its fallback wallpaper; the helper leaves source artwork and opaque navigation/playback URLs intact.

`modules.movie_submenu` accepts a complete approved label or a complete terminal breadcrumb segment. `vod.activate_catalog` captures explicit native folder/category labels. Movies classification must be proven by the result records or Kodi's movies content; TV, mixed media and unrelated child routes clear the property. The context belongs to `DirectorySource`, survives paging and playback reinitialization, and returns with its own parent on Back. Search classification is checked independently and the retained library context returns when search closes.

Existing profile-specific metadata keys, search history, optional metadata error handling, list ownership and sound preferences are preserved.

## Validation

Run the helper tests from the sibling `foundry-kodi-dist` checkout:

```powershell
python -X utf8 -m unittest discover -s tests -p test_movie_submenu_context.py
python -X utf8 -m unittest discover -s tests -p test_catalog_handoff.py
python -X utf8 -m unittest discover -s tests -p test_catalog_back_navigation.py
python -X utf8 -m unittest discover -s tests -p test_provider_catalog.py
python -X utf8 -m unittest discover -s tests -p test_library_partial_load.py
```

The distribution's native interface renderer adds three real catalog context-Play / Stop / Back cycles, source and selection checks, submenu persistence and full Kodi traceback capture. Final validation requires native Kodi 21+ and the complete source/extracted-package suites. Local Kodi 20.5 rejected the shipped skin's GUI 5.17 requirement before playback, so it supplies no playback success evidence.

The originally reported false error after stopping playback remains unconfirmed. A successful controlled native fixture does not identify or fix that device-specific error; preserve the affected device's complete `kodi.log` traceback and repeat its actual provider/playback/Stop/Back sequence before claiming a fix.
