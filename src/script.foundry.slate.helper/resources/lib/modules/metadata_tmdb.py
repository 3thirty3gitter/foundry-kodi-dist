"""Direct TMDb movie/series/season/episode metadata, independent of add-ons."""
import re
import requests
from .catalog_model import clean, label


class ProviderError(Exception):
    def __init__(self, status, backoff=0):
        self.status, self.backoff = status, backoff
        super().__init__(status)  # Never retain a URL, response body or credential.


def integer(value):
    return int(str(value)) if not isinstance(value,bool) and re.fullmatch(r'\d+',str(value)) else None


def image(path, size='original'):
    return 'https://image.tmdb.org/t/p/'+size+path if isinstance(path,str) and re.fullmatch(r'/[A-Za-z0-9_.-]+',path) else ''


def rows(value):
    return [v for v in value if isinstance(v,dict)] if isinstance(value,list) else []


class TmdbMetadataClient:
    URL = 'https://api.themoviedb.org/3'

    def __init__(self, key, language='en-US', region='CA', session=None):
        self.key, self.language, self.region = key, language, region
        self.session = session or requests.Session()

    def request(self, path, **params):
        if not self.key:
            raise ProviderError('missing_key')
        params['language'] = self.language
        headers = {'Accept':'application/json'}
        if re.fullmatch(r'[A-Fa-f0-9]{32}',self.key):
            params['api_key'] = self.key
        else:
            headers['Authorization'] = 'Bearer '+self.key.removeprefix('Bearer ').strip()
        try:
            response = self.session.get(self.URL+path,params=params,headers=headers,timeout=(5,10))
            if response.status_code in (401,403):
                raise ProviderError('invalid_key',86400)
            if response.status_code == 429:
                wait = response.headers.get('Retry-After','60')
                raise ProviderError('rate_limited',max(30,min(86400,int(wait))) if str(wait).isdigit() else 60)
            if response.status_code == 404:
                raise ProviderError('not_found')
            if response.status_code != 200:
                raise ProviderError('offline',30)
            data = response.json()
            if not isinstance(data,dict):
                raise ProviderError('offline',30)
            return data
        except (requests.RequestException,ValueError,TypeError):
            raise ProviderError('offline',30) from None

    def resolve(self, item, kind):
        unique = item.get('uniqueid') or {}
        tmdb = clean(unique.get('tmdb') or unique.get('themoviedb'))
        imdb = clean(unique.get('imdb') or item.get('imdbnumber'))
        if re.fullmatch(r'[1-9]\d*',tmdb):
            return int(tmdb)
        if re.fullmatch(r'tt\d+',imdb):
            found = rows(self.request('/find/'+imdb,external_source='imdb_id').get('tv_results' if kind=='tv' else 'movie_results'))
        else:
            title, year = label(item), clean(item.get('year'))
            if not title or not re.fullmatch(r'\d{4}',year):
                raise ProviderError('unidentified')
            params = {'query':title,'include_adult':'false', 'first_air_date_year' if kind=='tv' else 'year':year}
            results = rows(self.request('/search/'+kind,**params).get('results'))
            found = [r for r in results if title.casefold() in {clean(r.get(k)).casefold() for k in ('name','title','original_name','original_title')} and clean(r.get('first_air_date' if kind=='tv' else 'release_date'))[:4]==year]
        found = [r for r in found if integer(r.get('id')) and integer(r.get('id'))>0]
        if len(found) != 1:
            raise ProviderError('not_found')
        return int(found[0]['id'])

    def fetch(self, item):
        try:
            kind = item.get('type')
            if kind not in ('movie','tvshow','season','episode'):
                return {},'unidentified',0
            tv = kind != 'movie'
            parent = None
            if kind in ('season','episode'):
                unique = item.get('uniqueid') or {}
                series_id = clean(unique.get('tvshow.tmdb') or item.get('tvshow_tmdb_id'))
                if not re.fullmatch(r'[1-9]\d*',series_id):
                    # Episode IMDb IDs are distinct from their show's IMDb ID.
                    own_imdb = clean(unique.get('imdb') or item.get('imdbnumber'))
                    if kind=='episode' and re.fullmatch(r'tt\d+',own_imdb):
                        found = rows(self.request('/find/'+own_imdb,external_source='imdb_id').get('tv_episode_results'))
                        if len(found)==1:
                            for field,source in [('season','season_number'),('episode','episode_number')]:
                                if item.get(field) not in (None,'') and integer(item[field])!=integer(found[0].get(source)):
                                    raise ProviderError('not_found')
                            series_id=clean(found[0].get('show_id'))
                            item=dict(item,season=found[0].get('season_number'),episode=found[0].get('episode_number'))
                    if not re.fullmatch(r'[1-9]\d*',series_id):
                        parent_item={'title':clean(item.get('showtitle')),'year':item.get('tvshowyear'), 'uniqueid':{'imdb':unique.get('tvshow.imdb','')}}
                        series_id=str(self.resolve(parent_item,'tv'))
                season=integer(item.get('season'))
                if item.get('season') in (None,'') or season is None:
                    raise ProviderError('unidentified')
                path='/tv/'+series_id+'/season/'+str(season)
                if kind=='episode':
                    episode=integer(item.get('episode'))
                    if item.get('episode') in (None,'') or episode is None:
                        raise ProviderError('unidentified')
                    path+='/episode/'+str(episode)
                parent=self.request('/tv/'+series_id,append_to_response='images,content_ratings,external_ids',include_image_language=self.language.split('-')[0]+',en,null')
                if integer(parent.get('id'))!=int(series_id):raise ProviderError('not_found')
                data=self.request(path,append_to_response='images,credits,external_ids')
                if integer(data.get('season_number'))!=season or (kind=='episode' and integer(data.get('episode_number'))!=episode):
                    raise ProviderError('not_found')
                result=self.convert(data,kind,parent)
                result['uniqueid']['tvshow.tmdb']=series_id
                result['showtitle']=parent.get('name','')
                if (parent.get('external_ids') or {}).get('imdb_id'):result['uniqueid']['tvshow.imdb']=parent['external_ids']['imdb_id']
            else:
                tmdb_id=self.resolve(item,'tv' if tv else 'movie')
                path=('/tv/' if tv else '/movie/')+str(tmdb_id)
                data=self.request(path,append_to_response='images,credits,external_ids,'+('content_ratings' if tv else 'release_dates'),include_image_language=self.language.split('-')[0]+',en,null')
                if integer(data.get('id'))!=tmdb_id:raise ProviderError('not_found')
                result=self.convert(data,kind)
            requested=clean((item.get('uniqueid') or {}).get('imdb') or item.get('imdbnumber'))
            returned=result['uniqueid'].get('imdb')
            if requested and returned and requested!=returned:raise ProviderError('not_found')
            return result,'ready',0
        except ProviderError as error:
            return {},error.status,error.backoff
        except (ValueError,TypeError,KeyError,AttributeError):
            return {},'offline',30

    def convert(self, data, kind, parent=None):
        show=parent or data
        tv=kind!='movie'
        result={'type':kind,'art':{},'ratings':{},'uniqueid':{}}
        for target,source in [('title','name' if tv else 'title'),('originaltitle','original_name' if tv else 'original_title'),('plot','overview'),('tagline','tagline'),('status','status'),('original_language','original_language')]:
            if clean(data.get(source)):result[target]=clean(data[source])
        premiered=clean(data.get('air_date' if kind in ('season','episode') else 'first_air_date' if tv else 'release_date'))
        if premiered:
            result['premiered']=premiered
            if re.fullmatch(r'\d{4}',premiered[:4]):result['year']=int(premiered[:4])
        result['genre']=[r['name'] for r in rows(show.get('genres')) if clean(r.get('name'))]
        result['studio']=[r['name'] for r in rows(show.get('production_companies')) if clean(r.get('name'))]
        result['country']=[r['name'] for r in rows(show.get('production_countries')) if clean(r.get('name'))]
        runtime=integer(data.get('runtime'))
        if not runtime:
            times=show.get('episode_run_time') or []
            runtime=integer(times[0]) if isinstance(times,list) and times else None
        if runtime:result['runtime']=runtime*60
        result['uniqueid']['tmdb']=str(data.get('id',''))
        imdb=clean(data.get('imdb_id') or (data.get('external_ids') or {}).get('imdb_id'))
        if re.fullmatch(r'tt\d+',imdb):result['uniqueid']['imdb']=imdb;result['imdbnumber']=imdb
        if kind in ('season','episode'):
            result['season']=data.get('season_number')
            if kind=='episode':result['episode']=data.get('episode_number')
        for name,source,size in [('poster','poster_path','w780'),('fanart','backdrop_path','original'),('thumb','still_path','w780')]:
            value=image(data.get(source) or show.get(source),size)
            if value:result['art'][name]=value
        logos=rows((show.get('images') or {}).get('logos'))
        preference=(self.language.split('-')[0],'en',None)
        logos.sort(key=lambda r:(preference.index(r.get('iso_639_1')) if r.get('iso_639_1') in preference else 4,-(integer(r.get('width')) or 0)))
        for logo in logos:
            url=image(logo.get('file_path'))
            if url:result['art']['clearlogo']=url;break
        for company in rows(show.get('production_companies')):
            url=image(company.get('logo_path'),'w500')
            if url:result['art']['studiologo']=url;break
        credits=data.get('credits') or {}
        cast=rows(credits.get('cast'))+rows(credits.get('guest_stars'))
        seen=set();result['cast']=[]
        for row in cast:
            name=clean(row.get('name'))
            if not name or name in seen:continue
            seen.add(name)
            result['cast'].append({'name':name,'role':clean(row.get('character')),'thumbnail':image(row.get('profile_path'),'w185'),'order':len(result['cast'])})
            if len(result['cast'])>=40:break
        crew=rows(credits.get('crew'))
        result['director']=list(dict.fromkeys(r['name'] for r in crew if r.get('job')=='Director' and clean(r.get('name'))))
        result['writer']=list(dict.fromkeys(r['name'] for r in crew if r.get('department')=='Writing' and clean(r.get('name'))))
        try:
            vote=float(data.get('vote_average') or 0);count=int(data.get('vote_count') or 0)
            if 0<=vote<=10 and count>0:result['ratings']['tmdb']={'rating':round(vote,1),'votes':count}
        except (ValueError,TypeError):pass
        entries=rows((show.get('content_ratings' if tv else 'release_dates') or {}).get('results'))
        for country in dict.fromkeys((self.region,'CA','US')):
            region=next((r for r in entries if r.get('iso_3166_1')==country),{})
            if tv:rating=clean(region.get('rating'))
            else:
                releases=rows(region.get('release_dates'))
                order={3:0,4:1,5:2,6:3,2:4,1:5}
                releases.sort(key=lambda r:order.get(r.get('type'),6))
                rating=next((clean(r.get('certification')) for r in releases if clean(r.get('certification'))),'')
            if rating:result['mpaa']=country+' '+rating;break
        return result
