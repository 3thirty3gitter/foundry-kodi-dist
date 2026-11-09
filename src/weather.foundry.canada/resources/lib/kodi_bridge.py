"""Omega-only properties. Import Kodi modules only at the application boundary."""
from datetime import datetime, timezone
from .model import stamp, text

ICON_ROOT = 'resource://resource.images.weathericons.default/'
PREFIX = 'Foundry.Weather.'


def numeric(value):
    if value is None:
        return ''
    return str(int(round(value)))


def temperature(value, units='°C'):
    if value is None:
        return ''
    return numeric(value * 9 / 5 + 32 if 'F' in units else value) + ('°F' if 'F' in units else '°C')


def local_time(value, short=False, time_format='%H:%M'):
    when = stamp(value)
    if not when:
        return ''
    # Numeric dates avoid pretending that the device's C locale is the UI language.
    time_format=time_format.replace(':%S','').replace('%S:','')
    return when.astimezone().strftime(time_format if short else '%Y-%m-%d '+time_format)


def build_properties(model, fetched_at, stale=False, reason='fresh', units='°C', time_format='%H:%M'):
    current = model['current']
    stale = stale or model['source_stale']
    p = {'WeatherProvider': 'Foundry Canada Weather', 'Current.Location': model['name'] + ', ' + model['province'],
         'Current.Condition': current['condition'], 'Current.Temperature': numeric(current['temperature']),
         'Current.FeelsLike': numeric(current['feels_like']), 'Current.DewPoint': numeric(current['dewpoint']),
         'Current.Humidity': numeric(current['humidity']), 'Current.Wind': numeric(current['wind_kph']),
         'Current.WindDirection': current['wind_direction'] or ('CALM' if current['wind_kph'] == 0 else ''),
         'Current.OutlookIcon': current['icon'], 'Current.UVIndex': '',
         'Current.FanartCode': current['icon'][:-4],
         'Current.IsFetched': 'true' if current['temperature'] is not None else 'false',
         'Daily.IsFetched': 'true' if model['days'] else 'false',
         'Hourly.IsFetched': 'true' if model['hourly'] else 'false',
         PREFIX+'Status': 'stale' if stale else reason, PREFIX+'Stale': 'true' if stale else 'false',
         PREFIX+'HasCurrent': 'true' if current['temperature'] is not None else 'false',
         PREFIX+'Location': model['name'] + ', ' + model['province'],
         PREFIX+'Temperature': temperature(current['temperature'], units),
         PREFIX+'FeelsLike': temperature(current['feels_like'], units),
         PREFIX+'Condition': current['condition'], PREFIX+'Icon': ICON_ROOT + current['icon'],
         PREFIX+'ObservedAt': model['observed'], PREFIX+'ObservedLocal': local_time(model['observed'],False,time_format),
         PREFIX+'UpdatedAt': model['updated'], PREFIX+'FetchedAt': datetime.fromtimestamp(fetched_at, timezone.utc).isoformat(),
         PREFIX+'TimeBasis': 'device', PREFIX+'Attribution': model['attribution'], PREFIX+'LicenceURL': model['licence_url'],
         PREFIX+'HasAlerts': 'true' if model['alerts'] else 'false',
         PREFIX+'AlertCount': str(len(model['alerts'])), PREFIX+'AlertStatus': 'unverified' if stale else 'reported' if model.get('warnings_available') else 'unknown',
         PREFIX+'AlertsAreComplete': 'false', PREFIX+'DayCount': str(len(model['days'])),
         PREFIX+'HourCount': str(len(model['hourly']))}
    for index, day in enumerate(model['days']):
        key = 'Day' + str(index) + '.'
        p.update({key+'Title': day['title'], key+'HighTemp': numeric(day['high']), key+'LowTemp': numeric(day['low']),
                  key+'Outlook': day['condition'], key+'OutlookIcon': day['icon']})
        key = PREFIX+'Day.' + str(index+1) + '.'
        high,low=temperature(day['high'],units),temperature(day['low'],units)
        range_text=high+' / '+low if high and low else (('Max ' if model['language']=='fr' else 'High ')+high) if high else (('Min ' if model['language']=='fr' else 'Low ')+low) if low else ''
        p.update({key+'Title': day['title'], key+'High': temperature(day['high'],units), key+'Low': temperature(day['low'],units),
                  key+'Range':range_text, key+'Condition': day['condition'], key+'Icon': ICON_ROOT+day['icon'], key+'Summary': day['summary']})
    for index, hour in enumerate(model['hourly'], 1):
        key = 'Hourly.'+str(index)+'.'
        p.update({key+'Time':local_time(hour['time'],True,time_format), key+'Temperature':temperature(hour['temperature'],units),
                  key+'Outlook':hour['condition'], key+'OutlookIcon':ICON_ROOT+hour['icon'],
                  key+'Precipitation':numeric(hour['pop'])+'%' if hour['pop'] is not None else ''})
        key=PREFIX+'Hour.'+str(index)+'.'
        p.update({key+'Time':local_time(hour['time'],True,time_format), key+'Timestamp':hour['time'],
                  key+'Temperature':temperature(hour['temperature'],units), key+'Condition':hour['condition'],
                  key+'Icon':ICON_ROOT+hour['icon'],key+'PoP':numeric(hour['pop'])+'%' if hour['pop'] is not None else ''})
    for index, alert in enumerate(model['alerts'],1):
        for field, value in alert.items():
            p[PREFIX+'Alert.'+str(index)+'.'+field.title()] = value
    return p


def clear_properties(window):
    # Omega does not reset these automatically. Never clear another window's state.
    for field in ['Location','Condition','Temperature','FeelsLike','DewPoint','Humidity','Wind','WindDirection','OutlookIcon','ConditionIcon','UVIndex','WindSpeed','IsFetched','FanartCode']:
        window.clearProperty('Current.'+field)
    for field in ['Daily.IsFetched','Hourly.IsFetched','Weekend.IsFetched','36Hour.IsFetched','Alerts.IsFetched','WeatherProvider','WeatherProviderLogo']:
        window.clearProperty(field)
    for i in range(7):
        for field in ['Title','HighTemp','LowTemp','Outlook','OutlookIcon','FanartCode']:
            window.clearProperty('Day'+str(i)+'.'+field)
    for field in ['Status','Stale','HasCurrent','Location','Temperature','FeelsLike','Condition','Icon','ObservedAt','ObservedLocal','UpdatedAt','FetchedAt','TimeBasis','Attribution','LicenceURL','HasAlerts','AlertCount','AlertStatus','AlertsAreComplete','DayCount','HourCount']:
        window.clearProperty(PREFIX+field)
    for i in range(1,25):
        for field in ['Time','Temperature','Outlook','OutlookIcon','Precipitation']:
            window.clearProperty('Hourly.'+str(i)+'.'+field)
        for field in ['Time','Timestamp','Temperature','Condition','Icon','PoP']:
            window.clearProperty(PREFIX+'Hour.'+str(i)+'.'+field)
    for i in range(1,8):
        for field in ['Title','High','Low','Range','Condition','Icon','Summary']:
            window.clearProperty(PREFIX+'Day.'+str(i)+'.'+field)
    for i in range(1,21):
        for field in ['Headline','Type','Colour','Issued','Expires','Url']:
            window.clearProperty(PREFIX+'Alert.'+str(i)+'.'+field)


def publish(window, properties):
    clear_properties(window)
    for key,value in properties.items():
        window.setProperty(key, str(value))
