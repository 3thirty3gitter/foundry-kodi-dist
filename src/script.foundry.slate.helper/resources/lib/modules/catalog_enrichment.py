"""Identity-checked Kodi/TMDbHelper enrichment. No keys or playback URL rewrites.

TMDbHelper's documented info=details route owns its provider configuration.
Anonymous directory ratings are never relabelled IMDb or TMDb.
"""
import re
from urllib.parse import urlencode, urlsplit, parse_qs
import xbmc
from .catalog_model import clean, label
from .catalog_source import rpc, FIELDS, DIRECTORY_FIELDS
from .catalog_items import normalize, MEDIA_TYPES


# Rich fields belong on single-item detail lookups, not the bulk rail load.
# Kodi Omega warns that cast/ratings can increase directory response time.
NATIVE_DETAIL_FIELDS = {
    'movie': FIELDS + ['uniqueid','cast','director','writer','runtime','country','tagline',
                       'originaltitle','trailer','set','tag','dateadded'],
    'tvshow': FIELDS + ['uniqueid','cast','runtime','originaltitle','tag','dateadded'],
    'season': ['title','season','showtitle','playcount','episode','fanart','thumbnail','tvshowid','art'],
    'episode': ['title','plot','rating','firstaired','playcount','season','episode','showtitle',
                'fanart','thumbnail','tvshowid','uniqueid','art','ratings','genre','studio',
                'cast','director','writer','runtime','originaltitle','dateadded'],
}
DETAIL_DIRECTORY_FIELDS = DIRECTORY_FIELDS + [
    'cast','director','writer','runtime','country','tagline','originaltitle','trailer','set','tag','dateadded'
]


def media_type(item, section='Movies'):
    kind=item.get('type') or item.get('mediatype')
    return kind if kind in MEDIA_TYPES else ('tvshow' if section=='TV Shows' else 'movie' if section=='Movies' else 'video')


def identity(item, section='Movies'):
    return (media_type(item,section),clean(item.get('file')),label(item),clean(item.get('year')))


def lookup(item, section='Movies'):
    kind=media_type(item,section)
    if kind not in ('movie','tvshow'):return None
    unique=item.get('uniqueid') or {}
    if not isinstance(unique,dict):unique={}
    params={'info':'details','tmdb_type':'tv' if kind=='tvshow' else 'movie','cacheonly':'false'}
    imdb=clean(unique.get('imdb') or item.get('imdbnumber'))
    tmdb=clean(unique.get('tmdb') or unique.get('themoviedb'))
    # Only the known TMDbHelper route's documented ID params are interpreted.
    try:path=urlsplit(clean(item.get('file')))
    except ValueError:return None
    if path.scheme=='plugin' and path.netloc=='plugin.video.themoviedb.helper':
        query=parse_qs(path.query)
        tmdb=tmdb or query.get('tmdb_id',[''])[0]
        imdb=imdb or query.get('imdb_id',[''])[0]
    if re.fullmatch(r'tt\d+',imdb):params['imdb_id']=imdb
    elif re.fullmatch(r'\d+',tmdb):params['tmdb_id']=tmdb
    elif label(item) and re.fullmatch(r'\d{4}',clean(item.get('year'))):
        params.update(query=label(item),year=clean(item.get('year')))
    else:return None  # A title alone cannot disambiguate remakes.
    return params


def matching(item,details,params):
    if not isinstance(details,dict):return False
    kind=details.get('type') or details.get('mediatype')
    if kind in ('movie','tvshow') and params.get('tmdb_type') and kind!=('tvshow' if params['tmdb_type']=='tv' else 'movie'):return False
    if 'query' in params:
        return (label(item).casefold()==label(details).casefold() and
                clean(item.get('year'))==clean(details.get('year')))
    # The upstream ID route resolves the requested identity. Reject a returned
    # conflicting IMDb ID as an additional guard if that field is available.
    unique=details.get('uniqueid') if isinstance(details.get('uniqueid'),dict) else {}
    returned_imdb=details.get('imdbnumber') or unique.get('imdb')
    returned_tmdb=unique.get('tmdb') or unique.get('themoviedb')
    return not ((params.get('imdb_id') and returned_imdb and params['imdb_id']!=str(returned_imdb)) or
                (params.get('tmdb_id') and returned_tmdb and params['tmdb_id']!=str(returned_tmdb)))


