"""Tests for per-user channel preferences: API endpoint, DB helpers, and
manage_users admin actions (set_user_prefs)."""
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
    monkeypatch.setattr(app_module, "DATABASE",   users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",   tuners_db)
    init_db()
    init_tuners_db()
    # Create test users
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


# ─── Unit tests: get_user_prefs / save_user_prefs ────────────────────────────

class TestUserPrefsHelpers:
    def test_default_prefs_returned_for_new_user(self):
        prefs = get_user_prefs("newuser")
        assert prefs["auto_load_channel"] is None
        assert prefs["hidden_channels"] == []
        assert prefs["sizzle_reels_enabled"] is False

    def test_all_default_keys_present(self):
        prefs = get_user_prefs("nobody")
        for key in _DEFAULT_PREFS:
            assert key in prefs

    def test_save_and_retrieve(self):
        save_user_prefs("testuser", {
            "auto_load_channel": {"id": "ch1", "name": "Channel 1"},
            "hidden_channels": ["ch2", "ch3"],
            "sizzle_reels_enabled": True,
        })
        prefs = get_user_prefs("testuser")
        assert prefs["auto_load_channel"] == {"id": "ch1", "name": "Channel 1"}
        assert prefs["hidden_channels"] == ["ch2", "ch3"]
        assert prefs["sizzle_reels_enabled"] is True

    def test_upsert_overwrites_existing(self):
        save_user_prefs("testuser", {"auto_load_channel": {"id": "old", "name": "Old"},
                                     "hidden_channels": [], "sizzle_reels_enabled": False})
        save_user_prefs("testuser", {"auto_load_channel": None,
                                     "hidden_channels": ["x"],
                                     "sizzle_reels_enabled": True})
        prefs = get_user_prefs("testuser")
        assert prefs["auto_load_channel"] is None
        assert prefs["hidden_channels"] == ["x"]
        assert prefs["sizzle_reels_enabled"] is True

    def test_missing_keys_filled_with_defaults(self):
        """Partial JSON stored in DB should still return all expected keys."""
        import sqlite3
        db = app_module.DATABASE
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO user_preferences (username, prefs) VALUES (?, ?)",
                ("partial", json.dumps({"sizzle_reels_enabled": True}))
            )
        prefs = get_user_prefs("partial")
        assert prefs["auto_load_channel"] is None   # filled from defaults
        assert prefs["hidden_channels"] == []       # filled from defaults
        assert prefs["sizzle_reels_enabled"] is True

    def test_graceful_on_missing_table(self, monkeypatch, tmp_path):
        """get_user_prefs should return defaults if the table doesn't exist yet."""
        empty_db = str(tmp_path / "empty.db")
        import sqlite3
        # Create DB with only the users table (simulate pre-migration state)
        with sqlite3.connect(empty_db) as conn:
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        monkeypatch.setattr(app_module, "DATABASE", empty_db)
        prefs = get_user_prefs("nobody")
        assert prefs == dict(_DEFAULT_PREFS)

    def test_save_auto_heals_missing_table(self, monkeypatch, tmp_path):
        """save_user_prefs should call init_db() and retry when table is missing."""
        empty_db = str(tmp_path / "empty2.db")
        import sqlite3
        with sqlite3.connect(empty_db) as conn:
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        monkeypatch.setattr(app_module, "DATABASE", empty_db)
        # Should not raise — auto-heals by calling init_db() then retrying
        save_user_prefs("alice", {"auto_load_channel": None,
                                  "hidden_channels": [],
                                  "sizzle_reels_enabled": False})
        prefs = get_user_prefs("alice")
        assert prefs["hidden_channels"] == []


# ─── API endpoint: GET /api/user_prefs ───────────────────────────────────────

