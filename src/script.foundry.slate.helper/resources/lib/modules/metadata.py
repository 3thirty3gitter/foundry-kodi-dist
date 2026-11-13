"""Skin-wide metadata facade. Original playback and directory identity are immutable."""
import hashlib
import json
import re
import threading
import uuid
import xbmc
import xbmcaddon
import xbmcvfs
from .catalog_items import normalize
from .catalog_model import clean, label
from .metadata_cache import MetadataCache
from .metadata_tmdb import TmdbMetadataClient
from .apis.omdb import OmdbClient


def settings(addon=None):
    addon=addon or xbmcaddon.Addon('script.foundry.slate.helper')
    def text(name,default=''):
        try:return addon.getSetting(name).strip() or default
        except (AttributeError,RuntimeError):return default
    def flag(name,default=False):
        value=text(name)
        if value:return value.lower()=='true'
        try:
            # Defaults apply to newly added settings absent in older profiles.
            return addon.getSettingBool(name) if not default else default
        except (AttributeError,RuntimeError):return default
    language=text('metadata_language','en-US')
    region=text('metadata_region','CA').upper()
    return {'tmdb':text('tmdb_api_key') if flag('tmdb_enabled',True) else '',
            'omdb':text('omdb_api_key') if flag('omdb_enabled') else '',
            'language':language if re.fullmatch(r'[a-z]{2}(?:-[A-Z]{2})?',language) else 'en-US',
            'region':region if re.fullmatch(r'[A-Z]{2}',region) else 'CA',
            'show_tmdb':flag('metadata_show_tmdb',True),'show_imdb':flag('metadata_show_imdb',True),
            'show_rt':flag('omdb_show_rotten_tomatoes'),'show_metacritic':flag('omdb_show_metacritic'),
            'revision':xbmc.getInfoLabel('Window(Home).Property(foundry.slate.metadata.revision)')}


def fingerprint(config,provider):
    return hashlib.sha256(json.dumps([config.get(provider,''),config.get('language'),config.get('region'),config.get('revision','')]).encode()).hexdigest()


def compatible(item,payload):
    requested=dict(item.get('uniqueid') or {})
    if item.get('imdbnumber'):requested.setdefault('imdb',item['imdbnumber'])
    returned=payload.get('uniqueid') or {}
    return all(not clean(requested.get(name)) or not clean(returned.get(name)) or
               clean(requested[name])==clean(returned[name])
               for name in ('tmdb','imdb','tvshow.tmdb','tvshow.imdb'))


def item_key(item):
    unique=item.get('uniqueid') or {}
    kind=item.get('type')
    # Stable IDs share a record across add-ons even when labels/year differ.
    if kind in ('movie','tvshow'):
        for provider,value in [('tmdb',unique.get('tmdb') or unique.get('themoviedb')),
                               ('imdb',unique.get('imdb') or item.get('imdbnumber'))]:
            if re.fullmatch(r'[1-9]\d*' if provider=='tmdb' else r'tt\d+',clean(value)):
                return json.dumps([kind,provider,str(value)])
    if kind in ('season','episode'):
        own=clean(unique.get('imdb') or item.get('imdbnumber'))
        if kind=='episode' and re.fullmatch(r'tt\d+',own):return json.dumps([kind,'imdb',own])
        parent=unique.get('tvshow.tmdb') or item.get('tvshow_tmdb_id')
        if re.fullmatch(r'[1-9]\d*',clean(parent)):
            return json.dumps([kind,'tvshow.tmdb',str(parent),item.get('season'),item.get('episode')])
    return json.dumps([item.get('type'),unique.get('tmdb'),unique.get('imdb') or item.get('imdbnumber'),
                       unique.get('tvshow.tmdb') or item.get('tvshow_tmdb_id'),unique.get('tvshow.imdb'),
                       clean(item.get('showtitle')),item.get('tvshowyear'),item.get('season'),item.get('episode'),
                       label(item).casefold(),clean(item.get('year'))],sort_keys=True)


