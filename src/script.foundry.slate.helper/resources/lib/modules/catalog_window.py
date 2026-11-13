"""Dedicated native Kodi catalog window: owns paging, sorting and split search.

Provider folder/playback URLs pass through unchanged. A provider without a public
search/global sort interface is explicitly scoped to its loaded directory.
"""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time
import traceback
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from .catalog_model import CatalogState, clean, label
from .catalog_source import DirectorySource, rpc
from .catalog_metadata import details as hero_details, names as metadata_names
from .catalog_enrichment import enrich, identity, media_type
from .catalog_color import resolved as artwork_color, peek as cached_artwork_color
from .catalog_presentation import release_geometry, studio_logo as prepare_studio
from .catalog_items import normalize
from .movie_submenu import canonical_label, movie_context
from .metadata import settings as metadata_settings, fingerprint

BACK_ACTIONS = {9,10,92,216,247,257,275,61467}


def rating_owner(item,section):
    return label(item),str(item.get('year') or ''),media_type(item,section)


def apply_info(entry,item,section='Movies',restoring=False):
    item=normalize(item) or {}
    info={k:item[k] for k in ('title','year','plot','genre','studio','premiered','rating','mpaa','imdbnumber','playcount','season','episode','showtitle','director','writer','country','tagline','originaltitle','trailer','set','tag','dateadded','status') if item.get(k) not in (None,'')}
    if 'showtitle' in info:info['tvshowtitle']=info.pop('showtitle')
    if item.get('runtime'):info['duration']=item['runtime']
    for field in ('genre','studio','director','writer','country','tag'):
        if field in info:info[field]=metadata_names(info[field])
    info['mediatype']=media_type(item,section)
    if info['mediatype']=='episode' and item.get('firstaired'):
        info['premiered']=item['firstaired']
    if item.get('id') is not None:info['dbid']=item['id']
    if restoring:
        defaults={'plot':'','genre':[],'studio':[],'premiered':'','mpaa':'','imdbnumber':'',
                  'director':[],'writer':[],'country':[],'tagline':'','originaltitle':'','duration':0,'year':0,
                  'trailer':'','set':'','tag':[],'dateadded':'','status':''}
        info=dict(defaults,**info)
    entry.setInfo('video',info)
    if item.get('cast') or restoring:
        try:entry.setCast(item.get('cast') or [])
        except AttributeError:pass
    try:entry.setUniqueIDs(item.get('uniqueid') or {})
    except AttributeError:pass
    ratings={}
    for provider,value in (item.get('ratings') or {}).items():
        score=value.get('rating') if isinstance(value,dict) else value
        votes=value.get('votes',0) if isinstance(value,dict) else 0
        try:ratings[provider]=(float(score),int(votes))
        except (AttributeError,TypeError,ValueError):pass
    if item.get('rating') and not ratings:ratings['default']=(float(item['rating']),0)
    default=next((p for p in ('tmdb','themoviedb','default','imdb') if p in ratings),'')
    try:entry.getVideoInfoTag().setRatings(ratings,default)
    except AttributeError:pass


def metadata_fresh(cached,now):
    return bool(cached and now-cached[0]<cached[1].get('foundry.slate.metadata_ttl',3600))


def listitem(item,section='Movies'):
    item=normalize(item) or {}
    kind=item.get('kind','media')
    entry=xbmcgui.ListItem(label=label(item) or item.get('label',''), path=item.get('file',''), offscreen=True)
    entry.setProperty('catalog.kind',kind)
    entry.setProperty('catalog.accent','FFFFFFFF')
    if kind!='media':
        entry.setProperty('catalog.arrow','streampilot/catalog-%s.png'%('previous' if kind=='previous' else 'next'))
        return entry
    art=dict(item.get('art') or {})
    url=art.get('fanart') or art.get('tvshow.fanart') or art.get('poster') or art.get('tvshow.poster') or ''
    cached_color=cached_artwork_color(url)
    art['foundry.slate.catalog.glow']=cached_color[1] if cached_color else 'streampilot/glow-pending.svg'
    art['poster']=art.get('poster') or art.get('tvshow.poster') or art.get('thumb') or item.get('thumbnail') or 'streampilot/catalog-blank.png'
    entry.setArt(art)
    apply_info(entry,item,section)
    if item.get('filetype')!='directory':entry.setProperty('IsPlayable','true')
    return entry


