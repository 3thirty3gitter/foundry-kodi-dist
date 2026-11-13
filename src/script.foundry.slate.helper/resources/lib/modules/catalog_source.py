"""JSON-RPC source adapter. Existing provider URLs and playback paths stay intact."""
import json
import xbmc
from .catalog_model import split_directory
from .catalog_items import normalize, catalog_directory

FIELDS = ['title','year','plot','genre','studio','premiered','rating','ratings','mpaa','imdbnumber','art','playcount']
# Files.GetDirectory uses List.Fields.Files, which rejects the plural ratings
# property. VideoLibrary methods support it, so keep their richer field set.
DIRECTORY_FIELDS = [field for field in FIELDS if field != 'ratings']+['uniqueid','season','episode','showtitle','firstaired','tvshowid','thumbnail','fanart','mimetype']


def rpc(method, params):
    result = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params})))
    if 'error' in result:
        raise RuntimeError('Kodi could not read this media source.')
    return result.get('result', {})


def inherit_tv_context(item, parent, native_library=False):
    """Carry explicit parent identity, never guess numbers or copy show details."""
    if not isinstance(parent,dict) or item.get('type') not in ('season','episode'):
        return item
    parent_kind=parent.get('type')
    if parent_kind not in ('tvshow','season'):return item
    result=dict(item);ids=dict(item.get('uniqueid') or {});parent_ids=parent.get('uniqueid') or {}
    for provider in ('tmdb','imdb'):
        value=parent_ids.get('tvshow.'+provider) or (parent_ids.get(provider) if parent_kind=='tvshow' else '')
        if value:
            existing=ids.get('tvshow.'+provider)
            if existing and str(existing)!=str(value):return item
            ids['tvshow.'+provider]=str(value)
    result['uniqueid']=ids
    show=parent.get('showtitle') or (parent.get('title') or parent.get('label') if parent_kind=='tvshow' else '')
    if show and not result.get('showtitle'):result['showtitle']=show
    year=parent.get('tvshowyear') or (parent.get('year') if parent_kind=='tvshow' else None)
    if year and not result.get('tvshowyear'):result['tvshowyear']=year
    if parent_kind=='season' and item.get('type')=='episode' and item.get('season') is None:
        value=parent.get('season')
        if type(value) is int and value>=0:result['season']=value
    if native_library:
        dbid=parent.get('tvshowid') or (parent.get('id') if parent_kind=='tvshow' else None)
        if type(dbid) is int and dbid>0:result.setdefault('tvshowid',dbid)
    return result


class DirectorySource:
    def __init__(self, path, content='', parent=None, movie_submenu_label='', movie_submenu_verified=False):
        self.path = path
        self.parent = parent
        self.content = content
        self.initial = None
        self.movie_submenu_label = movie_submenu_label
        self.movie_submenu_verified = movie_submenu_verified
        self.scope = 'library' if path.startswith(('videodb://','library://video')) else 'provider directory'

    def load(self):
        if self.initial is not None:
            result, self.initial = self.initial, None
            return result
        params = {'directory':self.path,'media':'video','properties':DIRECTORY_FIELDS}
        try:
            result = rpc('Files.GetDirectory', params)
        except RuntimeError:
            # Some providers/Kodi versions expose only the common file fields.
            params['properties'] = ['title','year','plot','genre','studio','rating','art','season','episode','showtitle','firstaired','uniqueid','tvshowid']
            result = rpc('Files.GetDirectory', params)
        records=result.get('files', [])
        if not isinstance(records,list):raise RuntimeError('Kodi returned an invalid directory.')
        items,nxt,prev=split_directory([inherit_tv_context(normalize(i,self.content),self.parent,self.scope=='library') for i in records if isinstance(i,dict)])
        return {'items':items,'next_path':nxt,'previous_path':prev,'scope':self.scope,
                'catalog_eligible':catalog_directory(items,self.content,bool(nxt or prev))}

    def search(self, query, is_tv=False):
        # A Kodi library is searchable across its complete title index. A provider
        # owns its API: no guessed endpoint/query rewrite or fake server total.
        if self.scope == 'library':
            field = 'tvshows' if is_tv else 'movies'
            method = 'VideoLibrary.GetTVShows' if is_tv else 'VideoLibrary.GetMovies'
            result=rpc(method,{'filter':{'field':'title','operator':'contains','value':query},'properties':FIELDS+['file','uniqueid']})
            items=[normalize(i,'tvshows' if is_tv else 'movies') for i in result.get(field,[]) if isinstance(i,dict)]
            for item in items:
                # Kodi's own TV-show navigation path, not a provider URL guess.
                # Keep the physical file path as identity; browse native seasons.
                tvshowid=item.get('tvshowid')
                if is_tv and type(tvshowid) is int and tvshowid>0:
                    item['catalog_path']='videodb://tvshows/titles/%d/'%tvshowid
            return items
        return None
