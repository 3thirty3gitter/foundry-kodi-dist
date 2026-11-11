# Native QA runtime (not a distributed product)

Both development and release CI build this official Debian 13 amd64 image for
all five existing native renderers. Ubuntu runner packages are not used for Kodi.
The tested Kodi 21.2/Python 3.13 pairing avoids the independently reproduced
Kodi 21.3/Python 3.14 concurrent empty-script SIGSEGV. No renderer assertion or
product package is disabled or changed by this runtime selection.

## Provenance and reproducibility

- Official Debian base: `debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`.
- `packages.lock` is the complete 414-package `dpkg-query -W` inventory exported
  from validated local image `sha256:7de853ad1a02a8b0a23979346d15196bc5b711ce33895d8a3b8bf0494d2da213`.
- Kodi, kodi-bin and kodi-data: `2:21.2+dfsg-4`; Python: `3.13.5-1`.
- Packages are installed only through the base image's signed official Debian
  repositories. Every package version is requested explicitly and the complete
  resulting inventory must match the lock. No PPA, unsigned repository or
  unsupported-Kodi escape hatch is used.
- This pins runtime package contents, not a byte-identical Docker image ID.
  If Debian retires any locked version, the build intentionally fails rather than
  silently upgrading. Update the lock only after rerunning the compatibility
  reproduction and all five native gates. Repository snapshots are not silently
  substituted for the tested package set.

## Reproduce on Linux with Docker

From the distribution checkout, after creating the retained extracted workspace:

```sh
export NATIVE_QA_IMAGE=foundry-native-qa:debian13-kodi21.2
export QA=releases/1.5.3-qa
docker build --platform linux/amd64 -t "$NATIVE_QA_IMAGE" tools/native-qa
cd /path/to/extracted/apps/foundry-kodi-dist
bash tools/run_native_qa.sh tools/render_library.py
bash tools/run_native_qa.sh tools/render_startup_splash.py
bash tools/run_native_qa.sh tools/render_interface.py
bash tools/run_native_qa.sh tools/render_weather.py --output "$QA"
bash tools/run_native_qa.sh tools/render_games.py --output "$QA/games"
```

The wrapper creates the QA mountpoint first, mounts the extracted apps at `/work`
read-only, then overlays only the release QA directory writable. Renderer defaults
for library/splash/interface and explicit Weather/Games output resolve into that
same overlay. Each invocation gets a disposable container, HOME/XDG directories,
portable Kodi profile and Xvfb. Host UID/GID keeps collected evidence readable.
The scripts' exit status reaches the workflow; Bash pipefail preserves it through
tee. Existing per-renderer timeouts and run-after-failure evidence collection stay
in place. Image inspection, package inventory and Kodi/Python versions are retained
alongside native logs and reports. This is desktop QA, not physical phone/Shield,
provider, audible audio or gameplay certification.