def merge(base,extra,overwrite=True):
    result=normalize(base) or {}
    extra=normalize(extra) or {}
    # Never copy provider file, path, type, DB IDs, resume, watched or folder state.
    for field in ('plot','genre','studio','premiered','year','mpaa','imdbnumber','original_language',
                  'firstaired','showtitle','season','episode','runtime','cast','director','writer','country',
                  'originaltitle','tagline','status','tvshowyear'):
        value=extra.get(field)
        if value not in (None,'',[],{}) and (overwrite or result.get(field) in (None,'',[],{})):
            result[field]=value
    for field in ('uniqueid','art','ratings'):
        original=dict(result.get(field) or {})
        incoming=extra.get(field) or {}
        for name,value in incoming.items():
            if value not in (None,'',{},[]) and (overwrite or not original.get(name)):
                original[name]=value
        result[field]=original
    return normalize(result)


def omdb_query(item):
    kind=item.get('type')
    unique=item.get('uniqueid') or {}
    meta={'imdb_id':unique.get('imdb') or item.get('imdbnumber'),'title':label(item),'year':item.get('year'),
          'type':'movie' if kind=='movie' else 'episode' if kind=='episode' else 'series'}
    if kind=='season':return None  # A series rating must not impersonate a season.
    if kind=='episode' and not re.fullmatch(r'tt\d+',clean(meta.get('imdb_id'))):
        series=clean(unique.get('tvshow.imdb'))
        if series and item.get('season') is not None and item.get('episode') is not None:
            meta.update(imdb_id=series,season=item['season'],episode=item['episode'])
        else:return None
    if not re.fullmatch(r'tt\d+',clean(meta.get('imdb_id'))) and (not label(item) or not re.fullmatch(r'\d{4}',clean(item.get('year')))):
        return None
    return meta


def omdb_matches(payload,meta):
    requested=clean(meta.get('imdb_id'));returned=clean(payload.get('imdb_id'))
    if requested and returned and not ('season' in meta) and requested!=returned:return False
    if not requested:
        if clean(meta.get('title')).casefold()!=clean(payload.get('title')).casefold():return False
        if clean(meta.get('year'))!=clean(payload.get('year'))[:4]:return False
    expected=meta.get('type')
    if payload.get('media_type') and payload['media_type']!=expected:return False
    for field in ('season','episode'):
        if field in meta and str(payload.get(field))!=str(meta[field]):return False
    return True


def omdb_metadata(payload):
    result={'art':{},'ratings':{},'uniqueid':{}}
    mapping={'plot':'plot','certification':'mpaa','genres':'genre','studio':'studio','language':'original_language',
             'released':'premiered','runtime':'runtime','cast':'cast','director':'director','writer':'writer','country':'country'}
    for source,target in mapping.items():
        value=payload.get(source)
        if value not in (None,'',[],{}):result[target]=value
    for field in ('genre','country','original_language'):
        if isinstance(result.get(field),str) and field!='original_language':
            result[field]=[v.strip() for v in result[field].split(',') if v.strip()]
    if isinstance(result.get('cast'),list):result['cast']=[{'name':v} if isinstance(v,str) else v for v in result['cast']]
    # OMDb cannot always supply an ISO release date. Keep it only when parseable.
    released=clean(result.get('premiered'))
    match=re.fullmatch(r'(\d{2}) ([A-Z][a-z]{2}) (\d{4})',released)
    if match:
        months=('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')
        if match[2] in months:result['premiered']='%s-%02d-%s'%(match[3],months.index(match[2])+1,match[1])
    if payload.get('imdb_id'):result['imdbnumber']=payload['imdb_id'];result['uniqueid']['imdb']=payload['imdb_id']
    for source,name,scale in [('imdb_rating','imdb',1),('rotten_tomatoes','rottentomatoes',10),('metacritic','metacritic',10)]:
        value=clean(payload.get(source)).split('/')[0].rstrip('%')
        try:
            score=float(value)/scale
            if 0<=score<=10:result['ratings'][name]={'rating':score,'votes':int(clean(payload.get('imdb_votes')).replace(',','') or 0) if name=='imdb' else 0}
        except (TypeError,ValueError):pass
    return result


