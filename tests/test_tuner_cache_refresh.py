import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, add_user, add_tuner, get_setting, set_current_tuner


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    users_db = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE", users_db)
    monkeypatch.setattr(app_module, "TUNER_DB", tuners_db)
    monkeypatch.setattr(app_module, "cached_channels", [])
    monkeypatch.setattr(app_module, "cached_epg", {})
    init_db()
    init_tuners_db()
    add_user("admin", "adminpass")
    add_user("testuser", "testpass")
    yield


@pytest.fixture()
def client(isolated_env):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client, username="admin", pw="adminpass"):
    return client.post(
        "/login",
        data={"username": username, "password": pw},
        follow_redirects=True,
    )


class TestRefreshCurrentTuner:
    def test_refreshing_non_active_tuner_keeps_active_memory_cache(self):
        add_tuner("Active", "https://example.com/a.xml", "https://example.com/a.m3u")
        add_tuner("Other", "https://example.com/b.xml", "https://example.com/b.m3u")
        set_current_tuner("Active")
        app_module.cached_channels = [{"name": "Active Channel"}]
        app_module.cached_epg = {"active": [{"title": "Active Show"}]}

        with patch(
            "app.load_tuner_data",
            return_value=([{"name": "Other Channel"}], {"other": [{"title": "Other Show"}]}),
        ) as mock_load, patch("app.apply_epg_fallback", side_effect=lambda channels, epg: epg):
            assert app_module.refresh_current_tuner("Other") is True

        mock_load.assert_called_once_with("Other", force_refresh=True)
        assert app_module.cached_channels == [{"name": "Active Channel"}]
        assert app_module.cached_epg == {"active": [{"title": "Active Show"}]}
        assert get_setting("last_auto_refresh:Other", "").startswith("success|")


class TestAutoRefreshTriggerApi:
    def test_admin_can_refresh_selected_tuner(self, client):
        add_tuner("Refresh Source 1", "https://example.com/1.xml", "https://example.com/1.m3u")
        add_tuner("Refresh Source 2", "https://example.com/2.xml", "https://example.com/2.m3u")
        set_current_tuner("Refresh Source 1")
        login(client, "admin", "adminpass")

        with patch("app.refresh_current_tuner", return_value=True) as mock_refresh:
            resp = client.post("/api/auto_refresh/trigger", json={"tuner": "Refresh Source 2"})

        assert resp.status_code == 200
        assert resp.get_json() == {"ok": True, "tuner": "Refresh Source 2"}
        mock_refresh.assert_called_once_with("Refresh Source 2")

    def test_non_admin_cannot_refresh_tuner(self, client):
        add_tuner("Locked Refresh Tuner", "https://example.com/1.xml", "https://example.com/1.m3u")
        login(client, "testuser", "testpass")

        resp = client.post("/api/auto_refresh/trigger", json={"tuner": "Locked Refresh Tuner"})

        assert resp.status_code == 403
        assert resp.get_json()["error"] == "Unauthorized"
