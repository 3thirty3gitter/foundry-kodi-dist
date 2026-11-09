"""Normalize bilingual City Page Weather without fetching icons or inferring location."""
import math
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse
from .client import PayloadError

ID_RE = re.compile(r'^(ab|bc|mb|nb|nl|ns|nt|nu|on|pe|qc|sk|yt)-[a-z0-9]{1,8}$')
ATTRIBUTION = 'Data Source: Environment and Climate Change Canada'
LICENCE_URL = 'https://eccc-msc.github.io/open-data/licence/readme_en/'
# Source codes are not Kodi/Yahoo codes. These map to Kodi's bundled icons.
ICONS = {0:32,1:34,2:30,3:28,4:28,5:34,6:39,7:5,8:41,9:37,10:26,
         11:11,12:11,13:12,14:10,15:5,16:16,17:16,18:15,19:4,22:30,
         23:21,24:20,25:15,26:16,27:18,28:9,30:31,31:33,32:29,33:27,
         34:27,35:33,36:45,37:5,38:46,39:47,40:15,41:0,42:0,43:24,
         44:22,45:19,46:4,47:4,48:0}


def localized(value, language='en', default=''):
    if isinstance(value, dict):
        return value.get(language, value.get('en', default))
    return default if value is None else value


def text(value, limit=4000):
    if not isinstance(value, (str, int, float)):
        return ''
    # Kodi label markup is not trusted input. Preserve visible wording safely.
    result = str(value).replace('[', '［').replace(']', '］')
    return ''.join(c for c in result if c in '\n\t' or ord(c) >= 32)[:limit]


def number(value, language='en', minimum=-100, maximum=1000):
    if isinstance(value, dict) and 'value' in value:
        value = value['value']
    value = localized(value, language, None)
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and minimum <= result <= maximum else None
    except (TypeError, ValueError):
        return None


def stamp(value, language='en'):
    try:
        result = datetime.fromisoformat(str(localized(value, language)).replace('Z', '+00:00'))
        if result.tzinfo is None:
            return None
        return result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def icon(value):
    code = number(value)
    return str(ICONS.get(int(code), 'na')) + '.png' if code is not None and code.is_integer() else 'na.png'


def valid_id(value):
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None


def validate_feature(data, expected_id=None):
    if not isinstance(data, dict) or data.get('type') != 'Feature':
        raise PayloadError('Not a weather feature')
    properties = data.get('properties')
    if not isinstance(properties, dict) or not valid_id(data.get('id')):
        raise PayloadError('Invalid weather identity')
    if expected_id is not None and data['id'] != expected_id:
        raise PayloadError('Weather identity mismatch')
    if properties.get('identifier') != data['id'] or not isinstance(properties.get('name'), dict):
        raise PayloadError('Weather identity or name missing')
    if not stamp(properties.get('lastUpdated')):
        raise PayloadError('Weather update timestamp missing')
    if properties.get('warnings') is not None and not isinstance(properties['warnings'],list):
        raise PayloadError('Warning section has unexpected shape')
    for field in ('currentConditions', 'forecastGroup', 'hourlyForecastGroup', 'riseSet'):
        if properties.get(field) is not None and not isinstance(properties[field], dict):
            raise PayloadError('Weather section has unexpected shape')
    for group, field in [('forecastGroup','forecasts'),('hourlyForecastGroup','hourlyForecasts')]:
        values = (properties.get(group) or {}).get(field, [])
        if not isinstance(values,list) or any(not isinstance(value,dict) for value in values):
            raise PayloadError('Forecast section has unexpected shape')
    for container in [properties.get('currentConditions') or {}] + (properties.get('forecastGroup') or {}).get('forecasts',[]) + (properties.get('hourlyForecastGroup') or {}).get('hourlyForecasts',[]):
        for field in ('wind','period','temperatures','abbreviatedForecast'):
            if container.get(field) is not None and not isinstance(container[field],dict):
                raise PayloadError('Weather field has unexpected shape')
        wind=container.get('wind') or {}
        if wind.get('direction') is not None and not isinstance(wind['direction'],dict):
            raise PayloadError('Wind direction has unexpected shape')
        temperatures=(container.get('temperatures') or {}).get('temperature',[])
        if not isinstance(temperatures,list) or any(not isinstance(value,dict) for value in temperatures):
            raise PayloadError('Temperature list has unexpected shape')


def validate_catalogue(data):
    if not isinstance(data, dict) or data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
        raise PayloadError('Invalid location catalogue')
    if not data['features'] or len(data['features']) > 1000:
        raise PayloadError('Unexpected location count')
    count = data.get('numberMatched', len(data['features']))
    if isinstance(count, bool) or not isinstance(count, int) or count > len(data['features']):
        raise PayloadError('Location catalogue is incomplete')
    if any(isinstance(link,dict) and link.get('rel') == 'next' for link in data.get('links',[])):
        raise PayloadError('Location catalogue is incomplete')
    if any(not isinstance(feature,dict) or not isinstance(feature.get('properties'),dict) for feature in data['features']):
        raise PayloadError('Location catalogue has unexpected shape')


def locations(data, language='en', query=''):
    def fold(value):
        return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))
    query = fold(query.strip())
    result = []
    for feature in data.get('features', []):
        identifier = feature.get('id')
        properties = feature.get('properties', {})
        if not valid_id(identifier):
            continue
        name = text(localized(properties.get('name'), language), 160)
        label = name + ', ' + identifier.split('-')[0].upper()
        if name and (not query or query in fold(label)):
            result.append({'id': identifier, 'name': name, 'label': label})
    return sorted(result, key=lambda item: fold(item['label']))


