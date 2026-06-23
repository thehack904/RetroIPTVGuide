"""Tests for the /api/channel_health endpoint (lightweight health indicators)."""
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, add_user


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


# ─── User prefs ───────────────────────────────────────────────────────────────

class TestChannelHealthUserPrefs:
    def test_user_prefs_api_does_not_include_channel_health(self, client):
        login(client)
        resp = client.get("/api/user_prefs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "channel_health_enabled" not in data

    def test_channel_health_pref_is_not_persisted(self, client):
        login(client)
        resp = client.post(
            "/api/user_prefs",
            data=json.dumps({"channel_health_enabled": True}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "channel_health_enabled" not in data["prefs"]


# ─── /api/channel_health endpoint ────────────────────────────────────────────

class TestChannelHealthEndpoint:
    def test_requires_login(self, client):
        resp = client.post(
            "/api/channel_health",
            data=json.dumps({"channel_ids": []}),
            content_type="application/json",
        )
        # Unauthenticated → redirect to login
        assert resp.status_code in (302, 401)

    def test_empty_batch_returns_empty_results(self, client):
        login(client)
        resp = client.post(
            "/api/channel_health",
            data=json.dumps({"channel_ids": []}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"results": {}}

    def test_invalid_json_returns_400(self, client):
        login(client)
        resp = client.post(
            "/api/channel_health",
            data="not-json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_channel_ids_must_be_list(self, client):
        login(client)
        resp = client.post(
            "/api/channel_health",
            data=json.dumps({"channel_ids": "not-a-list"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unknown_channel_ids_return_virtual(self, client, monkeypatch):
        """Channels not in cached_channels (no URL) should return 'virtual'."""
        monkeypatch.setattr(app_module, "cached_channels", [])
        login(client)
        resp = client.post(
            "/api/channel_health",
            data=json.dumps({"channel_ids": ["ch.unknown"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"]["ch.unknown"] == "virtual"

    def test_reachable_channel_returns_up(self, client, monkeypatch):
        """A channel whose URL returns HTTP 200 should be reported as 'up'."""
        monkeypatch.setattr(app_module, "cached_channels", [
            {"tvg_id": "ch.live", "url": "http://example.com/stream.m3u8"},
        ])
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        login(client)
        with patch("app.requests.head", return_value=mock_resp):
            resp = client.post(
                "/api/channel_health",
                data=json.dumps({"channel_ids": ["ch.live"]}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"]["ch.live"] == "up"

    def test_unreachable_channel_returns_down(self, client, monkeypatch):
        """A channel whose URL raises an exception should be reported as 'down'."""
        monkeypatch.setattr(app_module, "cached_channels", [
            {"tvg_id": "ch.dead", "url": "http://dead.example.com/stream"},
        ])
        login(client)
        with patch("app.requests.head", side_effect=Exception("connection refused")):
            with patch("app.requests.get", side_effect=Exception("connection refused")):
                resp = client.post(
                    "/api/channel_health",
                    data=json.dumps({"channel_ids": ["ch.dead"]}),
                    content_type="application/json",
                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"]["ch.dead"] == "down"

    def test_channel_without_http_url_returns_virtual(self, client, monkeypatch):
        """Channels with non-http(s) scheme (e.g. rtmp://) are treated as virtual."""
        monkeypatch.setattr(app_module, "cached_channels", [
            {"tvg_id": "ch.rtmp", "url": "rtmp://example.com/live/stream"},
        ])
        login(client)
        resp = client.post(
            "/api/channel_health",
            data=json.dumps({"channel_ids": ["ch.rtmp"]}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"]["ch.rtmp"] == "virtual"

    def test_batch_size_capped(self, client, monkeypatch):
        """Batches larger than _HEALTH_CHECK_MAX_BATCH should be silently truncated."""
        from app import _HEALTH_CHECK_MAX_BATCH
        monkeypatch.setattr(app_module, "cached_channels", [])
        channel_ids = [f"ch.{i}" for i in range(_HEALTH_CHECK_MAX_BATCH + 20)]
        login(client)
        resp = client.post(
            "/api/channel_health",
            data=json.dumps({"channel_ids": channel_ids}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Should only have processed up to the cap
        assert len(data["results"]) <= _HEALTH_CHECK_MAX_BATCH

    def test_mixed_batch_results(self, client, monkeypatch):
        """Mixed batch: live + dead + virtual channels."""
        monkeypatch.setattr(app_module, "cached_channels", [
            {"tvg_id": "ch.live",    "url": "http://good.example.com/s"},
            {"tvg_id": "ch.dead",    "url": "http://bad.example.com/s"},
            {"tvg_id": "ch.virtual", "url": ""},
        ])
        good_resp = MagicMock()
        good_resp.status_code = 200

        def _fake_head(url, **kwargs):
            if "good" in url:
                return good_resp
            raise Exception("refused")

        def _fake_get(url, **kwargs):
            raise Exception("refused")

        login(client)
        with patch("app.requests.head", side_effect=_fake_head):
            with patch("app.requests.get", side_effect=_fake_get):
                resp = client.post(
                    "/api/channel_health",
                    data=json.dumps({"channel_ids": ["ch.live", "ch.dead", "ch.virtual"]}),
                    content_type="application/json",
                )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"]["ch.live"]    == "up"
        assert data["results"]["ch.dead"]    == "down"
        assert data["results"]["ch.virtual"] == "virtual"


# ─── Markup placement ────────────────────────────────────────────────────────

class TestChannelHealthMarkup:
    def test_guide_does_not_include_channel_health_script(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "channel-health.js" not in html

    def test_guide_header_does_not_include_desktop_toggle(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="toggleChannelHealth"' not in html

    def test_guide_header_does_not_include_mobile_toggle(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="mobileToggleChannelHealth"' not in html

    def test_diagnostics_page_includes_channel_health_panel(self, client):
        login(client)
        resp = client.get("/admin/diagnostics?tab=health")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Channel Stream Reachability" in html
        assert 'id="btnRunChannelHealth"' in html
        assert 'id="channelHealthOutput"' in html