class TestApiUserPrefsGet:
    def test_requires_login(self, client):
        resp = client.get("/api/user_prefs")
        assert resp.status_code in (302, 401)

    def test_returns_defaults_for_new_user(self, client):
        login(client)
        resp = client.get("/api/user_prefs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["auto_load_channel"] is None
        assert data["hidden_channels"] == []
        assert data["sizzle_reels_enabled"] is False

    def test_returns_saved_prefs(self, client):
        login(client)
        save_user_prefs("testuser", {"auto_load_channel": {"id": "abc", "name": "ABC"},
                                     "hidden_channels": ["x"], "sizzle_reels_enabled": True})
        resp = client.get("/api/user_prefs")
        data = resp.get_json()
        assert data["auto_load_channel"]["id"] == "abc"
        assert "x" in data["hidden_channels"]
        assert data["sizzle_reels_enabled"] is True


# ─── API endpoint: POST /api/user_prefs ──────────────────────────────────────

class TestApiUserPrefsPost:
    def test_requires_login(self, client):
        resp = client.post("/api/user_prefs",
                           data=json.dumps({}), content_type="application/json")
        assert resp.status_code in (302, 401)

    def test_set_auto_load_channel(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"auto_load_channel": {"id": "ch1", "name": "News"}}),
                           content_type="application/json")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert body["prefs"]["auto_load_channel"]["id"] == "ch1"
        # Verify persisted
        assert get_user_prefs("testuser")["auto_load_channel"]["id"] == "ch1"

    def test_clear_auto_load_channel(self, client):
        login(client)
        save_user_prefs("testuser", {"auto_load_channel": {"id": "ch1", "name": "News"},
                                     "hidden_channels": [], "sizzle_reels_enabled": False})
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"auto_load_channel": None}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert get_user_prefs("testuser")["auto_load_channel"] is None

    def test_add_hidden_channel(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"hidden_channels": ["sports", "news"]}),
                           content_type="application/json")
        assert resp.status_code == 200
        prefs = get_user_prefs("testuser")
        assert "sports" in prefs["hidden_channels"]
        assert "news" in prefs["hidden_channels"]

    def test_toggle_sizzle_reels(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data=json.dumps({"sizzle_reels_enabled": True}),
                           content_type="application/json")
        assert resp.status_code == 200
        assert get_user_prefs("testuser")["sizzle_reels_enabled"] is True

    def test_partial_update_preserves_other_keys(self, client):
        login(client)
        save_user_prefs("testuser", {"auto_load_channel": {"id": "ch1", "name": "News"},
                                     "hidden_channels": ["x"], "sizzle_reels_enabled": True})
        # Only update sizzle_reels_enabled
        client.post("/api/user_prefs",
                    data=json.dumps({"sizzle_reels_enabled": False}),
                    content_type="application/json")
        prefs = get_user_prefs("testuser")
        assert prefs["auto_load_channel"]["id"] == "ch1"   # unchanged
        assert prefs["hidden_channels"] == ["x"]           # unchanged
        assert prefs["sizzle_reels_enabled"] is False      # updated

    def test_invalid_json_returns_400(self, client):
        login(client)
        resp = client.post("/api/user_prefs",
                           data="not json", content_type="application/json")
        assert resp.status_code == 400

    def test_auto_load_missing_id_clears_pref(self, client):
        """auto_load_channel with no 'id' key should be treated as clearing it."""
        login(client)
        save_user_prefs("testuser", {"auto_load_channel": {"id": "ch1", "name": "x"},
                                     "hidden_channels": [], "sizzle_reels_enabled": False})
        client.post("/api/user_prefs",
                    data=json.dumps({"auto_load_channel": {}}),
                    content_type="application/json")
        assert get_user_prefs("testuser")["auto_load_channel"] is None


# ─── Admin: manage_users set_user_prefs action ───────────────────────────────

