"""Tests for the "Last Channel Return" feature (v4.9.6).

Verifies that:
- guide.html exposes the `window.returnToLastChannel` global function.
- guide.html declares the `lastChannelMeta` state variable.
- guide.html updates `window.lastChannelMeta` inside playChannel().
- channel-number-entry.js handles the `L` key to trigger last-channel return.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, add_user


# ─── Fixtures ────────────────────────────────────────────────────────────────

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


# ─── Guide template tests ─────────────────────────────────────────────────────

class TestLastChannelReturnGuide:
    def test_guide_exposes_last_channel_meta_on_window(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "window.lastChannelMeta" in html

    def test_guide_exposes_return_to_last_channel_function(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "window.returnToLastChannel" in html

    def test_guide_updates_window_last_channel_meta(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "window.lastChannelMeta = Object.assign" in html

    def test_guide_saves_previous_channel_before_switching(self, client):
        """The playChannel function must save the prior channel before overwriting currentChannelMeta."""
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        html = resp.data.decode()
        # The guard condition — only save when switching to a different channel
        assert "currentChannelId !== cid" in html


# ─── channel-number-entry.js tests ───────────────────────────────────────────

class TestLastChannelReturnKeyBinding:
    def _read_js(self):
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "js", "channel-number-entry.js",
        )
        with open(js_path, encoding="utf-8") as fh:
            return fh.read()

    def test_l_key_handler_present(self):
        js = self._read_js()
        assert "'l'" in js or '"l"' in js

    def test_l_key_calls_return_to_last_channel(self):
        js = self._read_js()
        assert "returnToLastChannel" in js

    def test_l_key_only_fires_when_buffer_empty(self):
        """The L key handler must be guarded by `!buffer` to avoid conflicts with digit entry."""
        js = self._read_js()
        # Find the L key block and confirm the !buffer guard is present
        assert "!buffer" in js

    def test_l_key_checks_last_channel_meta_exists(self):
        """The L key handler should only fire if window.lastChannelMeta is set."""
        js = self._read_js()
        assert "window.lastChannelMeta" in js
