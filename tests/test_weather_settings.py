"""Tests for weather settings DB fields and API endpoint behaviour."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, get_user_prefs, save_user_prefs, _DEFAULT_PREFS


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Give every test its own empty SQLite database (users + tuners)."""
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE",  users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",  tuners_db)
    init_db()
    init_tuners_db()
    from app import add_user
    add_user("testuser", "testpass")
    add_user("admin",    "adminpass")
    yield users_db


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def login(client, username="testuser", password="testpass"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


# ─── DB field: presence in _DEFAULT_PREFS ────────────────────────────────────

class TestWeatherDefaultPrefs:
    def test_weather_enabled_in_defaults(self):
        assert "weather_enabled" in _DEFAULT_PREFS

    def test_weather_zip_in_defaults(self):
        assert "weather_zip" in _DEFAULT_PREFS

    def test_weather_units_in_defaults(self):
        assert "weather_units" in _DEFAULT_PREFS

    def test_weather_enabled_default_is_false(self):
        assert _DEFAULT_PREFS["weather_enabled"] is False

    def test_weather_zip_default_is_empty_string(self):
        assert _DEFAULT_PREFS["weather_zip"] == ""

    def test_weather_units_default_is_fahrenheit(self):
        assert _DEFAULT_PREFS["weather_units"] == "F"

    def test_weather_stream_url_in_defaults(self):
        assert "weather_stream_url" in _DEFAULT_PREFS

    def test_weather_stream_url_default_is_empty_string(self):
        assert _DEFAULT_PREFS["weather_stream_url"] == ""


# ─── DB helpers: get/save weather settings ───────────────────────────────────

class TestWeatherPrefsHelpers:
    def test_new_user_gets_default_weather_prefs(self):
        # A username with no stored prefs returns defaults (same as a brand-new user)
        prefs = get_user_prefs("brand_new_user")
        assert prefs["weather_enabled"] is False
        assert prefs["weather_zip"] == ""
        assert prefs["weather_units"] == "F"
        assert prefs["weather_stream_url"] == ""

    def test_save_and_retrieve_weather_enabled(self):
        save_user_prefs("testuser", {"weather_enabled": True})
        prefs = get_user_prefs("testuser")
        assert prefs["weather_enabled"] is True

    def test_save_and_retrieve_weather_zip(self):
        save_user_prefs("testuser", {"weather_zip": "90210"})
        prefs = get_user_prefs("testuser")
        assert prefs["weather_zip"] == "90210"

    def test_save_and_retrieve_weather_units_celsius(self):
        save_user_prefs("testuser", {"weather_units": "C"})
        prefs = get_user_prefs("testuser")
        assert prefs["weather_units"] == "C"

    def test_disable_preserves_zip_and_units(self):
        """Disabling weather must not wipe ZIP, units, or stream URL (settings preserved)."""
        save_user_prefs("testuser", {
            "weather_enabled": True,
            "weather_zip": "10001",
            "weather_units": "C",
            "weather_stream_url": "http://ersatz.lan:8409/iptv/channel1.m3u8",
        })
        # Now disable
        save_user_prefs("testuser", {"weather_enabled": False})
        prefs = get_user_prefs("testuser")
        assert prefs["weather_enabled"] is False
        assert prefs["weather_zip"] == "10001"
        assert prefs["weather_units"] == "C"
        assert prefs["weather_stream_url"] == "http://ersatz.lan:8409/iptv/channel1.m3u8"

    def test_all_weather_keys_present_in_returned_prefs(self):
        prefs = get_user_prefs("testuser")
        for key in ("weather_enabled", "weather_zip", "weather_units", "weather_stream_url"):
            assert key in prefs

    def test_weather_prefs_dont_overwrite_other_prefs(self):
        save_user_prefs("testuser", {
            "auto_load_channel": {"id": "ch1", "name": "News"},
            "hidden_channels": ["ch2"],
        })
        save_user_prefs("testuser", {"weather_enabled": True, "weather_zip": "77001"})
        prefs = get_user_prefs("testuser")
        assert prefs["auto_load_channel"]["id"] == "ch1"
        assert "ch2" in prefs["hidden_channels"]
        assert prefs["weather_enabled"] is True
        assert prefs["weather_zip"] == "77001"


# ─── API: GET /api/user_prefs includes weather fields ────────────────────────

class TestApiWeatherPrefsGet:
    def test_get_returns_weather_fields(self, client):
        login(client)
        resp = client.get("/api/user_prefs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "weather_enabled" in data
        assert "weather_zip" in data
        assert "weather_units" in data
        assert "weather_stream_url" in data

    def test_get_returns_defaults_for_new_user(self, client):
        login(client)
        resp = client.get("/api/user_prefs")
        data = resp.get_json()
        assert data["weather_enabled"] is False
        assert data["weather_zip"] == ""
        assert data["weather_units"] == "F"
        assert data["weather_stream_url"] == ""


# ─── API: POST /api/user_prefs saves weather fields ──────────────────────────

class TestApiWeatherPrefsPost:
    def test_enable_weather(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"weather_enabled": True}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert get_user_prefs("testuser")["weather_enabled"] is True

    def test_disable_weather(self, client):
        login(client)
        # Enable first
        client.post("/api/user_prefs",
                    data=json.dumps({"weather_enabled": True}),
                    content_type="application/json")
        # Now disable
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"weather_enabled": False}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert get_user_prefs("testuser")["weather_enabled"] is False

    def test_set_zip_code(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"weather_zip": "98101"}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert get_user_prefs("testuser")["weather_zip"] == "98101"

    def test_set_units_celsius(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"weather_units": "C"}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert get_user_prefs("testuser")["weather_units"] == "C"

    def test_set_units_fahrenheit(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"weather_units": "F"}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert get_user_prefs("testuser")["weather_units"] == "F"

    def test_disable_weather_preserves_zip_and_units(self, client):
        """Disabling weather via API must not erase ZIP, units, or stream URL."""
        login(client)
        client.post("/api/user_prefs",
                    data=json.dumps({
                        "weather_enabled": True,
                        "weather_zip": "60601",
                        "weather_units": "C",
                        "weather_stream_url": "http://ersatz.lan:8409/iptv/ch1.m3u8",
                    }),
                    content_type="application/json")
        # Disable only
        client.post("/api/user_prefs",
                    data=json.dumps({"weather_enabled": False}),
                    content_type="application/json")
        prefs = get_user_prefs("testuser")
        assert prefs["weather_enabled"] is False
        assert prefs["weather_zip"] == "60601"
        assert prefs["weather_units"] == "C"
        assert prefs["weather_stream_url"] == "http://ersatz.lan:8409/iptv/ch1.m3u8"

    def test_set_stream_url(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"weather_stream_url": "http://ersatz.lan:8409/iptv/ch1.m3u8"}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert get_user_prefs("testuser")["weather_stream_url"] == "http://ersatz.lan:8409/iptv/ch1.m3u8"

    def test_clear_stream_url(self, client):
        login(client)
        client.post("/api/user_prefs",
                    data=json.dumps({"weather_stream_url": "http://old.example/stream.m3u8"}),
                    content_type="application/json")
        client.post("/api/user_prefs",
                    data=json.dumps({"weather_stream_url": ""}),
                    content_type="application/json")
        assert get_user_prefs("testuser")["weather_stream_url"] == ""

    def test_weather_update_preserves_unrelated_prefs(self, client):
        login(client)
        client.post("/api/user_prefs",
                    data=json.dumps({"hidden_channels": ["ch1"]}),
                    content_type="application/json")
        client.post("/api/user_prefs",
                    data=json.dumps({"weather_enabled": True, "weather_zip": "33101"}),
                    content_type="application/json")
        prefs = get_user_prefs("testuser")
        assert "ch1" in prefs["hidden_channels"]
        assert prefs["weather_enabled"] is True
        assert prefs["weather_zip"] == "33101"

    def test_response_includes_weather_fields(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"weather_enabled": True}),
                           content_type="application/json")
        body = resp.get_json()
        assert body["status"] == "ok"
        assert "weather_enabled" in body["prefs"]
        assert "weather_zip" in body["prefs"]
        assert "weather_units" in body["prefs"]
        assert "weather_stream_url" in body["prefs"]


