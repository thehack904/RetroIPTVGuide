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
    _build_weather_payload,
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
        login(client, 'admin', 'adminpass')
        resp = client.get('/change_tuner')
        assert resp.status_code == 200
        assert b'ch_weather_location' in resp.data
        assert b'ch_weather_lat'      in resp.data
        assert b'ch_weather_lon'      in resp.data
        assert b'ch_weather_units'    in resp.data

    def test_zip_lookup_field_in_change_tuner_page(self, client):
        """Zip code lookup field and button should be present in the weather panel."""
        login(client, 'admin', 'adminpass')
        resp = client.get('/change_tuner')
        assert resp.status_code == 200
        assert b'vc-zip-input'      in resp.data
        assert b'vc-zip-lookup-btn' in resp.data
        assert b'zippopotam.us'     in resp.data

    def test_preview_weather_link_present(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/change_tuner')
        assert b'/weather' in resp.data

    def test_saved_location_prefills_in_page(self, client):
        save_weather_config({'lat': '25.77', 'lon': '-80.19',
                             'location_name': 'Miami, FL', 'units': 'F'})
        login(client, 'admin', 'adminpass')
        resp = client.get('/change_tuner')
        assert b'Miami, FL' in resp.data
        assert b'25.77' in resp.data
        assert b'-80.19' in resp.data

    def test_save_weather_via_change_tuner_post(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/change_tuner', data={
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
        client.post('/change_tuner', data={
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
        resp = client.post('/change_tuner', data={
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
        """Full round-trip: save via change_tuner → /api/weather returns it."""
        login(client, 'admin', 'adminpass')
        client.post('/change_tuner', data={
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
