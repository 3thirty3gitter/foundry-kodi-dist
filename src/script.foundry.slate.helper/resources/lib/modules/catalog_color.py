"""Read Kodi's actual texture-cache mapping, off the GUI thread."""
from pathlib import Path
import hashlib
import json
import os
import tempfile
import re
from urllib.parse import unquote
import xbmcvfs
from PIL import Image
from .catalog_source import rpc
from .osd import dominant_color


def _index_path(artwork):
    folder=Path(xbmcvfs.translatePath('special://profile/addon_data/script.foundry.slate.helper/catalog-glow'))
    return folder/('art-'+hashlib.sha256(artwork.encode()).hexdigest()+'.json')


def peek(artwork):
    """Reuse a validated local color immediately, without image decoding or RPC."""
    if not artwork:return None
    try:
        index=_index_path(artwork)
        data=json.loads(index.read_text())
        source=Path(data['source']);stat=source.stat()
        target=Path(data['texture'])
        template=Path(xbmcvfs.translatePath('special://skin/media/streampilot/catalog-glow.png'))
        if (stat.st_mtime_ns,stat.st_size)!=(data['mtime'],data['size']):return None
        if template.stat().st_mtime_ns!=data['template_mtime']:return None
        if not re.fullmatch(r'FF[0-9A-F]{6}',data['accent']):return None
        if target.parent!=index.parent or not re.fullmatch(r'tint-[0-9a-f]{12}-FF[0-9A-F]{6}\.png',target.name) or not target.is_file():return None
        return data['accent'],str(target)
    except (OSError,ValueError,KeyError,TypeError):return None


def cached_paths(artwork):
    if not artwork:return []
    decoded=unquote(artwork[8:]).rstrip('/') if artwork.startswith('image://') else artwork
    paths=[]
    # Both Windows drive paths and POSIX local paths are legitimate. No remote
    # shares or URLs are opened by PIL; remote artwork is owned/cached by Kodi.
    local=xbmcvfs.translatePath(decoded)
    if (Path(local).is_absolute() or (len(local)>2 and local[1:3] in (':\\',':/'))) and not local.startswith(('\\\\','//')):
        paths.append(local)
    for url in dict.fromkeys((artwork,decoded)):
        try:
            response=rpc('Textures.GetTextures',{'properties':['cachedurl'],'filter':{'field':'url','operator':'is','value':url}})
            textures=response.get('textures',[]) if isinstance(response,dict) else []
        except RuntimeError:textures=[]
        for texture in textures:
            cached=texture.get('cachedurl','')
            if cached and not any(p=='..' for p in cached.replace('\\','/').split('/')):
                paths.append(xbmcvfs.translatePath('special://profile/Thumbnails/'+cached))
    return list(dict.fromkeys(paths))


def color(artwork,paths=None):
    for path in cached_paths(artwork) if paths is None else paths:
        try:
            with Image.open(path) as image:
                if image.width*image.height>40_000_000:continue
                rgb=dominant_color(image,fallback=(255,255,255))
                return 'FF%02X%02X%02X'%rgb
        except (OSError,ValueError,Image.DecompressionBombError):continue
    return None


def resolved(artwork):
    """Return the sampled color and a pre-tinted effect texture, off the GUI thread.

    Native Kodi21.3 list experiments render a dynamic texture path correctly,
    while the tested dynamic diffuse-color forms produce white/empty effects.
    Tint the existing glow's RGB only; never modify its alpha or media artwork.
    """
    cached=peek(artwork)
    if cached:return cached
    paths=cached_paths(artwork)
    value=color(artwork,paths)
    source=next((Path(path) for path in paths if Path(path).is_file()),None)
    if not value:return None
    if not re.fullmatch(r'FF[0-9A-F]{6}',value):return None
    template=Path(xbmcvfs.translatePath('special://skin/media/streampilot/catalog-glow.png'))
    data=template.read_bytes()
    revision=hashlib.sha256(data).hexdigest()[:12]
    folder=Path(xbmcvfs.translatePath('special://profile/addon_data/script.foundry.slate.helper/catalog-glow'))
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/('tint-%s-%s.png'%(revision,value))
    if not target.exists():
        with Image.open(template) as original:
            image=Image.new('RGBA',original.size,tuple(int(value[i:i+2],16) for i in (2,4,6))+(255,))
            image.putalpha(original.convert('RGBA').getchannel('A'))
            descriptor,name=tempfile.mkstemp(prefix='.tint-',suffix='.png',dir=folder)
            os.close(descriptor);temporary=Path(name)
            try:
                image.save(temporary,format='PNG')
                temporary.replace(target)
            finally:temporary.unlink(missing_ok=True)
        # Only this module's generated effects are eligible for eviction.
        generated=sorted(folder.glob('tint-????????????-????????.png'),key=lambda p:p.stat().st_mtime)
        for stale in generated[:-256]:
            if stale.parent==folder and stale!=target:stale.unlink(missing_ok=True)
    if source:
        try:
            stat=source.stat();index=_index_path(artwork)
            temporary=index.with_suffix('.tmp')
            temporary.write_text(json.dumps({'source':str(source),'mtime':stat.st_mtime_ns,'size':stat.st_size,
                'template_mtime':template.stat().st_mtime_ns,'accent':value,'texture':str(target)}))
            temporary.replace(index)
            records=sorted(folder.glob('art-*.json'),key=lambda p:p.stat().st_mtime)
            for stale in records[:-256]:stale.unlink(missing_ok=True)
        except OSError:pass
    return value,str(target)
