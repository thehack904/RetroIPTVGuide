"""Tests for weather configuration helpers, enriched /api/weather shape, and /weather page."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import (
    app, init_db, init_tuners_db,
    get_weather_config, save_weather_config,
    _wmo_label, _wmo_icon, _to_night_icon, _wind_dir,
    _build_weather_payload, _fetch_nws_alerts,
    save_virtual_channel_settings,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    users_db = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE", users_db)
    monkeypatch.setattr(app_module, "TUNER_DB", tuners_db)
    init_db()
    init_tuners_db()
    from app import add_user
    add_user("testuser", "testpass")
    add_user("admin", "adminpass")
    yield users_db


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client, username="testuser", password="testpass"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


# ─── get/save_weather_config ──────────────────────────────────────────────────

class TestWeatherConfig:
    def test_defaults(self):
        cfg = get_weather_config()
        assert cfg['lat'] == ''
        assert cfg['lon'] == ''
        assert cfg['location_name'] == ''
        assert cfg['units'] == 'F'

    def test_save_and_reload(self):
        save_weather_config({'lat': '25.77', 'lon': '-80.19',
                             'location_name': 'Miami, FL', 'units': 'F'})
        cfg = get_weather_config()
        assert cfg['lat'] == '25.77'
        assert cfg['lon'] == '-80.19'
        assert cfg['location_name'] == 'Miami, FL'
        assert cfg['units'] == 'F'

    def test_celsius_units_saved(self):
        save_weather_config({'lat': '51.5', 'lon': '-0.12',
                             'location_name': 'London, UK', 'units': 'C'})
        assert get_weather_config()['units'] == 'C'

    def test_invalid_lat_raises(self):
        with pytest.raises(ValueError):
            save_weather_config({'lat': 'notanumber', 'lon': '-80.0',
                                 'location_name': '', 'units': 'F'})

    def test_invalid_lon_raises(self):
        with pytest.raises(ValueError):
            save_weather_config({'lat': '25.0', 'lon': 'abc',
                                 'location_name': '', 'units': 'F'})

    def test_invalid_units_raises(self):
        with pytest.raises(ValueError):
            save_weather_config({'lat': '', 'lon': '', 'location_name': '', 'units': 'K'})

    def test_empty_lat_lon_is_valid(self):
        save_weather_config({'lat': '', 'lon': '', 'location_name': 'Anywhere', 'units': 'F'})
        cfg = get_weather_config()
        assert cfg['lat'] == ''
        assert cfg['lon'] == ''


# ─── WMO helpers ─────────────────────────────────────────────────────────────

class TestWmoHelpers:
    def test_sunny_label(self):
        assert _wmo_label(0) == 'Sunny'

    def test_sunny_icon(self):
        assert _wmo_icon(0) == 'sunny'

    def test_thunderstorm_label(self):
        assert _wmo_label(95) == 'T-Storms'

    def test_thunderstorm_icon(self):
        assert _wmo_icon(95) == 'thunderstorm'

    def test_partly_cloudy(self):
        assert _wmo_icon(2) == 'partly_cloudy'

    def test_unknown_code_returns_cloudy(self):
        assert _wmo_icon(999) == 'cloudy'
        assert _wmo_label(999) == 'Unknown'

    def test_all_wmo_codes_have_label_and_icon(self):
        for code in [0, 1, 2, 3, 45, 48, 51, 53, 55, 61, 63, 65,
                     71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99]:
            assert isinstance(_wmo_label(code), str) and _wmo_label(code)
            assert isinstance(_wmo_icon(code), str) and _wmo_icon(code)


class TestWindDir:
    def test_north(self):
        assert _wind_dir(0) == 'N'

    def test_south(self):
        assert _wind_dir(180) == 'S'

    def test_east(self):
        assert _wind_dir(90) == 'E'

    def test_west(self):
        assert _wind_dir(270) == 'W'

    def test_invalid_returns_empty(self):
        assert _wind_dir('bad') == ''


class TestNightIcon:
    def test_sunny_becomes_partly_cloudy_night(self):
        assert _to_night_icon('sunny') == 'partly_cloudy_night'

    def test_partly_cloudy_becomes_partly_cloudy_night(self):
        assert _to_night_icon('partly_cloudy') == 'partly_cloudy_night'

    def test_cloudy_becomes_cloudy_night(self):
        assert _to_night_icon('cloudy') == 'cloudy_night'

    def test_thunderstorm_unchanged(self):
        assert _to_night_icon('thunderstorm') == 'thunderstorm'

    def test_rain_unchanged(self):
        assert _to_night_icon('rain') == 'rain'


# ─── _build_weather_payload (stub mode) ──────────────────────────────────────

class TestBuildWeatherPayloadStub:
    def setup_method(self):
        self.cfg = {'lat': '', 'lon': '', 'location_name': 'Test City', 'units': 'F'}

    def test_has_updated(self):
        p = _build_weather_payload(self.cfg)
        assert 'updated' in p and p['updated']

    def test_updated_is_iso_utc_string(self):
        """updated field must be an ISO 8601 UTC timestamp parseable by datetime.fromisoformat."""
        from datetime import datetime as _dt, timezone as _tz
        p = _build_weather_payload(self.cfg)
        dt = _dt.fromisoformat(p['updated'])
        assert dt.tzinfo is not None  # must carry timezone info
        # Normalise to UTC and verify it is not far from now
        dt_utc = dt.astimezone(_tz.utc)
        assert abs((_dt.now(_tz.utc) - dt_utc).total_seconds()) < 10

    def test_has_location(self):
        p = _build_weather_payload(self.cfg)
        assert p['location'] == 'Test City'

    def test_has_now_keys(self):
        p = _build_weather_payload(self.cfg)
        now = p['now']
        for key in ('temp', 'condition', 'humidity', 'wind', 'feels_like', 'icon'):
            assert key in now

    def test_has_today_list(self):
        p = _build_weather_payload(self.cfg)
        assert isinstance(p['today'], list)
        assert len(p['today']) == 3

    def test_today_periods_have_required_keys(self):
        p = _build_weather_payload(self.cfg)
        for period in p['today']:
            for key in ('label', 'temp', 'condition', 'icon'):
                assert key in period

    def test_has_extended_list(self):
        p = _build_weather_payload(self.cfg)
        assert isinstance(p['extended'], list)

    def test_has_ticker_list(self):
        p = _build_weather_payload(self.cfg)
        assert isinstance(p['ticker'], list)

    def test_has_forecast_list_for_compat(self):
        p = _build_weather_payload(self.cfg)
        assert isinstance(p['forecast'], list)

    def test_default_location_when_empty(self):
        cfg = {'lat': '', 'lon': '', 'location_name': '', 'units': 'F'}
        p = _build_weather_payload(cfg)
        assert p['location'] == 'Local Weather'


# ─── /weather page route ─────────────────────────────────────────────────────

class TestWeatherPage:
    def test_requires_login(self, client):
        resp = client.get('/weather')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/weather')
        assert resp.status_code == 200

    def test_page_contains_weather_title(self, client):
        login(client)
        resp = client.get('/weather')
        assert b'Weather' in resp.data

    def test_page_contains_ticker_element(self, client):
        login(client)
        resp = client.get('/weather')
        assert b'wx-ticker' in resp.data

    def test_page_contains_api_fetch(self, client):
        login(client)
        resp = client.get('/weather')
        assert b'/api/weather' in resp.data


# ─── /api/weather enriched shape ─────────────────────────────────────────────

class TestApiWeatherEnriched:
    def test_requires_login(self, client):
        resp = client.get('/api/weather')
        assert resp.status_code in (302, 401)

    def test_returns_200(self, client):
        login(client)
        resp = client.get('/api/weather')
        assert resp.status_code == 200

    def test_has_all_top_level_keys(self, client):
        login(client)
        data = client.get('/api/weather').get_json()
        for key in ('updated', 'location', 'now', 'today', 'extended', 'ticker', 'forecast'):
            assert key in data, f"Missing key: {key}"

    def test_now_has_enriched_fields(self, client):
        login(client)
        data = client.get('/api/weather').get_json()
        for key in ('temp', 'condition', 'humidity', 'wind', 'feels_like', 'icon'):
            assert key in data['now'], f"now missing key: {key}"

    def test_today_is_list_of_three(self, client):
        login(client)
        data = client.get('/api/weather').get_json()
        assert isinstance(data['today'], list)
        assert len(data['today']) == 3

    def test_today_periods_shape(self, client):
        login(client)
        data = client.get('/api/weather').get_json()
        for p in data['today']:
            for key in ('label', 'temp', 'condition', 'icon'):
                assert key in p

    def test_extended_is_list(self, client):
        login(client)
        data = client.get('/api/weather').get_json()
        assert isinstance(data['extended'], list)

    def test_ticker_is_list(self, client):
        login(client)
        data = client.get('/api/weather').get_json()
        assert isinstance(data['ticker'], list)

    def test_forecast_is_list(self, client):
        login(client)
        data = client.get('/api/weather').get_json()
        assert isinstance(data['forecast'], list)

    def test_location_uses_configured_name(self, client):
        save_weather_config({'lat': '', 'lon': '',
                             'location_name': 'Springfield, IL', 'units': 'F'})
        login(client)
        data = client.get('/api/weather').get_json()
        assert data['location'] == 'Springfield, IL'


# ─── Weather settings in change_tuner UI ─────────────────────────────────────

class TestChangeTunerWeatherSettings:
    """Weather config fields are surfaced in the Virtual Channel overlay panel."""

    def test_weather_fields_in_change_tuner_page(self, client):
        save_virtual_channel_settings({'virtual.weather': True})
        login(client, 'admin', 'adminpass')
        resp = client.get('/virtual_channels')
        assert resp.status_code == 200
        assert b'ch_weather_location' in resp.data
        assert b'ch_weather_lat'      in resp.data
        assert b'ch_weather_lon'      in resp.data
        assert b'ch_weather_units'    in resp.data

    def test_zip_lookup_field_in_change_tuner_page(self, client):
        """Zip code lookup field and button should be present in the weather panel."""
        login(client, 'admin', 'adminpass')
        resp = client.get('/virtual_channels')
        assert resp.status_code == 200
        assert b'vc-zip-input'      in resp.data
        assert b'vc-zip-lookup-btn' in resp.data
        assert b'zippopotam.us'     in resp.data

    def test_preview_weather_link_present(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/virtual_channels')
        assert b'/weather' in resp.data

    def test_saved_location_prefills_in_page(self, client):
        save_weather_config({'lat': '25.77', 'lon': '-80.19',
                             'location_name': 'Miami, FL', 'units': 'F'})
        save_virtual_channel_settings({'virtual.weather': True})
        login(client, 'admin', 'adminpass')
        resp = client.get('/virtual_channels')
        assert b'Miami, FL' in resp.data
        assert b'25.77' in resp.data
        assert b'-80.19' in resp.data

    def test_save_weather_via_change_tuner_post(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '#ffffff',
            'ch_bg_color': '#000000',
            'ch_test_text': '',
            'ch_weather_location': 'Denver, CO',
            'ch_weather_lat': '39.73',
            'ch_weather_lon': '-104.99',
            'ch_weather_units': 'F',
        }, follow_redirects=True)
        assert resp.status_code == 200
        cfg = get_weather_config()
        assert cfg['location_name'] == 'Denver, CO'
        assert cfg['lat'] == '39.73'
        assert cfg['lon'] == '-104.99'
        assert cfg['units'] == 'F'

    def test_save_celsius_units_via_change_tuner(self, client):
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '',
            'ch_bg_color': '',
            'ch_test_text': '',
            'ch_weather_location': 'London, UK',
            'ch_weather_lat': '51.5',
            'ch_weather_lon': '-0.12',
            'ch_weather_units': 'C',
        }, follow_redirects=True)
        cfg = get_weather_config()
        assert cfg['units'] == 'C'
        assert cfg['location_name'] == 'London, UK'

    def test_invalid_lat_shows_warning(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '',
            'ch_bg_color': '',
            'ch_test_text': '',
            'ch_weather_location': 'Test',
            'ch_weather_lat': 'not-a-number',
            'ch_weather_lon': '-80.0',
            'ch_weather_units': 'F',
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Server should flash a warning for invalid lat
        assert b'Invalid' in resp.data or b'invalid' in resp.data

    def test_api_weather_reflects_saved_location_name(self, client):
        """Full round-trip: save via virtual_channels → /api/weather returns it."""
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '',
            'ch_bg_color': '',
            'ch_test_text': '',
            'ch_weather_location': 'Austin, TX',
            'ch_weather_lat': '',
            'ch_weather_lon': '',
            'ch_weather_units': 'F',
        }, follow_redirects=True)
        data = client.get('/api/weather').get_json()
        assert data['location'] == 'Austin, TX'


# ─── _fetch_nws_alerts ────────────────────────────────────────────────────────

class TestFetchNwsAlerts:
    def test_returns_list_on_network_error(self, monkeypatch):
        """_fetch_nws_alerts returns [] (not raises) when the NWS API is unavailable."""
        import requests as req_mod

        def _fail(*a, **kw):
            raise req_mod.exceptions.ConnectionError("mocked failure")

        monkeypatch.setattr(req_mod, "get", _fail)
        result = _fetch_nws_alerts('25.77', '-80.19')
        assert result == []

    def test_returns_list_on_bad_json(self, monkeypatch):
        """_fetch_nws_alerts returns [] when the response body is not valid JSON."""
        import requests as req_mod

        class _BadResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): raise ValueError("bad json")

        monkeypatch.setattr(req_mod, "get", lambda *a, **kw: _BadResp())
        result = _fetch_nws_alerts('25.77', '-80.19')
        assert result == []

    def test_parses_alert_fields(self, monkeypatch):
        """_fetch_nws_alerts correctly maps NWS GeoJSON feature properties."""
        import requests as req_mod

        sample = {
            "features": [
                {
                    "properties": {
                        "event":       "Winter Storm Warning",
                        "headline":    "Winter Storm Warning until Monday",
                        "description": "Heavy snow expected.",
                        "severity":    "Severe",
                        "urgency":     "Expected",
                        "certainty":   "Likely",
                        "onset":       "2026-01-10T06:00:00-05:00",
                        "expires":     "2026-01-11T06:00:00-05:00",
                    }
                }
            ]
        }

        class _OkResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return sample

        monkeypatch.setattr(req_mod, "get", lambda *a, **kw: _OkResp())
        result = _fetch_nws_alerts('40.71', '-74.00')
        assert len(result) == 1
        a = result[0]
        assert a['event']       == 'Winter Storm Warning'
        assert a['headline']    == 'Winter Storm Warning until Monday'
        assert a['severity']    == 'Severe'
        assert a['urgency']     == 'Expected'
        assert a['certainty']   == 'Likely'
        assert a['expires']     == '2026-01-11T06:00:00-05:00'

    def test_empty_features_returns_empty_list(self, monkeypatch):
        import requests as req_mod

        class _OkResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"features": []}

        monkeypatch.setattr(req_mod, "get", lambda *a, **kw: _OkResp())
        assert _fetch_nws_alerts('51.5', '-0.12') == []

    def test_missing_features_key_returns_empty_list(self, monkeypatch):
        import requests as req_mod

        class _OkResp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"type": "FeatureCollection"}

        monkeypatch.setattr(req_mod, "get", lambda *a, **kw: _OkResp())
        assert _fetch_nws_alerts('25.77', '-80.19') == []


# ─── _build_weather_payload – alerts key ─────────────────────────────────────

class TestBuildWeatherPayloadAlerts:
    def test_stub_payload_has_alerts_key(self):
        """Stub (no lat/lon) payload must include an 'alerts' key."""
        cfg = {'lat': '', 'lon': '', 'location_name': 'Anywhere', 'units': 'F'}
        p = _build_weather_payload(cfg)
        assert 'alerts' in p
        assert isinstance(p['alerts'], list)

    def test_stub_alerts_is_empty(self):
        cfg = {'lat': '', 'lon': '', 'location_name': 'Anywhere', 'units': 'F'}
        p = _build_weather_payload(cfg)
        assert p['alerts'] == []

    def test_alerts_from_nws_populate_ticker(self, monkeypatch):
        """When NWS returns alerts, their headlines become the ticker entries."""
        import requests as req_mod

        nws_sample = {
            "features": [
                {"properties": {
                    "event": "Flood Warning",
                    "headline": "Flood Warning in effect until Tuesday",
                    "description": "Significant flooding expected.",
                    "severity": "Severe", "urgency": "Immediate",
                    "certainty": "Observed", "onset": "", "expires": "",
                }}
            ]
        }
        open_meteo_sample = {
            "current": {
                "temperature_2m": 72, "apparent_temperature": 70,
                "relative_humidity_2m": 60, "weather_code": 0,
                "wind_speed_10m": 5, "wind_direction_10m": 90,
            },
            "current_units": {"wind_speed_10m": "mph"},
            "hourly": {"time": [], "temperature_2m": [], "weather_code": []},
            "daily": {
                "time": [], "temperature_2m_max": [], "temperature_2m_min": [],
                "weather_code": [], "sunrise": [], "sunset": [],
            },
        }

        call_log = []

        def _mock_get(url, *a, **kw):
            call_log.append(url)

            class _Resp:
                status_code = 200
                def raise_for_status(self): pass
                def json(self_):
                    if 'open-meteo' in url:
                        return open_meteo_sample
                    return nws_sample

            return _Resp()

        monkeypatch.setattr(req_mod, "get", _mock_get)
        cfg = {'lat': '25.77', 'lon': '-80.19', 'location_name': 'Miami', 'units': 'F'}
        p = _build_weather_payload(cfg)

        assert 'alerts' in p
        assert len(p['alerts']) == 1
        assert p['alerts'][0]['event'] == 'Flood Warning'
        # Ticker should use the NWS headline
        assert any('Flood Warning' in t for t in p['ticker'])

    def test_wmo_ticker_used_when_no_nws_alerts(self, monkeypatch):
        """When NWS returns no alerts and WMO code is thunderstorm, ticker still fires."""
        import requests as req_mod

        open_meteo_sample = {
            "current": {
                "temperature_2m": 78, "apparent_temperature": 76,
                "relative_humidity_2m": 80, "weather_code": 95,
                "wind_speed_10m": 15, "wind_direction_10m": 180,
            },
            "current_units": {"wind_speed_10m": "mph"},
            "hourly": {"time": [], "temperature_2m": [], "weather_code": []},
            "daily": {
                "time": [], "temperature_2m_max": [], "temperature_2m_min": [],
                "weather_code": [], "sunrise": [], "sunset": [],
            },
        }

        def _mock_get(url, *a, **kw):
            class _Resp:
                status_code = 200
                def raise_for_status(self): pass
                def json(self_):
                    if 'open-meteo' in url:
                        return open_meteo_sample
                    return {"features": []}
            return _Resp()

        monkeypatch.setattr(req_mod, "get", _mock_get)
        cfg = {'lat': '25.77', 'lon': '-80.19', 'location_name': 'Miami', 'units': 'F'}
        p = _build_weather_payload(cfg)
        assert p['alerts'] == []
        assert any('Thunderstorm' in t or 'thunderstorm' in t.lower() for t in p['ticker'])


# ─── /api/weather – alerts key present ───────────────────────────────────────

class TestApiWeatherAlertsKey:
    def test_api_weather_has_alerts_key(self, client):
        login(client)
        data = client.get('/api/weather').get_json()
        assert 'alerts' in data
        assert isinstance(data['alerts'], list)


# ─── Animated Background Override ────────────────────────────────────────────

class TestWeatherBgConditionOverride:
    """Tests for bg_condition_override config key and /api/weather/bg_override endpoint."""

    def test_default_bg_condition_override_is_empty(self):
        cfg = get_weather_config()
        assert cfg.get('bg_condition_override', '') == ''

    def test_save_valid_condition(self):
        save_weather_config({'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
                             'bg_condition_override': 'rain'})
        assert get_weather_config()['bg_condition_override'] == 'rain'

    def test_save_empty_condition_clears_override(self):
        save_weather_config({'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
                             'bg_condition_override': 'snow'})
        save_weather_config({'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
                             'bg_condition_override': ''})
        assert get_weather_config()['bg_condition_override'] == ''

    def test_invalid_bg_condition_raises(self):
        with pytest.raises(ValueError):
            save_weather_config({'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
                                 'bg_condition_override': 'rainbow'})

    def test_all_valid_conditions_accepted(self):
        valid = ['', 'sunny', 'partly_cloudy', 'cloudy', 'rain', 'drizzle',
                 'showers', 'snow', 'thunderstorm', 'foggy', 'windy']
        for cond in valid:
            save_weather_config({'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
                                 'bg_condition_override': cond})
            assert get_weather_config()['bg_condition_override'] == cond

    def test_payload_includes_bg_condition(self):
        cfg = {'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
               'bg_condition_override': ''}
        p = _build_weather_payload(cfg)
        assert 'bg_condition' in p
        assert 'bg_condition_override' in p

    def test_override_sets_bg_condition_in_payload(self):
        cfg = {'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
               'bg_condition_override': 'snow'}
        p = _build_weather_payload(cfg)
        assert p['bg_condition'] == 'snow'
        assert p['bg_condition_override'] == 'snow'

    def test_no_override_uses_default_condition(self):
        cfg = {'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
               'bg_condition_override': ''}
        p = _build_weather_payload(cfg)
        # Stub payload defaults to 'cloudy' icon, so bg_condition should be 'cloudy'
        assert p['bg_condition'] == 'cloudy'
        assert p['bg_condition_override'] == ''


class TestBgOverrideEndpoint:
    """Tests for the /api/weather/bg_override AJAX endpoint."""

    def test_get_returns_empty_by_default(self, client):
        login(client)
        r = client.get('/api/weather/bg_override')
        assert r.status_code == 200
        data = r.get_json()
        assert data['condition'] == ''

    def test_post_sets_condition(self, client):
        login(client)
        r = client.post('/api/weather/bg_override',
                        json={'condition': 'thunderstorm'},
                        content_type='application/json')
        assert r.status_code == 200
        data = r.get_json()
        assert data['ok'] is True
        assert data['condition'] == 'thunderstorm'

    def test_post_persists_condition(self, client):
        login(client)
        client.post('/api/weather/bg_override',
                    json={'condition': 'rain'},
                    content_type='application/json')
        r = client.get('/api/weather/bg_override')
        assert r.get_json()['condition'] == 'rain'

    def test_post_auto_clears_override(self, client):
        login(client)
        client.post('/api/weather/bg_override',
                    json={'condition': 'snow'},
                    content_type='application/json')
        client.post('/api/weather/bg_override',
                    json={'condition': 'auto'},
                    content_type='application/json')
        r = client.get('/api/weather/bg_override')
        assert r.get_json()['condition'] == ''

    def test_post_empty_string_clears_override(self, client):
        login(client)
        client.post('/api/weather/bg_override',
                    json={'condition': 'sunny'},
                    content_type='application/json')
        client.post('/api/weather/bg_override',
                    json={'condition': ''},
                    content_type='application/json')
        r = client.get('/api/weather/bg_override')
        assert r.get_json()['condition'] == ''

    def test_post_invalid_condition_returns_400(self, client):
        login(client)
        r = client.post('/api/weather/bg_override',
                        json={'condition': 'tornado'},
                        content_type='application/json')
        assert r.status_code == 400
        assert r.get_json()['ok'] is False

    def test_delete_clears_override(self, client):
        login(client)
        client.post('/api/weather/bg_override',
                    json={'condition': 'foggy'},
                    content_type='application/json')
        r = client.delete('/api/weather/bg_override')
        assert r.status_code == 200
        assert r.get_json()['condition'] == ''
        r2 = client.get('/api/weather/bg_override')
        assert r2.get_json()['condition'] == ''

    def test_requires_login_get(self, client):
        r = client.get('/api/weather/bg_override')
        assert r.status_code in (302, 401)

    def test_requires_login_post(self, client):
        r = client.post('/api/weather/bg_override',
                        json={'condition': 'snow'},
                        content_type='application/json')
        assert r.status_code in (302, 401)

    def test_api_weather_reflects_override(self, client):
        """After setting override, /api/weather returns that bg_condition."""
        login(client)
        client.post('/api/weather/bg_override',
                    json={'condition': 'windy'},
                    content_type='application/json')
        data = client.get('/api/weather').get_json()
        assert data['bg_condition'] == 'windy'
        assert data['bg_condition_override'] == 'windy'
