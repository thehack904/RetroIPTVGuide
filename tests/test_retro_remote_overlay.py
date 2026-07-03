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


class TestRetroRemoteOverlay:
    def test_guide_renders_remote_toggle_overlay_and_script(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")

        assert 'id="retroRemoteToggle"' in html
        assert 'id="mobileRetroRemoteToggle"' in html
        assert 'aria-controls="retroRemoteOverlay"' in html
        assert "img/remote_icon.png" in html
        assert 'id="retroRemoteOverlay"' in html
        assert 'data-key="1" data-key-code="49"' in html
        assert 'data-key="." data-key-code="190"' in html
        assert 'data-key="Enter" data-key-code="13"' in html
        assert 'data-key="l" data-key-code="76"' in html
        assert 'data-remote-action="channel-up"' in html
        assert 'data-remote-action="channel-down"' in html
        assert 'data-remote-action="fullscreen"' in html
        assert "Toggle fullscreen" in html
        assert "js/retro-remote.js" in html

    def test_remote_toggle_is_after_logout_in_desktop_header(self, client):
        login(client)
        resp = client.get("/guide")
        html = resp.data.decode("utf-8")

        logout_pos = html.find('<a href="/logout">LOGOUT</a>')
        toggle_pos = html.find('id="retroRemoteToggle"')
        clock_pos = html.find('id="clock"')

        assert logout_pos != -1
        assert toggle_pos != -1
        assert clock_pos != -1
        assert logout_pos < toggle_pos < clock_pos

    def test_remote_does_not_render_outside_guide(self, client):
        login(client)
        resp = client.get("/whats_on_now")
        assert resp.status_code == 200

        assert b"retroRemoteToggle" not in resp.data
        assert b"mobileRetroRemoteToggle" not in resp.data
        assert b"retroRemoteOverlay" not in resp.data
        assert b"retro-remote.js" not in resp.data
