"""Use direct signed Ubuntu repositories in disposable native-test runners."""
import argparse
from pathlib import Path

REPLACEMENTS = {
    b"mirror+file:/etc/apt/apt-mirrors.txt": b"https://archive.ubuntu.com/ubuntu",
    b"http://azure.archive.ubuntu.com/ubuntu": b"https://archive.ubuntu.com/ubuntu",
    b"http://archive.ubuntu.com/ubuntu": b"https://archive.ubuntu.com/ubuntu",
    b"http://security.ubuntu.com/ubuntu": b"https://archive.ubuntu.com/ubuntu",
    b"https://security.ubuntu.com/ubuntu": b"https://archive.ubuntu.com/ubuntu",
}


def configure(root):
    found = False
    for relative in ("sources.list", "sources.list.d/ubuntu.sources"):
        path = Path(root) / relative
        if not path.exists():
            continue
        original = path.read_bytes()
        updated = original
        for old, new in REPLACEMENTS.items():
            updated = updated.replace(old, new)
        if b"https://archive.ubuntu.com/ubuntu" in updated:
            found = True
        if updated != original:
            path.write_bytes(updated)
    if not found:
        raise RuntimeError("No supported Ubuntu source found; refusing to invent a repository configuration")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/etc/apt"))
    configure(parser.parse_args().root)
