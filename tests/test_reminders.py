"""Tests for the reminders / notifications feature (v4.9.7)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, add_user, _DEFAULT_PREFS


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE",   users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",   tuners_db)
    init_db()
    init_tuners_db()
    add_user("admin", "adminpass")
    yield


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "adminpass"},
        follow_redirects=True,
    )


# ─── Default prefs ────────────────────────────────────────────────────────────

class TestRemindersDefaultPrefs:
    def test_reminders_key_exists_in_default_prefs(self):
        assert "reminders" in _DEFAULT_PREFS

    def test_reminders_empty_by_default(self):
        assert _DEFAULT_PREFS["reminders"] == []

    def test_user_prefs_api_includes_reminders(self, client):
        login(client)
        resp = client.get("/api/user_prefs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reminders" in data
        assert data["reminders"] == []


# ─── API sanitization ─────────────────────────────────────────────────────────

_VALID_REMINDER = {
    "id": "abc123",
    "channel_id": "ch.bbc1",
    "channel_name": "BBC One",
    "program_title": "The News at Ten",
    "program_start": "2026-06-17T22:00:00",
    "notify_before_mins": 5,
}


class TestRemindersApiSanitization:
    def test_set_single_reminder(self, client):
        login(client)
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [_VALID_REMINDER]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        reminders = data["prefs"]["reminders"]
        assert len(reminders) == 1
        r = reminders[0]
        assert r["channel_id"] == "ch.bbc1"
        assert r["program_title"] == "The News at Ten"
        assert r["notify_before_mins"] == 5

    def test_non_list_reminders_coerced_to_empty(self, client):
        login(client)
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": "not-a-list"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["prefs"]["reminders"] == []

    def test_reminder_without_id_is_dropped(self, client):
        login(client)
        bad = dict(_VALID_REMINDER)
        del bad["id"]
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [bad]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["prefs"]["reminders"] == []

    def test_reminder_without_channel_id_is_dropped(self, client):
        login(client)
        bad = dict(_VALID_REMINDER)
        del bad["channel_id"]
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [bad]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["prefs"]["reminders"] == []

    def test_notify_before_out_of_range_defaults_to_5(self, client):
        login(client)
        bad = dict(_VALID_REMINDER)
        bad["notify_before_mins"] = 999
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [bad]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        r = resp.get_json()["prefs"]["reminders"][0]
        assert r["notify_before_mins"] == 5

    def test_notify_before_string_defaults_to_5(self, client):
        login(client)
        bad = dict(_VALID_REMINDER)
        bad["notify_before_mins"] = "ten"
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [bad]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        r = resp.get_json()["prefs"]["reminders"][0]
        assert r["notify_before_mins"] == 5

    def test_notify_before_zero_is_valid(self, client):
        login(client)
        r = dict(_VALID_REMINDER)
        r["notify_before_mins"] = 0
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [r]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        result = resp.get_json()["prefs"]["reminders"][0]
        assert result["notify_before_mins"] == 0

    def test_reminders_capped_at_max(self, client):
        from app import _MAX_REMINDERS
        login(client)
        many = []
        for i in range(_MAX_REMINDERS + 10):
            r = dict(_VALID_REMINDER)
            r["id"] = f"id-{i}"
            many.append(r)
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": many}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        saved = resp.get_json()["prefs"]["reminders"]
        assert len(saved) == _MAX_REMINDERS

    def test_non_dict_items_in_list_are_dropped(self, client):
        login(client)
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [_VALID_REMINDER, "string", 42, None]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        saved = resp.get_json()["prefs"]["reminders"]
        assert len(saved) == 1

    def test_clear_reminders(self, client):
        login(client)
        # First set one
        client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [_VALID_REMINDER]}),
            content_type="application/json",
        )
        # Then clear
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": []}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["prefs"]["reminders"] == []

    def test_reminder_requires_login(self, client):
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"reminders": [_VALID_REMINDER]}),
            content_type="application/json",
        )
        assert resp.status_code in (302, 401)


# ─── Guide template includes reminders.js and header buttons ─────────────────

class TestRemindersGuideMarkup:
    def test_guide_includes_reminders_script(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "reminders.js" in html

    def test_guide_header_includes_desktop_reminders_btn(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="remindersBtn"' in html

    def test_guide_header_includes_mobile_reminders_btn(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="mobileRemindersBtn"' in html
