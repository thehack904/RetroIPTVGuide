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
                 VIRTUAL_CHANNELS)


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
        assert len(channels) == 3

    def test_all_have_is_virtual_true(self):
        for ch in get_virtual_channels():
            assert ch.get("is_virtual") is True

    def test_known_tvg_ids_present(self):
        ids = {ch["tvg_id"] for ch in get_virtual_channels()}
        assert "virtual.news" in ids
        assert "virtual.weather" in ids
        assert "virtual.status" in ids

    def test_each_has_required_keys(self):
        required = {"name", "logo", "url", "tvg_id", "is_virtual",
                    "playback_mode", "loop_asset", "overlay_type", "overlay_refresh_seconds"}
        for ch in get_virtual_channels():
            assert required.issubset(ch.keys()), f"Missing keys in {ch['tvg_id']}"

    def test_loop_assets_are_mp4_paths(self):
        for ch in get_virtual_channels():
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
        resp = client.get("/change_tuner")
        assert b"Virtual Channels" in resp.data

    def test_admin_can_disable_virtual_channel(self, client):
        login(client, "admin", "adminpass")
        # Omit news (unchecked) — only submit checked channels, matching real browser behaviour
        resp = client.post("/change_tuner", data={
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
        })
        login(client, "admin", "adminpass")
        resp = client.post("/change_tuner", data={
            "action": "update_virtual_channels",
            "vc_virtual.news": "1",
            "vc_virtual.weather": "1",
            "vc_virtual.status": "1",
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
        resp = client.get('/change_tuner')
        # Each channel has a per-channel settings button; overlay action present in page
        assert b'update_channel_overlay_appearance' in resp.data

    def test_admin_can_save_per_channel_appearance(self, client):
        login(client, 'admin', 'adminpass')
        resp = client.post('/change_tuner', data={
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
        resp = client.post('/change_tuner', data={
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
        resp = client.post('/change_tuner', data={
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
        client.post('/change_tuner', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '',
            'ch_bg_color': '',
            'ch_test_text': '',
        }, follow_redirects=True)
        assert get_channel_overlay_appearance('virtual.weather')['test_text'] == ''

    def test_channels_can_have_independent_settings(self, client):
        login(client, 'admin', 'adminpass')
        client.post('/change_tuner', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.status',
            'ch_text_color': '#ff0000',
            'ch_bg_color': '',
            'ch_test_text': 'status test',
        }, follow_redirects=True)
        # Weather channel: appearance fields are always cleared via HTTP route
        client.post('/change_tuner', data={
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
        client.post('/change_tuner', data={
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
        client.post('/change_tuner', data={
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
        resp = client.post('/change_tuner', data={
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
        resp = client.get('/change_tuner')
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
        resp = client.post('/change_tuner', data={
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
        idx, ms = get_current_feed_state(6)
        assert 0 <= idx < 6
        assert 0 < ms <= 5 * 60 * 1000  # at most one full slot (5 min for 6 feeds)

    def test_get_current_feed_state_zero_feeds_fallback(self):
        from app import get_current_feed_state
        idx, ms = get_current_feed_state(0)
        assert idx == 0
        assert ms == 5 * 60 * 1000