def official_url(value, language):
    url = localized(value, language)
    try:
        parsed = urlparse(url) if isinstance(url, str) else None
        if parsed and parsed.scheme == 'https' and parsed.hostname in ('weather.gc.ca', 'meteo.gc.ca', 'www.weather.gc.ca', 'www.meteo.gc.ca') and parsed.port in (None,443) and not parsed.username and not parsed.password and not any(ord(c)<32 for c in url):
            return url
    except ValueError:
        pass
    return ''


def normalize(feature, language='en', now=None):
    validate_feature(feature)
    language = language if language in ('en', 'fr') else 'en'
    now = now or datetime.now(timezone.utc)
    p = feature['properties']
    cc = p.get('currentConditions') or {}
    wind = cc.get('wind') or {}
    temperature = number(cc.get('temperature'), language, -100, 65)
    chill = number(cc.get('windChill'), language, -150, 65)
    humidex = number(cc.get('humidex'), language, -100, 100)
    feels = chill if temperature is not None and temperature <= 0 and chill is not None else humidex if temperature is not None and temperature >= 20 and humidex is not None else temperature
    observed = stamp(cc.get('timestamp'), language)
    updated = stamp(p.get('lastUpdated'))
    model = {'id': feature['id'], 'name': text(localized(p['name'], language), 160),
             'province': feature['id'].split('-')[0].upper(), 'language': language,
             'updated': updated.isoformat(), 'observed': observed.isoformat() if observed else '',
             'source_stale': not -300 <= (now - updated).total_seconds() <= 10800 or (temperature is not None and observed is None) or (observed is not None and not -300 <= (now-observed).total_seconds() <= 10800),
             'current': {'temperature': temperature, 'feels_like': feels,
                         'condition': text(localized(cc.get('condition'), language), 240),
                         'icon': icon(cc.get('iconCode')), 'humidity': number(cc.get('relativeHumidity'), language, 0, 100),
                         'dewpoint': number(cc.get('dewpoint'), language, -100, 65),
                         'wind_kph': number(wind.get('speed'), language, 0, 500),
                         'wind_direction': text(localized((wind.get('direction') or {}).get('value',wind.get('direction')), language), 16),
                         'gust_kph': number(wind.get('gust'), language, 0, 500),
                         'pressure_kpa': number(cc.get('pressure'), language, 50, 120)},
             'days': [], 'hourly': [], 'alerts': [], 'warnings_available': isinstance(p.get('warnings'),list),
             'attribution': ATTRIBUTION, 'licence_url': LICENCE_URL}
    # Combine each actual named daytime/nighttime pair; do not fabricate dates.
    groups = []
    for period in (p.get('forecastGroup') or {}).get('forecasts', [])[:20]:
        per = period.get('period') or {}
        name_en = str(localized(per.get('value'), 'en'))
        group_key = re.sub(r'\s+night$', '', name_en, flags=re.I)
        if group_key.casefold() in ('today','tonight','this evening','this afternoon','this morning'):
            group_key = '__today__'
        abbreviated = period.get('abbreviatedForecast') or {}
        entry = {'title': text(localized(per.get('textForecastName'), language), 80),
                 'high': None, 'low': None, 'condition': text(localized(abbreviated.get('textSummary'), language), 240),
                 'icon': icon(abbreviated.get('icon')), 'summary': text(localized(period.get('textSummary'), language)),
                 'key': group_key}
        for temp in (period.get('temperatures') or {}).get('temperature', []):
            kind = localized(temp.get('class'), 'en')
            if kind in ('high', 'low'):
                entry[kind] = number(temp, language, -100, 65)
        if groups and groups[-1]['key'] == group_key:
            for kind in ('high', 'low'):
                if entry[kind] is not None:
                    groups[-1][kind] = entry[kind]
            if entry['summary']:
                groups[-1]['summary'] += '\n'+entry['title']+': '+entry['summary']
        else:
            groups.append(entry)
    model['days'] = groups[:7]
    for hour in (p.get('hourlyForecastGroup') or {}).get('hourlyForecasts', [])[:72]:
        when = stamp(hour.get('timestamp'), language)
        if when is None or when < now:
            continue
        model['hourly'].append({'time': when.isoformat(), 'temperature': number(hour.get('temperature'), language, -100,65),
                                'condition': text(localized(hour.get('condition'), language), 240),
                                'icon': icon(hour.get('iconCode')), 'pop': number(hour.get('lop'), language, 0,100)})
        if len(model['hourly']) == 24:
            break
    warnings = p.get('warnings') or []
    if not isinstance(warnings, list):
        warnings = []
    for warning in warnings[:20]:
        if not isinstance(warning, dict):
            continue
        expires = stamp(warning.get('expiryTime'), language)
        issued = stamp(warning.get('eventIssue'), language)
        headline = text(localized(warning.get('description'), language), 1000)
        if not headline or expires is None or expires <= now:
            continue
        model['alerts'].append({'headline': headline, 'type': text(localized(warning.get('type'), language),40),
                                'colour': text(localized(warning.get('alertColourLevel'),language),40),
                                'issued': issued.isoformat() if issued else '', 'expires': expires.isoformat(),
                                'url': official_url(warning.get('url'),language)})
    return model
