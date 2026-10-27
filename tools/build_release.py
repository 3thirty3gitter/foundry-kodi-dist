"""Build deterministic Kodi ZIPs from the checked-out Foundry repositories."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import zipfile


def package(source, output):
    manifest = ET.parse(source / "addon.xml").getroot()
    addon_id, version = manifest.get("id"), manifest.get("version")
    target = output / addon_id
    target.mkdir(parents=True, exist_ok=True)
    archive = target / (addon_id + "-" + version + ".zip")
    # These unreferenced assets duplicate the active Foundry artwork.
    unused_skin_artwork = {"resources/fanart.png", "media/foundry-backdrops/foundry-loading-splash.png"}
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if not path.is_file() or any(part.startswith(".") or part in {"__pycache__", "scripts", "Blank xmls"} for part in relative.parts):
                continue
            if path.suffix in {".pyc", ".pyo"} or path.name == "Makefile" or path.name.endswith("-old.xml"):
                continue
            if addon_id == "skin.foundry" and relative.as_posix() in unused_skin_artwork:
                continue
            entry = zipfile.ZipInfo(addon_id + "/" + relative.as_posix(), (2026, 10, 26, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    Path(str(archive) + ".sha256").write_text(digest + "\n")
    for asset in manifest.findall("./extension/assets/*"):
        if asset.text and (source / asset.text).is_file():
            dest = target / asset.text
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / asset.text, dest)
    return manifest, {"id": addon_id, "version": version, "path": archive.relative_to(output).as_posix(), "sha256": digest, "size": archive.stat().st_size}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skin", type=Path, required=True)
    parser.add_argument("--helper", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sources = [root / "src/repository.foundry", args.skin, args.helper,
               root / "src/script.program.foundry-build", root / "src/script.program.foundry-bootstrap"]
    feed, packages = ET.Element("addons"), []
    for source in sources:
        manifest, details = package(source, root)
        feed.append(manifest)
        packages.append(details)
    ET.indent(feed, space="  ")
    xml = ET.tostring(feed, encoding="utf-8", xml_declaration=True) + b"\n"
    (root / "addons.xml").write_bytes(xml)
    (root / "addons.xml.md5").write_text(hashlib.md5(xml).hexdigest() + "\n")
    repo = next(p for p in packages if p["id"] == "repository.foundry")
    filename = Path(repo["path"]).name
    shutil.copyfile(root / repo["path"], root / filename)
    for addon_id in ("script.program.foundry-build", "script.program.foundry-bootstrap"):
        installer = next(p for p in packages if p["id"] == addon_id)
        shutil.copyfile(root / installer["path"], root / (addon_id + ".zip"))
    versions = {p["id"]: p["version"] for p in packages}
    (root / "release.json").write_text(json.dumps({
        "release": versions["script.program.foundry-build"],
        "skin": versions["skin.foundry"], "packages": packages,
    }, indent=2) + "\n")
    (root / "index.html").write_text('''<!doctype html>
<html><head><meta charset="utf-8"><title>Foundry Kodi Source</title></head>
<body><h1>Foundry Kodi Source</h1>
<p>Install the repository ZIP below. Then open Install from repository &gt; Foundry Repository &gt; Program add-ons &gt; Foundry Build.</p>
<ul><li><a href="''' + filename + '''">''' + filename + '''</a></li></ul>
</body></html>
''')
    print(json.dumps(packages, indent=2))


if __name__ == "__main__":
    main()
