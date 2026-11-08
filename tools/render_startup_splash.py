"""Capture Kodi's real cold-start splash with an isolated writable home."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

from PIL import Image, ImageGrab


ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT.parent / 'skin.foundry-nimbus'


def main():
    release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))['release']
    output = ROOT / 'releases' / (release + '-qa')
    output.mkdir(parents=True, exist_ok=True)
    source = SKIN / 'media/foundry-home-backdrop.png'
    expected = Image.open(source).convert('RGB').resize((1920, 1080))
    samples = [(x, y) for x in (190, 570, 960, 1340, 1730) for y in (190, 410, 650, 890)]
    with tempfile.TemporaryDirectory(prefix='foundry-splash-') as temporary:
        home = Path(temporary) / 'kodi'
        shutil.copytree('/usr/share/kodi', home, ignore_dangling_symlinks=True)
        profile = home / 'portable_data'
        media = profile / 'media'
        media.mkdir(parents=True)
        # These exact bytes are installed by the shipped helper, covered by
        # migration tests. Here we verify Kodi itself selects and renders them.
        shutil.copyfile(source, media / 'splash.png')
        userdata = profile / 'userdata'
        userdata.mkdir()
        (userdata / 'guisettings.xml').write_text('<settings version="2"><setting id="addons.updatemode">2</setting></settings>')
        environment = dict(os.environ, DISPLAY=':99', KODI_HOME=str(home), LIBGL_ALWAYS_SOFTWARE='1', AE_SINK='NULL')
        kodi = None
        with (output / 'splash-console.log').open('w') as log:
            xserver = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1920x1080x24', '-ac', '-nolisten', 'tcp'], stdout=log, stderr=log)
            try:
                time.sleep(1)
                kodi = subprocess.Popen(['kodi', '-p', '-fs', '--windowing=x11', '--debug'], env=environment, stdout=log, stderr=log, start_new_session=True)
                deadline = time.monotonic() + 45
                captured = False
                while time.monotonic() < deadline:
                    frame = ImageGrab.grab(xdisplay=':99').convert('RGB')
                    differences = [abs(a-b) for point in samples for a,b in zip(frame.getpixel(point), expected.getpixel(point))]
                    if max(differences) < 45 and sum(differences)/len(differences) < 12:
                        frame.save(output / 'startup-splash.png')
                        captured = True
                        break
                    time.sleep(.04)
                assert captured, 'Foundry artwork was not observed in the actual Kodi cold-start splash'
                (output / 'startup-splash-verification.json').write_text(json.dumps({
                    'real_kodi_cold_start': True,
                    'writable_home_override_selected': True,
                    'approved_artwork_unchanged': (media / 'splash.png').read_bytes() == source.read_bytes(),
                    'canvas': [1920, 1080],
                    'scope': 'Native desktop Kodi; Shield restart remains unverified'
                }, indent=2) + '\n')
            finally:
                if kodi:
                    try: os.killpg(kodi.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: kodi.wait(timeout=5)
                    except subprocess.TimeoutExpired: pass
                    # Kodi's launcher can exit while its native child survives.
                    # Always stop this fixture's remaining process-group members.
                    try: os.killpg(kodi.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    kodi.wait(timeout=5)
                xserver.terminate()
                xserver.wait(timeout=5)
                logs = profile / 'temp/kodi.log'
                if logs.exists(): shutil.copyfile(logs, output / 'splash-kodi.log')


if __name__ == '__main__':
    main()
