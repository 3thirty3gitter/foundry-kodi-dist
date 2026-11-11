"""Fail packaging until every approved, standalone widget wallpaper is present."""
import hashlib
import json
from pathlib import Path
import struct

CATEGORIES = {"movies", "tvshows", "music", "musicvideos", "livetv", "radio", "games", "addons", "pictures", "video", "favorites", "weather", "settings", "home"}


ACTIVE_SOURCE = "SOURCE-trending-fixed-20261111.json"
APP_ARTWORK_SHA256 = "a30da8f51f0828f2b11f398eab546ae2f880550b624244aff4810cf98a3971a9"
BACKGROUND_SHA256 = "9d254d3949ab9dc2690ac285bc8da5a51b42c0644ec48566464a5aaf057c6212"


def _validate_set(folder, mode):
    """Use the current approval explicitly; never reinterpret historical SOURCE.json."""
    source = folder / ACTIVE_SOURCE
    if not source.is_file():
        raise ValueError(mode + ": approved standalone artwork is incomplete")
    provenance = json.loads(source.read_text(encoding="utf-8"))
    rows = provenance.get("files", [])
    entries = {entry["slug"]: entry for entry in rows}
    if (provenance.get("schema_version") != 3 or provenance.get("mode") != mode
            or len(rows) != len(CATEGORIES) or set(entries) != CATEGORIES
            or provenance.get("dimensions") != [1672, 941]
            or provenance.get("background_sha256") != BACKGROUND_SHA256
            or not provenance.get("review_library_file_id")
            or not provenance.get("approval", {}).get("quote")):
        raise ValueError(mode + ": complete fixed-background artwork approval is required")
    if provenance.get("widget_group_scale") != .55:
        raise ValueError(mode + ": approved uniform foreground scale must remain 0.55")
    for category, entry in entries.items():
        expected = ("resources/" if mode == "full" else "") + category + ".png"
        if entry.get("filename") != expected or entry.get("dimensions") != [1672, 941]:
            raise ValueError(category + ": approved filename/dimensions differ")
        data = (folder / expected).read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", data[16:24]) != (1672, 941):
            raise ValueError(category + ": approved complete 1672x941 frame is required")
        if len(data) != entry.get("bytes") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise ValueError(category + ": approved " + mode + " bytes differ")
    return entries


def validate_widget_assets(skin):
    return _validate_set(Path(skin) / "media/foundry-widget-wallpapers", "widget")


def validate_rich_pairs(skin, resource):
    """Reject incomplete pairs, stale approval metadata, or changed approved bytes."""
    records = {"full": _validate_set(Path(resource), "full"),
               "widget": validate_widget_assets(skin)}
    for name in ("media/foundry-home-backdrop.png", "media/foundry-widget-base.png",
                 "media/streampilot/catalog-base.png"):
        if hashlib.sha256((Path(skin) / name).read_bytes()).hexdigest() != BACKGROUND_SHA256:
            raise ValueError("Fallbacks must use the approved fixed clean background")
    for name in ("resources/foundry-fanart.png", "media/foundry-backdrops/foundry-loading-splash.png"):
        if hashlib.sha256((Path(skin) / name).read_bytes()).hexdigest() != APP_ARTWORK_SHA256:
            raise ValueError("App fanart/startup must use the approved Foundry Media Center frame")
    return records


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("skin", type=Path)
    args = parser.parse_args()
    try:
        files = validate_widget_assets(args.skin)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")
    print("Validated all", len(files), "approved standalone widget wallpapers")
