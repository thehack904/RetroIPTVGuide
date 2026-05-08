"""Tests for the channel logo field in the /api/current_program endpoint (issue #198)."""
import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, add_user


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE", users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",  tuners_db)
    init_db()
    init_tuners_db()
    add_user("admin", "adminpass")
    yield


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client, username="admin", password="adminpass"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_channels(logo="https://example.com/logo.png"):
    return [{"tvg_id": "test.ch1", "name": "Test Channel 1", "logo": logo, "number": "1"}]


def _make_epg(tvg_id="test.ch1"):
    now = datetime.now(timezone.utc)
    return {
        tvg_id: [
            {
                "title": "Test Show",
                "desc": "A test description",
                "start": now - timedelta(minutes=15),
                "stop":  now + timedelta(minutes=45),
            }
        ]
    }


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestCurrentProgramLogoField:
    """The /api/current_program response must include a top-level 'logo' field."""

    def test_logo_present_in_response(self, client, monkeypatch):
        """Response includes 'logo' key with the channel's logo URL."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/api/current_program?tvg_id=test.ch1")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert "logo" in body
        assert body["logo"] == "https://example.com/logo.png"

    def test_logo_empty_string_when_no_logo(self, client, monkeypatch):
        """When the channel has no logo, 'logo' is an empty string (not None/absent)."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels(logo=""))
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/api/current_program?tvg_id=test.ch1")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "logo" in body
        assert body["logo"] == ""

    def test_logo_empty_string_when_logo_is_none(self, client, monkeypatch):
        """When the channel logo field is None, 'logo' is normalised to ''."""
        channels = [{"tvg_id": "test.ch1", "name": "Test Channel", "logo": None, "number": "1"}]
        monkeypatch.setattr(app_module, "cached_channels", channels)
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/api/current_program?tvg_id=test.ch1")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "logo" in body
        assert body["logo"] == ""

    def test_logo_present_when_no_guide_data(self, client, monkeypatch):
        """'logo' is returned even when no EPG program is available."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      {})
        login(client)
        resp = client.get("/api/current_program?tvg_id=test.ch1")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert "logo" in body
        assert body["logo"] == "https://example.com/logo.png"

    def test_program_fields_still_present(self, client, monkeypatch):
        """Existing program fields are not broken by the logo addition."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/api/current_program?tvg_id=test.ch1")
        body = resp.get_json()
        assert body["ok"] is True
        assert body["channel"] == "Test Channel 1"
        assert body["tvg_id"]  == "test.ch1"
        prog = body["program"]
        assert prog["title"] == "Test Show"
        assert prog["desc"]  == "A test description"
        assert prog["start_iso"] is not None
        assert prog["stop_iso"]  is not None
