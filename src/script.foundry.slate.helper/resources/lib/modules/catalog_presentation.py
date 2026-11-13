"""StreamPilot text spacing and StudioLogo bitmap preparation for Kodi."""
from functools import lru_cache
import hashlib
import math
from pathlib import Path
import xbmcvfs
from PIL import Image, ImageFont
from .catalog_color import cached_paths


@lru_cache(maxsize=8)
def font(size, bold=False):
    return ImageFont.truetype(xbmcvfs.translatePath('special://skin/fonts/Roboto-%s.ttf' % ('Bold' if bold else 'Regular')), size)


def text_width(text, size=22, bold=False):
    try:
        return math.ceil(font(size, bold).getlength(str(text)))
    except (OSError, AttributeError):
        return math.ceil(len(str(text)) * size * .55)


def footer_geometry(page, sort):
    width = text_width(page)
    return width, 112 + width + 28, max(116, text_width(sort) + 48)


def release_geometry(released, certification):
    return 92 + (text_width(released) + 18 if released else 0), text_width(certification, 20, True) + 28


def studio_logo(artwork):
    """Port StudioLogo.kt's alpha crop and monochrome tint, using Kodi's cache."""
    for path in cached_paths(artwork):
        try:
            with Image.open(path) as source:
                if source.width * source.height > 40_000_000:
                    continue
                image = source.convert('RGBA')
                alpha = image.getchannel('A')
                bounds = alpha.point(lambda value: 255 if value > 8 else 0).getbbox()
                if not bounds:
                    return None
                colored = opaque = 0
                for pixel in image.getdata():
                    if pixel[3] > 8:
                        opaque += 1
                        colored += max(pixel[:3]) - min(pixel[:3]) > 28
                image = image.crop(bounds)
                if colored / opaque < .08:
                    tinted = Image.new('RGBA', image.size, 'white')
                    tinted.putalpha(image.getchannel('A'))
                    image = tinted
                digest = hashlib.sha256(image.tobytes() + str(image.size).encode()).hexdigest()
                folder = Path(xbmcvfs.translatePath('special://profile/addon_data/script.foundry.slate.helper/catalog-studios'))
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / (digest + '.png')
                if not target.exists():
                    temporary = target.with_suffix('.tmp')
                    image.save(temporary, format='PNG')
                    temporary.replace(target)
                    for stale in sorted(folder.glob('*.png'), key=lambda p: p.stat().st_mtime)[:-128]:
                        if stale != target:
                            stale.unlink(missing_ok=True)
                return str(target)
        except (OSError, ValueError, Image.DecompressionBombError):
            continue
    return None