class TestManageUsersSetPrefs:
    def test_non_admin_cannot_set_prefs(self, client):
        login(client, "testuser", "testpass")
        resp = client.post("/manage_users", data={
            "action": "set_user_prefs",
            "username": "testuser",
        }, follow_redirects=True)
        # Non-admins are redirected away from manage_users; prefs remain unchanged
        assert get_user_prefs("testuser")["auto_load_channel"] is None

    def test_auto_load_channel_name_from_form_field(self, client):
        """Channel name must come from the submitted auto_load_channel_name form
        field, not from a server-side lookup against cached_channels."""
        login(client, "admin", "adminpass")
        resp = client.post("/manage_users", data={
            "action": "set_user_prefs",
            "username": "testuser",
            "auto_load_channel_id": "tvg-xyz",
            "auto_load_channel_name": "My Channel XYZ",
        }, follow_redirects=True)
        assert resp.status_code == 200
        prefs = get_user_prefs("testuser")
        assert prefs["auto_load_channel"]["id"] == "tvg-xyz"
        # Name must be what the form submitted, not a cached_channels lookup
        assert prefs["auto_load_channel"]["name"] == "My Channel XYZ"

    def test_auto_load_channel_name_falls_back_to_id(self, client):
        """If auto_load_channel_name is missing, the ID is used as the name."""
        login(client, "admin", "adminpass")
        resp = client.post("/manage_users", data={
            "action": "set_user_prefs",
            "username": "testuser",
            "auto_load_channel_id": "tvg-fallback",
            # no auto_load_channel_name submitted
        }, follow_redirects=True)
        assert resp.status_code == 200
        prefs = get_user_prefs("testuser")
        assert prefs["auto_load_channel"]["id"] == "tvg-fallback"
        assert prefs["auto_load_channel"]["name"] == "tvg-fallback"

    def test_manage_users_get_returns_200_for_admin(self, client):
        """GET /manage_users renders without error for admin."""
        login(client, "admin", "adminpass")
        resp = client.get("/manage_users")
        assert resp.status_code == 200

    def test_manage_users_includes_user_prefs_in_response(self, client):
        """After setting prefs, a GET of manage_users reflects the saved values."""
        save_user_prefs("testuser", {
            "auto_load_channel": {"id": "ch99", "name": "Test Ch"},
            "hidden_channels": [],
            "sizzle_reels_enabled": False,
        })
        login(client, "admin", "adminpass")
        resp = client.get("/manage_users")
        assert resp.status_code == 200
        # The saved channel name should appear in the rendered page
        assert b"Test Ch" in resp.data

    def test_user_api_update_reflected_in_admin_panel(self, client):
        """When the user updates their auto_load_channel via /api/user_prefs,
        the admin manage_users page should reflect the new value."""
        # User logs in and sets their channel via the REST API
        login(client, "testuser", "testpass")
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"auto_load_channel": {"id": "api-set-ch", "name": "API Set Channel"}}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        # Log out testuser, log in as admin
        client.get("/logout")
        login(client, "admin", "adminpass")
        resp = client.get("/manage_users")
        assert resp.status_code == 200
        assert b"API Set Channel" in resp.data

    def test_assign_tuner_change_clears_auto_load_channel(self, client):
        """Reassigning a user to a different tuner must wipe their auto-load channel."""
        save_user_prefs("testuser", {
            "auto_load_channel": {"id": "old-ch", "name": "Old Tuner Channel"},
            "hidden_channels": [],
            "sizzle_reels_enabled": False,
        })
        # Give testuser an initial assigned_tuner
        login(client, "admin", "adminpass")
        client.post("/manage_users", data={
            "action": "assign_tuner",
            "username": "testuser",
            "tuner_name": "Tuner 1",
        }, follow_redirects=True)
        # auto_load was set, tuner was None → Tuner 1, so it should be cleared
        assert get_user_prefs("testuser")["auto_load_channel"] is None

    def test_assign_tuner_same_tuner_keeps_auto_load_channel(self, client):
        """Re-assigning the SAME tuner must NOT clear the auto-load channel."""
        save_user_prefs("testuser", {
            "auto_load_channel": {"id": "keep-ch", "name": "Keep This Channel"},
            "hidden_channels": [],
            "sizzle_reels_enabled": False,
        })
        login(client, "admin", "adminpass")
        # First, assign Tuner 1 to testuser (tuner was None → Tuner 1, so auto_load clears here)
        client.post("/manage_users", data={
            "action": "assign_tuner",
            "username": "testuser",
            "tuner_name": "Tuner 1",
        }, follow_redirects=True)
        # Now set prefs again after the tuner is already Tuner 1
        save_user_prefs("testuser", {
            "auto_load_channel": {"id": "keep-ch", "name": "Keep This Channel"},
            "hidden_channels": [],
            "sizzle_reels_enabled": False,
        })
        # Re-assign the SAME tuner — channel must be preserved
        client.post("/manage_users", data={
            "action": "assign_tuner",
            "username": "testuser",
            "tuner_name": "Tuner 1",
        }, follow_redirects=True)
        prefs = get_user_prefs("testuser")
        assert prefs["auto_load_channel"] is not None
        assert prefs["auto_load_channel"]["id"] == "keep-ch"

    def test_manage_users_response_has_no_store_header(self, client):
        """GET /manage_users must return Cache-Control: no-store so browsers
        always fetch a fresh copy rather than serving a cached page."""
        login(client, "admin", "adminpass")
        resp = client.get("/manage_users")
        assert resp.status_code == 200
        assert 'no-store' in resp.headers.get('Cache-Control', '')

    def test_combined_tuner_channels_shown_in_manage_users(self, client):
        """A user assigned to a combined tuner (non-active) should have its merged
        channel list available in the manage_users page channel-selector dropdown."""
        from app import add_combined_tuner
        from unittest.mock import patch

        # The default tuners DB already has Tuner 1 and Tuner 2.
        # Create a combined tuner that merges both.
        add_combined_tuner("My Combined", ["Tuner 1", "Tuner 2"])

        # Assign testuser to the combined tuner.
        login(client, "admin", "adminpass")
        client.post("/manage_users", data={
            "action": "assign_tuner",
            "username": "testuser",
            "tuner_name": "My Combined",
        }, follow_redirects=True)

        # Mock load_tuner_data so we control what channels come back without
        # real network calls.
        fake_channels = [
            {"tvg_id": "combo-ch1", "name": "Combined Channel One", "url": "", "logo": ""},
            {"tvg_id": "combo-ch2", "name": "Combined Channel Two", "url": "", "logo": ""},
        ]
        with patch("app.load_tuner_data", return_value=(fake_channels, {})):
            resp = client.get("/manage_users")

        assert resp.status_code == 200
        assert b"Combined Channel One" in resp.data
        assert b"Combined Channel Two" in resp.data

    def test_active_combined_tuner_channels_shown_in_manage_users(self, client):
        """When the combined tuner IS the active (current) tuner, its merged
        channels must still appear in manage_users for users defaulting to that tuner.

        This exercises the path where cached_channels is populated via
        load_tuner_data() during a tuner switch rather than via raw m3u access.
        """
        from app import add_combined_tuner
        from unittest.mock import patch
        import app as app_module

        add_combined_tuner("Active Combined", ["Tuner 1", "Tuner 2"])

        fake_channels = [
            {"tvg_id": "act-ch1", "name": "Active Combined Channel", "url": "", "logo": ""},
        ]

        login(client, "admin", "adminpass")
        # Switch to the combined tuner; the fixed code calls load_tuner_data() to
        # populate cached_channels so combined tuners' channels are available.
        with patch("app.load_tuner_data", return_value=(fake_channels, {})):
            client.post("/change_tuner", data={
                "action": "switch_tuner",
                "tuner": "Active Combined",
            }, follow_redirects=True)

        # testuser has no assigned_tuner, so manage_users uses curr_tuner
        # ("Active Combined") and falls into the `ch_list = cached_channels` path.
        # cached_channels must now contain the fake channels set during the switch.
        resp = client.get("/manage_users")
        assert resp.status_code == 200
        assert b"Active Combined Channel" in resp.data
