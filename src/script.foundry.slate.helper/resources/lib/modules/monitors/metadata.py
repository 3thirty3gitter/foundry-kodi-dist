"""Asynchronous shared metadata bindings for focused items and the playing video."""
from concurrent.futures import ThreadPoolExecutor
import json
import time
import xbmc
from ..catalog_model import clean
from ..metadata import service, settings
from ..studio_art import ART_KEYS, resolve as resolve_studio
from ..catalog_metadata import details as media_details,episode_heading


PROPERTIES=('title','plot','poster','fanart','clearlogo','thumb','studiologo','genre','studio','premiered',
            'mpaa','runtime','cast','director','writer','country','tagline','original_language','imdb','tmdb',
            'rotten_tomatoes','metacritic','imdb_id','tmdb_id','tmdb_status','omdb_status',
            'media_type','season','episode','showtitle','episode_heading','details','released_label','certification')
CAST_PROPERTIES=tuple('cast.%d.%s'%(i,field) for i in range(40) for field in ('name','role','thumbnail'))
PROPERTIES=PROPERTIES+('loading',)+CAST_PROPERTIES
OWNER_FIELDS=('label','year','type','season','episode','imdb','tmdb','imdbnumber','showtitle','path')
LEGACY={'plot':'plot','premiered':'released','mpaa':'certification','genre':'genres','studio':'studio',
        'original_language':'language','imdb':'imdb_rating','rotten_tomatoes':'rotten_tomatoes','metacritic':'metacritic','imdb_id':'imdb_id'}


def snapshot(player=False,info=None):
    info=info or xbmc.getInfoLabel
    prefix='VideoPlayer.' if player else 'ListItem.'
    def value(name):return clean(info(prefix+name))
    kind='' if player else value('DBTYPE').lower()
    if player:
        if xbmc.getCondVisibility('VideoPlayer.Content(livetv)') or not xbmc.getCondVisibility('Player.HasVideo'):return None
        kind='episode' if xbmc.getCondVisibility('VideoPlayer.Content(episodes)') else 'movie' if xbmc.getCondVisibility('VideoPlayer.Content(movies)') else ''
    else:
        kind=kind or value('Property(mediatype)').lower()
    path=clean(info('Player.FilenameAndPath')) if player else value('FileNameAndPath') or value('Path')
    favorite=not player and path.startswith('favourites://')
    if kind not in ('movie','tvshow','season','episode') and not favorite:return None
    if favorite:kind='favorite'
    raw_label=value('Title') if player else value('Label')
    title=value('Title') or raw_label
    year=value('Year')
    imdb=value('UniqueID(imdb)') or value('IMDBNumber') or value('Property(imdb)')
    tmdb=value('UniqueID(tmdb)') or value('Property(TMDb_ID)') or value('Property(tmdb)')
    raw_kind=kind if player else value('DBTYPE')
    owner=(raw_label,year,raw_kind,value('Season'),value('Episode'),value('UniqueID(imdb)'),value('UniqueID(tmdb)'),value('IMDBNumber'),value('TVShowTitle'),path)
    item={'title':title,'label':raw_label,'type':kind,'year':year,'imdbnumber':imdb,
          'uniqueid':{'imdb':imdb,'tmdb':tmdb,'tvshow.tmdb':value('Property(tvshow.tmdb_id)'), 'tvshow.imdb':value('Property(tvshow.imdb_id)')},
          'file':path,
          'showtitle':value('TVShowTitle'),'tvshowyear':value('Property(tvshow.year)'),
          'plot':value('Plot'),'mpaa':value('MPAA'),'genre':value('Genre'),'studio':value('Studio'),'premiered':value('Premiered'),
          'season':value('Season') if kind in ('season','episode') else None,
          'episode':value('Episode') if kind=='episode' else None,'art':{}}
    if favorite:item['foundry.slate.favorite']=True
    for name in ('poster','fanart','clearlogo','thumb','tvshow.poster','tvshow.fanart','tvshow.clearlogo') + ART_KEYS:
        art=clean(info(('Player.Art(' if player else 'ListItem.Art(')+name+')'))
        if art:item['art'][name]=art
    item['ratings']={}
    for provider in ('tmdb','themoviedb','imdb','rottentomatoes','metacritic'):
        rating=value('Rating('+provider+')')
        try:
            number=float(rating)
            if 0<number<=10:item['ratings'][provider]={'rating':number}
        except (TypeError,ValueError):pass
    if not player and not clean(info('Container.PluginName')):
        dbid=value('DBID')
        if dbid.isdigit() and int(dbid)>0:item['id']=int(dbid);item['foundry.slate.native_library']=True
    return owner,item


