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
    get_traffic_demo_roads, _overpass_to_geojson,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE",  users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",  tuners_db)
    # Also clear the module-level caches between tests
    monkeypatch.setattr(app_module, "_TRAFFIC_DEMO_CACHE", {})
    monkeypatch.setattr(app_module, "_ROADS_CACHE", {})
    monkeypatch.setattr(app_module, "_ROADS_CACHE_TIME", {})
    monkeypatch.setattr(app_module, "_OVERPASS_LAST_ERROR", {})
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
        for k in ('updated', 'city', 'summary', 'segments', 'demo_mode', 'time_slot'):
            assert k in p, f"Missing key: {k}"

    def test_demo_mode_is_true(self):
        p = _build_traffic_demo_payload()
        assert p['demo_mode'] is True

    def test_city_has_required_keys(self):
        city = _build_traffic_demo_payload()['city']
        for k in ('id', 'name', 'state', 'lat', 'lon'):
            assert k in city

    def test_city_id_is_int(self):
        city = _build_traffic_demo_payload()['city']
        assert isinstance(city['id'], int)

    def test_time_slot_is_int(self):
        assert isinstance(_build_traffic_demo_payload()['time_slot'], int)

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

    def test_no_cities_returns_no_cities_flag(self):
        set_all_traffic_demo_cities_enabled(False)
        p = _build_traffic_demo_payload()
        assert p == {'no_cities': True}

    def test_random_pack_mode_disable_all_returns_no_cities_flag(self):
        # Reproduce: pick random pack, then disable all cities — must see no_cities
        pick_random_traffic_demo_pack(5)
        save_traffic_demo_config({'mode': 'random_pack', 'pack_size': '5',
                                  'rotation_seconds': '120'})
        set_all_traffic_demo_cities_enabled(False)
        p = _build_traffic_demo_payload()
        assert p == {'no_cities': True}


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
        for k in ('updated', 'city', 'summary', 'segments', 'demo_mode',
                  'ms_until_next', 'time_slot'):
            assert k in data, f"Missing key: {k}"

    def test_city_includes_id(self, client):
        login(client)
        data = client.get('/api/traffic').get_json()
        assert 'id' in data['city']
        assert isinstance(data['city']['id'], int)

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

    def test_no_cities_selected_returns_no_cities_flag(self, client):
        login(client)
        client.post('/api/traffic/demo/disable_all')
        data = client.get('/api/traffic').get_json()
        assert data['no_cities'] is True
        assert data['ms_until_next'] > 0


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
        resp = client.get('/virtual_channels')
        assert resp.status_code == 200
        assert b'ch_traffic_demo_mode'       in resp.data
        assert b'ch_traffic_rotation_seconds' in resp.data
        assert b'ch_traffic_pack_size'        in resp.data

    def test_no_api_key_field_in_change_tuner_page(self, client):
        """TomTom API key input must no longer be present."""
        login(client, 'admin', 'adminpass')
        resp = client.get('/virtual_channels')
        assert b'ch_traffic_api_key' not in resp.data
        assert b'TomTom' not in resp.data

    def test_city_table_present(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/virtual_channels')
        assert b'traffic-demo-city-table' in resp.data
        assert b'New York City' in resp.data

    def test_demo_mode_badge_in_traffic_section(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/virtual_channels')
        assert b'Demo Mode' in resp.data or b'demo' in resp.data.lower()

    def test_save_demo_config_via_change_tuner_post(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
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
        resp = client.post('/virtual_channels', data={
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

    def test_page_uses_osm_leaflet_map(self, client):
        """traffic.html uses static PNGs (primary) with Leaflet+OSM fallback; no dark CDN."""
        login(client)
        resp = client.get('/traffic')
        # Static PNG path for pre-generated basemaps
        assert b'static/maps/traffic_demo' in resp.data
        # Leaflet vendor bundle present as fallback
        assert b'leaflet' in resp.data.lower()
        # OpenStreetMap URL present in fallback tile layer
        assert b'openstreetmap.org' in resp.data
        # CartoDB dark tiles are gone
        assert b'cartocdn' not in resp.data.lower()

    def test_page_has_retroiptv_traffic_title(self, client):
        """traffic.html header must read 'RetroIPTV Traffic' to match channel naming."""
        login(client)
        resp = client.get('/traffic')
        assert b'RetroIPTV Traffic' in resp.data
        assert b'(Simulated)' in resp.data


# ─── _overpass_to_geojson helper ─────────────────────────────────────────────

class TestOverpassToGeojson:
    """Unit tests for the Overpass JSON → GeoJSON converter."""

    def _make_overpass(self, nodes, ways):
        elements = []
        for nid, lat, lon in nodes:
            elements.append({'type': 'node', 'id': nid, 'lat': lat, 'lon': lon})
        for wid, node_ids, tags in ways:
            elements.append({'type': 'way', 'id': wid, 'nodes': node_ids, 'tags': tags})
        return {'elements': elements}

    def test_empty_input_returns_empty_feature_collection(self):
        result = _overpass_to_geojson({'elements': []})
        assert result['type'] == 'FeatureCollection'
        assert result['features'] == []

    def test_single_way_produces_one_feature(self):
        raw = self._make_overpass(
            nodes=[(1, 41.88, -87.63), (2, 41.89, -87.64)],
            ways=[(100, [1, 2], {'highway': 'primary', 'name': 'N Michigan Ave'})],
        )
        result = _overpass_to_geojson(raw)
        assert len(result['features']) == 1
        f = result['features'][0]
        assert f['type'] == 'Feature'
        assert f['geometry']['type'] == 'LineString'
        assert len(f['geometry']['coordinates']) == 2
        assert f['properties']['highway'] == 'primary'
        assert f['properties']['name'] == 'N Michigan Ave'
        assert f['properties']['way_id'] == 100

    def test_coordinates_are_lon_lat_order(self):
        """GeoJSON uses [longitude, latitude] order."""
        raw = self._make_overpass(
            nodes=[(1, 41.88, -87.63), (2, 41.89, -87.64)],
            ways=[(10, [1, 2], {'highway': 'motorway'})],
        )
        result = _overpass_to_geojson(raw)
        coord0 = result['features'][0]['geometry']['coordinates'][0]
        assert coord0 == (-87.63, 41.88)  # [lon, lat]

    def test_way_with_single_node_is_skipped(self):
        """A way with only one node cannot form a LineString — should be omitted."""
        raw = self._make_overpass(
            nodes=[(1, 41.88, -87.63)],
            ways=[(10, [1], {'highway': 'primary'})],
        )
        result = _overpass_to_geojson(raw)
        assert len(result['features']) == 0

    def test_way_with_missing_node_coords_is_skipped(self):
        """If a node referenced by a way is missing, the way is dropped."""
        raw = self._make_overpass(
            nodes=[],
            ways=[(10, [1, 2], {'highway': 'primary'})],
        )
        result = _overpass_to_geojson(raw)
        assert len(result['features']) == 0

    def test_multiple_ways(self):
        raw = self._make_overpass(
            nodes=[(1, 41.88, -87.63), (2, 41.89, -87.64), (3, 41.90, -87.65)],
            ways=[
                (10, [1, 2], {'highway': 'motorway'}),
                (11, [2, 3], {'highway': 'trunk'}),
            ],
        )
        result = _overpass_to_geojson(raw)
        assert len(result['features']) == 2


# ─── get_traffic_demo_roads (with mocked Overpass) ───────────────────────────

class TestGetTrafficDemoRoads:
    """Test the caching road-fetch helper using a monkeypatched _fetch_overpass_roads."""

    def _minimal_overpass(self):
        return {
            'elements': [
                {'type': 'node', 'id': 1, 'lat': 41.88, 'lon': -87.63},
                {'type': 'node', 'id': 2, 'lat': 41.89, 'lon': -87.64},
                {'type': 'way',  'id': 10, 'nodes': [1, 2],
                 'tags': {'highway': 'primary', 'name': 'Test St'}},
            ]
        }

    def test_returns_feature_collection(self, monkeypatch):
        monkeypatch.setattr(app_module, '_fetch_overpass_roads',
                            lambda lat, lon, radius_m=80_467: self._minimal_overpass())
        cities = get_traffic_demo_cities()
        result = get_traffic_demo_roads(cities[0]['id'])
        assert result['type'] == 'FeatureCollection'
        assert len(result['features']) >= 1

    def test_result_is_cached(self, monkeypatch):
        call_count = {'n': 0}
        def fake_fetch(lat, lon, radius_m=80_467):
            call_count['n'] += 1
            return self._minimal_overpass()
        monkeypatch.setattr(app_module, '_fetch_overpass_roads', fake_fetch)
        cities = get_traffic_demo_cities()
        cid = cities[0]['id']
        get_traffic_demo_roads(cid)
        get_traffic_demo_roads(cid)
        # Should only call Overpass once — second call hits cache
        assert call_count['n'] == 1

    def test_overpass_failure_returns_empty_geojson(self, monkeypatch):
        monkeypatch.setattr(app_module, '_fetch_overpass_roads',
                            lambda lat, lon, radius_m=80_467: {'elements': []})
        cities = get_traffic_demo_cities()
        result = get_traffic_demo_roads(cities[0]['id'])
        assert result['type'] == 'FeatureCollection'
        assert result['features'] == []

    def test_unknown_city_id_returns_empty(self, monkeypatch):
        monkeypatch.setattr(app_module, '_fetch_overpass_roads',
                            lambda lat, lon, radius_m=80_467: self._minimal_overpass())
        result = get_traffic_demo_roads(99999)
        assert result['type'] == 'FeatureCollection'
        assert result['features'] == []


# ─── /api/traffic/demo/roads/<city_id> endpoint ───────────────────────────────

class TestApiTrafficDemoRoads:
    def _minimal_overpass(self):
        return {
            'elements': [
                {'type': 'node', 'id': 1, 'lat': 41.88, 'lon': -87.63},
                {'type': 'node', 'id': 2, 'lat': 41.89, 'lon': -87.64},
                {'type': 'way',  'id': 10, 'nodes': [1, 2],
                 'tags': {'highway': 'primary', 'name': 'Main St'}},
            ]
        }

    def test_requires_login(self, client):
        resp = client.get('/api/traffic/demo/roads/1')
        assert resp.status_code in (302, 401)

    def test_returns_200_for_valid_city(self, client, monkeypatch):
        monkeypatch.setattr(app_module, '_fetch_overpass_roads',
                            lambda lat, lon, radius_m=80_467: self._minimal_overpass())
        login(client)
        cities = get_traffic_demo_cities()
        resp = client.get(f'/api/traffic/demo/roads/{cities[0]["id"]}')
        assert resp.status_code == 200

    def test_response_is_geojson_feature_collection(self, client, monkeypatch):
        monkeypatch.setattr(app_module, '_fetch_overpass_roads',
                            lambda lat, lon, radius_m=80_467: self._minimal_overpass())
        login(client)
        cities = get_traffic_demo_cities()
        data = client.get(f'/api/traffic/demo/roads/{cities[0]["id"]}').get_json()
        assert data['type'] == 'FeatureCollection'
        assert 'features' in data

    def test_features_have_geometry_and_properties(self, client, monkeypatch):
        monkeypatch.setattr(app_module, '_fetch_overpass_roads',
                            lambda lat, lon, radius_m=80_467: self._minimal_overpass())
        login(client)
        cities = get_traffic_demo_cities()
        data = client.get(f'/api/traffic/demo/roads/{cities[0]["id"]}').get_json()
        assert len(data['features']) == 1
        f = data['features'][0]
        assert f['geometry']['type'] == 'LineString'
        assert 'highway' in f['properties']

    def test_unknown_city_returns_empty_collection(self, client, monkeypatch):
        monkeypatch.setattr(app_module, '_fetch_overpass_roads',
                            lambda lat, lon, radius_m=80_467: self._minimal_overpass())
        login(client)
        data = client.get('/api/traffic/demo/roads/99999').get_json()
        assert data['type'] == 'FeatureCollection'
        assert data['features'] == []

    def test_overpass_failure_returns_empty_collection(self, client, monkeypatch):
        monkeypatch.setattr(app_module, '_fetch_overpass_roads',
                            lambda lat, lon, radius_m=80_467: {'elements': []})
        login(client)
        cities = get_traffic_demo_cities()
        data = client.get(f'/api/traffic/demo/roads/{cities[0]["id"]}').get_json()
        assert data['type'] == 'FeatureCollection'
        assert data['features'] == []


# ─── _OVERPASS_LAST_ERROR tracking ───────────────────────────────────────────

class TestOverpassLastError:
    """Verify that _fetch_overpass_roads populates and clears _OVERPASS_LAST_ERROR."""

    def _make_http_error_response(self, status_code):
        """Build a minimal mock response that raises an HTTPError."""
        import requests as _req

        class _MockResp:
            def __init__(self, code):
                self.status_code = code

            def raise_for_status(self):
                raise _req.exceptions.HTTPError(
                    f"{self.status_code} Error", response=self
                )

            def json(self):
                return {}

        return _MockResp(status_code)

    def test_429_populates_last_error(self, monkeypatch):
        """A 429 from requests.post should record the error in _OVERPASS_LAST_ERROR."""
        import requests as _req

        resp = self._make_http_error_response(429)
        monkeypatch.setattr(_req, "post", lambda *a, **kw: resp)

        from app import _fetch_overpass_roads
        _fetch_overpass_roads(40.7128, -74.006)

        err = app_module._OVERPASS_LAST_ERROR
        assert err, "_OVERPASS_LAST_ERROR should be non-empty after 429"
        assert err["status_code"] == 429
        assert err["lat"] == 40.7128
        assert err["lon"] == -74.006
        assert "ts" in err

    def test_504_populates_last_error(self, monkeypatch):
        """A 504 from requests.post should record the error in _OVERPASS_LAST_ERROR."""
        import requests as _req

        resp = self._make_http_error_response(504)
        monkeypatch.setattr(_req, "post", lambda *a, **kw: resp)

        from app import _fetch_overpass_roads
        _fetch_overpass_roads(33.4484, -112.074)

        err = app_module._OVERPASS_LAST_ERROR
        assert err["status_code"] == 504

    def test_success_clears_last_error(self, monkeypatch):
        """A successful fetch should clear _OVERPASS_LAST_ERROR."""
        import requests as _req

        # Seed an error first
        monkeypatch.setattr(app_module, "_OVERPASS_LAST_ERROR", {
            "status_code": 429, "lat": 40.7128, "lon": -74.006,
            "ts": 0, "message": "stale",
        })

        class _OkResp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"elements": []}

        monkeypatch.setattr(_req, "post", lambda *a, **kw: _OkResp())

        from app import _fetch_overpass_roads
        _fetch_overpass_roads(40.7128, -74.006)

        assert app_module._OVERPASS_LAST_ERROR == {}, \
            "_OVERPASS_LAST_ERROR should be cleared after a successful fetch"

    def test_429_returns_empty_elements(self, monkeypatch):
        """A 429 should return {'elements': []} so callers get an empty GeoJSON."""
        import requests as _req

        resp = self._make_http_error_response(429)
        monkeypatch.setattr(_req, "post", lambda *a, **kw: resp)

        from app import _fetch_overpass_roads
        result = _fetch_overpass_roads(40.7128, -74.006)
        assert result == {"elements": []}
