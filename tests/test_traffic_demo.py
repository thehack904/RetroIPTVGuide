"""Tests for Traffic Demo Mode: DB helpers, simulation engine, and API endpoints."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import (
    app, init_db, init_tuners_db,
    get_traffic_demo_config, save_traffic_demo_config,
    get_traffic_demo_cities, save_traffic_demo_city,
    set_all_traffic_demo_cities_enabled, pick_random_traffic_demo_pack,
    _get_congestion_distribution, _build_traffic_demo_payload,
    _TRAFFIC_DEMO_CITIES_SEED, _TRAFFIC_DEMO_CACHE,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE",  users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",  tuners_db)
    # Also clear the module-level demo cache between tests
    monkeypatch.setattr(app_module, "_TRAFFIC_DEMO_CACHE", {})
    init_db()
    init_tuners_db()
    from app import add_user
    add_user("testuser", "testpass")
    add_user("admin",    "adminpass")
    yield users_db


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client, username="testuser", password="testpass"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


# ─── City seed data ───────────────────────────────────────────────────────────

class TestCitySeedData:
    def test_seed_has_ten_cities(self):
        assert len(_TRAFFIC_DEMO_CITIES_SEED) == 10

    def test_all_seed_cities_over_one_million(self):
        for city in _TRAFFIC_DEMO_CITIES_SEED:
            assert city['population'] > 1_000_000, (
                f"{city['name']}, {city['state']} population {city['population']} is not > 1M"
            )

    def test_seed_cities_have_required_keys(self):
        required = {'name', 'state', 'lat', 'lon', 'population'}
        for city in _TRAFFIC_DEMO_CITIES_SEED:
            assert required.issubset(city.keys()), f"Missing keys in {city}"

    def test_seed_lat_lon_are_floats(self):
        for city in _TRAFFIC_DEMO_CITIES_SEED:
            assert isinstance(city['lat'], float)
            assert isinstance(city['lon'], float)


# ─── DB init — table creation and seeding ─────────────────────────────────────

class TestTrafficDemoDb:
    def test_cities_table_seeded_on_init(self):
        cities = get_traffic_demo_cities()
        assert len(cities) == len(_TRAFFIC_DEMO_CITIES_SEED)

    def test_seeded_cities_are_enabled_by_default(self):
        for city in get_traffic_demo_cities():
            assert city['enabled'] is True

    def test_seeded_cities_have_weight_one(self):
        for city in get_traffic_demo_cities():
            assert city['weight'] == 1

    def test_cities_have_expected_fields(self):
        required = {'id', 'name', 'state', 'lat', 'lon', 'population', 'enabled', 'weight'}
        for city in get_traffic_demo_cities():
            assert required.issubset(city.keys())


# ─── get/save_traffic_demo_config ─────────────────────────────────────────────

class TestTrafficDemoConfig:
    def test_defaults(self):
        cfg = get_traffic_demo_config()
        assert cfg['mode']             == 'admin_rotation'
        assert cfg['pack_size']        == '10'
        assert cfg['rotation_seconds'] == '120'

    def test_save_and_reload(self):
        save_traffic_demo_config({'mode': 'random_pack', 'pack_size': '5',
                                  'rotation_seconds': '60'})
        cfg = get_traffic_demo_config()
        assert cfg['mode']             == 'random_pack'
        assert cfg['pack_size']        == '5'
        assert cfg['rotation_seconds'] == '60'

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            save_traffic_demo_config({'mode': 'invalid_mode', 'pack_size': '10',
                                      'rotation_seconds': '120'})

    def test_pack_size_too_low_raises(self):
        with pytest.raises(ValueError):
            save_traffic_demo_config({'mode': 'admin_rotation', 'pack_size': '0',
                                      'rotation_seconds': '120'})

    def test_pack_size_too_high_raises(self):
        with pytest.raises(ValueError):
            save_traffic_demo_config({'mode': 'admin_rotation', 'pack_size': '100',
                                      'rotation_seconds': '120'})

    def test_rotation_too_low_raises(self):
        with pytest.raises(ValueError):
            save_traffic_demo_config({'mode': 'admin_rotation', 'pack_size': '10',
                                      'rotation_seconds': '10'})

    def test_rotation_too_high_raises(self):
        with pytest.raises(ValueError):
            save_traffic_demo_config({'mode': 'admin_rotation', 'pack_size': '10',
                                      'rotation_seconds': '9999'})


# ─── save_traffic_demo_city / bulk helpers ───────────────────────────────────

class TestCityHelpers:
    def test_save_city_disable(self):
        cities = get_traffic_demo_cities()
        city_id = cities[0]['id']
        save_traffic_demo_city(city_id, False)
        updated = [c for c in get_traffic_demo_cities() if c['id'] == city_id][0]
        assert updated['enabled'] is False

    def test_save_city_weight(self):
        cities = get_traffic_demo_cities()
        city_id = cities[0]['id']
        save_traffic_demo_city(city_id, True, weight=3)
        updated = [c for c in get_traffic_demo_cities() if c['id'] == city_id][0]
        assert updated['weight'] == 3

    def test_enable_all(self):
        # First disable all, then re-enable
        set_all_traffic_demo_cities_enabled(False)
        assert all(not c['enabled'] for c in get_traffic_demo_cities())
        set_all_traffic_demo_cities_enabled(True)
        assert all(c['enabled'] for c in get_traffic_demo_cities())

    def test_disable_all(self):
        set_all_traffic_demo_cities_enabled(False)
        assert all(not c['enabled'] for c in get_traffic_demo_cities())

    def test_pick_random_pack_returns_cities(self):
        chosen = pick_random_traffic_demo_pack(5)
        assert len(chosen) == 5

    def test_pick_random_pack_respects_size(self):
        chosen = pick_random_traffic_demo_pack(3)
        assert len(chosen) == 3

    def test_pick_random_pack_stores_in_settings(self):
        chosen = pick_random_traffic_demo_pack(4)
        cfg = get_traffic_demo_config()
        pack = json.loads(cfg['pack'])
        assert len(pack) == 4
        assert all(c['id'] in pack for c in chosen)


# ─── _get_congestion_distribution ────────────────────────────────────────────

class TestCongestionDistribution:
    def test_sums_to_100(self):
        for hour in range(24):
            g, y, r = _get_congestion_distribution(hour)
            assert g + y + r == 100

    def test_weekend_sums_to_100(self):
        for hour in range(24):
            g, y, r = _get_congestion_distribution(hour, is_weekend=True)
            assert g + y + r == 100

    def test_rush_hour_has_more_red(self):
        g_rush, y_rush, r_rush = _get_congestion_distribution(7)   # morning rush
        g_night, y_night, r_night = _get_congestion_distribution(3)  # overnight
        assert r_rush > r_night

    def test_overnight_mostly_green(self):
        g, y, r = _get_congestion_distribution(3)
        assert g >= 85

    def test_evening_rush_high_congestion(self):
        g, y, r = _get_congestion_distribution(17)  # 5 pm
        assert r >= 20


# ─── _build_traffic_demo_payload ─────────────────────────────────────────────

class TestBuildTrafficDemoPayload:
    def test_has_required_keys(self):
        p = _build_traffic_demo_payload()
        for k in ('updated', 'city', 'summary', 'segments', 'demo_mode'):
            assert k in p, f"Missing key: {k}"

    def test_demo_mode_is_true(self):
        p = _build_traffic_demo_payload()
        assert p['demo_mode'] is True

    def test_city_has_required_keys(self):
        city = _build_traffic_demo_payload()['city']
        for k in ('name', 'state', 'lat', 'lon'):
            assert k in city

    def test_summary_has_required_keys(self):
        summary = _build_traffic_demo_payload()['summary']
        for k in ('congestion_level', 'green_percent', 'yellow_percent', 'red_percent'):
            assert k in summary

    def test_percentages_sum_to_roughly_100(self):
        s = _build_traffic_demo_payload()['summary']
        total = s['green_percent'] + s['yellow_percent'] + s['red_percent']
        assert 98 <= total <= 102

    def test_segments_is_list_of_24(self):
        segs = _build_traffic_demo_payload()['segments']
        assert isinstance(segs, list)
        assert len(segs) == 24

    def test_segments_have_id_and_color(self):
        for seg in _build_traffic_demo_payload()['segments']:
            assert 'id' in seg
            assert seg['color'] in ('green', 'yellow', 'red')

    def test_payload_is_cached(self):
        p1 = _build_traffic_demo_payload()
        p2 = _build_traffic_demo_payload()
        assert p1 is p2  # same object from cache

    def test_city_is_from_seed_data(self):
        city = _build_traffic_demo_payload()['city']
        seed_names = {c['name'] for c in _TRAFFIC_DEMO_CITIES_SEED}
        assert city['name'] in seed_names

    def test_congestion_level_is_valid(self):
        level = _build_traffic_demo_payload()['summary']['congestion_level']
        assert level in ('Light', 'Moderate', 'Heavy')

    def test_updated_is_iso_string(self):
        from datetime import datetime as _dt, timezone as _tz
        updated = _build_traffic_demo_payload()['updated']
        dt = _dt.fromisoformat(updated)
        assert dt.tzinfo is not None


# ─── /api/traffic endpoint ────────────────────────────────────────────────────

class TestApiTrafficEndpoint:
    def test_requires_login(self, client):
        resp = client.get('/api/traffic')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/api/traffic')
        assert resp.status_code == 200

    def test_response_has_required_keys(self, client):
        login(client)
        data = client.get('/api/traffic').get_json()
        for k in ('updated', 'city', 'summary', 'segments', 'demo_mode', 'ms_until_next'):
            assert k in data, f"Missing key: {k}"

    def test_demo_mode_flag_is_true(self, client):
        login(client)
        data = client.get('/api/traffic').get_json()
        assert data['demo_mode'] is True

    def test_ms_until_next_is_positive(self, client):
        login(client)
        data = client.get('/api/traffic').get_json()
        assert data['ms_until_next'] > 0

    def test_summary_percentages_present(self, client):
        login(client)
        data = client.get('/api/traffic').get_json()
        for k in ('green_percent', 'yellow_percent', 'red_percent', 'congestion_level'):
            assert k in data['summary']


# ─── /api/traffic/demo alias ─────────────────────────────────────────────────

class TestApiTrafficDemoAlias:
    def test_alias_returns_same_as_traffic(self, client):
        login(client)
        r1 = client.get('/api/traffic').get_json()
        r2 = client.get('/api/traffic/demo').get_json()
        assert r1['city'] == r2['city']
        assert r1['demo_mode'] == r2['demo_mode']


# ─── /api/traffic/demo/cities ────────────────────────────────────────────────

class TestApiTrafficDemoCities:
    def test_requires_login(self, client):
        resp = client.get('/api/traffic/demo/cities')
        assert resp.status_code in (302, 401)

    def test_returns_city_list(self, client):
        login(client)
        data = client.get('/api/traffic/demo/cities').get_json()
        assert 'cities' in data
        assert len(data['cities']) == len(_TRAFFIC_DEMO_CITIES_SEED)

    def test_city_update_endpoint(self, client):
        login(client)
        cities = client.get('/api/traffic/demo/cities').get_json()['cities']
        city_id = cities[0]['id']
        resp = client.post(f'/api/traffic/demo/cities/{city_id}',
                           data=json.dumps({'enabled': False, 'weight': 2}),
                           content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        # Verify change persisted
        updated_cities = client.get('/api/traffic/demo/cities').get_json()['cities']
        updated = next(c for c in updated_cities if c['id'] == city_id)
        assert updated['enabled'] is False
        assert updated['weight'] == 2


# ─── /api/traffic/demo/enable_all and /disable_all ───────────────────────────

class TestApiTrafficDemoBulkActions:
    def test_enable_all(self, client):
        login(client)
        client.post('/api/traffic/demo/disable_all')
        resp = client.post('/api/traffic/demo/enable_all')
        assert resp.get_json()['ok'] is True
        cities = client.get('/api/traffic/demo/cities').get_json()['cities']
        assert all(c['enabled'] for c in cities)

    def test_disable_all(self, client):
        login(client)
        resp = client.post('/api/traffic/demo/disable_all')
        assert resp.get_json()['ok'] is True
        cities = client.get('/api/traffic/demo/cities').get_json()['cities']
        assert all(not c['enabled'] for c in cities)


# ─── /api/traffic/demo/pick_random ───────────────────────────────────────────

class TestApiTrafficDemoPickRandom:
    def test_pick_random_returns_ok(self, client):
        login(client)
        resp = client.post('/api/traffic/demo/pick_random',
                           data=json.dumps({'pack_size': 5}),
                           content_type='application/json')
        data = resp.get_json()
        assert data['ok'] is True
        assert 'cities' in data
        assert len(data['cities']) == 5

    def test_pick_random_uses_default_pack_size(self, client):
        login(client)
        resp = client.post('/api/traffic/demo/pick_random',
                           data='{}', content_type='application/json')
        data = resp.get_json()
        assert data['ok'] is True
        assert len(data['cities']) == 10  # default pack_size


# ─── Admin UI — change_tuner page ────────────────────────────────────────────

class TestChangeTunerTrafficDemoUI:
    def test_traffic_demo_fields_in_change_tuner_page(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/change_tuner')
        assert resp.status_code == 200
        assert b'ch_traffic_demo_mode'       in resp.data
        assert b'ch_traffic_rotation_seconds' in resp.data
        assert b'ch_traffic_pack_size'        in resp.data

    def test_no_api_key_field_in_change_tuner_page(self, client):
        """TomTom API key input must no longer be present."""
        login(client, 'admin', 'adminpass')
        resp = client.get('/change_tuner')
        assert b'ch_traffic_api_key' not in resp.data
        assert b'TomTom' not in resp.data

    def test_city_table_present(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/change_tuner')
        assert b'traffic-demo-city-table' in resp.data
        assert b'New York City' in resp.data

    def test_demo_mode_badge_in_traffic_section(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/change_tuner')
        assert b'Demo Mode' in resp.data or b'demo' in resp.data.lower()

    def test_save_demo_config_via_change_tuner_post(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/change_tuner', data={
            'action':                        'update_channel_overlay_appearance',
            'tvg_id':                        'virtual.traffic',
            'ch_text_color':                 '',
            'ch_bg_color':                   '',
            'ch_test_text':                  '',
            'ch_traffic_demo_mode':          'random_pack',
            'ch_traffic_pack_size':          '8',
            'ch_traffic_rotation_seconds':   '90',
        }, follow_redirects=True)
        assert resp.status_code == 200
        cfg = get_traffic_demo_config()
        assert cfg['mode']             == 'random_pack'
        assert cfg['pack_size']        == '8'
        assert cfg['rotation_seconds'] == '90'

    def test_invalid_rotation_seconds_shows_warning(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/change_tuner', data={
            'action':                      'update_channel_overlay_appearance',
            'tvg_id':                      'virtual.traffic',
            'ch_text_color':               '',
            'ch_bg_color':                 '',
            'ch_test_text':                '',
            'ch_traffic_demo_mode':        'admin_rotation',
            'ch_traffic_pack_size':        '10',
            'ch_traffic_rotation_seconds': '5',  # too low
        }, follow_redirects=True)
        assert resp.status_code == 200
        # ValueError message says "rotation_seconds must be between 30 and 3600"
        assert b'rotation_seconds' in resp.data or b'between 30 and 3600' in resp.data


# ─── /traffic page ────────────────────────────────────────────────────────────

class TestTrafficPage:
    def test_requires_login(self, client):
        resp = client.get('/traffic')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/traffic')
        assert resp.status_code == 200

    def test_page_contains_demo_mode_text(self, client):
        login(client)
        resp = client.get('/traffic')
        assert b'Demo Mode' in resp.data or b'demo' in resp.data.lower()

    def test_page_fetches_api_traffic(self, client):
        login(client)
        resp = client.get('/traffic')
        assert b'/api/traffic' in resp.data

    def test_page_contains_svg_map_code(self, client):
        login(client)
        resp = client.get('/traffic')
        assert b'SEG_LINES' in resp.data or b'buildSvg' in resp.data
