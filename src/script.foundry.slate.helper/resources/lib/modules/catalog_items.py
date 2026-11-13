"""Provider-neutral validation of Kodi directory records, never URL rewriting."""
import math
import re
from .catalog_model import clean, label

MEDIA_TYPES={'movie','tvshow','season','episode','musicvideo','video'}
CONTENT_TYPES={'movies':'movie','tvshows':'tvshow','seasons':'season','episodes':'episode','musicvideos':'musicvideo','videos':'video'}

def normalize(item,content=''):
    if not isinstance(item,dict):return None
    result=dict(item)
    for name in ('title','label','plot','mpaa','imdbnumber','premiered','firstaired','showtitle','original_language','language'):
        if name in result and not isinstance(result[name],str):result.pop(name)
    # An opaque file URL (including headers/query parameters) stays byte-for-byte.
    if not isinstance(result.get('file',''),str):result.pop('file',None)
    kind=result.get('type')
    if not isinstance(kind,str) or kind not in MEDIA_TYPES:kind=result.get('mediatype')
    inferred=item.get('foundry_type_inferred',not isinstance(kind,str) or kind not in MEDIA_TYPES)
    if not isinstance(kind,str) or kind not in MEDIA_TYPES:inferred=True
    if inferred:kind=CONTENT_TYPES.get(content,'unknown')
    result['type']=kind
    result['foundry_type_inferred']=inferred
    if result.get('filetype') not in ('file','directory') and kind in MEDIA_TYPES:
        result['filetype']='directory' if kind in ('tvshow','season') else 'file'
    art=item.get('art')
    result['art']={k:v for k,v in art.items() if isinstance(k,str) and isinstance(v,str) and clean(v)} if isinstance(art,dict) else {}
    # Kodi exposes these legacy artwork fields as well as the art map.
    for name in ('fanart','thumbnail'):
        value=item.get(name)
        if isinstance(value,str) and clean(value):result['art'].setdefault('fanart' if name=='fanart' else 'thumb',value)
    ids=item.get('uniqueid')
    result['uniqueid']={str(k).lower():str(v) for k,v in ids.items() if isinstance(v,(str,int)) and not isinstance(v,bool)} if isinstance(ids,dict) else {}
    for field in ('year','id','movieid','tvshowid','seasonid','episodeid','musicvideoid','season','episode','playcount'):
        value=item.get(field)
        if field not in item:continue
        if isinstance(value,bool) or not re.fullmatch(r'\d+',str(value)):result.pop(field,None)
        else:result[field]=int(value)
    ratings=item.get('ratings');result['ratings']={}
    if isinstance(ratings,dict):
        for provider,value in ratings.items():
            if not isinstance(provider,str):continue
            score=value.get('rating') if isinstance(value,dict) else value
            try:valid=not isinstance(score,bool) and math.isfinite(float(score)) and 0<float(score)<=10
            except (TypeError,ValueError):valid=False
            if valid:result['ratings'][provider.lower()]=value
    if 'rating' in result:
        try:valid=not isinstance(result['rating'],bool) and math.isfinite(float(result['rating'])) and 0<float(result['rating'])<=10
        except (TypeError,ValueError):valid=False
        if not valid:result.pop('rating')
    return result

def media_record(item,content=''):
    if item.get('type') in MEDIA_TYPES and not item.get('foundry_type_inferred'):return True
    if isinstance(item.get('mimetype'),str) and item['mimetype'].startswith('video/'):return True
    # Generic directories require title identity plus meaningful media metadata;
    # a poster/icon or a file alone is not evidence of a playable title.
    if not label(item):return False
    ids=item.get('uniqueid') or {}
    identified=bool(re.fullmatch(r'tt\d+',clean(ids.get('imdb') or item.get('imdbnumber'))) or re.fullmatch(r'\d+',clean(ids.get('tmdb'))))
    return bool(identified or (content in CONTENT_TYPES and type(item.get('id')) is int and item['id']>0) or
                (item.get('year') and (item.get('plot') or item.get('art',{}).get('poster'))))

def catalog_directory(items,content='',has_pages=False):
    if not items:return bool(content in CONTENT_TYPES or has_pages)
    return all(media_record(item,content) for item in items)

def section_for(items,default='Movies'):
    kinds={i.get('type') for i in items}
    if kinds and kinds<={'tvshow','season','episode'}:return 'TV Shows'
    if kinds and kinds<={'movie'}:return 'Movies'
    return default