class CatalogWindow(xbmcgui.WindowXML):
    def __init__(self,*args,source=None,section='Movies',breadcrumb='',**kwargs):
        super().__init__(*args,**kwargs)
        self.source=source
        if source is not None and not getattr(source, 'movie_submenu_label', ''):
            source.movie_submenu_label=canonical_label(breadcrumb)
        self.section=section
        self.breadcrumb=breadcrumb if str(breadcrumb).startswith('VOD') else 'VOD  /  '+section+'  /  '+(breadcrumb or 'Your Library')
        self.state=CatalogState()
        self.library_state=None
        self.stack=[]
        self.rail=[]
        self.results=[]
        self.hero=None
        self.last_focus=(-1,-1)
        self.closed=False
        self.close_requested=False
        self.exit_back=False
        self.focus_pending=None
        self.initialized=False
        self.reported_errors=set()
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='foundry-catalog')
        self.pending=None
        self.request=0
        self.search=False
        self.enrichment_executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='foundry-metadata')
        self.enrichment_jobs={}
        self.enrichment_cache={}
        self.metadata_stamp=None
        self.hero_changed_at=0
        self.color_executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='foundry-color')
        self.color_job=None
        self.color_retry=0
        self.color_attempts=0
        self.color_cache={}
        self.studio_job=None
        self.studio_cache={}
        self.studio_retry=0
        self.studio_attempts=0
        self.pending_artwork_redraw={}
        self.edit_value=''
        self.changed_at=0
        self.clock=time.monotonic
        self.history_path=Path(xbmcvfs.translatePath('special://profile/addon_data/script.foundry.slate.helper/vod-search-history.json'))
        try:self.history=json.loads(self.history_path.read_text())[:10]
        except (OSError,ValueError,TypeError):self.history=[]

    def p(self,name,value=''):
        self.setProperty('catalog.'+name,str(value))

    def focus(self,cid):
        # Properties update visibility on Kodi's next GUI frame. Retrying focus
        # avoids targeting hidden sort/search controls in the same callback.
        self.focus_pending=cid

    def diagnostic(self,stage,error):
        # No titles, URLs, provider parameters, exception values or keys in logs.
        frames=traceback.extract_tb(error.__traceback__)
        location=' > '.join('%s:%d:%s'%(Path(f.filename).name,f.lineno,f.name) for f in frames[-3:])
        signature=(stage,type(error).__name__,location)
        if signature not in self.reported_errors:
            self.reported_errors.add(signature)
            xbmc.log('[Foundry catalog] %s %s at %s'%signature,xbmc.LOGERROR)

    def set_hero(self,item):
        item=normalize(item) or {}
        # Populate safe essentials first, so a single optional field/color failure
        # cannot leave only a logo or retain metadata from the previous poster.
        cached=getattr(self,'enrichment_cache',{}).get(identity(item,self.section))
        if cached and metadata_fresh(cached,self.clock()):item=cached[1]
        previous=getattr(self,'hero',None)
        changed_item=not previous or identity(previous,self.section)!=identity(item,self.section)
        self.hero=item
        art=item.get('art') or {}
        if not isinstance(art,dict):art={}
        kind=media_type(item,self.section)
        defaults={'title':label(item),'clearlogo':art.get('clearlogo') or art.get('tvshow.clearlogo') or '',
                  'fanart':art.get('fanart') or art.get('tvshow.fanart') or '',
                  'studio_logo':'','released':'','certification':'','details':'TV Series' if kind in ('tvshow','season','episode') else 'Video' if kind=='video' else 'Movie',
                  'plot':clean(item.get('plot')) or 'No description available.','imdb':'','tmdb':'','rt':'','metacritic':''}
        if changed_item:
            for field,value in defaults.items():self.p(field,value)
        self.hero_changed_at=self.clock() if hasattr(self,'clock') else time.monotonic()
        self.studio_attempts=0;self.studio_retry=0
        try:self.update_hero(item)
        except Exception as error:self.diagnostic('metadata',error)
        url=art.get('fanart') or art.get('tvshow.fanart') or art.get('poster') or art.get('tvshow.poster') or ''
        cached_color=getattr(self,'color_cache',{}).get(url) or cached_artwork_color(url)
        if getattr(self,'color_owner',None)!=url:
            self.color_owner=url
            self.color_attempts=0;self.color_retry=0
            if cached_color:self.publish_color(*cached_color)
            else:
                self.p('accent','00FFFFFF')
                xbmcgui.Window(10000).setProperty('foundry.slate.catalog.glow','streampilot/glow-pending.svg')
        elif cached_color:self.publish_color(*cached_color)

    def onInit(self):
        if self.initialized:
            # Kodi releases WindowXML's native list when fullscreen playback
            # replaces the window. Rehydrate from the retained state on return.
            self.setContent('tvshows' if self.section=='TV Shows' else 'movies')
            xbmc.executebuiltin('Container.SetViewMode(50)')
            if not self.getListSize():self.refresh()
            return
        self.initialized=True
        self.setContent('tvshows' if self.section=='TV Shows' else 'movies')
        xbmc.executebuiltin('Container.SetViewMode(50)')
        self.p('section',self.section);self.p('breadcrumb',self.breadcrumb)
        self.p('accent','FFFFFFFF')
        self.focus(5701)
        self.p('search_scope',self.section+' in your library' if self.source.scope=='library' else self.section+' in this folder')
        for i,q in enumerate(self.history):self.p('history'+str(i),q)
        initial = getattr(self.source, 'initial', None)
        if initial is None:
            self.load()
        else:
            # Adoption already read and classified this exact directory. Bind
            # that result before Kodi paints the new window, rather than showing
            # an empty window and filling it on a later executor/tick cycle.
            self.source.initial = None
            try:
                self.apply_page(initial)
            except Exception as error:
                self.diagnostic('catalog_render', error)
                self.p('message', 'The catalog could not be displayed. Go Back and retry.')
                self.focus(5701)

    def apply_page(self, result):
        if result.get('catalog_eligible') is False:
            self.setProperty('foundry.slate.movie_submenu_label','')
            self.open_native(self.source.path)
            return False
        self.state.items = result.get('items', [])
        self.state.next_path = result.get('next_path', '')
        self.state.previous_path = result.get('previous_path', '')
        self.state.server_page = int(result.get('page') or self.state.server_page)
        self.state.server_total_pages = int(result.get('total_pages') or 0)
        self.refresh()
        self.p('loading', '')
        return True

    def load(self):
        self.update_movie_submenu_context()
        self.request+=1;self.p('loading','true');self.p('preparing','Preparing page '+str(self.state.page));self.p('message','')
        self.pending=(self.request,'load',self.executor.submit(self.source.load))

    def update_movie_submenu_context(self):
        source=getattr(self,'source',None)
        label=movie_context(self.section,self.state.items,getattr(source,'content',''),
                            getattr(source,'movie_submenu_label',''),
                            getattr(source,'movie_submenu_verified',False))
        if source is not None and self.state.items:source.movie_submenu_verified=bool(label)
        self.setProperty('foundry.slate.movie_submenu_label',label)

    def refresh(self,selection=None):
        self.update_movie_submenu_context()
        self.rail=self.state.rail()
        control=self.getControl(50);self.clearList();self.addItems([listitem(i,self.section) for i in self.rail])
        offset=1 if self.rail and self.rail[0].get('kind')=='previous' else 0
        target=offset+min(self.state.selected,max(0,len(self.state.page_items())-1)) if selection is None else selection
        if self.rail:self.setCurrentListPosition(max(0,min(target,len(self.rail)-1)))
        self.p('has_next','true' if self.rail and self.rail[-1].get('kind')=='next' else '')
        self.p('page',self.state.page_label())
        self.p('scope','')
        self.getControl(5708).setWidth(500)
        self.p('message','' if self.state.items else 'No library matches on this page. Continue to the next page or choose Your Library.')
        self.last_focus=(50,target) if self.rail else (-1,-1)
        media=self.state.page_items()
        if media:
            self.set_hero(media[min(self.state.selected,len(media)-1)])
        else:
            self.hero=None
            for field in ('title','clearlogo','studio_logo','tmdb','imdb','rt','metacritic'):self.p(field,'')
        # Page and sort resets go to the first media item; info return does not call refresh.
        self.focus(50 if self.rail else 5701)

    def tick(self):
        if not self.initialized or self.closed:return
        if self.focus_pending is not None:
            target=self.focus_pending
            if self.getControl(target).isVisible():
                self.setFocusId(target)
                if self.getFocusId()==target:self.focus_pending=None
        if self.pending and self.pending[2].done():
            generation,kind,future=self.pending;self.pending=None
            if generation==self.request:
                try:result=future.result()
                except Exception as error:
                    self.diagnostic('source' if kind=='load' else 'search',error)
                    self.p('loading','');self.p('message','This source could not be loaded. Go Back and retry.');self.p('search_message','Search is unavailable. Go Back and retry.');self.focus(5801 if self.search else 5701)
                else:
                    try:
                        if kind=='load':
                            if not self.apply_page(result):return
                        else:self.search_results(result)
                        self.p('loading','')
                    except Exception as error:
                        self.diagnostic('catalog_render',error)
                        self.p('loading','');self.p('message','The catalog could not be displayed. Go Back and retry.');self.focus(5701)
        if self.search:
            text=self.getControl(5801).getText()
            if text!=self.edit_value:
                self.edit_value=text;self.changed_at=self.clock();self.p('results_label','Searching…')
                self.request+=1  # invalidates any in-flight result immediately
            if self.changed_at and self.clock()-self.changed_at>=.25:
                self.changed_at=0;self.search_query(self.edit_value)
        try:
            cid=self.getFocusId()
            if cid in (50,51):
                index=self.getCurrentListPosition() if cid==50 else self.getControl(cid).getSelectedPosition()
                if (cid,index)!=self.last_focus:
                    self.last_focus=(cid,index)
                    items=self.state.page_items() if cid==51 else self.rail
                    if 0<=index<len(items) and items[index].get('kind','media')=='media':
                        if cid==50:self.state.selected=index-(1 if self.rail[0].get('kind')=='previous' else 0)
                        self.set_hero(items[index])
        except RuntimeError:pass
        try:self.update_optional_ratings()
        except Exception as error:self.diagnostic('optional_ratings',error)
        if hasattr(self,'enrichment_executor'):
            try:
                self.tick_enrichment()
                self.flush_artwork_redraw()
            except Exception as error:self.diagnostic('enrichment',error)

    def update_hero(self,item):
        art=item.get('art') or {};self.p('title',label(item));self.p('clearlogo',art.get('clearlogo') or art.get('tvshow.clearlogo') or '')
        self.p('fanart',art.get('fanart') or art.get('tvshow.fanart') or '')
        from .studio_art import resolve as resolve_studio
        studio_logo=resolve_studio(item)
        self.p('studio_source',studio_logo)
        self.p('studio_logo',getattr(self,'studio_cache',{}).get(studio_logo,studio_logo))
        kind=media_type(item,self.section)
        for field,value in hero_details(item,kind in ('tvshow','season','episode'),kind).items():self.p(field,value)
        released=self.getProperty('catalog.released');certification=self.getProperty('catalog.certification')
        cert_x,cert_width=release_geometry(released,certification)
        self.getControl(5712).setWidth(max(1,cert_x-110))
        for control_id in (5710,5711):
            control=self.getControl(control_id);control.setPosition(cert_x,298);control.setWidth(cert_width)
        self.p('imdb','');self.p('tmdb','');self.p('rt','');self.p('metacritic','')
        ratings=item.get('ratings') or {}
        config=metadata_settings()
        for provider,score in (ratings if isinstance(ratings,dict) else {}).items():
            value=score.get('rating') if isinstance(score,dict) else score
            if value in (None,0,'0','N/A',''):continue
            name='tmdb' if provider in ('tmdb','themoviedb') else provider
            if name in ('tmdb','imdb') and config.get('show_'+name):self.p(name,str(value)+('/10' if name=='imdb' else ''))
            if name=='rottentomatoes' and config.get('show_rt'):self.p('rt','%g%%'%(float(value)*10))
            if name=='metacritic' and config.get('show_metacritic'):self.p('metacritic','%g/100'%(float(value)*10))
        try:fresh=float(self.getProperty('catalog.rt').rstrip('%'))>=60
        except ValueError:fresh=True
        self.p('rt_badge','streampilot/source-rating_rt_%s.png'%('fresh' if fresh else 'rotten'))

    def tick_enrichment(self):
        now=self.clock()
        self.tick_color(now)
        self.tick_studio(now)
        config=metadata_settings()
        stamp=(fingerprint(config,'tmdb'),fingerprint(config,'omdb'),tuple(config.get(k) for k in ('show_tmdb','show_imdb','show_rt','show_metacritic')))
        if stamp!=getattr(self,'metadata_stamp',None):
            previous=getattr(self,'metadata_stamp',None)
            self.metadata_stamp=stamp;self.enrichment_cache.clear()
            if previous is not None:self.restore_metadata()
        for key,(item,future,submitted_stamp) in list(self.enrichment_jobs.items()):
            if not future.done():continue
            del self.enrichment_jobs[key]
            if submitted_stamp!=stamp:continue
            try:result=future.result()
            except Exception as error:
                self.diagnostic('metadata_lookup',error);result=item
            self.enrichment_cache[key]=(now,result)
            self.enrichment_cache[identity(result,self.section)]=(now,result)
            while len(self.enrichment_cache)>128:self.enrichment_cache.pop(next(iter(self.enrichment_cache)))
            # Update art in place. Never reset the native list, selection or scroll.
            hero_key=identity(self.hero,self.section) if self.hero else None
            for cid,items in ((50,self.rail),(51,self.state.page_items() if self.search else [])):
                for index,current in enumerate(items):
                    if current.get('kind','media')=='media' and identity(current,self.section)==key:
                        current.update(result)
                        entry=self.getListItem(index) if cid==50 else self.getControl(51).getListItem(index)
                        art=result.get('art') or {}
                        changed=any(entry.getArt(name)!=value for name,value in art.items())
                        entry.setArt(art)
                        if changed:self.schedule_artwork_redraw(cid)
                        apply_info(entry,result,self.section)
            if hero_key==key:
                self.set_hero(result)
        if not self.hero or now-self.hero_changed_at<.2:return
        key=identity(self.hero,self.section)
        cached=self.enrichment_cache.get(key)
        if not metadata_fresh(cached,now):
            if key not in self.enrichment_jobs and len(self.enrichment_jobs)<2:
                item=dict(self.hero)
                self.enrichment_jobs[key]=(item,self.enrichment_executor.submit(enrich,item,self.section,self.source.scope=='library'),stamp)
        # Prefetch a bounded neighborhood of the visible rail after focus settles.
        # Never queue the entire provider catalog or more than two outstanding jobs.
        page=self.state.page_items()
        center=min(self.state.selected,max(0,len(page)-1))
        for item in page[max(0,center-2):center+4]:
            candidate=identity(item,self.section)
            cached=self.enrichment_cache.get(candidate)
            if candidate not in self.enrichment_jobs and not metadata_fresh(cached,now) and len(self.enrichment_jobs)<2:
                self.enrichment_jobs[candidate]=(dict(item),self.enrichment_executor.submit(enrich,dict(item),self.section,self.source.scope=='library'),stamp)
    def tick_color(self,now):
        # Color jobs have their own executor and do not wait behind API metadata.
        if not self.hero:return
        art=self.hero.get('art') or {}
        url=art.get('fanart') or art.get('tvshow.fanart') or art.get('poster') or art.get('tvshow.poster') or ''
        if self.color_job and self.color_job[1].done():
            owner,future=self.color_job;self.color_job=None
            try:result=future.result()
            except Exception as error:self.diagnostic('artwork_color',error);result=None
            if result:
                self.color_cache[owner]=result
            while len(self.color_cache)>128:self.color_cache.pop(next(iter(self.color_cache)))
            if owner==url:
                if result:self.publish_color(*result)
                else:self.color_retry=now+.15
        if url in self.color_cache:self.publish_color(*self.color_cache[url])
        elif url and not self.color_job and now>=self.color_retry and self.color_attempts<30:
            self.color_attempts+=1
            self.color_job=(url,getattr(self,'color_executor',self.enrichment_executor).submit(artwork_color,url))

    def tick_studio(self,now):
        url=self.getProperty('catalog.studio_source')
        if getattr(self,'studio_job',None) and self.studio_job[1].done():
            owner,future=self.studio_job;self.studio_job=None
            try:prepared=future.result()
            except Exception:prepared=None
            if prepared:
                self.studio_cache[owner]=prepared
                while len(self.studio_cache)>128:self.studio_cache.pop(next(iter(self.studio_cache)))
            if owner==url:
                if prepared:self.p('studio_logo',prepared)
                else:self.studio_retry=now+1
        if url in getattr(self,'studio_cache',{}):self.p('studio_logo',self.studio_cache[url])
        elif url and not getattr(self,'studio_job',None) and now>=getattr(self,'studio_retry',0) and getattr(self,'studio_attempts',0)<10:
            self.studio_attempts=getattr(self,'studio_attempts',0)+1
            self.studio_job=(url,self.enrichment_executor.submit(prepare_studio,url))

    def restore_metadata(self):
        # Revert provider-owned presentation fields in place after key removal or
        # cache clearing. Keep each native ListItem and its focus/playback URL.
        for cid,items in ((50,self.rail),(51,self.state.page_items() if self.search else [])):
            for index,current in enumerate(items):
                original=current.get('foundry.slate.metadata_original')
                if not isinstance(original,dict):continue
                art_names=set((current.get('art') or {}).keys())
                restored=normalize(original) or {}
                current.clear();current.update(restored)
                entry=self.getListItem(index) if cid==50 else self.getControl(51).getListItem(index)
                art={name:'' for name in art_names}
                art.update(restored.get('art') or {})
                art['poster']=art.get('poster') or art.get('tvshow.poster') or art.get('thumb') or 'streampilot/catalog-blank.png'
                art['foundry.slate.catalog.glow']='streampilot/catalog-glow.png'
                entry.setArt(art);apply_info(entry,restored,self.section,restoring=True)
                self.schedule_artwork_redraw(cid)
        if self.hero:
            original=self.hero.get('foundry.slate.metadata_original')
            self.set_hero(original if isinstance(original,dict) else self.hero)

    def publish_color(self,value,texture):
        self.p('accent',value)
        xbmcgui.Window(10000).setProperty('foundry.slate.catalog.glow',texture)
        # SetArt invalidates the native item's cached layout. Window property
        # changes alone do not require a list item's image labels to refresh.
        if self.getFocusId()==50 and self.rail and self.rail[self.getCurrentListPosition()].get('kind','media')=='media':
            entry=self.getListItem(self.getCurrentListPosition())
            if entry.getArt('foundry.slate.catalog.glow')!=texture:
                entry.setArt({'foundry.slate.catalog.glow':texture})
                self.schedule_artwork_redraw(50)

    def schedule_artwork_redraw(self,cid):
        # UpdateInfo and local texture allocation run on subsequent GUI frames.
        # A same-callback redraw can precede them and preserve the old pixels.
        self.pending_artwork_redraw.setdefault(cid,self.clock()+.05)

    def flush_artwork_redraw(self):
        now=self.clock()
        for cid,deadline in list(self.pending_artwork_redraw.items()):
            if now>=deadline:
                del self.pending_artwork_redraw[cid]
                self.redraw_catalog_control(cid)

    def redraw_catalog_control(self,cid):
        # Kodi's Python API exposes no direct MarkDirtyRegion. Native21.3
        # experiments show late item-art changes can leave old pixels until an
        # unrelated redraw. SetWidth marks the container dirty (Omega
        # GUIControl.cpp), so restore its exact width synchronously. The extra
        # right-edge unit is clipped by the viewport; no list reset/focus action.
        control=self.getControl(cid)
        width=control.getWidth()
        try:control.setWidth(width+1)
        finally:control.setWidth(width)

    def update_optional_ratings(self):
        if not self.hero:return
        home=xbmcgui.Window(10000)
        owner=tuple(home.getProperty('foundry.slate.omdb.owner_'+n) for n in ('label','year','type'))
        expected=rating_owner(self.hero,self.section)
        if owner!=expected:return
        for name,field in [('imdb','imdb_rating'),('rt','rotten_tomatoes'),('metacritic','metacritic')]:
            if name=='rt' and home.getProperty('foundry.slate.omdb.show_rotten_tomatoes')!='true':continue
            if name=='metacritic' and home.getProperty('foundry.slate.omdb.show_metacritic')!='true':continue
            value=clean(home.getProperty('foundry.slate.omdb.'+field))
            if value:self.p(name,value)
        try:fresh=int(self.getProperty('catalog.rt').strip('%'))>=60
        except ValueError:fresh=True
        self.p('rt_badge','streampilot/source-rating_rt_%s.png'%('fresh' if fresh else 'rotten'))

    def turn_page(self,direction):
        target=self.state.next_path if direction=='next' and self.state.page==self.state.total_pages else self.state.previous_path if direction=='previous' and self.state.page==1 else ''
        if target:
            self.stack.append((self.source,self.state));self.source=DirectorySource(target,getattr(self.source,'content',''),
                movie_submenu_label=getattr(self.source,'movie_submenu_label',''),
                movie_submenu_verified=getattr(self.source,'movie_submenu_verified',False));self.state=CatalogState(server_page=self.state.server_page+(1 if direction=='next' else -1));self.load()
        else:self.state.move_page(direction);self.refresh()

    def start_search(self):
        self.library_state=self.state;self.search=True;self.p('search','true');self.p('results_label','0 results');self.p('search_message','Start typing to search your library.' if self.source.scope=='library' else 'Start typing to search loaded provider titles.')
        self.getControl(5801).setText('');self.focus(5801)

    def search_query(self,query):
        self.request+=1
        if self.source.scope=='library' and query.strip():
            self.pending=(self.request,'search',self.executor.submit(self.source.search,query,self.section=='TV Shows'))
        else:
            state=CatalogState(items=self.library_state.items,query=query);self.search_results(state.filtered() if query.strip() else [])

    def search_results(self,items):
        self.results=list(items or [])
        self.state=CatalogState(items=self.results)
        self.update_movie_submenu_context()
        control=self.getControl(51);control.reset();control.addItems([listitem(i,self.section) for i in self.state.page_items()])
        self.p('results_label',str(len(self.results))+(' result' if len(self.results)==1 else ' results'));self.p('search_message','' if self.results else 'No matching titles.' if self.edit_value.strip() else 'Start typing to search your library.')
        self.p('page',self.state.page_label())
        self.last_focus=(-1,-1)

    def save_history(self):
        query=self.edit_value.strip()
        if not query:return
        self.history=([query]+[q for q in self.history if q.casefold()!=query.casefold()])[:10]
        self.history_path.parent.mkdir(parents=True,exist_ok=True);self.history_path.write_text(json.dumps(self.history))
        for i,q in enumerate(self.history):self.p('history'+str(i),q)

    def leave_search(self):
        self.save_history();self.request+=1;self.pending=None;self.search=False;self.p('search','');self.state=self.library_state
        self.update_movie_submenu_context()
        # The catalog list is retained while the search panel owns focus. Do not
        # reset/repopulate it on return: its exact native scroll offset survives.
        self.p('page',self.state.page_label());self.last_focus=(-1,-1);self.focus(50)

    def onClick(self,cid):
        if getattr(self,'closed',False):return
        if cid==5701:self.back()
        elif cid==5802:self.leave_search()
        elif 5830<=cid<=5839:
            index=cid-5830
            if index<len(self.history):self.getControl(5801).setText(self.history[index]);self.focus(51)
        elif cid in (5811,5812):
            self.state.move_page('previous' if cid==5811 else 'next');control=self.getControl(51);control.reset();control.addItems([listitem(i,self.section) for i in self.state.page_items()]);self.p('page',self.state.page_label());self.last_focus=(-1,-1);self.focus(51)
        elif cid in (50,51):
            index=self.getCurrentListPosition() if cid==50 else self.getControl(cid).getSelectedPosition();items=self.rail if cid==50 else self.state.page_items()
            if not 0<=index<len(items):return
            item=items[index];kind=item.get('kind','media')
            if kind in ('next','previous'):self.turn_page(kind);return
            if self.search:self.save_history()
            if item.get('filetype')=='directory':
                if self.search:self.leave_search()
                target=(item.get('catalog_path') if self.source.scope=='library' else '') or item['file']
                content={'tvshow':'seasons','season':'episodes'}.get(media_type(item,self.section),'')
                self.stack.append((self.source,self.state));self.source=DirectorySource(target,content,parent=item);self.state=CatalogState();self.load()
            else:
                # Kodi's native information dialog retains playback/resume/context behavior.
                # Returning leaves this window, list selection and scroll state intact.
                xbmcgui.Dialog().info(listitem(item,self.section))
                self.focus(cid)

    def close_once(self):
        # Kodi WindowXML.close() is a navigation action, not an idempotent
        # resource release. A second call pops the newly restored native window.
        if not getattr(self, 'close_requested', False):
            self.close_requested = True
            self.close()

    def back(self):
        if getattr(self,'closed',False):return
        if self.search:
            if self.getFocusId()==51:self.focus(5801)
            else:self.leave_search()
        elif self.stack:
            # The replacement page can still be in flight when Back is pressed.
            # Do not let its late response overwrite the restored parent.
            self.request += 1
            if self.pending:self.pending[2].cancel()
            self.pending = None
            self.p('loading', '')
            self.source,self.state=self.stack.pop();self.refresh()
        else:self.exit_back=True;self.closed=True;self.close_once()

    def open_native(self,path):
        # Do not turn a selected source/action/settings directory into posters.
        # Hand its untouched URL back to Kodi and suppress recapturing that path.
        if getattr(self,'closed',False):return
        self.setProperty('foundry.slate.movie_submenu_label','')
        self.closed=True;self.close_once()
        xbmcgui.Window(10000).setProperty('foundry.slate.catalog.handled_path',path)
        rpc('GUI.ActivateWindow',{'window':'videos','parameters':[path,'return']})

    def onAction(self,action):
        if getattr(self,'closed',False):return
        aid=action.getId()
        if aid in BACK_ACTIONS:self.back()
        elif self.search and aid==2 and self.getFocusId()==5801:
            if self.results:self.focus(51)
        elif self.search and aid==1 and self.getFocusId()==51 and self.getControl(51).getSelectedPosition()%3==0:
            self.focus(5801)
        elif aid==117:
            cid=self.getFocusId()
            if cid in (50,51):
                items=self.rail if cid==50 else self.state.page_items();idx=self.getCurrentListPosition() if cid==50 else self.getControl(cid).getSelectedPosition()
                if 0<=idx<len(items) and items[idx].get('kind','media')=='media':
                    item=items[idx];choice=xbmcgui.Dialog().contextmenu(['Play','Information','Open in Kodi'])
                    if choice==0:rpc('Player.Open',{'item':{'file':item.get('file','')}})
                    elif choice==1:xbmcgui.Dialog().info(listitem(item,self.section))
                    elif choice==2:
                        self.open_native(self.source.path)

    def dispose(self):
        self.closed=True;self.request+=1
        xbmcgui.Window(10000).clearProperty('foundry.slate.catalog.glow')
        if hasattr(self,'enrichment_executor'):
            for job in self.enrichment_jobs.values():job[1].cancel()
            if self.color_job:self.color_job[1].cancel()
            if self.studio_job:self.studio_job[1].cancel()
            self.enrichment_executor.shutdown(wait=False)
            if hasattr(self,'color_executor'):self.color_executor.shutdown(wait=False)
        self.executor.shutdown(wait=False);self.close_once()


def open_catalog(path,section='Movies',breadcrumb='',source=None):
    if not path:return False
    addon=xbmcaddon.Addon('script.foundry.slate.helper')
    window=CatalogWindow('script-foundry-vod.xml',addon.getAddonInfo('path'),'default','1080i',True,source=source or DirectorySource(path),section=section,breadcrumb=breadcrumb)
    home=xbmcgui.Window(10000)
    home.setProperty('foundry.slate.catalog.active','true')
    home.setProperty('foundry.slate.catalog.handled_path',path)
    try:
        window.show();monitor=xbmc.Monitor()
        while not window.closed and not monitor.waitForAbort(.05):window.tick()
        return True
    finally:
        back=window.exit_back
        window.dispose();del window
        home.clearProperty('foundry.slate.catalog.active')
        # Close restores the exact Videos window that adopted this catalog.
        # Move up ONE native directory only if it still owns the same path.
        # Never send a global Back to a newer window, playback, or Home.
        if (back and xbmc.getCondVisibility('Window.IsActive(videos)') and
                xbmc.getInfoLabel('Container.FolderPath') == path):
            xbmc.executebuiltin('Action(Back,videos)')
