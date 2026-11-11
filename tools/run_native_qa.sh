#!/usr/bin/env bash
# Run unchanged renderers against ZIP-extracted add-ons, never writable product sources.
set -euo pipefail
: "${NATIVE_QA_IMAGE:?Build the pinned native QA image first}"
: "${QA:?Set the release QA relative path}"
apps="$(cd .. && pwd)"
# Extraction excludes old QA: create the nested mountpoint before mounting /work read-only.
mkdir -p "$QA"
output="$(cd "$QA" && pwd)"
exec docker run --rm --init --platform linux/amd64 \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$apps,target=/work,readonly" \
  --mount "type=bind,source=$output,target=/work/foundry-kodi-dist/$QA" \
  --workdir /work/foundry-kodi-dist \
  "$NATIVE_QA_IMAGE" sh -ec 'mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"; exec python3 "$@"' sh "$@"
