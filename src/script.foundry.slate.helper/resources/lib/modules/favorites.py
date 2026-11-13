"""Recover metadata for native favorites without executing their saved actions."""
import csv
import hashlib
import re
from urllib.parse import unquote, urlsplit, parse_qs
from .catalog_items import normalize
from .catalog_model import clean
from .catalog_source import rpc, DIRECTORY_FIELDS

FIELDS=('type','title','label','year','plot','genre','studio','premiered','firstaired','runtime',
        'mpaa','imdbnumber','uniqueid','art','ratings','rating','cast','director','writer','country',
        'tagline','originaltitle','original_language','showtitle','tvshowyear','tvshowid','season','episode')

def source_key(path):
    return hashlib.sha256(path.encode('utf-8')).hexdigest()

def remember(cache,item):
    path=item.get('file')
    if not isinstance(path,str) or not path or path.startswith('favourites://'):return
    if item.get('type') not in ('movie','tvshow','season','episode'):return
    payload={key:item[key] for key in FIELDS if key in item}
    # Playback URLs, provider credentials and arbitrary properties are excluded.
    cache.put('source','v1',source_key(path),payload,ttl=30*86400)

def saved_target(path):
    """Decode only Kodi's whitelisted favorite action envelopes; never execute."""
    if not path.startswith('favourites://'):return None
    encoded=path[len('favourites://'):].rstrip('/')
    command=unquote(encoded)
    match=re.fullmatch(r'(?is)(playmedia|activatewindow)\((.*)\)',command)
    if not match:return None
    try:parts=next(csv.reader([match[2]],skipinitialspace=True,escapechar='\\',strict=True))
    except (csv.Error,StopIteration):return None
    action=match[1].lower()
    if action=='playmedia' and parts:return 'media',parts[0]
    if action=='activatewindow' and len(parts)>1 and parts[0].lower() in ('10025','videos','video'):
        return 'window',parts[1]
    return None

def resolve(item,cache):
    expected=saved_target(item.get('file',''))
    if not expected:return None
    # The index is advisory. Match the exact saved target and alias as well so
    # reordering/removal or duplicate display names cannot select another item.
    try:rows=rpc('Favourites.GetFavourites',{'properties':['path','window','windowparameter','thumbnail']}).get('favourites',[])
    except RuntimeError:return None
    candidates=[]
    for row in rows:
        if not isinstance(row,dict) or clean(row.get('title'))!=clean(item.get('label')):continue
        target=row.get('windowparameter') if row.get('type')=='window' and str(row.get('window','')).lower() in ('10025','videos','video') else row.get('path') if row.get('type')=='media' else ''
        if target==expected[1] and row.get('type')==expected[0]:candidates.append((row,target))
    if len(candidates)!=1:return None
    favorite,target=candidates[0]
    result=cache.get('source','v1',source_key(target)) or {}
    # Kodi's library/file metadata is readable without playing the favorite.
    # Do not probe arbitrary plugin play/source actions or open streams.
    plugin=urlsplit(target).scheme=='plugin'
    if not plugin:
        try:
            details=rpc('Files.GetFileDetails',{'file':target,'media':'video','properties':DIRECTORY_FIELDS}).get('filedetails',{})
            if details.get('type') in ('movie','tvshow','season','episode'):
                result=dict(result,**details);result['foundry.slate.native_library']=True
        except RuntimeError:pass
    if not result and plugin:
        parsed=urlsplit(target)
        if parsed.netloc=='plugin.video.themoviedb.helper':
            query=parse_qs(parsed.query);kind=query.get('tmdb_type',[''])[0]
            tmdb=query.get('tmdb_id',[''])[0];imdb=query.get('imdb_id',[''])[0]
            if kind in ('movie','tv') and (re.fullmatch(r'[1-9]\d*',tmdb) or re.fullmatch(r'tt\d+',imdb)):
                result={'type':'movie' if kind=='movie' else 'tvshow','uniqueid':{'tmdb':tmdb,'imdb':imdb}}
    if result.get('type') not in ('movie','tvshow','season','episode'):return None
    result=dict(result,file=target,foundry_type_inferred=False)
    result['art']=dict(result.get('art') or {})
    if favorite.get('thumbnail'):result['art'].setdefault('poster',favorite['thumbnail'])
    return normalize(result)
