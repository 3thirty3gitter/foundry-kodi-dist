# Slate 0.1.2 and Canada Weather 0.1.1

Owner approved publishing expanded Slate weather, location persistence fix, larger menu text, optional menu icons, and visible footer focus. Original Foundry skin and installer remain unchanged.

Slate weather uses existing seven-day provider properties with missing-day visibility guards and selected-day details. Main-menu Right routes weather into forecasts or settings, retaining other category routes. Menu font is 31 (nearest integer to 28 plus 10%). Icons default shown; persisted SlateHideMainMenuIcons controls menu images only. Footer Power/Settings/Search retain actions and gain accent tint/115% focus transition.

Canada Weather chooser actions close the add-on settings dialog before running selection, so new location settings are saved instead of being discarded when an open dialog exits via Back. No setting key migration.

Native gates retain original tests and add Slate weather. Weather gate exercises actual settings chooser/search/select, reopen/Back and same-profile restart. Slate navigation gate preserves three-cycle navigation and adds actual radio toggle, two restarts and footer pixel differences. Known generated Slate evidence is cleared before each run to prevent prior published reports satisfying waits.

Offline synthetic native fixtures only. No physical Shield or live-provider certification. Publication requires all source, extracted-package, deterministic build, native and public-download gates.
