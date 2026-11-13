"""Validate exact requested Movies-category artwork before packaging."""
import hashlib,json,struct
from pathlib import Path

LABELS={'Genres':'genres','Providers':'providers','Languages':'languages','Years':'years','Decades':'decades','Certifications':'certifications','Because You Watched...':'because-you-watched','Watched':'watched','Recently Watched':'recently-watched','In Progress':'in-progress'}
SOURCE='SOURCE-extra-categories-20261112.json'
BASE='9d254d3949ab9dc2690ac285bc8da5a51b42c0644ec48566464a5aaf057c6212'

def validate_extra_movie_wallpapers(skin):
    folder=Path(skin)/'media/foundry-movie-submenus'
    doc=json.loads((folder/SOURCE).read_text(encoding='utf-8'))
    rows=doc.get('files',[])
    if len(rows)!=10 or {r['label']:r['slug'] for r in rows}!=LABELS:
        raise ValueError('All ten requested Movies categories are required')
    if doc.get('background_sha256')!=BASE:
        raise ValueError('Extra Movies categories require the fixed Trending plate')
    for row in rows:
        if row['filename']!=row['slug']+'.png' or row['dimensions']!=[1672,941]:
            raise ValueError('Invalid category filename or dimensions')
        data=(folder/row['filename']).read_bytes()
        if data[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',data[16:24])!=(1672,941):
            raise ValueError('Category must be a complete 1672x941 PNG')
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise ValueError('Category bytes differ from requested composition')
    return rows