def merge(base,extra,tmdb=False):
    base=normalize(base) or {}
    extra=normalize(extra) or {}
    result=dict(base)
    # Provider identity/file/filetype/dbid never come from the metadata endpoint.
    for field in ('title','originaltitle','plot','genre','studio','premiered','year','mpaa','imdbnumber','original_language','firstaired','showtitle','tvshowyear','season','episode','runtime','cast','director','writer','country','tagline','trailer','set','tag','dateadded','status'):
        if extra.get(field) not in (None,'',[],{}):result[field]=extra[field]
    result['uniqueid']=dict(base.get('uniqueid') or {});result['uniqueid'].update(extra.get('uniqueid') or {})
    art=dict(base.get('art') or {})
    for name,value in (extra.get('art') or {}).items():
        if value:art[name]=value
    result['art']=art
    ratings=dict(base.get('ratings') or {})
    ratings.update(extra.get('ratings') or {})
    # This singular rating is known TMDb only because the upstream documented
    # endpoint defines it as TMDb average; generic Files ratings remain unknown.
    if tmdb and extra.get('rating'):ratings['tmdb']={'rating':extra['rating']}
    result['ratings']=ratings
    return normalize(result)


def enrich_with_status(item,section='Movies',native_library=False):
    result=normalize(item) or {};item=result;kind=media_type(item,section)
    dbid=item.get(kind+'id') or item.get('id')
    if native_library and kind in ('movie','tvshow','season','episode') and type(dbid) is int and dbid>0:
        method='VideoLibrary.Get'+{'movie':'Movie','tvshow':'TVShow','season':'Season','episode':'Episode'}[kind]+'Details'
        properties=NATIVE_DETAIL_FIELDS[kind]
        key=kind+'details'
        native_details={}
        try:
            native_details=rpc(method,{kind+'id':dbid,'properties':properties}).get(key,{})
            if not isinstance(native_details,dict):native_details={}
            result=merge(result,native_details)
        except RuntimeError:pass  # A stale Kodi DB ID must not break the rail.
        # A season/episode's own TMDb ID is not its show's ID. Recover only
        # scoped parent identity from Kodi; do not merge the show's story/date.
        parent_id=result.get('tvshowid') or native_details.get('tvshowid')
        if kind in ('season','episode') and type(parent_id) is int and parent_id>0:
            try:
                parent=rpc('VideoLibrary.GetTVShowDetails',{'tvshowid':parent_id,'properties':['title','year','uniqueid']}).get('tvshowdetails',{})
                from .catalog_source import inherit_tv_context
                if isinstance(parent,dict):
                    result=inherit_tv_context(result,dict(parent,type='tvshow',tvshowid=parent_id),True)
            except RuntimeError:pass
    # The direct provider facade is shared with Home/widgets, dialogs and OSD.
    # Keep the existing TMDbHelper route only as a fallback without a direct key.
    from .metadata import service, settings
    direct=settings()
    params=lookup(result,section) if not direct.get('tmdb') else None
    if params and xbmc.getCondVisibility('System.HasAddon(plugin.video.themoviedb.helper)'):
        try:
            data=rpc('Files.GetDirectory',{'directory':'plugin://plugin.video.themoviedb.helper/?'+urlencode(params),'media':'video','properties':DETAIL_DIRECTORY_FIELDS}).get('files',[])
            if len(data)==1 and matching(result,data[0],params):result=merge(result,data[0],tmdb=True)
        except RuntimeError:pass
    return service().enrich(result,section)


def enrich(item,section='Movies',native_library=False):
    return enrich_with_status(item,section,native_library)[0]
