"""Tests for channel info banner markup in the guide player."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, add_user


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    users_db = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE", users_db)
    monkeypatch.setattr(app_module, "TUNER_DB", tuners_db)
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


class TestChannelInfoBannerGuideMarkup:
    def test_guide_contains_inline_and_fullscreen_banner_markup(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'id="chanInfoBtn"' in html
        assert 'id="channelInfoBanner"' in html
        assert 'id="vcFsOverlayInfo"' in html
        assert 'id="vcFsChannelInfoBanner"' in html

    def test_guide_exposes_channel_info_banner_toggle_hook(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "window.showChannelInfoBanner =" in html
        assert "window.toggleChannelInfoBanner = toggleBanner;" in html

    def test_guide_includes_native_fullscreen_styles(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert (
            "#video:fullscreen,\n"
            "    #video:-webkit-full-screen {\n"
            "        width: 100vw !important;\n"
            "        height: 100vh !important;\n"
            "        object-fit: contain !important;\n"
            "    }"
        ) in html

    def test_guide_handles_delayed_hls_stream_startup(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "let hlsStartupRetryTimer = null;" in html
        assert "HLS_STARTUP_RETRY_MAX_ATTEMPTS = 12" in html
        assert "hlsInstance.on(Hls.Events.ERROR" in html
        assert "hlsInstance.startLoad();" in html