def values(item,statuses,config):
    result={name:'' for name in PROPERTIES}
    kind=item.get('type','')
    result['media_type']=kind
    result['episode_heading']=episode_heading(item)
    presentation=media_details(item,kind in ('tvshow','season','episode'),kind)
    result['details']=presentation['details'];result['released_label']=presentation['released'];result['certification']=presentation['certification']
    for name in ('season','episode','showtitle'):
        if item.get(name) is not None:result[name]=str(item[name])
    for name in ('title','plot','mpaa','runtime','premiered','tagline','original_language'):
        result[name]=clean(item.get(name))
    if result['runtime']:
        try:result['runtime']=str(int(float(result['runtime']))//60)+' min'
        except (ValueError,TypeError):result['runtime']=''
    for name in ('genre','studio','director','writer','country'):
        value=item.get(name) or []
        result[name]=' / '.join(str(v) for v in value) if isinstance(value,list) else clean(value)
    cast=item.get('cast') or []
    # The native information dialog may open before enrichment finishes.
    # Publish bounded structured actors so its fallback cast list can update live.
    actors=[v if isinstance(v,dict) else {'name':v} for v in cast if isinstance(v,(dict,str))] if isinstance(cast,list) else []
    actors=[v for v in actors if clean(v.get('name'))][:40]
    result['cast']=' / '.join(clean(v.get('name')) for v in actors)
    for index,actor in enumerate(actors):
        for field in ('name','role','thumbnail'):
            value=actor.get(field)
            result['cast.%d.%s'%(index,field)]=clean(value) if isinstance(value,str) else ''
    art=item.get('art') or {}
    for name in ('poster','fanart','clearlogo','thumb','studiologo'):result[name]=art.get(name) or art.get('tvshow.'+name) or ''
    result['studiologo']=resolve_studio(item)
    unique=item.get('uniqueid') or {}
    result.update(imdb_id=unique.get('imdb') or item.get('imdbnumber',''),tmdb_id=unique.get('tmdb',''))
    for provider,field,enabled in [('tmdb','tmdb','show_tmdb'),('themoviedb','tmdb','show_tmdb'),('imdb','imdb','show_imdb'),('rottentomatoes','rotten_tomatoes','show_rt'),('metacritic','metacritic','show_metacritic')]:
        rating=(item.get('ratings') or {}).get(provider)
        rating=rating.get('rating') if isinstance(rating,dict) else rating
        if not config.get(enabled) or rating in (None,''):continue
        try:
            number=float(rating)
            if not 0<=number<=10:continue
            result[field]=('%g'%round(number*10))+'%' if field=='rotten_tomatoes' else ('%g'%round(number*10))+'/100' if field=='metacritic' else ('%g'%number)+('/10' if field=='imdb' else '')
        except (ValueError,TypeError):pass
    for provider in ('tmdb','omdb'):result[provider+'_status']=statuses.get(provider,'disabled')
    return result


class MetadataMonitor:
    def __init__(self,window,provider=None,clock=time.monotonic,executor=None):
        self.window,self.provider,self.clock=window,provider,clock
        self.executor=executor or ThreadPoolExecutor(max_workers=2,thread_name_prefix='foundry-shared-metadata')
        self.slots={};self.config=None;self.generation=0;self.stopped=False;self.paused=False

    def enrich(self,*args):
        # Initialize SQLite on a worker; a profile/cache failure cannot stop the service.
        if args[0].get('foundry.slate.favorite'):
            from ..favorites import resolve
            item=resolve(args[0],service().cache)
            if not item:return {},{'tmdb':'unidentified','omdb':'unidentified'}
            args=(item,'Movies' if item['type']=='movie' else 'TV Shows')
        if self.provider:return self.provider.enrich(*args)
        from ..catalog_enrichment import enrich_with_status
        return enrich_with_status(*args,native_library=bool(args[0].get('foundry.slate.native_library')))

    def pause(self):
        if self.paused:return
        self.paused=True;self.generation+=1
        self.clear('foundry.slate.metadata.');self.clear('foundry.slate.player.')
        for slot in self.slots.values():slot.update(current=None,retry=0)

    def clear(self,prefix):
        for name in PROPERTIES+tuple('owner_'+f for f in OWNER_FIELDS):self.window.clearProperty(prefix+name)
        if prefix=='foundry.slate.metadata.':
            for name in tuple(LEGACY.values())+('owner_label','owner_year','owner_type','owner_path','status','show_rotten_tomatoes','show_metacritic'):
                self.window.clearProperty('foundry.slate.omdb.'+name)

    def refresh_config(self):
        config=settings()
        if config!=self.config:
            self.config=config;self.generation+=1
            self.clear('foundry.slate.metadata.');self.clear('foundry.slate.player.')
            # Keep outstanding jobs bounded until they actually finish.
            for slot in self.slots.values():slot.update(current=None,changed=self.clock(),retry=0)
        return config

    def process_current_item(self):
        if self.stopped:return
        self.paused=False
        self.refresh_config()
        for player,prefix in ((False,'foundry.slate.metadata.'),(True,'foundry.slate.player.')):
            captured=snapshot(player)
            # Take a second snapshot to reject focus/player changes during collection.
            if captured!=snapshot(player):continue
            slot=self.slots.setdefault(prefix,{'current':None,'changed':0,'future':None,'retry':0})
            if slot['current']!=captured:
                slot.update(current=captured,changed=self.clock(),retry=0)
                self.clear(prefix)
            future=slot.get('future')
            if future and future.done():
                slot['future']=None
                try:item,statuses=future.result()
                except Exception:item,statuses={}, {'tmdb':'offline','omdb':'offline'}
                if slot['submitted']==captured and slot['generation']==self.generation and captured and captured==snapshot(player):
                    self.publish(prefix,captured[0],item,statuses)
                    slot['retry']=self.clock()+(1 if 'busy' in statuses.values() else 30 if 'offline' in statuses.values() else 60)
            if captured and not slot['future'] and self.clock()-slot['changed']>=.25 and self.clock()>=slot['retry']:
                slot['submitted']=captured;slot['generation']=self.generation
                if not self.window.getProperty(prefix+'owner_label'):
                    self.publish(prefix,captured[0],captured[1],{})
                self.window.setProperty(prefix+'loading','true')
                slot['future']=self.executor.submit(self.enrich,captured[1], 'TV Shows' if captured[1]['type']!='movie' else 'Movies')

    def publish(self,prefix,owner,item,statuses):
        self.clear(prefix)
        published=values(item,statuses,self.config)
        for name,value in published.items():
            if value:self.window.setProperty(prefix+name,str(value))
        for name,value in zip(OWNER_FIELDS,owner):self.window.setProperty(prefix+'owner_'+name,str(value))
        if prefix=='foundry.slate.metadata.':
            for name,field in LEGACY.items():
                if published[name]:self.window.setProperty('foundry.slate.omdb.'+field,published[name])
            for name,value in zip(('label','year','type'),owner):self.window.setProperty('foundry.slate.omdb.owner_'+name,str(value))
            if len(owner)>9:self.window.setProperty('foundry.slate.omdb.owner_path',str(owner[9]))
            self.window.setProperty('foundry.slate.omdb.status',statuses.get('omdb','disabled'))
            for field,setting in [('show_rotten_tomatoes','show_rt'),('show_metacritic','show_metacritic')]:
                self.window.setProperty('foundry.slate.omdb.'+field,str(bool(self.config.get(setting))).lower())

    def stop(self):
        self.stopped=True;self.generation+=1
        self.executor.shutdown(wait=False,cancel_futures=True)
        self.clear('foundry.slate.metadata.');self.clear('foundry.slate.player.')