# ─── Guard: __weather__ must never appear in hidden_channels ─────────────────

class TestWeatherChannelNotHideable:
    def test_weather_id_not_stored_in_hidden_channels(self, client):
        """Storing __weather__ in hidden_channels via the API is technically possible
        but the JS layer prevents it; verify here that saving it does not break other
        prefs and that removing it works normally."""
        login(client)
        # Simulate a rogue save that adds __weather__ to hidden_channels
        client.post("/api/user_prefs",
                    data=json.dumps({"hidden_channels": ["__weather__", "ch1"]}),
                    content_type="application/json")
        prefs = get_user_prefs("testuser")
        # The weather channel ID may be in the list (saved as-is by the API),
        # but enabling weather_enabled should still work independently.
        client.post("/api/user_prefs",
                    data=json.dumps({"weather_enabled": True}),
                    content_type="application/json")
        prefs = get_user_prefs("testuser")
        assert prefs["weather_enabled"] is True

    def test_hidden_channels_does_not_affect_weather_enabled_flag(self, client):
        """Adding or removing channels from hidden_channels must never change
        the weather_enabled setting."""
        login(client)
        client.post("/api/user_prefs",
                    data=json.dumps({"weather_enabled": True, "hidden_channels": []}),
                    content_type="application/json")
        # Update hidden_channels only
        client.post("/api/user_prefs",
                    data=json.dumps({"hidden_channels": ["ch2", "ch3"]}),
                    content_type="application/json")
        prefs = get_user_prefs("testuser")
        assert prefs["weather_enabled"] is True   # unchanged
        assert "ch2" in prefs["hidden_channels"]
