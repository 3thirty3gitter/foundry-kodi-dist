"""Install the approved full-frame Foundry artwork for Kodi's next launch."""
import hashlib
import os
import tempfile

import xbmcaddon
import xbmcvfs


ARTWORK_SHA256 = "a30da8f51f0828f2b11f398eab546ae2f880550b624244aff4810cf98a3971a9"


def install_startup_splash():
    """Optional Slate skin never changes global Kodi configuration."""
    return False


def _preserve(path):
    """Keep every prior custom splash without overwriting an earlier backup."""
    backup = path + ".before-foundry"
    number = 1
    while os.path.exists(backup):
        backup = path + ".before-foundry.slate." + str(number)
        number += 1
    os.replace(path, backup)
