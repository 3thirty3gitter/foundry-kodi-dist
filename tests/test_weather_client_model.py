"""Offline regression tests. Run: python -m unittest discover -s tests -v."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError

LIB = Path(__file__).resolve().parents[1] / 'src/weather.foundry.canada/resources/lib'
# Package alias keeps dotted add-on directory names out of Python imports.
NAME = 'foundry_weather_test_lib'
spec = importlib.util.spec_from_file_location(NAME, LIB / '__init__.py', submodule_search_locations=[str(LIB)])
if NAME not in sys.modules:
    package = importlib.util.module_from_spec(spec)
    sys.modules[NAME] = package
    spec.loader.exec_module(package)
from foundry_weather_test_lib import client, model

NOW = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)
PATH = client.COLLECTION + '/items/on-118?f=json'


def bi(en, fr=None):
    return {'en': en, 'fr': en if fr is None else fr}


def feature():
    return {'type': 'Feature', 'id': 'on-118', 'properties': {
        'identifier': 'on-118', 'name': bi('Ottawa', 'Ottawa'),
        'lastUpdated': '2026-01-05T12:00:00Z',
        'currentConditions': {'timestamp': bi('2026-01-05T11:30:00Z'),
            'temperature': {'value': bi(0)}, 'windChill': {'value': bi(-7)},
            'condition': bi('Snow', 'Neige'), 'relativeHumidity': {'value': bi(0)},
            'wind': {'speed': {'value': bi(0)}, 'direction': {'value': bi('N', 'N')}}}}}


def period(name, kind, value, french=None):
    return {'period': {'value': bi(name), 'textForecastName': bi(name, french or name)},
            'temperatures': {'temperature': [{'class': bi(kind), 'value': bi(value)}]},
            'abbreviatedForecast': {'textSummary': bi('Snow', 'Neige'), 'icon': {'value': 16}}}


class ModelTests(unittest.TestCase):
    def test_zero_negative_and_missing_values_are_distinct(self):
        p = feature()
        c = model.normalize(p, now=NOW)['current']
        self.assertEqual((c['temperature'], c['feels_like'], c['humidity'], c['wind_kph']), (0, -7, 0, 0))
        self.assertIsNone(c['dewpoint'])
        p['properties']['currentConditions']['temperature'] = {'value': bi(-25)}
        self.assertEqual(model.normalize(p, now=NOW)['current']['temperature'], -25)
        p['properties']['currentConditions'] = {}
        self.assertIsNone(model.normalize(p, now=NOW)['current']['temperature'])

    def test_nonfinite_boolean_and_out_of_range_values(self):
        for value in (True, False, float('nan'), float('inf'), 'bad', None, [], 10000):
            with self.subTest(value=value):
                self.assertIsNone(model.number(value))

    def test_humidex_and_bilingual_fields(self):
        p = feature()
        p['properties']['name'] = bi('Quebec', 'Québec')
        p['properties']['currentConditions'].update(temperature={'value': bi(25)}, humidex={'value': bi(31)})
        result = model.normalize(p, 'fr', NOW)
        self.assertEqual(result['name'], 'Québec')
        self.assertEqual(result['current']['condition'], 'Neige')
        self.assertEqual(result['current']['feels_like'], 31)
        self.assertEqual(model.normalize(p, 'xx', NOW)['language'], 'en')

    def test_day_and_night_group_without_losing_zero(self):
        p = feature()
        p['properties']['forecastGroup'] = {'forecasts': [period('Monday', 'high', 0, 'Lundi'),
            period('Monday night', 'low', -10), period('Tuesday', 'high', -2)]}
        days = model.normalize(p, 'fr', NOW)['days']
        self.assertEqual(len(days), 2)
        self.assertEqual((days[0]['title'], days[0]['high'], days[0]['low']), ('Lundi', 0, -10))
        self.assertEqual(days[1]['high'], -2)

    def test_today_and_tonight_pair(self):
        p = feature()
        p['properties']['forecastGroup'] = {'forecasts': [period('Today', 'high', 2), period('Tonight', 'low', -4)]}
        days = model.normalize(p, now=NOW)['days']
        self.assertEqual(len(days), 1)
        self.assertEqual((days[0]['high'], days[0]['low']), (2, -4))

    def test_markup_and_control_characters_are_sanitized(self):
        result = model.text('[COLOR red]Snow[/COLOR]\x00\x01')
        self.assertNotIn('[', result)
        self.assertNotIn('\x00', result)
        self.assertIn('Snow', result)
        self.assertEqual(model.text('x' * 200, 10), 'x' * 10)

    def test_urls_reject_untrusted_hosts_credentials_and_schemes(self):
        for url in ('http://weather.gc.ca/a', 'https://evil.test/a', 'https://weather.gc.ca.evil.test/a',
                    'https://user:password@weather.gc.ca/a', 'javascript:alert(1)', '//weather.gc.ca/a'):
            with self.subTest(url=url):
                self.assertEqual(model.official_url(url, 'en'), '')
        self.assertEqual(model.official_url(bi('https://weather.gc.ca/a', 'https://meteo.gc.ca/a'), 'fr'), 'https://meteo.gc.ca/a')

    def test_alerts_require_future_expiry(self):
        p = feature()
        p['properties']['warnings'] = [
            {'description': bi('Warning', 'Alerte'), 'expiryTime': bi(expiry), 'url': 'https://evil.test/'}
            for expiry in ('2026-01-05T13:00:00Z', '2026-01-05T12:00:00Z', '2026-01-04T12:00:00Z', 'bad')]
        alerts = model.normalize(p, 'fr', NOW)['alerts']
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['headline'], 'Alerte')
        self.assertEqual(alerts[0]['url'], '')

    def test_source_stale_and_hourly_cutoff(self):
        p = feature()
        p['properties']['currentConditions']['timestamp'] = bi('2026-01-05T08:59:59Z')
        p['properties']['hourlyForecastGroup'] = {'hourlyForecasts': [
            {'timestamp': bi(ts), 'temperature': {'value': bi(0)}} for ts in
            ('2026-01-05T11:00:00Z', '2026-01-05T12:00:00Z', '2026-01-05T13:00:00Z', 'bad')]}
        result = model.normalize(p, now=NOW)
        self.assertTrue(result['source_stale'])
        self.assertEqual(len(result['hourly']), 2)
        self.assertEqual(result['hourly'][0]['temperature'], 0)

    def test_alphanumeric_quebec_identifier_is_supported(self):
        p = feature()
        p['id'] = p['properties']['identifier'] = 'qc-b9'
        model.validate_feature(p, 'qc-b9')
        catalogue = {'type': 'FeatureCollection', 'features': [p], 'numberMatched': 1}
        model.validate_catalogue(catalogue)
        self.assertEqual(model.locations(catalogue)[0]['id'], 'qc-b9')
        for identifier in ('qc-../b9', 'qc-B9', 'qc-b9/extra', 'zz-b9'):
            self.assertFalse(model.valid_id(identifier))

    def test_wrong_identity_is_rejected(self):
        p = feature()
        with self.assertRaises(client.PayloadError):
            model.validate_feature(p, 'bc-74')
        p['properties']['identifier'] = 'bc-74'
        with self.assertRaises(client.PayloadError):
            model.validate_feature(p)

    def test_catalogue_count_and_accent_insensitive_search(self):
        p = feature()
        p['properties']['name'] = bi('Quebec', 'Québec')
        catalogue = {'type': 'FeatureCollection', 'features': [p], 'numberMatched': 1}
        model.validate_catalogue(catalogue)
        self.assertEqual(model.locations(catalogue, 'fr', 'quebec')[0]['name'], 'Québec')
        catalogue['numberMatched'] = 2
        with self.assertRaises(client.PayloadError):
            model.validate_catalogue(catalogue)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 10000.0
        self.responses = []
        self.calls = []
        self.client = client.Client(self.tmp.name, self.fetch, lambda: self.now)

    def fetch(self, path, headers):
        self.calls.append((path, headers))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def get(self, **kwargs):
        return self.client.get(PATH, lambda p: model.validate_feature(p, 'on-118'), **kwargs)

    def prime(self):
        self.responses.append((200, {'ETag': 'version1', 'Last-Modified': 'Mon, 05 Jan 2026 12:00:00 GMT'}, json.dumps(feature()).encode()))
        return self.get()

    def test_ttl_boundary(self):
        self.prime()
        self.now += 899
        self.assertEqual(self.get()[3], 'cached')
        self.assertEqual(len(self.calls), 1)
        self.now += 1
        self.responses.append((200, {}, json.dumps(feature()).encode()))
        self.assertEqual(self.get()[3], 'fresh')
        self.assertEqual(len(self.calls), 2)

    def test_offline_stale_backoff_and_recovery(self):
        self.prime()
        self.now += 900
        self.responses.append(URLError('offline'))
        payload, fetched, stale, reason = self.get()
        self.assertEqual((fetched, stale, reason), (10000, True, 'offline'))
        self.assertEqual(self.get()[3], 'backoff')
        self.assertEqual(len(self.calls), 2)
        self.now += 60
        self.responses.append((200, {}, json.dumps(feature()).encode()))
        self.assertFalse(self.get()[2])

    def test_expired_stale_is_not_returned(self):
        self.prime()
        self.now += 21601
        self.responses.append(URLError('offline'))
        with self.assertRaises(client.WeatherError):
            self.get()

    def test_304_preserves_payload_and_renews_fetch_time(self):
        self.prime()
        self.now += 900
        self.responses.append(HTTPError('https://api.weather.gc.ca', 304, 'Not Modified', {'ETag': 'version1'}, None))
        result = self.get()
        self.assertEqual(result[0]['id'], 'on-118')
        self.assertEqual(result[1:], (self.now, False, 'fresh'))
        self.assertEqual(self.calls[-1][1]['If-None-Match'], 'version1')
        self.assertIn('If-Modified-Since', self.calls[-1][1])

    def test_304_without_cache_fails(self):
        self.responses.append((304, {}, b''))
        with self.assertRaises(client.WeatherError):
            self.get()

    def test_retry_after_limits_and_http_date(self):
        self.assertEqual(client.retry_delay('1', self.now), 60)
        self.assertEqual(client.retry_delay('999999', self.now), 86400)
        self.assertIsNone(client.retry_delay('bad', self.now))
        self.assertEqual(client.retry_delay('Thu, 01 Jan 1970 03:00:00 GMT', self.now), 800)
        self.prime()
        self.now += 900
        self.responses.append(HTTPError('https://api.weather.gc.ca', 429, 'Limited', {'Retry-After': '600'}, None))
        self.assertEqual(self.get()[3], 'offline')
        self.now += 599
        self.assertEqual(self.get()[3], 'backoff')
        self.assertEqual(len(self.calls), 2)

    def test_wrong_network_identity_keeps_good_cache(self):
        self.prime()
        self.now += 900
        bad = feature()
        bad['id'] = bad['properties']['identifier'] = 'bc-74'
        self.responses.append((200, {}, json.dumps(bad).encode()))
        result = self.get()
        self.assertEqual(result[0]['id'], 'on-118')
        self.assertTrue(result[2])

    def test_invalid_json_and_oversized_payload_fail_closed(self):
        for body in (b'not json', b'x' * (client.MAX_BYTES + 1)):
            with self.subTest(size=len(body)):
                self.now += 1000
                self.responses.append((200, {}, body))
                with self.assertRaises(client.WeatherError):
                    self.get()


class PendingHardeningTests(unittest.TestCase):
    """Review findings that must remain fixed."""
    def test_malformed_nested_objects_fail_safely(self):
        for key, value in [('currentConditions', []), ('currentConditions', 'bad'),
                           ('forecastGroup', ['bad']), ('forecastGroup', {'forecasts': [None]}),
                           ('hourlyForecastGroup', {'hourlyForecasts': [False]})]:
            with self.subTest(key=key, value=value):
                p = feature()
                p['properties'][key] = value
                try:
                    model.normalize(p, now=NOW)
                except client.PayloadError:
                    pass  # Explicit validation rejection is also safe.

    def test_bad_catalogue_entries_fail_safely(self):
        data = {'type': 'FeatureCollection', 'features': [None, 'bad', feature()]}
        try:
            model.validate_catalogue(data)
            entries = model.locations(data)
            self.assertEqual(len(entries), 1)
        except client.PayloadError:
            pass

    def test_fractional_icon_code_is_unknown(self):
        self.assertEqual(model.icon(32.9), 'na.png')

    def test_official_url_rejects_nonstandard_port(self):
        self.assertEqual(model.official_url('https://weather.gc.ca:8443/a', 'en'), '')

    def test_official_url_malformed_host_is_safe(self):
        self.assertEqual(model.official_url('https://[broken', 'en'), '')

    def test_catalogue_next_link_without_count_is_incomplete(self):
        data = {'type': 'FeatureCollection', 'features': [feature()],
                'links': [{'rel': 'next', 'href': 'https://api.weather.gc.ca/next'}]}
        with self.assertRaises(client.PayloadError):
            model.validate_catalogue(data)

    def test_corrupt_cache_metadata_is_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def fetch(path, headers):
                calls.append(path)
                return 200, {}, json.dumps(feature()).encode()
            instance = client.Client(directory, fetch, lambda: 10000)
            client.atomic_json(instance._file(PATH), {'schema': client.SCHEMA,
                'fetched_at': 'bad', 'payload': feature()})
            result = instance.get(PATH, model.validate_feature)
            self.assertEqual(result[3], 'fresh')
            self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
