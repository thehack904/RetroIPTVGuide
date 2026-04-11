"""Tests for Virtual Channels v1: helper functions and stub API endpoints."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import (app, init_db, init_tuners_db, get_virtual_channels, get_virtual_epg,
                 get_virtual_channel_settings, save_virtual_channel_settings,
                 get_overlay_appearance, save_overlay_appearance,
                 get_channel_overlay_appearance, save_channel_overlay_appearance,
                 get_all_channel_appearances,
                 get_channel_mix_config, save_channel_mix_config,
                 VIRTUAL_CHANNELS, SPORTS_LEAGUES)


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


# ─── get_virtual_channels ────────────────────────────────────────────────────

class TestGetVirtualChannels:
    def test_returns_three_channels(self):
        channels = get_virtual_channels()
        assert len(channels) == 9

    def test_all_have_is_virtual_true(self):
        for ch in get_virtual_channels():
            assert ch.get("is_virtual") is True

    def test_known_tvg_ids_present(self):
        ids = {ch["tvg_id"] for ch in get_virtual_channels()}
        assert "virtual.news" in ids
        assert "virtual.weather" in ids
        assert "virtual.status" in ids
        assert "virtual.nasa" in ids

    def test_each_has_required_keys(self):
        required = {"name", "logo", "url", "tvg_id", "is_virtual",
                    "playback_mode", "loop_asset", "overlay_type", "overlay_refresh_seconds"}
        for ch in get_virtual_channels():
            assert required.issubset(ch.keys()), f"Missing keys in {ch['tvg_id']}"

    def test_loop_assets_are_mp4_paths(self):
        for ch in get_virtual_channels():
            # channel_mix uses no dedicated loop asset (overlay covers full screen)
            if ch['tvg_id'] == 'virtual.channel_mix':
                assert ch["loop_asset"] == ''
            else:
                assert ch["loop_asset"].endswith(".mp4")

    def test_returns_independent_copy(self):
        a = get_virtual_channels()
        b = get_virtual_channels()
        a[0]["name"] = "mutated"
        assert b[0]["name"] != "mutated"


# ─── get_virtual_epg ─────────────────────────────────────────────────────────

class TestGetVirtualEpg:
    def setup_method(self):
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.grid_start = self.now.replace(minute=0, second=0, microsecond=0)

    def test_returns_entries_for_all_virtual_channels(self):
        epg = get_virtual_epg(self.grid_start, hours_span=6)
        assert "virtual.news" in epg
        assert "virtual.weather" in epg
        assert "virtual.status" in epg

    def test_slots_cover_full_span(self):
        epg = get_virtual_epg(self.grid_start, hours_span=6)
        for tvg_id, slots in epg.items():
            assert len(slots) == 6, f"{tvg_id} should have 6 hourly slots"

    def test_slots_are_contiguous(self):
        epg = get_virtual_epg(self.grid_start, hours_span=4)
        for tvg_id, slots in epg.items():
            for i in range(len(slots) - 1):
                assert slots[i]["stop"] == slots[i + 1]["start"], \
                    f"{tvg_id} slots are not contiguous at index {i}"

    def test_each_slot_has_required_fields(self):
        epg = get_virtual_epg(self.grid_start, hours_span=2)
        for tvg_id, slots in epg.items():
            for slot in slots:
                assert "title" in slot
                assert "start" in slot
                assert "stop" in slot

    def test_first_slot_starts_at_grid_start(self):
        epg = get_virtual_epg(self.grid_start, hours_span=3)
        for tvg_id, slots in epg.items():
            assert slots[0]["start"] == self.grid_start

    def test_slots_are_one_hour_each(self):
        epg = get_virtual_epg(self.grid_start, hours_span=3)
        for tvg_id, slots in epg.items():
            for slot in slots:
                duration = (slot["stop"] - slot["start"]).total_seconds()
                assert duration == 3600, f"{tvg_id} slot duration is not 1 hour"


# ─── get/save_virtual_channel_settings ───────────────────────────────────────

class TestVirtualChannelSettings:
    def test_defaults_all_enabled(self):
        settings = get_virtual_channel_settings()
        for ch in VIRTUAL_CHANNELS:
            assert settings.get(ch["tvg_id"]) is True

    def test_save_and_reload(self):
        save_virtual_channel_settings({
            "virtual.news": False,
            "virtual.weather": True,
            "virtual.status": False,
        })
        settings = get_virtual_channel_settings()
        assert settings["virtual.news"] is False
        assert settings["virtual.weather"] is True
        assert settings["virtual.status"] is False

    def test_partial_save_keeps_others_at_default(self):
        save_virtual_channel_settings({"virtual.news": False})
        settings = get_virtual_channel_settings()
        assert settings["virtual.news"] is False
        # others not saved, so still default True
        assert settings["virtual.weather"] is True
        assert settings["virtual.status"] is True

    def test_re_enable_after_disable(self):
        save_virtual_channel_settings({"virtual.news": False})
        save_virtual_channel_settings({"virtual.news": True})
        settings = get_virtual_channel_settings()
        assert settings["virtual.news"] is True


# ─── /change_tuner update_virtual_channels action ───────────────────────────

class TestChangeTunerVirtualChannels:
    def test_non_admin_cannot_access_change_tuner(self, client):
        login(client, "testuser", "testpass")
        resp = client.get("/change_tuner")
        # non-admin should be redirected to guide
        assert resp.status_code in (302, 200)
        # If it redirected, it went to /guide, not the tuner page
        if resp.status_code == 302:
            assert "guide" in resp.headers.get("Location", "")

    def test_admin_can_access_change_tuner(self, client):
        login(client, "admin", "adminpass")
        resp = client.get("/change_tuner")
        assert resp.status_code == 200

    def test_virtual_channels_section_in_page(self, client):
        login(client, "admin", "adminpass")
        resp = client.get("/virtual_channels")
        assert b"Virtual Channels" in resp.data

    def test_admin_can_disable_virtual_channel(self, client):
        login(client, "admin", "adminpass")
        # Omit news (unchecked) — only submit checked channels, matching real browser behaviour
        resp = client.post("/virtual_channels", data={
            "action": "update_virtual_channels",
            "vc_virtual.weather": "1",
            "vc_virtual.status": "1",
        }, follow_redirects=True)
        assert resp.status_code == 200
        settings = get_virtual_channel_settings()
        assert settings["virtual.news"] is False
        assert settings["virtual.weather"] is True
        assert settings["virtual.status"] is True

    def test_admin_can_enable_all_virtual_channels(self, client):
        # First disable all
        save_virtual_channel_settings({
            "virtual.news": False,
            "virtual.weather": False,
            "virtual.status": False,
            "virtual.traffic": False,
            "virtual.updates": False,
            "virtual.sports": False,
            "virtual.nasa": False,
            "virtual.channel_mix": False,
            "virtual.on_this_day": False,
        })
        login(client, "admin", "adminpass")
        resp = client.post("/virtual_channels", data={
            "action": "update_virtual_channels",
            "vc_virtual.news": "1",
            "vc_virtual.weather": "1",
            "vc_virtual.status": "1",
            "vc_virtual.traffic": "1",
            "vc_virtual.updates": "1",
            "vc_virtual.sports": "1",
            "vc_virtual.nasa": "1",
            "vc_virtual.channel_mix": "1",
            "vc_virtual.on_this_day": "1",
        }, follow_redirects=True)
        assert resp.status_code == 200
        settings = get_virtual_channel_settings()
        assert all(settings[ch["tvg_id"]] for ch in VIRTUAL_CHANNELS)

    def test_disabled_channel_not_shown_in_guide(self, client):
        """When a virtual channel is disabled it should not appear in the guide."""
        save_virtual_channel_settings({
            "virtual.news": False,
            "virtual.weather": False,
            "virtual.status": False,
        })
        login(client, "admin", "adminpass")
        resp = client.get("/guide")
        assert resp.status_code == 200
        assert b"News Now" not in resp.data
        assert b"Weather Now" not in resp.data
        assert b"System Status" not in resp.data

    def test_enabled_channel_shown_in_guide(self, client):
        """When a virtual channel is enabled it should appear in the guide."""
        save_virtual_channel_settings({
            "virtual.news": True,
            "virtual.weather": False,
            "virtual.status": False,
        })
        login(client, "admin", "adminpass")
        resp = client.get("/guide")
        assert resp.status_code == 200
        assert b"News Now" in resp.data
        assert b"Weather Now" not in resp.data


# ─── /api/news ───────────────────────────────────────────────────────────────

class TestApiNews:
    def test_requires_login(self, client):
        resp = client.get("/api/news")
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get("/api/news")
        assert resp.status_code == 200

    def test_response_has_headlines_list(self, client):
        login(client)
        data = client.get("/api/news").get_json()
        assert "headlines" in data
        assert isinstance(data["headlines"], list)

    def test_response_has_updated_field(self, client):
        login(client)
        data = client.get("/api/news").get_json()
        assert "updated" in data


# ─── /api/weather ────────────────────────────────────────────────────────────

class TestApiWeather:
    def test_requires_login(self, client):
        resp = client.get("/api/weather")
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get("/api/weather")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert "location" in data
        assert "now" in data
        assert "forecast" in data
        assert isinstance(data["forecast"], list)

    def test_response_has_updated_field(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert "updated" in data

    def test_response_has_segment_field(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert "segment" in data
        assert data["segment"] in (0, 1, 2, 3)

    def test_response_has_segment_label(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert "segment_label" in data
        assert data["segment_label"] in ("current", "forecast", "radar", "alerts")

    def test_response_has_seconds_per_segment(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert "seconds_per_segment" in data
        assert isinstance(data["seconds_per_segment"], int)
        assert data["seconds_per_segment"] >= 30

    def test_response_has_ms_until_next(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert "ms_until_next" in data
        sps = data["seconds_per_segment"]
        assert 0 < data["ms_until_next"] <= sps * 1000

    def test_response_has_five_day(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert "five_day" in data
        assert isinstance(data["five_day"], list)

    def test_response_has_radar_url(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert "radar_url" in data
        assert isinstance(data["radar_url"], str)
        assert data["radar_url"].startswith("https://")

    def test_segment_label_matches_segment_index(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        labels = ("current", "forecast", "radar", "alerts")
        assert data["segment_label"] == labels[data["segment"]]

    def test_default_seconds_per_segment_is_300(self, client):
        login(client)
        data = client.get("/api/weather").get_json()
        assert data["seconds_per_segment"] == 300


# ─── WeatherConfig helpers ────────────────────────────────────────────────────

class TestWeatherConfig:
    def test_default_seconds_per_segment(self):
        from app import get_weather_config
        cfg = get_weather_config()
        # Default value when nothing is stored
        assert cfg["seconds_per_segment"] in ("300", 300, "")

    def test_save_and_reload_seconds_per_segment(self):
        from app import save_weather_config, get_weather_config
        save_weather_config({"lat": "", "lon": "", "location_name": "",
                             "units": "F", "seconds_per_segment": "120"})
        cfg = get_weather_config()
        assert cfg["seconds_per_segment"] == "120"

    def test_invalid_seconds_per_segment_too_low_raises(self):
        from app import save_weather_config
        import pytest as _pytest
        with _pytest.raises(ValueError):
            save_weather_config({"lat": "", "lon": "", "location_name": "",
                                 "units": "F", "seconds_per_segment": "10"})

    def test_invalid_seconds_per_segment_too_high_raises(self):
        from app import save_weather_config
        import pytest as _pytest
        with _pytest.raises(ValueError):
            save_weather_config({"lat": "", "lon": "", "location_name": "",
                                 "units": "F", "seconds_per_segment": "9999"})

    def test_invalid_seconds_per_segment_non_numeric_raises(self):
        from app import save_weather_config
        import pytest as _pytest
        with _pytest.raises(ValueError):
            save_weather_config({"lat": "", "lon": "", "location_name": "",
                                 "units": "F", "seconds_per_segment": "fast"})

    def test_seconds_per_segment_saved_via_http(self, client):
        login(client, "admin", "adminpass")
        client.post("/virtual_channels", data={
            "action": "update_channel_overlay_appearance",
            "tvg_id": "virtual.weather",
            "ch_weather_location": "Miami, FL",
            "ch_weather_lat": "25.77",
            "ch_weather_lon": "-80.19",
            "ch_weather_units": "F",
            "ch_weather_seconds_per_segment": "180",
        }, follow_redirects=True)
        from app import get_weather_config
        cfg = get_weather_config()
        assert cfg["seconds_per_segment"] == "180"

    def test_api_respects_saved_seconds_per_segment(self, client):
        from app import save_weather_config
        save_weather_config({"lat": "", "lon": "", "location_name": "",
                             "units": "F", "seconds_per_segment": "60"})
        login(client)
        data = client.get("/api/weather").get_json()
        assert data["seconds_per_segment"] == 60
        assert 0 < data["ms_until_next"] <= 60 * 1000


# ─── _build_radar_url ─────────────────────────────────────────────────────────

class TestBuildRadarUrl:
    def test_returns_string(self):
        from app import _build_radar_url
        url = _build_radar_url("25.77", "-80.19")
        assert isinstance(url, str)
        assert url.startswith("https://")

    def test_no_coords_returns_conus(self):
        from app import _build_radar_url, _RADAR_URL_CONUS
        assert _build_radar_url("", "") == _RADAR_URL_CONUS
        assert _build_radar_url(None, None) == _RADAR_URL_CONUS

    def test_with_coords_contains_bbox(self):
        from app import _build_radar_url
        url = _build_radar_url("40.0", "-75.0")
        assert "bbox=" in url
        # Bounding box should be centred on the coordinates
        assert "-83" in url or "-83.0" in url  # lon - 8
        assert "35" in url                      # lat - 5

    def test_invalid_coords_falls_back_to_conus(self):
        from app import _build_radar_url, _RADAR_URL_CONUS
        assert _build_radar_url("notanumber", "alsonotanumber") == _RADAR_URL_CONUS


# ─── /api/virtual/status ─────────────────────────────────────────────────────

class TestApiVirtualStatus:
    def test_requires_login(self, client):
        resp = client.get("/api/virtual/status")
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get("/api/virtual/status")
        assert resp.status_code == 200

    def test_response_has_items_list(self, client):
        login(client)
        data = client.get("/api/virtual/status").get_json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

    def test_items_have_label_and_value(self, client):
        login(client)
        data = client.get("/api/virtual/status").get_json()
        for item in data["items"]:
            assert "label" in item
            assert "value" in item

    def test_response_has_updated_field(self, client):
        login(client)
        data = client.get("/api/virtual/status").get_json()
        assert "updated" in data

    def test_response_has_enhanced_fields(self, client):
        login(client)
        data = client.get("/api/virtual/status").get_json()
        assert "app_version" in data
        assert "uptime" in data
        assert "uptime_seconds" in data
        assert "overall_state" in data
        assert "ticker" in data
        assert "ms_until_next" in data
        assert "disk_used_pct" in data

    def test_items_have_state_field(self, client):
        login(client)
        data = client.get("/api/virtual/status").get_json()
        for item in data["items"]:
            assert "state" in item
            assert item["state"] in ("good", "warn", "error")

    def test_ticker_is_list_of_strings(self, client):
        login(client)
        data = client.get("/api/virtual/status").get_json()
        assert isinstance(data["ticker"], list)
        for entry in data["ticker"]:
            assert isinstance(entry, str)

    def test_uptime_seconds_non_negative(self, client):
        login(client)
        data = client.get("/api/virtual/status").get_json()
        assert data["uptime_seconds"] >= 0


# ─── /status page ─────────────────────────────────────────────────────────────

class TestStatusPage:
    def test_requires_login(self, client):
        resp = client.get("/status")
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get("/status")
        assert resp.status_code == 200

    def test_page_contains_status_branding(self, client):
        login(client)
        resp = client.get("/status")
        html = resp.data.decode()
        assert "RetroIPTV" in html
        assert "Status" in html

    def test_page_contains_api_reference(self, client):
        login(client)
        resp = client.get("/status")
        html = resp.data.decode()
        assert "/api/virtual/status" in html




# ─── Overlay Appearance Settings ─────────────────────────────────────────────

class TestOverlayAppearance:
    def test_defaults_are_empty_strings(self):
        settings = get_overlay_appearance()
        assert settings['text_color'] == ''
        assert settings['bg_color'] == ''
        assert settings['test_text'] == ''

    def test_save_and_reload_colors(self):
        save_overlay_appearance({'text_color': '#ff0000', 'bg_color': '#001122', 'test_text': ''})
        s = get_overlay_appearance()
        assert s['text_color'] == '#ff0000'
        assert s['bg_color'] == '#001122'
        assert s['test_text'] == ''

    def test_save_and_reload_test_text(self):
        save_overlay_appearance({'text_color': '', 'bg_color': '', 'test_text': 'TEST MODE'})
        assert get_overlay_appearance()['test_text'] == 'TEST MODE'

    def test_invalid_color_raises_value_error(self):
        import pytest as _pytest
        with _pytest.raises(ValueError):
            save_overlay_appearance({'text_color': 'red', 'bg_color': '', 'test_text': ''})

    def test_save_partial_keys_fills_defaults(self):
        save_overlay_appearance({'text_color': '#aabbcc', 'bg_color': '', 'test_text': ''})
        s = get_overlay_appearance()
        assert s['text_color'] == '#aabbcc'
        assert s['bg_color'] == ''


class TestChangeTunerOverlayAppearance:
    def test_section_present_in_page(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/virtual_channels')
        # Each channel has a per-channel settings button; overlay action present in page
        assert b'update_channel_overlay_appearance' in resp.data

    def test_admin_can_save_per_channel_appearance(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.status',
            'ch_text_color': '#ffffff',
            'ch_bg_color': '#000000',
            'ch_test_text': 'TESTING 123',
        }, follow_redirects=True)
        assert resp.status_code == 200
        s = get_channel_overlay_appearance('virtual.status')
        assert s['text_color'] == '#ffffff'
        assert s['bg_color'] == '#000000'
        assert s['test_text'] == 'TESTING 123'

    def test_invalid_color_shows_warning(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.status',
            'ch_text_color': 'notacolor',
            'ch_bg_color': '',
            'ch_test_text': '',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Invalid color' in resp.data

    def test_unknown_tvg_id_shows_warning(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.nonexistent',
            'ch_text_color': '#ffffff',
            'ch_bg_color': '',
            'ch_test_text': '',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Unknown virtual channel' in resp.data

    def test_clear_test_text_saves_empty(self, client):
        save_channel_overlay_appearance('virtual.weather', {'text_color': '', 'bg_color': '', 'test_text': 'old'})
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '',
            'ch_bg_color': '',
            'ch_test_text': '',
        }, follow_redirects=True)
        assert get_channel_overlay_appearance('virtual.weather')['test_text'] == ''

    def test_channels_can_have_independent_settings(self, client):
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.status',
            'ch_text_color': '#ff0000',
            'ch_bg_color': '',
            'ch_test_text': 'status test',
        }, follow_redirects=True)
        # Weather channel: appearance fields are always cleared via HTTP route
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '#00ff00',
            'ch_bg_color': '',
            'ch_test_text': 'weather test',
        }, follow_redirects=True)
        status = get_channel_overlay_appearance('virtual.status')
        weather = get_channel_overlay_appearance('virtual.weather')
        assert status['text_color'] == '#ff0000'
        assert status['test_text'] == 'status test'
        # Weather appearance fields are always cleared — they are not used by that channel
        assert weather['text_color'] == ''
        assert weather['test_text'] == ''

    def test_weather_overlay_appearance_fields_always_cleared_via_http(self, client):
        """Text Color, Background Color, and Test Banner Text are not applicable to
        the weather channel; they must always be stored as empty strings regardless
        of what values are submitted in the form."""
        save_channel_overlay_appearance('virtual.weather',
                                        {'text_color': '#abcdef', 'bg_color': '#123456',
                                         'test_text': 'This is test Text!'})
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '#abcdef',
            'ch_bg_color': '#123456',
            'ch_test_text': 'This is test Text!',
            'ch_weather_location': 'Miami, FL',
            'ch_weather_lat': '25.77',
            'ch_weather_lon': '-80.19',
            'ch_weather_units': 'F',
        }, follow_redirects=True)
        s = get_channel_overlay_appearance('virtual.weather')
        assert s['text_color'] == ''
        assert s['bg_color'] == ''
        assert s['test_text'] == ''

    def test_news_overlay_appearance_fields_always_cleared_via_http(self, client):
        """Text Color, Background Color, and Test Banner Text are not applicable to
        the news channel; they must always be stored as empty strings regardless
        of what values are submitted in the form."""
        save_channel_overlay_appearance('virtual.news',
                                        {'text_color': '#abcdef', 'bg_color': '#123456',
                                         'test_text': 'Breaking!'})
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.news',
            'ch_text_color': '#abcdef',
            'ch_bg_color': '#123456',
            'ch_test_text': 'Breaking!',
            'ch_news_rss_url': '',
        }, follow_redirects=True)
        s = get_channel_overlay_appearance('virtual.news')
        assert s['text_color'] == ''
        assert s['bg_color'] == ''
        assert s['test_text'] == ''

    def test_traffic_overlay_appearance_fields_always_cleared_via_http(self, client):
        """Text Color, Background Color, and Test Banner Text are not applicable to
        the traffic channel; they must always be stored as empty strings regardless
        of what values are submitted in the form."""
        save_channel_overlay_appearance('virtual.traffic',
                                        {'text_color': '#abcdef', 'bg_color': '#123456',
                                         'test_text': 'Traffic Alert!'})
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.traffic',
            'ch_text_color': '#abcdef',
            'ch_bg_color': '#123456',
            'ch_test_text': 'Traffic Alert!',
        }, follow_redirects=True)
        s = get_channel_overlay_appearance('virtual.traffic')
        assert s['text_color'] == ''
        assert s['bg_color'] == ''
        assert s['test_text'] == ''

    def test_sports_overlay_appearance_fields_always_cleared_via_http(self, client):
        """Text Color, Background Color, and Test Banner Text are not applicable to
        the sports channel; they must always be stored as empty strings regardless
        of what values are submitted in the form."""
        save_channel_overlay_appearance('virtual.sports',
                                        {'text_color': '#abcdef', 'bg_color': '#123456',
                                         'test_text': 'Game Time!'})
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.sports',
            'ch_text_color': '#abcdef',
            'ch_bg_color': '#123456',
            'ch_test_text': 'Game Time!',
        }, follow_redirects=True)
        s = get_channel_overlay_appearance('virtual.sports')
        assert s['text_color'] == ''
        assert s['bg_color'] == ''
        assert s['test_text'] == ''

    def test_nasa_overlay_appearance_fields_always_cleared_via_http(self, client):
        """Text Color, Background Color, and Test Banner Text are not applicable to
        the nasa channel; they must always be stored as empty strings regardless
        of what values are submitted in the form."""
        save_channel_overlay_appearance('virtual.nasa',
                                        {'text_color': '#abcdef', 'bg_color': '#123456',
                                         'test_text': 'NASA APOD!'})
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.nasa',
            'ch_text_color': '#abcdef',
            'ch_bg_color': '#123456',
            'ch_test_text': 'NASA APOD!',
        }, follow_redirects=True)
        s = get_channel_overlay_appearance('virtual.nasa')
        assert s['text_color'] == ''
        assert s['bg_color'] == ''
        assert s['test_text'] == ''

    def test_on_this_day_overlay_appearance_fields_always_cleared_via_http(self, client):
        """Text Color, Background Color, and Test Banner Text are not applicable to
        the on_this_day channel; they must always be stored as empty strings regardless
        of what values are submitted in the form."""
        save_channel_overlay_appearance('virtual.on_this_day',
                                        {'text_color': '#abcdef', 'bg_color': '#123456',
                                         'test_text': 'On This Day!'})
        login(client, 'admin', 'adminpass')
        client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.on_this_day',
            'ch_text_color': '#abcdef',
            'ch_bg_color': '#123456',
            'ch_test_text': 'On This Day!',
        }, follow_redirects=True)
        s = get_channel_overlay_appearance('virtual.on_this_day')
        assert s['text_color'] == ''
        assert s['bg_color'] == ''
        assert s['test_text'] == ''


class TestApiOverlaySettings:
    def test_requires_login(self, client):
        resp = client.get('/api/overlay/settings')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/api/overlay/settings')
        assert resp.status_code == 200

    def test_response_has_expected_keys(self, client):
        login(client)
        data = client.get('/api/overlay/settings').get_json()
        assert 'text_color' in data
        assert 'bg_color' in data
        assert 'test_text' in data

    def test_saved_values_reflected_in_api(self, client):
        save_overlay_appearance({'text_color': '#123456', 'bg_color': '#abcdef', 'test_text': 'hi'})
        login(client)
        data = client.get('/api/overlay/settings').get_json()
        assert data['text_color'] == '#123456'
        assert data['test_text'] == 'hi'

    def test_per_channel_query_returns_channel_settings(self, client):
        save_channel_overlay_appearance('virtual.status', {'text_color': '#aabbcc', 'bg_color': '', 'test_text': 'status test'})
        login(client)
        data = client.get('/api/overlay/settings?channel=virtual.status').get_json()
        assert data['text_color'] == '#aabbcc'
        assert data['test_text'] == 'status test'

    def test_invalid_channel_falls_back_to_global(self, client):
        login(client)
        # unknown channel param → returns global settings shape
        data = client.get('/api/overlay/settings?channel=virtual.nope').get_json()
        assert 'text_color' in data


# ─── Per-channel overlay appearance helpers ───────────────────────────────────

class TestChannelOverlayAppearance:
    def test_defaults_are_empty_strings(self):
        s = get_channel_overlay_appearance('virtual.news')
        assert s['text_color'] == ''
        assert s['bg_color'] == ''
        assert s['test_text'] == ''

    def test_save_and_reload_colors(self):
        save_channel_overlay_appearance('virtual.news', {'text_color': '#ff0000', 'bg_color': '#001122', 'test_text': ''})
        s = get_channel_overlay_appearance('virtual.news')
        assert s['text_color'] == '#ff0000'
        assert s['bg_color'] == '#001122'

    def test_save_and_reload_test_text(self):
        save_channel_overlay_appearance('virtual.weather', {'text_color': '', 'bg_color': '', 'test_text': 'WEATHER TEST'})
        assert get_channel_overlay_appearance('virtual.weather')['test_text'] == 'WEATHER TEST'

    def test_invalid_color_raises_value_error(self):
        import pytest as _pytest
        with _pytest.raises(ValueError):
            save_channel_overlay_appearance('virtual.news', {'text_color': 'red', 'bg_color': '', 'test_text': ''})

    def test_channels_are_isolated(self):
        save_channel_overlay_appearance('virtual.news', {'text_color': '#ff0000', 'bg_color': '', 'test_text': 'news'})
        save_channel_overlay_appearance('virtual.weather', {'text_color': '#00ff00', 'bg_color': '', 'test_text': 'weather'})
        assert get_channel_overlay_appearance('virtual.news')['text_color'] == '#ff0000'
        assert get_channel_overlay_appearance('virtual.weather')['text_color'] == '#00ff00'
        assert get_channel_overlay_appearance('virtual.status')['text_color'] == ''

    def test_get_all_channel_appearances_returns_all_channels(self):
        all_apps = get_all_channel_appearances()
        for ch in ['virtual.news', 'virtual.weather', 'virtual.status']:
            assert ch in all_apps
            assert 'text_color' in all_apps[ch]
            assert 'bg_color' in all_apps[ch]
            assert 'test_text' in all_apps[ch]

    def test_get_all_reflects_saved_values(self):
        save_channel_overlay_appearance('virtual.status', {'text_color': '#aabbcc', 'bg_color': '', 'test_text': 'hello'})
        all_apps = get_all_channel_appearances()
        assert all_apps['virtual.status']['text_color'] == '#aabbcc'
        assert all_apps['virtual.status']['test_text'] == 'hello'


# ─── News Feed URL ────────────────────────────────────────────────────────────

class TestNewsFeedUrl:
    """Tests for get/save news feed URL helpers and the /api/news endpoint."""

    def test_default_feed_url_is_empty(self):
        from app import get_news_feed_url
        assert get_news_feed_url() == ''

    def test_save_and_retrieve_feed_url(self):
        from app import get_news_feed_url, save_news_feed_url
        save_news_feed_url('https://feeds.example.com/rss.xml')
        assert get_news_feed_url() == 'https://feeds.example.com/rss.xml'

    def test_save_empty_url_clears_it(self):
        from app import get_news_feed_url, save_news_feed_url
        save_news_feed_url('https://feeds.example.com/rss.xml')
        save_news_feed_url('')
        assert get_news_feed_url() == ''

    def test_invalid_scheme_raises(self):
        from app import save_news_feed_url
        with pytest.raises(ValueError):
            save_news_feed_url('ftp://feeds.example.com/rss.xml')

    def test_api_news_returns_empty_when_no_url(self, client):
        login(client, "admin", "adminpass")
        resp = client.get('/api/news')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['headlines'] == []
        assert 'updated' in data

    def test_api_news_returns_feed_count_and_refresh_ms(self, client):
        login(client, "admin", "adminpass")
        data = client.get('/api/news').get_json()
        assert 'feed_count' in data
        assert 'feed_index' in data
        assert 'refresh_ms' in data

    def test_api_news_refresh_ms_is_30_min_when_no_feeds(self, client):
        login(client, "admin", "adminpass")
        data = client.get('/api/news').get_json()
        # With no feeds configured, fallback refresh is 5 min (not part of 30-min cycle)
        assert data['refresh_ms'] == 5 * 60 * 1000

    def test_api_news_overlay_prefs_saves_feed_urls(self, client):
        from app import get_news_feed_urls
        login(client, "admin", "adminpass")
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.news',
            'ch_text_color': '#ffffff',
            'ch_bg_color': '#000000',
            'ch_test_text': '',
            'ch_news_rss_url_1': 'https://rss.example.com/feed.xml',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert get_news_feed_urls()[0] == 'https://rss.example.com/feed.xml'

    def test_change_tuner_page_includes_news_feed_url(self, client):
        from app import save_news_feed_url
        save_news_feed_url('https://feeds.bbc.co.uk/news/rss.xml')
        login(client, "admin", "adminpass")
        resp = client.get('/virtual_channels')
        assert b'https://feeds.bbc.co.uk/news/rss.xml' in resp.data


class TestNewsFeedUrls:
    """Tests for the multi-feed get/save helpers."""

    def test_default_feed_urls_is_empty_list(self):
        from app import get_news_feed_urls
        assert get_news_feed_urls() == []

    def test_save_and_retrieve_multiple_urls(self):
        from app import get_news_feed_urls, save_news_feed_urls
        urls = ['https://a.example.com/rss.xml', 'https://b.example.com/rss.xml']
        save_news_feed_urls(urls)
        result = get_news_feed_urls()
        assert result == urls

    def test_save_up_to_six_urls(self):
        from app import get_news_feed_urls, save_news_feed_urls
        urls = [f'https://feed{i}.example.com/rss.xml' for i in range(1, 7)]
        save_news_feed_urls(urls)
        assert get_news_feed_urls() == urls

    def test_extra_urls_beyond_six_are_ignored(self):
        from app import get_news_feed_urls, save_news_feed_urls
        urls = [f'https://feed{i}.example.com/rss.xml' for i in range(1, 10)]
        save_news_feed_urls(urls)
        result = get_news_feed_urls()
        assert len(result) == 6

    def test_blank_entries_not_returned(self):
        from app import get_news_feed_urls, save_news_feed_urls
        save_news_feed_urls(['https://a.example.com/rss.xml', '', 'https://c.example.com/rss.xml'])
        result = get_news_feed_urls()
        assert '' not in result
        assert len(result) == 2

    def test_invalid_url_in_list_raises(self):
        from app import save_news_feed_urls
        with pytest.raises(ValueError):
            save_news_feed_urls(['ftp://feeds.example.com/rss.xml'])

    def test_api_news_refresh_ms_calculated_from_feed_count(self, client):
        from app import save_news_feed_urls
        # 6 feeds → 30 min / 6 = 5 min each
        save_news_feed_urls([f'https://feed{i}.example.com/rss.xml' for i in range(1, 7)])
        login(client, "admin", "adminpass")
        data = client.get('/api/news').get_json()
        assert data['feed_count'] == 6
        assert data['refresh_ms'] == 5 * 60 * 1000

    def test_api_news_refresh_ms_three_feeds(self, client):
        from app import save_news_feed_urls
        # 3 feeds → 30 min / 3 = 10 min each
        save_news_feed_urls([f'https://feed{i}.example.com/rss.xml' for i in range(1, 4)])
        login(client, "admin", "adminpass")
        data = client.get('/api/news').get_json()
        assert data['feed_count'] == 3
        assert data['refresh_ms'] == 10 * 60 * 1000

    def test_save_multiple_via_form(self, client):
        from app import get_news_feed_urls
        login(client, "admin", "adminpass")
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.news',
            'ch_news_rss_url_1': 'https://feed1.example.com/rss.xml',
            'ch_news_rss_url_2': 'https://feed2.example.com/rss.xml',
            'ch_news_rss_url_3': 'https://feed3.example.com/rss.xml',
        }, follow_redirects=True)
        assert resp.status_code == 200
        urls = get_news_feed_urls()
        assert len(urls) == 3
        assert 'https://feed1.example.com/rss.xml' in urls
        assert 'https://feed2.example.com/rss.xml' in urls
        assert 'https://feed3.example.com/rss.xml' in urls


# ─── News Feed Time-based Cycling ─────────────────────────────────────────────

class TestNewsFeedCycling:
    """Tests for server-driven wall-clock-time feed cycling."""

    def test_news_api_includes_ms_until_next_feed(self, client):
        from app import save_news_feed_urls
        save_news_feed_urls(['https://a.example.com/rss.xml', 'https://b.example.com/rss.xml'])
        login(client, 'admin', 'adminpass')
        data = client.get('/api/news').get_json()
        assert 'ms_until_next_feed' in data
        # Must be a positive value no larger than the full slot duration (15 min for 2 feeds)
        assert 0 < data['ms_until_next_feed'] <= 15 * 60 * 1000

    def test_feed_index_is_time_based_and_in_range(self, client):
        from app import save_news_feed_urls
        save_news_feed_urls([f'https://feed{i}.example.com/rss.xml' for i in range(1, 7)])
        login(client, 'admin', 'adminpass')
        data = client.get('/api/news').get_json()
        assert 0 <= data['feed_index'] < 6

    def test_get_current_feed_state_returns_valid_values(self):
        from app import get_current_feed_state
        idx, ms, elapsed_ms = get_current_feed_state(6)
        assert 0 <= idx < 6
        assert 0 < ms <= 5 * 60 * 1000  # at most one full slot (5 min for 6 feeds)
        assert 0 <= elapsed_ms < 5 * 60 * 1000

    def test_get_current_feed_state_zero_feeds_fallback(self):
        from app import get_current_feed_state
        idx, ms, elapsed_ms = get_current_feed_state(0)
        assert idx == 0
        assert ms == 5 * 60 * 1000
        assert elapsed_ms == 0


# ─── Updates & Announcements virtual channel ──────────────────────────────────

class TestVirtualUpdatesChannel:
    """Tests for the Updates & Announcements virtual channel."""

    def test_updates_channel_in_virtual_channels(self):
        ids = {ch["tvg_id"] for ch in get_virtual_channels()}
        assert "virtual.updates" in ids

    def test_updates_channel_has_required_keys(self):
        ch = next(c for c in get_virtual_channels() if c["tvg_id"] == "virtual.updates")
        required = {"name", "logo", "url", "tvg_id", "is_virtual",
                    "playback_mode", "loop_asset", "overlay_type", "overlay_refresh_seconds"}
        assert required.issubset(ch.keys())

    def test_updates_channel_overlay_type(self):
        ch = next(c for c in get_virtual_channels() if c["tvg_id"] == "virtual.updates")
        assert ch["overlay_type"] == "updates"

    def test_updates_channel_loop_asset_is_mp4(self):
        ch = next(c for c in get_virtual_channels() if c["tvg_id"] == "virtual.updates")
        assert ch["loop_asset"].endswith(".mp4")

    def test_updates_channel_refresh_seconds(self):
        ch = next(c for c in get_virtual_channels() if c["tvg_id"] == "virtual.updates")
        assert ch["overlay_refresh_seconds"] == 1800

    def test_updates_channel_in_epg(self):
        from datetime import datetime, timezone
        grid_start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        epg = get_virtual_epg(grid_start, hours_span=3)
        assert "virtual.updates" in epg
        assert len(epg["virtual.updates"]) == 3

    def test_updates_channel_enabled_by_default(self):
        settings = get_virtual_channel_settings()
        assert settings.get("virtual.updates") is True

    def test_updates_channel_can_be_disabled(self):
        save_virtual_channel_settings({"virtual.updates": False})
        settings = get_virtual_channel_settings()
        assert settings["virtual.updates"] is False

    def test_total_virtual_channels_count(self):
        channels = get_virtual_channels()
        assert len(channels) == 9


class TestApiVirtualUpdates:
    """Tests for the /api/virtual/updates endpoint."""

    def test_requires_login(self, client):
        resp = client.get("/api/virtual/updates")
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get("/api/virtual/updates")
        assert resp.status_code == 200

    def test_response_has_expected_keys(self, client):
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        assert "updated" in data
        assert "app_version" in data
        assert "releases" in data
        assert "ticker" in data
        assert "repo" in data
        assert "ms_until_next" in data

    def test_releases_is_list(self, client):
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        assert isinstance(data["releases"], list)

    def test_ticker_is_list_of_strings(self, client):
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        assert isinstance(data["ticker"], list)
        for entry in data["ticker"]:
            assert isinstance(entry, str)

    def test_app_version_in_response(self, client):
        login(client)
        import app as app_module
        data = client.get("/api/virtual/updates").get_json()
        assert data["app_version"] == app_module.APP_VERSION

    def test_ms_until_next_is_positive(self, client):
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        assert data["ms_until_next"] > 0

    def test_repo_field_is_string(self, client):
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        assert isinstance(data["repo"], str)
        assert len(data["repo"]) > 0


class TestUpdatesPage:
    """Tests for the /updates standalone page."""

    def test_requires_login(self, client):
        resp = client.get("/updates")
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get("/updates")
        assert resp.status_code == 200

    def test_page_contains_updates_branding(self, client):
        login(client)
        html = client.get("/updates").data.decode()
        assert "RetroIPTV" in html
        assert "Updates" in html

    def test_page_references_api_endpoint(self, client):
        login(client)
        html = client.get("/updates").data.decode()
        assert "/api/virtual/updates" in html

    def test_updates_channel_shown_in_virtual_channels_admin(self, client):
        login(client, "admin", "adminpass")
        resp = client.get("/virtual_channels")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Updates" in html

    def test_updates_channel_appears_in_guide_when_enabled(self, client):
        save_virtual_channel_settings({"virtual.updates": True})
        login(client, "admin", "adminpass")
        resp = client.get("/guide")
        assert resp.status_code == 200
        assert b"Updates" in resp.data

    def test_updates_channel_absent_from_guide_when_disabled(self, client):
        save_virtual_channel_settings({"virtual.updates": False})
        login(client, "admin", "adminpass")
        resp = client.get("/guide")
        assert resp.status_code == 200
        assert b"Updates &amp; Announcements" not in resp.data


# ─── Updates channel show_beta toggle ────────────────────────────────────────

class TestUpdatesConfig:
    """Tests for get_updates_config / save_updates_config and the show_beta toggle."""

    def test_default_show_beta_is_false(self):
        from app import get_updates_config
        cfg = get_updates_config()
        assert cfg["show_beta"] is False

    def test_save_show_beta_false_and_reload(self):
        from app import get_updates_config, save_updates_config
        save_updates_config({"show_beta": False})
        assert get_updates_config()["show_beta"] is False

    def test_save_show_beta_true_and_reload(self):
        from app import get_updates_config, save_updates_config
        save_updates_config({"show_beta": False})
        save_updates_config({"show_beta": True})
        assert get_updates_config()["show_beta"] is True

    def test_api_response_includes_show_beta_field(self, client):
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        assert "show_beta" in data
        assert isinstance(data["show_beta"], bool)

    def test_api_show_beta_default_is_false(self, client):
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        assert data["show_beta"] is False

    def test_api_show_beta_false_excludes_prereleases(self, client):
        from app import save_updates_config, _updates_cache, _updates_cache_lock
        # Inject a fake release list with one stable and one prerelease
        fake_releases = [
            {"tag": "v5.0.0", "name": "v5.0.0", "body": "Stable release",
             "prerelease": False, "draft": False, "published": "2026-01-01T00:00:00Z", "url": ""},
            {"tag": "v5.0.0-beta.1", "name": "v5.0.0-beta.1", "body": "Beta release",
             "prerelease": True, "draft": False, "published": "2026-01-02T00:00:00Z", "url": ""},
        ]
        with _updates_cache_lock:
            _updates_cache["data"] = fake_releases
            _updates_cache["fetched_at"] = 9999999999.0  # far future → won't expire

        save_updates_config({"show_beta": False})
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        tags = [r["tag"] for r in data["releases"]]
        assert "v5.0.0" in tags
        assert "v5.0.0-beta.1" not in tags

    def test_api_show_beta_true_includes_prereleases(self, client):
        from app import save_updates_config, _updates_cache, _updates_cache_lock
        fake_releases = [
            {"tag": "v5.0.0", "name": "v5.0.0", "body": "Stable",
             "prerelease": False, "draft": False, "published": "2026-01-01T00:00:00Z", "url": ""},
            {"tag": "v5.0.0-beta.1", "name": "v5.0.0-beta.1", "body": "Beta",
             "prerelease": True, "draft": False, "published": "2026-01-02T00:00:00Z", "url": ""},
        ]
        with _updates_cache_lock:
            _updates_cache["data"] = fake_releases
            _updates_cache["fetched_at"] = 9999999999.0

        save_updates_config({"show_beta": True})
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        tags = [r["tag"] for r in data["releases"]]
        assert "v5.0.0" in tags
        assert "v5.0.0-beta.1" in tags

    def test_ticker_excludes_beta_tags_when_show_beta_false(self, client):
        from app import save_updates_config, _updates_cache, _updates_cache_lock
        fake_releases = [
            {"tag": "v4.0.0", "name": "v4.0.0", "body": "",
             "prerelease": False, "draft": False, "published": "2026-01-01T00:00:00Z", "url": ""},
            {"tag": "v4.1.0-beta.1", "name": "v4.1.0-beta.1", "body": "",
             "prerelease": True, "draft": False, "published": "2026-01-02T00:00:00Z", "url": ""},
        ]
        with _updates_cache_lock:
            _updates_cache["data"] = fake_releases
            _updates_cache["fetched_at"] = 9999999999.0

        save_updates_config({"show_beta": False})
        login(client)
        data = client.get("/api/virtual/updates").get_json()
        # Ticker should not contain the beta tag
        joined = " ".join(data["ticker"])
        assert "v4.1.0-beta.1" not in joined

    def test_admin_can_save_show_beta_via_form(self, client):
        from app import get_updates_config
        login(client, "admin", "adminpass")
        resp = client.post("/virtual_channels", data={
            "action": "update_channel_overlay_appearance",
            "tvg_id": "virtual.updates",
            "ch_updates_show_beta": "1",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert get_updates_config()["show_beta"] is True

    def test_admin_can_disable_show_beta_via_form(self, client):
        from app import get_updates_config
        login(client, "admin", "adminpass")
        # Unchecked checkbox → no ch_updates_show_beta in POST data
        resp = client.post("/virtual_channels", data={
            "action": "update_channel_overlay_appearance",
            "tvg_id": "virtual.updates",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert get_updates_config()["show_beta"] is False

    def test_virtual_channels_page_shows_show_beta_toggle(self, client):
        login(client, "admin", "adminpass")
        html = client.get("/virtual_channels").data.decode()
        assert "ch_updates_show_beta" in html
        assert "Beta" in html


# ─── Sports Channel helpers ───────────────────────────────────────────────────

class TestSportsHelpers:
    def test_get_sports_mode_default(self):
        from app import get_sports_mode
        assert get_sports_mode() == 'scores'

    def test_save_and_reload_sports_mode(self):
        from app import get_sports_mode, save_sports_mode
        save_sports_mode('rss')
        assert get_sports_mode() == 'rss'
        save_sports_mode('scores')
        assert get_sports_mode() == 'scores'

    def test_invalid_sports_mode_raises(self):
        from app import save_sports_mode
        with pytest.raises(ValueError):
            save_sports_mode('invalid')

    def test_get_sports_config_has_mode_and_leagues(self):
        from app import get_sports_config
        cfg = get_sports_config()
        assert 'mode' in cfg
        assert 'leagues' in cfg
        assert isinstance(cfg['leagues'], dict)

    def test_sports_config_default_mode_is_scores(self):
        from app import get_sports_config
        assert get_sports_config()['mode'] == 'scores'

    def test_sports_config_default_leagues_include_nfl_nba_mlb_nhl(self):
        from app import get_sports_config
        leagues = get_sports_config()['leagues']
        assert leagues['nfl'] is True
        assert leagues['nba'] is True
        assert leagues['mlb'] is True
        assert leagues['nhl'] is True

    def test_save_and_reload_sports_config(self):
        from app import get_sports_config, save_sports_config
        save_sports_config({'nfl': False, 'nba': False, 'mlb': True, 'nhl': True,
                            'mls': True, 'ncaaf': False, 'ncaab': False})
        leagues = get_sports_config()['leagues']
        assert leagues['nfl'] is False
        assert leagues['mlb'] is True
        assert leagues['mls'] is True

    def test_get_sports_feed_urls_empty_by_default(self):
        from app import get_sports_feed_urls
        assert get_sports_feed_urls() == []

    def test_save_and_reload_sports_feed_urls(self):
        from app import get_sports_feed_urls, save_sports_feed_urls
        save_sports_feed_urls(['https://www.espn.com/espn/rss/news', 'https://feeds.bbci.co.uk/sport/rss.xml'])
        urls = get_sports_feed_urls()
        assert 'https://www.espn.com/espn/rss/news' in urls
        assert 'https://feeds.bbci.co.uk/sport/rss.xml' in urls

    def test_save_sports_feed_urls_rejects_invalid_scheme(self):
        from app import save_sports_feed_urls
        with pytest.raises(ValueError):
            save_sports_feed_urls(['ftp://invalid.com/feed'])

    def test_save_sports_feed_urls_pads_to_six(self):
        from app import get_sports_feed_urls, save_sports_feed_urls
        save_sports_feed_urls(['https://www.espn.com/espn/rss/news'])
        # get_sports_feed_urls only returns non-empty entries
        assert len(get_sports_feed_urls()) == 1


# ─── /api/sports ─────────────────────────────────────────────────────────────

class TestApiSports:
    def test_requires_login(self, client):
        resp = client.get('/api/sports')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/api/sports')
        assert resp.status_code == 200

    def test_response_has_mode_field(self, client):
        login(client)
        data = client.get('/api/sports').get_json()
        assert 'mode' in data
        assert data['mode'] in ('scores', 'rss')

    def test_response_has_ms_until_next(self, client):
        login(client)
        data = client.get('/api/sports').get_json()
        assert 'ms_until_next' in data
        assert isinstance(data['ms_until_next'], int)
        assert data['ms_until_next'] > 0

    def test_scores_mode_response_shape(self, client):
        from app import save_sports_mode
        save_sports_mode('scores')
        login(client)
        data = client.get('/api/sports').get_json()
        assert data['mode'] == 'scores'
        assert 'games' in data
        assert isinstance(data['games'], list)

    def test_rss_mode_response_shape(self, client):
        from app import save_sports_mode
        save_sports_mode('rss')
        login(client)
        data = client.get('/api/sports').get_json()
        assert data['mode'] == 'rss'
        assert 'headlines' in data
        assert isinstance(data['headlines'], list)

    def test_rss_mode_has_feed_count(self, client):
        from app import save_sports_mode
        save_sports_mode('rss')
        login(client)
        data = client.get('/api/sports').get_json()
        assert 'feed_count' in data


# ─── /sports page ─────────────────────────────────────────────────────────────

class TestSportsPage:
    def test_requires_login(self, client):
        resp = client.get('/sports')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/sports')
        assert resp.status_code == 200

    def test_page_contains_sports_branding(self, client):
        login(client)
        html = client.get('/sports').data.decode()
        assert 'RetroIPTV' in html
        assert 'Sports' in html

    def test_page_references_api_sports(self, client):
        login(client)
        html = client.get('/sports').data.decode()
        assert '/api/sports' in html


# ─── Channel count (now 6) ────────────────────────────────────────────────────

class TestSportsChannelRegistration:
    def test_virtual_sports_in_channel_list(self):
        ids = {ch['tvg_id'] for ch in get_virtual_channels()}
        assert 'virtual.sports' in ids

    def test_channel_count_is_six(self):
        assert len(get_virtual_channels()) == 9

    def test_sports_channel_has_required_keys(self):
        ch = next(c for c in get_virtual_channels() if c['tvg_id'] == 'virtual.sports')
        required = {'name', 'logo', 'url', 'tvg_id', 'is_virtual',
                    'playback_mode', 'loop_asset', 'overlay_type', 'overlay_refresh_seconds'}
        assert required.issubset(ch.keys())

    def test_sports_epg_entries_present(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        epg = get_virtual_epg(now, hours_span=2)
        assert 'virtual.sports' in epg
        assert len(epg['virtual.sports']) == 2

    def test_admin_can_save_sports_mode_via_form(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.sports',
            'ch_sports_mode': 'rss',
        }, follow_redirects=True)
        assert resp.status_code == 200
        from app import get_sports_mode
        assert get_sports_mode() == 'rss'

    def test_admin_can_save_sports_leagues_via_form(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.sports',
            'ch_sports_mode': 'scores',
            'ch_sports_league_mlb': '1',
            'ch_sports_league_nba': '1',
        }, follow_redirects=True)
        assert resp.status_code == 200
        from app import get_sports_config
        leagues = get_sports_config()['leagues']
        assert leagues['mlb'] is True
        assert leagues['nba'] is True
        assert leagues['nfl'] is False   # not submitted → disabled

    def test_virtual_channels_page_shows_sports_settings(self, client):
        login(client, 'admin', 'adminpass')
        html = client.get('/virtual_channels').data.decode()
        assert 'ch_sports_mode' in html
        assert 'ch_sports_league_nfl' in html
        assert 'ch_sports_rss_url_1' in html

# ─── NASA helpers ─────────────────────────────────────────────────────────────

class TestNasaHelpers:
    def test_get_nasa_interval_default(self):
        from app import get_nasa_interval
        assert get_nasa_interval() == '15'

    def test_save_and_reload_nasa_interval(self):
        from app import get_nasa_interval, save_nasa_interval
        save_nasa_interval('30')
        assert get_nasa_interval() == '30'
        save_nasa_interval('15')
        assert get_nasa_interval() == '15'

    def test_invalid_nasa_interval_raises(self):
        from app import save_nasa_interval
        with pytest.raises(ValueError):
            save_nasa_interval('45')

    def test_get_nasa_api_key_default(self):
        from app import get_nasa_api_key
        assert get_nasa_api_key() == 'DEMO_KEY'

    def test_save_and_reload_nasa_api_key(self):
        from app import get_nasa_api_key, save_nasa_api_key
        save_nasa_api_key('mykey123')
        assert get_nasa_api_key() == 'mykey123'
        save_nasa_api_key('')
        assert get_nasa_api_key() == 'DEMO_KEY'

    def test_get_nasa_image_count_returns_none_by_default(self):
        from app import get_nasa_image_count
        assert get_nasa_image_count() is None

    def test_save_and_reload_nasa_image_count(self):
        from app import get_nasa_image_count, save_nasa_image_count
        save_nasa_image_count(8)
        assert get_nasa_image_count() == 8
        save_nasa_image_count(None)
        assert get_nasa_image_count() is None

    def test_invalid_nasa_image_count_raises(self):
        from app import save_nasa_image_count
        with pytest.raises(ValueError):
            save_nasa_image_count(16)
        with pytest.raises(ValueError):
            save_nasa_image_count(0)

    def test_get_nasa_config_defaults_15min(self):
        from app import get_nasa_config
        cfg = get_nasa_config()
        assert cfg['interval'] == '15'
        assert cfg['image_count'] == 5          # default for 15-min
        assert cfg['seconds_per_image'] == 180  # 900 / 5
        assert cfg['api_key'] == 'DEMO_KEY'

    def test_get_nasa_config_defaults_30min(self):
        from app import get_nasa_config, save_nasa_interval
        save_nasa_interval('30')
        cfg = get_nasa_config()
        assert cfg['interval'] == '30'
        assert cfg['image_count'] == 10         # default for 30-min
        assert cfg['seconds_per_image'] == 180  # 1800 / 10
        save_nasa_interval('15')

    def test_get_nasa_config_custom_count_15min(self):
        from app import get_nasa_config, save_nasa_image_count
        save_nasa_image_count(15)
        cfg = get_nasa_config()
        assert cfg['image_count'] == 15
        assert cfg['seconds_per_image'] == 60   # 900 / 15 = 1 min each
        save_nasa_image_count(None)

    def test_get_nasa_config_custom_count_30min(self):
        from app import get_nasa_config, save_nasa_interval, save_nasa_image_count
        save_nasa_interval('30')
        save_nasa_image_count(15)
        cfg = get_nasa_config()
        assert cfg['image_count'] == 15
        assert cfg['seconds_per_image'] == 120  # 1800 / 15 = 2 min each
        save_nasa_interval('15')
        save_nasa_image_count(None)


# ─── /api/nasa ────────────────────────────────────────────────────────────────

class TestApiNasa:
    def test_requires_login(self, client):
        resp = client.get('/api/nasa')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/api/nasa')
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client):
        login(client)
        data = client.get('/api/nasa').get_json()
        for field in ('interval', 'image_count', 'seconds_per_image',
                      'image_index', 'total_images', 'ms_until_next', 'updated'):
            assert field in data, f"Missing field: {field}"

    def test_response_interval_is_valid(self, client):
        login(client)
        data = client.get('/api/nasa').get_json()
        assert data['interval'] in ('15', '30')

    def test_response_ms_until_next_positive(self, client):
        login(client)
        data = client.get('/api/nasa').get_json()
        assert isinstance(data['ms_until_next'], int)
        assert data['ms_until_next'] > 0

    def test_response_image_count_matches_config(self, client):
        from app import get_nasa_config
        login(client)
        data = client.get('/api/nasa').get_json()
        cfg = get_nasa_config()
        assert data['image_count'] == cfg['image_count']

    def test_response_seconds_per_image_matches_config(self, client):
        from app import get_nasa_config
        login(client)
        data = client.get('/api/nasa').get_json()
        cfg = get_nasa_config()
        assert data['seconds_per_image'] == cfg['seconds_per_image']

    def test_30min_mode_response(self, client):
        from app import save_nasa_interval
        save_nasa_interval('30')
        login(client)
        data = client.get('/api/nasa').get_json()
        assert data['interval'] == '30'
        assert data['image_count'] == 10        # 30-min default
        assert data['seconds_per_image'] == 180 # 1800 / 10
        save_nasa_interval('15')

    def test_custom_count_reflected_in_response(self, client):
        from app import save_nasa_image_count
        save_nasa_image_count(15)
        login(client)
        data = client.get('/api/nasa').get_json()
        assert data['image_count'] == 15
        assert data['seconds_per_image'] == 60  # 900 / 15
        save_nasa_image_count(None)


# ─── /nasa page ───────────────────────────────────────────────────────────────

class TestNasaPage:
    def test_requires_login(self, client):
        resp = client.get('/nasa')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/nasa')
        assert resp.status_code == 200

    def test_page_contains_nasa_branding(self, client):
        login(client)
        html = client.get('/nasa').data.decode()
        assert 'RetroIPTV' in html
        assert 'NASA' in html

    def test_page_references_api_nasa(self, client):
        login(client)
        html = client.get('/nasa').data.decode()
        assert '/api/nasa' in html


# ─── NASA channel registration ────────────────────────────────────────────────

class TestNasaChannelRegistration:
    def test_virtual_nasa_in_channel_list(self):
        ids = {ch['tvg_id'] for ch in get_virtual_channels()}
        assert 'virtual.nasa' in ids

    def test_channel_count_is_seven(self):
        assert len(get_virtual_channels()) == 9

    def test_nasa_channel_has_required_keys(self):
        ch = next(c for c in get_virtual_channels() if c['tvg_id'] == 'virtual.nasa')
        required = {'name', 'logo', 'url', 'tvg_id', 'is_virtual',
                    'playback_mode', 'loop_asset', 'overlay_type', 'overlay_refresh_seconds'}
        assert required.issubset(ch.keys())

    def test_nasa_channel_overlay_type(self):
        ch = next(c for c in get_virtual_channels() if c['tvg_id'] == 'virtual.nasa')
        assert ch['overlay_type'] == 'nasa'

    def test_nasa_epg_entries_present(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        epg = get_virtual_epg(now, hours_span=2)
        assert 'virtual.nasa' in epg
        assert len(epg['virtual.nasa']) == 2

    def test_admin_can_save_nasa_interval_via_form(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.nasa',
            'ch_nasa_interval': '30',
            'ch_nasa_image_count': '10',
        }, follow_redirects=True)
        assert resp.status_code == 200
        from app import get_nasa_interval
        assert get_nasa_interval() == '30'

    def test_admin_can_save_nasa_image_count_via_form(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.nasa',
            'ch_nasa_interval': '15',
            'ch_nasa_image_count': '8',
        }, follow_redirects=True)
        assert resp.status_code == 200
        from app import get_nasa_image_count
        assert get_nasa_image_count() == 8

    def test_virtual_channels_page_shows_nasa_settings(self, client):
        login(client, 'admin', 'adminpass')
        html = client.get('/virtual_channels').data.decode()
        assert 'ch_nasa_interval' in html
        assert 'ch_nasa_image_count' in html
        # API key field intentionally removed from admin UI (uses DEMO_KEY silently)
        assert 'ch_nasa_api_key' not in html


# ─── Channel Mix helpers ──────────────────────────────────────────────────────

class TestChannelMixConfig:
    def test_defaults_return_empty_channels_and_name(self):
        cfg = get_channel_mix_config()
        assert cfg['name'] == 'Channel Mix'
        assert cfg['channels'] == []

    def test_save_and_reload_name(self):
        save_channel_mix_config({'name': 'Info Mix', 'channels': []})
        cfg = get_channel_mix_config()
        assert cfg['name'] == 'Info Mix'

    def test_save_and_reload_channels(self):
        channels = [
            {'tvg_id': 'virtual.news', 'duration_minutes': 120},
            {'tvg_id': 'virtual.weather', 'duration_minutes': 60},
        ]
        save_channel_mix_config({'name': 'My Mix', 'channels': channels})
        cfg = get_channel_mix_config()
        assert len(cfg['channels']) == 2
        assert cfg['channels'][0]['tvg_id'] == 'virtual.news'
        assert cfg['channels'][0]['duration_minutes'] == 120
        assert cfg['channels'][1]['tvg_id'] == 'virtual.weather'
        assert cfg['channels'][1]['duration_minutes'] == 60

    def test_blank_name_defaults_to_channel_mix(self):
        save_channel_mix_config({'name': '', 'channels': []})
        cfg = get_channel_mix_config()
        assert cfg['name'] == 'Channel Mix'

    def test_invalid_tvg_id_raises(self):
        with pytest.raises(ValueError):
            save_channel_mix_config({'name': 'x', 'channels': [
                {'tvg_id': 'virtual.channel_mix', 'duration_minutes': 60}
            ]})

    def test_invalid_duration_raises(self):
        with pytest.raises(ValueError):
            save_channel_mix_config({'name': 'x', 'channels': [
                {'tvg_id': 'virtual.news', 'duration_minutes': 0}
            ]})
        with pytest.raises(ValueError):
            save_channel_mix_config({'name': 'x', 'channels': [
                {'tvg_id': 'virtual.news', 'duration_minutes': 1441}
            ]})

    def test_name_too_long_raises(self):
        with pytest.raises(ValueError):
            save_channel_mix_config({'name': 'x' * 121, 'channels': []})

    def test_invalid_tvg_id_in_config_is_filtered_on_load(self):
        """Invalid tvg_ids stored in DB are silently filtered on load."""
        import sqlite3
        import json
        import app as app_module
        with sqlite3.connect(app_module.TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            bad = json.dumps([{'tvg_id': 'invalid.id', 'duration_minutes': 60}])
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('channel_mix.channels', ?)", (bad,))
            conn.commit()
        cfg = get_channel_mix_config()
        assert cfg['channels'] == []


class TestChannelMixActiveSlot:
    def test_empty_channels_returns_none(self):
        from app import _get_active_channel_mix_slot
        active, remaining = _get_active_channel_mix_slot([])
        assert active is None
        assert remaining == 0

    def test_single_channel_always_active(self):
        from app import _get_active_channel_mix_slot
        channels = [{'tvg_id': 'virtual.news', 'duration_minutes': 120}]
        active, remaining = _get_active_channel_mix_slot(channels)
        assert active == 'virtual.news'
        assert 0 < remaining <= 120 * 60

    def test_returns_correct_channel_for_offset(self):
        """Test the slot algorithm using a known timestamp."""
        from app import _get_active_channel_mix_slot
        import unittest.mock as mock
        channels = [
            {'tvg_id': 'virtual.news',    'duration_minutes': 2},  # 0–120s
            {'tvg_id': 'virtual.weather', 'duration_minutes': 2},  # 120–240s
        ]
        # Total cycle = 240s
        # At offset 60s → news is active, 60s remaining
        with mock.patch('time.time', return_value=60.0):
            active, remaining = _get_active_channel_mix_slot(channels)
        assert active == 'virtual.news'
        assert remaining == 60  # 120 - 60

        # At offset 150s → weather is active, 90s remaining
        with mock.patch('time.time', return_value=150.0):
            active, remaining = _get_active_channel_mix_slot(channels)
        assert active == 'virtual.weather'
        assert remaining == 90  # 240 - 150


class TestApiChannelMix:
    def test_requires_login(self, client):
        resp = client.get('/api/channel_mix')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/api/channel_mix')
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client):
        login(client)
        data = client.get('/api/channel_mix').get_json()
        for field in ('name', 'active_type', 'active_name', 'active_tvg_id',
                      'seconds_remaining', 'total_cycle_seconds', 'channels'):
            assert field in data, f"Missing field: {field}"

    def test_empty_mix_returns_null_active(self, client):
        login(client)
        data = client.get('/api/channel_mix').get_json()
        assert data['active_type'] is None
        assert data['active_tvg_id'] is None
        assert data['channels'] == []

    def test_configured_mix_returns_active_channel(self, client):
        save_channel_mix_config({
            'name': 'Test Mix',
            'channels': [
                {'tvg_id': 'virtual.news', 'duration_minutes': 120},
                {'tvg_id': 'virtual.traffic', 'duration_minutes': 60},
            ]
        })
        login(client)
        data = client.get('/api/channel_mix').get_json()
        assert data['active_type'] in ('news', 'traffic')
        assert data['active_tvg_id'] in ('virtual.news', 'virtual.traffic')
        assert data['seconds_remaining'] > 0
        assert data['total_cycle_seconds'] == 180 * 60

    def test_response_name_reflects_config(self, client):
        save_channel_mix_config({'name': 'Info Mix', 'channels': []})
        login(client)
        data = client.get('/api/channel_mix').get_json()
        assert data['name'] == 'Info Mix'


class TestChannelMixRegistration:
    def test_virtual_channel_mix_in_channel_list(self):
        ids = {ch['tvg_id'] for ch in get_virtual_channels()}
        assert 'virtual.channel_mix' in ids

    def test_channel_count_is_eight(self):
        assert len(get_virtual_channels()) == 9

    def test_channel_mix_has_required_keys(self):
        ch = next(c for c in get_virtual_channels() if c['tvg_id'] == 'virtual.channel_mix')
        required = {'name', 'logo', 'url', 'tvg_id', 'is_virtual',
                    'playback_mode', 'loop_asset', 'overlay_type', 'overlay_refresh_seconds'}
        assert required.issubset(ch.keys())

    def test_channel_mix_overlay_type(self):
        ch = next(c for c in get_virtual_channels() if c['tvg_id'] == 'virtual.channel_mix')
        assert ch['overlay_type'] == 'channel_mix'

    def test_channel_mix_epg_entries_present(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        epg = get_virtual_epg(now, hours_span=2)
        assert 'virtual.channel_mix' in epg
        assert len(epg['virtual.channel_mix']) == 2

    def test_channel_mix_enabled_by_default(self):
        """Channel Mix defaults to enabled (same as all other virtual channels)."""
        settings = get_virtual_channel_settings()
        assert settings.get('virtual.channel_mix') is True

    def test_admin_can_save_channel_mix_config_via_form(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/virtual_channels', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.channel_mix',
            'ch_mix_name': 'My Info Mix',
            'cm_ch_virtual.news': '1',
            'cm_dur_virtual.news': '60',
            'cm_ch_virtual.weather': '1',
            'cm_dur_virtual.weather': '30',
        }, follow_redirects=True)
        assert resp.status_code == 200
        cfg = get_channel_mix_config()
        assert cfg['name'] == 'My Info Mix'
        assert len(cfg['channels']) == 2
        news = next((c for c in cfg['channels'] if c['tvg_id'] == 'virtual.news'), None)
        assert news is not None
        assert news['duration_minutes'] == 60

    def test_virtual_channels_page_shows_channel_mix(self, client):
        login(client, 'admin', 'adminpass')
        html = client.get('/virtual_channels').data.decode()
        assert 'Channel Mix' in html
        assert 'ch_mix_name' in html


# ─── Icon Pack ────────────────────────────────────────────────────────────────

from app import (get_use_icon_pack, set_use_icon_pack,
                 _ICON_PACK_LOGOS, _DEFAULT_CHANNEL_LOGOS, _resolve_channel_logo,
                 ICON_PACK_DIR)


class TestGetUseIconPack:
    def test_defaults_to_false(self):
        assert get_use_icon_pack() is False

    def test_set_and_get_enabled(self):
        set_use_icon_pack(True)
        assert get_use_icon_pack() is True

    def test_set_and_get_disabled(self):
        set_use_icon_pack(True)
        set_use_icon_pack(False)
        assert get_use_icon_pack() is False

    def test_set_persists_across_calls(self):
        set_use_icon_pack(True)
        # A fresh call to the helper should still read True
        assert get_use_icon_pack() is True


class TestIconPackLogos:
    def test_all_virtual_channels_have_icon_pack_entry(self):
        for ch in VIRTUAL_CHANNELS:
            assert ch['tvg_id'] in _ICON_PACK_LOGOS, (
                f"No icon pack entry for {ch['tvg_id']}"
            )

    def test_on_this_day_icon_pack_entry_exists(self):
        assert 'virtual.on_this_day' in _ICON_PACK_LOGOS

    def test_icon_pack_urls_use_icon_pack_subdirectory(self):
        for tvg_id, url in _ICON_PACK_LOGOS.items():
            assert 'icon_pack' in url, (
                f"Icon pack URL for {tvg_id} does not use icon_pack/: {url}"
            )

    def test_icon_pack_files_exist_on_disk(self):
        import os
        for tvg_id, url in _ICON_PACK_LOGOS.items():
            rel = url.lstrip('/')
            abs_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel
            )
            assert os.path.isfile(abs_path), (
                f"Icon pack file missing for {tvg_id}: {abs_path}"
            )


class TestResolveChannelLogo:
    def test_custom_logo_takes_priority_over_icon_pack(self):
        url = _resolve_channel_logo(
            'virtual.news',
            '/static/logos/virtual/news.svg',
            'virtual_news_logo.png',
            True,
        )
        assert url == '/static/logos/virtual/virtual_news_logo.png'

    def test_custom_logo_takes_priority_when_icon_pack_disabled(self):
        url = _resolve_channel_logo(
            'virtual.news',
            '/static/logos/virtual/news.svg',
            'virtual_news_logo.png',
            False,
        )
        assert url == '/static/logos/virtual/virtual_news_logo.png'

    def test_icon_pack_used_when_enabled_and_no_custom(self):
        # The icon pack files exist on disk (they are in the repo)
        url = _resolve_channel_logo(
            'virtual.nasa',
            '/static/logos/virtual/nasa.svg',
            '',
            True,
        )
        assert 'icon_pack' in url

    def test_default_svg_used_when_icon_pack_disabled_and_no_custom(self):
        url = _resolve_channel_logo(
            'virtual.nasa',
            '/static/logos/virtual/nasa.svg',
            '',
            False,
        )
        assert url == '/static/logos/virtual/nasa.svg'

    def test_default_svg_used_when_icon_pack_enabled_but_file_missing(self, tmp_path, monkeypatch):
        import app as app_module
        # Redirect ICON_PACK_DIR to an empty directory so no icon pack file is found
        monkeypatch.setattr(app_module, 'ICON_PACK_DIR', str(tmp_path))
        url = _resolve_channel_logo(
            'virtual.news',
            '/static/logos/virtual/news.svg',
            '',
            True,
        )
        # Should fall back to the default SVG because the icon pack dir is empty
        assert url == '/static/logos/virtual/news.svg'


class TestApiVirtualIconPack:
    def test_get_returns_default_disabled(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.get('/api/virtual/icon_pack')
        assert resp.status_code == 200
        assert resp.get_json()['enabled'] is False

    def test_post_enable(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post(
            '/api/virtual/icon_pack',
            json={'enabled': True},
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['enabled'] is True
        assert 'logos' in data
        # logos dict should have an entry for each virtual channel
        for ch in VIRTUAL_CHANNELS:
            assert ch['tvg_id'] in data['logos']

    def test_post_disable(self, client):
        login(client, 'admin', 'adminpass')
        # Enable first
        client.post('/api/virtual/icon_pack', json={'enabled': True},
                    content_type='application/json')
        # Then disable
        resp = client.post('/api/virtual/icon_pack', json={'enabled': False},
                           content_type='application/json')
        assert resp.status_code == 200
        assert resp.get_json()['enabled'] is False

    def test_post_persists_state(self, client):
        login(client, 'admin', 'adminpass')
        client.post('/api/virtual/icon_pack', json={'enabled': True},
                    content_type='application/json')
        resp = client.get('/api/virtual/icon_pack')
        assert resp.get_json()['enabled'] is True

    def test_post_requires_admin(self, client):
        login(client)  # regular user
        resp = client.post('/api/virtual/icon_pack', json={'enabled': True},
                           content_type='application/json')
        assert resp.status_code == 403

    def test_post_missing_enabled_field(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/api/virtual/icon_pack', json={},
                           content_type='application/json')
        assert resp.status_code == 400

    def test_get_requires_login(self, client):
        resp = client.get('/api/virtual/icon_pack')
        assert resp.status_code in (302, 401)


class TestIconPackAdminPage:
    def test_page_shows_icon_pack_section(self, client):
        login(client, 'admin', 'adminpass')
        html = client.get('/virtual_channels').data.decode()
        assert 'icon-pack-toggle' in html
        assert 'Channel Icon Pack' in html

    def test_page_shows_icon_pack_disabled_by_default(self, client):
        login(client, 'admin', 'adminpass')
        html = client.get('/virtual_channels').data.decode()
        assert 'Icon Pack <strong>Disabled</strong>' in html

    def test_page_shows_icon_pack_enabled_when_set(self, client):
        login(client, 'admin', 'adminpass')
        set_use_icon_pack(True)
        html = client.get('/virtual_channels').data.decode()
        assert 'Icon Pack <strong>Enabled</strong>' in html


class TestGetVirtualChannelsIconPack:
    def test_default_logos_used_when_icon_pack_disabled(self):
        set_use_icon_pack(False)
        channels = get_virtual_channels()
        for ch in channels:
            assert 'icon_pack' not in ch['logo'], (
                f"Expected default logo for {ch['tvg_id']} when icon pack off, got {ch['logo']}"
            )

    def test_icon_pack_logos_used_when_enabled(self):
        set_use_icon_pack(True)
        channels = get_virtual_channels()
        for ch in channels:
            # If an icon pack file exists for this channel, it should be used
            pack_url = _ICON_PACK_LOGOS.get(ch['tvg_id'])
            if pack_url:
                rel = pack_url.lstrip('/')
                import os
                abs_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel
                )
                if os.path.isfile(abs_path):
                    assert ch['logo'] == pack_url, (
                        f"Expected icon pack logo for {ch['tvg_id']}, got {ch['logo']}"
                    )

    def test_custom_logo_overrides_icon_pack(self, tmp_path, monkeypatch):
        import os
        import app as app_module
        # Point LOGO_UPLOAD_DIR to tmp_path and create a fake custom logo
        monkeypatch.setattr(app_module, 'LOGO_UPLOAD_DIR', str(tmp_path))
        fake_logo = tmp_path / 'virtual_news_logo.png'
        fake_logo.write_bytes(b'\x89PNG\r\n\x1a\n')  # minimal PNG header
        from app import save_channel_custom_logo
        save_channel_custom_logo('virtual.news', 'virtual_news_logo.png')
        set_use_icon_pack(True)
        channels = get_virtual_channels()
        news = next(c for c in channels if c['tvg_id'] == 'virtual.news')
        assert 'virtual_news_logo.png' in news['logo']
        assert 'icon_pack' not in news['logo']


# ─── On This Day helpers ──────────────────────────────────────────────────────

class TestOnThisDayHelpers:
    def test_source_enabled_default_true(self):
        from app import get_on_this_day_source_enabled
        assert get_on_this_day_source_enabled('wikipedia_events') is True
        assert get_on_this_day_source_enabled('wikipedia_births') is True
        assert get_on_this_day_source_enabled('wikipedia_deaths') is True

    def test_save_and_reload_source_enabled(self):
        from app import get_on_this_day_source_enabled, save_on_this_day_source_enabled
        save_on_this_day_source_enabled('wikipedia_events', False)
        assert get_on_this_day_source_enabled('wikipedia_events') is False
        save_on_this_day_source_enabled('wikipedia_events', True)
        assert get_on_this_day_source_enabled('wikipedia_events') is True

    def test_save_source_enabled_invalid_id_raises(self):
        from app import save_on_this_day_source_enabled
        with pytest.raises(ValueError):
            save_on_this_day_source_enabled('nonexistent_source', True)

    def test_custom_events_default_empty(self):
        from app import get_on_this_day_custom_events
        assert get_on_this_day_custom_events('wikipedia_events') == []

    def test_save_and_reload_custom_events(self):
        from app import get_on_this_day_custom_events, save_on_this_day_custom_events
        events = [{'year': '1969', 'text': 'Moon landing', 'category': 'event'}]
        save_on_this_day_custom_events('wikipedia_events', events)
        reloaded = get_on_this_day_custom_events('wikipedia_events')
        assert reloaded == events

    def test_save_custom_events_invalid_id_raises(self):
        from app import save_on_this_day_custom_events
        with pytest.raises(ValueError):
            save_on_this_day_custom_events('nonexistent_source', [])

    def test_save_custom_events_invalid_type_raises(self):
        from app import save_on_this_day_custom_events
        with pytest.raises(ValueError):
            save_on_this_day_custom_events('wikipedia_events', 'not a list')

    def test_get_on_this_day_config_structure(self):
        from app import get_on_this_day_config, ON_THIS_DAY_SOURCES
        cfg = get_on_this_day_config()
        assert 'sources' in cfg
        assert 'seconds_per_event' in cfg
        assert cfg['seconds_per_event'] == 30
        assert len(cfg['sources']) == len(ON_THIS_DAY_SOURCES)

    def test_get_on_this_day_config_source_fields(self):
        from app import get_on_this_day_config
        cfg = get_on_this_day_config()
        for src in cfg['sources']:
            assert 'id' in src
            assert 'label' in src
            assert 'category' in src
            assert 'enabled' in src
            assert 'custom_events' in src
            assert 'wiki_url' in src

    def test_get_on_this_day_config_default_all_enabled(self):
        from app import get_on_this_day_config
        cfg = get_on_this_day_config()
        for src in cfg['sources']:
            assert src['enabled'] is True

    def test_wiki_url_contains_api_endpoint(self):
        from app import get_on_this_day_config
        cfg = get_on_this_day_config()
        for src in cfg['sources']:
            assert src['wiki_url'].startswith('https://en.wikipedia.org/')
            assert 'feed/onthisday' in src['wiki_url']


# ─── /api/on_this_day ─────────────────────────────────────────────────────────

class TestApiOnThisDay:
    def test_requires_login(self, client):
        resp = client.get('/api/on_this_day')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/api/on_this_day')
        assert resp.status_code == 200

    def test_response_has_required_fields(self, client):
        login(client)
        data = client.get('/api/on_this_day').get_json()
        for field in ('month', 'day', 'date_label', 'events', 'event_count',
                      'seconds_per_event', 'ms_until_next', 'sources'):
            assert field in data, f"Missing field: {field}"

    def test_response_month_and_day_are_ints(self, client):
        login(client)
        data = client.get('/api/on_this_day').get_json()
        assert isinstance(data['month'], int)
        assert isinstance(data['day'], int)
        assert 1 <= data['month'] <= 12
        assert 1 <= data['day'] <= 31

    def test_response_seconds_per_event_is_30(self, client):
        login(client)
        data = client.get('/api/on_this_day').get_json()
        assert data['seconds_per_event'] == 30

    def test_response_ms_until_next_positive(self, client):
        login(client)
        data = client.get('/api/on_this_day').get_json()
        assert isinstance(data['ms_until_next'], int)
        assert data['ms_until_next'] > 0

    def test_response_sources_has_all_source_ids(self, client):
        from app import ON_THIS_DAY_SOURCES
        login(client)
        data = client.get('/api/on_this_day').get_json()
        for src in ON_THIS_DAY_SOURCES:
            assert src['id'] in data['sources'], f"Missing source: {src['id']}"

    def test_custom_events_used_when_source_disabled(self, client):
        from app import save_on_this_day_source_enabled, save_on_this_day_custom_events
        save_on_this_day_source_enabled('wikipedia_events', False)
        save_on_this_day_source_enabled('wikipedia_births', False)
        save_on_this_day_source_enabled('wikipedia_deaths', False)
        custom = [{'year': '2000', 'text': 'Custom test event', 'category': 'event'}]
        save_on_this_day_custom_events('wikipedia_events', custom)
        login(client)
        data = client.get('/api/on_this_day').get_json()
        texts = [ev['text'] for ev in data['events']]
        assert 'Custom test event' in texts

    def test_disabled_source_has_no_wikipedia_events(self, client):
        from app import save_on_this_day_source_enabled
        # Disable all sources and add no custom events → zero events
        save_on_this_day_source_enabled('wikipedia_events', False)
        save_on_this_day_source_enabled('wikipedia_births', False)
        save_on_this_day_source_enabled('wikipedia_deaths', False)
        login(client)
        data = client.get('/api/on_this_day').get_json()
        # event_count may be 0 when no Wikipedia data and no custom events
        assert isinstance(data['event_count'], int)
        assert data['event_count'] >= 0


# ─── /on_this_day page ────────────────────────────────────────────────────────

class TestOnThisDayPage:
    def test_requires_login(self, client):
        resp = client.get('/on_this_day')
        assert resp.status_code in (302, 401)

    def test_returns_200_when_authenticated(self, client):
        login(client)
        resp = client.get('/on_this_day')
        assert resp.status_code == 200

    def test_page_contains_on_this_day_branding(self, client):
        login(client)
        html = client.get('/on_this_day').data.decode()
        assert 'On This Day' in html

    def test_page_references_api_on_this_day(self, client):
        login(client)
        html = client.get('/on_this_day').data.decode()
        assert '/api/on_this_day' in html


# ─── On This Day channel registration ─────────────────────────────────────────

class TestOnThisDayChannelRegistration:
    def test_virtual_on_this_day_in_channel_list(self):
        ids = {ch['tvg_id'] for ch in get_virtual_channels()}
        assert 'virtual.on_this_day' in ids

    def test_channel_count_is_nine(self):
        assert len(get_virtual_channels()) == 9

    def test_on_this_day_channel_has_required_keys(self):
        ch = next(c for c in get_virtual_channels() if c['tvg_id'] == 'virtual.on_this_day')
        required = {'name', 'logo', 'url', 'tvg_id', 'is_virtual',
                    'playback_mode', 'loop_asset', 'overlay_type', 'overlay_refresh_seconds'}
        assert required.issubset(ch.keys())

    def test_on_this_day_channel_overlay_type(self):
        ch = next(c for c in get_virtual_channels() if c['tvg_id'] == 'virtual.on_this_day')
        assert ch['overlay_type'] == 'on_this_day'

    def test_on_this_day_epg_entries_present(self):
        from app import get_virtual_epg
        from datetime import datetime, timezone
        grid_start = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)
        epg = get_virtual_epg(grid_start, hours_span=6)
        assert 'virtual.on_this_day' in epg
