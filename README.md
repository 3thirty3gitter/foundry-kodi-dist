# Foundry Kodi source

Permanent Kodi File Manager source: https://3thirty3gitter.github.io/foundry-kodi-dist/

Install `repository.foundry-1.1.0.zip`, then open **Install from repository > Foundry Repository > Program add-ons > Foundry Build**.
Kodi installs Foundry 0.2.0 and Foundry Helper 1.0.1 using its dependency manager.
Run Foundry Build to activate the skin. Requires Kodi 21 Omega or newer.

`release.json` records ZIP versions and SHA-256 checksums. The repository feed and downloads are public and require no login.
Historical ZIPs remain available; the source listing always shows the current repository installer.

Build with sibling checkouts of `skin.foundry-nimbus` and `script.foundry.helper`:

    python3 tools/build_release.py --skin ../skin.foundry-nimbus --helper ../script.foundry.helper
    python3 tests/test_release.py -v

Runtime tests use mocked Kodi APIs; final navigation, rendering and playback are tested in Kodi on the target device.
