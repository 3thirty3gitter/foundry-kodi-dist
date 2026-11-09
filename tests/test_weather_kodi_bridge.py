"""Offline property and application-boundary tests; this is not a Kodi runtime test."""
import importlib.util
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch
from test_weather_client_model import LIB, NOW, feature, model
from foundry_weather_test_lib import client, kodi_bridge as bridge

P = bridge.PREFIX


class Window:
    def __init__(self):
        self.properties = {}

    def setProperty(self, key, value):
        self.properties[key] = value

    def getProperty(self, key):
        return self.properties.get(key, '')

    def clearProperty(self, key):
        self.properties.pop(key, None)


class BridgeTests(unittest.TestCase):
    def build(self, payload=None, **kwargs):
        return bridge.build_properties(model.normalize(payload or feature(), now=NOW), NOW.timestamp(), **kwargs)

    def test_zero_and_missing_fields_are_not_confused(self):
        values = self.build()
        self.assertEqual(values['Current.Temperature'], '0')
        self.assertEqual(values[P+'Temperature'], '0°C')
        self.assertEqual(values['Current.DewPoint'], '')
        self.assertEqual(values[P+'HasCurrent'], 'true')
        p = feature()
        p['properties']['currentConditions'] = {}
        values = self.build(p)
        self.assertEqual(values[P+'HasCurrent'], 'false')
        self.assertEqual(values[P+'Temperature'], '')
        self.assertEqual(values['Current.IsFetched'], 'false')

    def test_fahrenheit_is_display_only(self):
        values = self.build(units='°F')
        self.assertEqual(values['Current.Temperature'], '0')
        self.assertEqual(values[P+'Temperature'], '32°F')
        self.assertEqual(values['Current.FeelsLike'], '-7')
        self.assertEqual(values[P+'FeelsLike'], '19°F')

    def test_stale_alert_status_is_explicit(self):
        values = self.build(stale=True)
        self.assertEqual(values[P+'Stale'], 'true')
        self.assertEqual(values[P+'Status'], 'stale')
        self.assertEqual(values[P+'AlertStatus'], 'unverified')
        self.assertEqual(values[P+'AlertsAreComplete'], 'false')
        self.assertEqual(values[P+'TimeBasis'], 'device')

    def test_publish_clears_shrunken_arrays_but_keeps_request_token(self):
        window = Window()
        old = ['Current.FanartCode','Day6.FanartCode','WeatherProviderLogo',
               'Hourly.24.Temperature', P+'Hour.24.Temperature', P+'Day.7.High', P+'Alert.20.Url']
        for key in old:
            window.setProperty(key, 'obsolete')
        window.setProperty(P+'RequestToken', 'request1')
        window.setProperty('Location1', 'Ottawa, ON')
        bridge.publish(window, self.build())
        for key in old:
            self.assertNotEqual(window.getProperty(key), 'obsolete')
        self.assertEqual(window.getProperty(P+'RequestToken'), 'request1')
        self.assertEqual(window.getProperty('Location1'), 'Ottawa, ON')
        self.assertTrue(all(isinstance(v, str) for v in window.properties.values()))

    def test_clear_removes_every_published_field(self):
        window = Window()
        bridge.publish(window, self.build())
        bridge.clear_properties(window)
        self.assertEqual(window.properties, {})

    def test_time_format_and_invalid_timestamp(self):
        self.assertEqual(bridge.local_time('invalid'), '')
        result = bridge.local_time('2026-01-05T12:34:56Z', True, '%H:%M:%S')
        self.assertEqual(result.count(':'), 1)
        self.assertEqual(len(result), 5)


class DefaultBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.window = Window()
        self.settings = {'language': 'en', 'location1_id': 'on-118', 'location1_label': 'Ottawa, ON'}
        self.dialog = Mock()
        self.provider = 'weather.foundry.canada'
        self.current_location = 1
        def rpc(raw):
            request = json.loads(raw)
            self.assertEqual(request['params']['setting'], 'weather.currentlocation')
            if request['method'] == 'Settings.SetSettingValue':
                self.current_location = request['params']['value']
                return json.dumps({'result': True})
            self.assertEqual(request['method'], 'Settings.GetSettingValue')
            return json.dumps({'result': {'value': self.current_location}})
        addon = Mock()
        addon.getSetting.side_effect = lambda key: self.settings.get(key, '')
        addon.setSetting.side_effect = lambda key, value: self.settings.__setitem__(key, value)
        xbmc = types.SimpleNamespace(ISO_639_1=0, LOGWARNING=2, getLanguage=lambda _: 'en',
            getInfoLabel=lambda key: self.provider if key == 'Weather.Plugin' else '',
            getRegion=lambda key: '°C' if key == 'tempunit' else '%H:%M', log=Mock(), executebuiltin=Mock(),
            executeJSONRPC=Mock(side_effect=rpc))
        modules = {'xbmc': xbmc, 'xbmcaddon': types.SimpleNamespace(Addon=lambda: addon),
                   'xbmcgui': types.SimpleNamespace(Window=lambda _: self.window, Dialog=lambda: self.dialog),
                   'xbmcvfs': types.SimpleNamespace(translatePath=lambda x: x),
                   'resources': types.ModuleType('resources'),
                   'resources.lib': sys.modules['foundry_weather_test_lib'],
                   'resources.lib.client': client, 'resources.lib.model': model,
                   'resources.lib.kodi_bridge': bridge}
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location('foundry_boundary_test', LIB.parents[1] / 'default.py')
            self.app = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.app)
        self.app.normalize = lambda payload, language, now: model.normalize(payload, language, NOW)

    def test_current_failure_clears_previous_data(self):
        self.window.setProperty(P+'Temperature', '20°C')
        self.window.setProperty(P+'Alert.1.Headline', 'Old warning')
        self.app.client = lambda: Mock(get=Mock(side_effect=client.WeatherError('offline')))
        self.app.update(1)
        self.assertEqual(self.window.getProperty(P+'Status'), 'unavailable')
        self.assertEqual(self.window.getProperty(P+'HasCurrent'), 'false')
        self.assertEqual(self.window.getProperty(P+'AlertStatus'), 'unknown')
        self.assertEqual(self.window.getProperty(P+'Temperature'), '')
        self.assertEqual(self.window.getProperty(P+'Alert.1.Headline'), '')

    def test_no_location_clears_old_temperature(self):
        self.settings.clear()
        self.window.setProperty(P+'Temperature', '20°C')
        self.app.update(1)
        self.assertEqual(self.window.getProperty(P+'Status'), 'needs_location')
        self.assertEqual(self.window.getProperty(P+'HasCurrent'), 'false')
        self.assertEqual(self.window.getProperty(P+'Temperature'), '')

    def test_superseded_success_does_not_publish(self):
        def fetch(*args):
            self.window.setProperty(P+'RequestToken', 'newer')
            self.window.setProperty(P+'Temperature', 'newer-temperature')
            return feature(), NOW.timestamp(), False, 'fresh'
        self.app.client = lambda: Mock(get=fetch)
        self.app.update(1)
        self.assertEqual(self.window.getProperty(P+'Temperature'), 'newer-temperature')
        self.assertEqual(self.window.getProperty(P+'RequestToken'), 'newer')

    def test_superseded_failure_does_not_clear(self):
        def fetch(*args):
            self.window.setProperty(P+'RequestToken', 'newer')
            self.window.setProperty(P+'Temperature', 'newer-temperature')
            raise client.WeatherError('old request failed')
        self.app.client = lambda: Mock(get=fetch)
        self.app.update(1)
        self.assertEqual(self.window.getProperty(P+'Temperature'), 'newer-temperature')
        self.assertEqual(self.window.getProperty(P+'RequestToken'), 'newer')

    def test_current_success_publishes(self):
        self.app.client = lambda: Mock(get=lambda *args: (feature(), NOW.timestamp(), False, 'fresh'))
        self.app.update(1)
        self.assertEqual(self.window.getProperty(P+'Temperature'), '0°C')
        self.assertEqual(self.window.getProperty(P+'Status'), 'fresh')

    def test_home_refresh_preserves_native_selected_city(self):
        self.settings.update(location2_id='bc-74', location2_label='Vancouver, BC')
        self.current_location = 2
        self.app.update = Mock()
        self.app.refresh_current()
        self.app.update.assert_called_once_with(2)
        self.assertEqual(self.current_location, 2)
        self.assertTrue(all(json.loads(c.args[0])['method'] == 'Settings.GetSettingValue'
                            for c in self.app.xbmc.executeJSONRPC.call_args_list))

    def test_home_next_city_shares_native_index_and_wraps(self):
        self.settings.update(location2_id='bc-74', location2_label='Vancouver, BC')
        self.app.update = Mock()
        self.app.refresh_current(next_location=True)
        self.assertEqual(self.current_location, 2)
        self.app.update.assert_called_with(2)
        self.app.refresh_current(next_location=True)
        self.assertEqual(self.current_location, 1)
        self.app.update.assert_called_with(1)

    def test_home_refresh_clamps_removed_native_city(self):
        self.current_location = 3
        self.app.update = Mock()
        self.app.refresh_current()
        self.assertEqual(self.current_location, 1)
        self.app.update.assert_called_once_with(1)

    def test_inactive_home_actions_never_read_or_mutate_native_setting(self):
        self.provider = 'weather.other'
        self.app.update = Mock()
        self.app.refresh_current()
        self.app.refresh_current(next_location=True)
        self.app.xbmc.executeJSONRPC.assert_not_called()
        self.app.update.assert_not_called()

    def test_unavailable_location_setting_does_not_guess_city(self):
        self.app.xbmc.executeJSONRPC.side_effect = lambda _: '{"error":{"code":-32602}}'
        self.app.update = Mock()
        self.app.refresh_current()
        self.app.update.assert_not_called()

    def test_failed_location_change_does_not_fetch_wrong_city(self):
        self.settings.update(location2_id='bc-74', location2_label='Vancouver, BC')
        self.app.xbmc.executeJSONRPC.side_effect = ['{"result":{"value":1}}', '{"result":false}']
        self.app.update = Mock()
        self.app.refresh_current(next_location=True)
        self.app.update.assert_not_called()

    def test_native_city_change_during_fetch_does_not_publish(self):
        def fetch(*args):
            self.current_location = 2
            self.window.setProperty(P+'Temperature', 'new city pending')
            return feature(), NOW.timestamp(), False, 'fresh'
        self.app.client = lambda: Mock(get=fetch)
        self.app.update(1)
        self.assertEqual(self.window.getProperty(P+'Temperature'), 'new city pending')

    def test_native_city_change_during_failed_fetch_does_not_clear(self):
        def fetch(*args):
            self.current_location = 2
            self.window.setProperty(P+'Temperature', 'new city pending')
            raise client.WeatherError('old request')
        self.app.client = lambda: Mock(get=fetch)
        self.app.update(1)
        self.assertEqual(self.window.getProperty(P+'Temperature'), 'new city pending')

    def test_obsolete_native_job_does_not_cancel_current_request(self):
        self.settings.update(location2_id='bc-74', location2_label='Vancouver, BC')
        self.current_location = 2
        self.window.setProperty(P+'RequestToken', 'new city pending')
        self.app.client = Mock(side_effect=AssertionError('No stale slot fetch'))
        self.app.update(1)
        self.app.client.assert_not_called()
        self.assertEqual(self.window.getProperty(P+'RequestToken'), 'new city pending')

    def test_location_reset_supersedes_older_success_or_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                self.settings.update(location1_id='on-118', location1_label='Ottawa, ON')
                def fetch(*args):
                    self.settings.clear()
                    self.app.update(1)
                    if failure:raise client.WeatherError('old request')
                    return feature(), NOW.timestamp(), False, 'fresh'
                self.app.client = lambda: Mock(get=fetch)
                self.app.update(1)
                self.assertEqual(self.window.getProperty(P+'Status'), 'needs_location')
                self.assertEqual(self.window.getProperty(P+'Temperature'), '')

    def test_changed_location_id_supersedes_older_success_or_failure(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                self.settings.update(location1_id='on-118', location1_label='Ottawa, ON')
                def fetch(*args):
                    self.settings.update(location1_id='bc-74', location1_label='Vancouver, BC')
                    self.window.setProperty(P+'Temperature', 'replacement pending')
                    if failure:raise client.WeatherError('old request')
                    return feature(), NOW.timestamp(), False, 'fresh'
                self.app.client = lambda: Mock(get=fetch)
                self.app.update(1)
                self.assertEqual(self.window.getProperty(P+'Temperature'), 'replacement pending')

    def test_inactive_provider_does_not_fetch_or_touch_shared_state(self):
        self.provider = 'weather.other'
        self.window.setProperty('Current.Temperature', '17')
        self.window.setProperty('Location1', 'Other city')
        before = dict(self.window.properties)
        self.app.client = Mock(side_effect=AssertionError('No inactive fetch'))
        self.app.update(1)
        self.assertEqual(self.window.properties, before)
        self.app.client.assert_not_called()

    def test_provider_change_during_fetch_does_not_publish(self):
        def fetch(*args):
            self.provider = 'weather.other'
            self.window.setProperty('Current.Temperature', '17')
            return feature(), NOW.timestamp(), False, 'fresh'
        self.app.client = lambda: Mock(get=fetch)
        self.app.update(1)
        self.assertEqual(self.window.getProperty('Current.Temperature'), '17')
        self.assertEqual(self.window.getProperty(P+'Temperature'), '')

    def test_provider_change_during_failed_fetch_does_not_clear(self):
        def fetch(*args):
            self.provider = 'weather.other'
            self.window.setProperty('Current.Temperature', '17')
            raise client.WeatherError('offline')
        self.app.client = lambda: Mock(get=fetch)
        self.app.update(1)
        self.assertEqual(self.window.getProperty('Current.Temperature'), '17')

    def test_configuring_inactive_provider_preserves_native_locations(self):
        self.provider = 'weather.other'
        self.window.setProperty('Locations', '2')
        self.window.setProperty('Location1', 'Other city')
        self.dialog.input.return_value = 'Ottawa'
        self.dialog.select.return_value = 0
        self.app.client = lambda: Mock(get=lambda *a, **k: ({}, 0, False, 'fresh'))
        self.app.locations = lambda *a: [{'id': 'on-118', 'label': 'Ottawa, ON'}]
        self.app.choose_location(1)
        self.assertEqual(self.settings['location1_id'], 'on-118')
        self.assertEqual(self.window.getProperty('Locations'), '2')
        self.assertEqual(self.window.getProperty('Location1'), 'Other city')
        self.app.xbmc.executebuiltin.assert_not_called()

    def test_forecast_dialog_uses_snapshot_without_network(self):
        self.window.setProperty(P+'Location','Ottawa, ON')
        self.window.setProperty(P+'Day.1.Title','Today')
        self.window.setProperty(P+'Day.1.Range','High 0°C')
        self.window.setProperty(P+'Day.1.Summary','Snow. Tonight: Clear.')
        self.app.client=Mock(side_effect=AssertionError('No fetch on display'))
        self.app.show_forecast()
        shown=self.dialog.textviewer.call_args.args[1]
        self.assertIn('High 0°C',shown)
        self.assertIn('Tonight: Clear.',shown)
        self.app.client.assert_not_called()

    def test_empty_forecast_is_unavailable_not_zero(self):
        self.app.show_forecast()
        shown=self.dialog.textviewer.call_args.args[1]
        self.assertIn('Forecast unavailable',shown)
        self.assertNotIn('0°C',shown)

    def test_unknown_advisory_status_is_explicit(self):
        self.window.setProperty(P+'AlertStatus','unknown')
        self.app.show_alerts()
        self.assertIn('Current advisory status is unavailable',self.dialog.textviewer.call_args.args[1])

    def test_cancel_location_search_does_not_fetch(self):
        self.dialog.input.return_value=''
        self.app.client=Mock(side_effect=AssertionError('No fetch on cancel'))
        self.app.choose_location(1)
        self.app.client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
