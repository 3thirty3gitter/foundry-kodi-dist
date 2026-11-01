"""Fail packaging until every approved, standalone widget wallpaper is present."""
import hashlib
import json
from pathlib import Path
import struct

CATEGORIES = {"movies", "tvshows", "music", "musicvideos", "livetv", "radio", "games", "addons", "pictures", "video", "favorites", "weather", "settings", "home"}


def validate_widget_assets(skin):
    folder = Path(skin) / "media/foundry-widget-wallpapers"
    source = folder / "SOURCE.json"
    entries = json.loads(source.read_text()).get("files", {}) if source.exists() else {}
    missing = sorted(category for category in CATEGORIES if not (folder / (category + ".png")).is_file() or category not in entries)
    if missing:
        raise ValueError("Approved standalone widget artwork is incomplete: " + ", ".join(missing))
    for category in sorted(CATEGORIES):
        data = (folder / (category + ".png")).read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(category + ": expected a lossless PNG")
        width, height = struct.unpack(">II", data[16:24])
        if width < 1280 or height < 720 or abs(width / height - 16 / 9) > .005:
            raise ValueError(category + ": expected a complete landscape 16:9 frame")
        entry = entries[category]
        if not entry.get("library_file_id") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise ValueError(category + ": approval provenance/checksum is missing or mismatched")
    return entries


def validate_rich_pairs(skin, resource):
    """Reject incomplete pairs, stale widget revisions, or changed approved bytes."""
    locations = {
        "full": (Path(resource) / "resources", Path(resource) / "SOURCE.json", 0),
        "widget": (Path(skin) / "media/foundry-widget-wallpapers", Path(skin) / "media/foundry-widget-wallpapers/SOURCE.json", 1),
    }
    records = {}
    for mode, (folder, source, approved_version) in locations.items():
        provenance = json.loads(source.read_text(encoding="utf-8"))
        entries = provenance.get("files", {})
        if provenance.get("schema_version") != 2 or set(entries) != CATEGORIES:
            raise ValueError(mode + ": complete corrected rich artwork provenance is required")
        if provenance.get("widget_group_scale") != .55:
            raise ValueError(mode + ": approved uniform foreground scale must remain 0.55")
        for category, entry in entries.items():
            if entry.get("version") != approved_version or entry.get("current_version_number") != approved_version:
                raise ValueError(category + ": stale " + mode + " revision")
            data = (folder / (category + ".png")).read_bytes()
            if data[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", data[16:24]) != (1672, 941):
                raise ValueError(category + ": approved complete 1672x941 frame is required")
            if not entry.get("library_file_id") or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                raise ValueError(category + ": approved " + mode + " bytes differ")
        records[mode] = entries
    home_hash = records["full"]["home"]["sha256"]
    for name in ("media/foundry-home-backdrop.png", "resources/foundry-fanart.png"):
        if hashlib.sha256((Path(skin) / name).read_bytes()).hexdigest() != home_hash:
            raise ValueError("Home fallback/fanart must use the approved MEDIA CENTER frame")
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