class MetadataService:
    def __init__(self,cache=None,config_reader=settings,tmdb_factory=TmdbMetadataClient,omdb_factory=OmdbClient):
        self.cache=cache or MetadataCache(xbmcvfs.translatePath('special://profile/addon_data/script.foundry.slate.helper/metadata.sqlite'))
        self.config_reader,self.tmdb_factory,self.omdb_factory=config_reader,tmdb_factory,omdb_factory

    def _fetch(self,provider,item,config):
        if provider=='tmdb':return self.tmdb_factory(config['tmdb'],config['language'],config['region']).fetch(item)
        meta=omdb_query(item)
        if not meta:return {},'unidentified',0
        payload,status,backoff=self.omdb_factory(config['omdb']).fetch(meta)
        if status=='ready':
            if not omdb_matches(payload,meta):return {},'not_found',0
            payload=omdb_metadata(payload)
        return payload,status,backoff

    def provider(self,provider,item,config):
        if not config.get(provider):return {},'disabled'
        owner,key=fingerprint(config,provider),item_key(item)
        cached=self.cache.get(provider,owner,key)
        if cached is not None:return (cached,'ready' if cached else 'not_found') if compatible(item,cached) else ({},'not_found')
        stale=self.cache.get(provider,owner,key,stale=True) or {}
        if not compatible(item,stale):stale={}
        blocked=self.cache.blocked(provider,owner)
        if blocked:return stale,blocked
        lease=self.cache.claim(provider,owner,key)
        if not lease:return stale,'busy'
        try:
            # Another interpreter may have completed just before the claim.
            cached=self.cache.get(provider,owner,key)
            if cached is not None:return (cached,'ready' if cached else 'not_found') if compatible(item,cached) else ({},'not_found')
            payload,status,backoff=self._fetch(provider,item,config)
            # Configuration changes discard results from old credentials.
            current=self.config_reader()
            if fingerprint(current,provider)!=owner or not current.get(provider):return {},'changed'
            if status=='ready':self.cache.put(provider,owner,key,payload)
            elif status in ('not_found','unidentified'):self.cache.put(provider,owner,key,{},ttl=900)
            elif status in ('offline','invalid_key','rate_limited'):self.cache.block(provider,owner,status,max(30,backoff))
            return payload if status=='ready' else stale,status
        finally:self.cache.release(lease)

    def enrich(self,item,section='Movies'):
        original=item.get('foundry.slate.metadata_original') if isinstance(item,dict) else None
        result=normalize(original if isinstance(original,dict) else item) or {}
        from .favorites import remember
        try:remember(self.cache,result)
        except Exception:pass  # Optional source history must never hide live metadata.
        config=self.config_reader();statuses={}
        if not config.get('tmdb') and not config.get('omdb'):return result,{'tmdb':'disabled','omdb':'disabled'}
        base=dict(result)
        if result.get('type') not in ('movie','tvshow','season','episode'):
            if not result.get('type') or result.get('type')=='unknown':
                result['type']='tvshow' if section=='TV Shows' else 'movie' if section=='Movies' else 'unknown'
        result['foundry_type_inferred']=False
        if result.get('type') not in ('movie','tvshow','season','episode'):return result,{}
        for provider in ('tmdb','omdb'):
            try:extra,status=self.provider(provider,result,config)
            except Exception:
                # Provider/cache failures cannot break navigation; never log request data.
                extra,status={},'offline'
            result=merge(result,extra,overwrite=provider=='tmdb')
            if provider=='omdb':result['ratings'].update(extra.get('ratings') or {})
            statuses[provider]=status
        result['foundry.slate.metadata_original']=base
        result['foundry.slate.metadata_ttl']=1 if 'busy' in statuses.values() else 30 if 'offline' in statuses.values() else 60 if any(v in ('rate_limited','changed') for v in statuses.values()) else 3600
        return result,statuses


_service=None
_lock=threading.Lock()


def service():
    global _service
    with _lock:
        if _service is None:_service=MetadataService()
        return _service


def clear_cache():
    import xbmcgui
    # Invalidate results already held by other Kodi Python interpreters too.
    xbmcgui.Window(10000).setProperty('foundry.slate.metadata.revision',uuid.uuid4().hex)
    service().cache.clear()
