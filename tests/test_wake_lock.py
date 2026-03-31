"""Tests for the Fire TV screen-saver prevention (wake-lock) feature."""
import os
import sys

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
    monkeypatch.setattr(app_module, "TUNER_DB", tuners_db)
    init_db()
    init_tuners_db()
    add_user("testuser", "testpass")
    yield


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client):
    return client.post("/login",
                       data={"username": "testuser", "password": "testpass"},
                       follow_redirects=True)


# ─── Static file ─────────────────────────────────────────────────────────────

class TestWakeLockStaticFile:
    def test_wake_lock_js_is_served(self, client):
        """wake-lock.js must be served as a static asset."""
        resp = client.get("/static/js/wake-lock.js")
        assert resp.status_code == 200

    def test_wake_lock_js_contains_wake_lock_api_call(self, client):
        """wake-lock.js must attempt to use the Screen Wake Lock API."""
        resp = client.get("/static/js/wake-lock.js")
        assert b"wakeLock" in resp.data

    def test_wake_lock_js_contains_video_fallback(self, client):
        """wake-lock.js must include a video-based fallback for browsers that
        don't support the Wake Lock API (e.g. older Silk versions)."""
        resp = client.get("/static/js/wake-lock.js")
        assert b"startFallback" in resp.data

    def test_wake_lock_js_handles_visibility_change(self, client):
        """wake-lock.js must re-acquire the lock on visibilitychange."""
        resp = client.get("/static/js/wake-lock.js")
        assert b"visibilitychange" in resp.data


# ─── Guide template ───────────────────────────────────────────────────────────

class TestGuideIncludesWakeLock:
    def test_guide_references_wake_lock_script(self, client):
        """The guide page HTML must reference wake-lock.js so it loads for TV
        user-agents alongside tv-remote-nav.js."""
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        assert b"wake-lock.js" in resp.data

    def test_wake_lock_script_near_tv_remote_nav(self, client):
        """wake-lock.js must appear in the same TV-detection block as
        tv-remote-nav.js so both load together for Fire TV / Silk users."""
        # Both scripts are injected by the same ~30-line JS block, so they
        # must be within this many characters of each other in the HTML output.
        MAX_SCRIPT_DISTANCE = 500

        login(client)
        resp = client.get("/guide")
        html = resp.data.decode("utf-8")
        tv_nav_pos = html.find("tv-remote-nav.js")
        wake_lock_pos = html.find("wake-lock.js")
        assert tv_nav_pos != -1, "tv-remote-nav.js not found in guide"
        assert wake_lock_pos != -1, "wake-lock.js not found in guide"
        # wake-lock.js should appear close to tv-remote-nav.js
        assert abs(wake_lock_pos - tv_nav_pos) < MAX_SCRIPT_DISTANCE, (
            "wake-lock.js is not near tv-remote-nav.js in the guide HTML "
            f"(positions: tv-remote-nav={tv_nav_pos}, wake-lock={wake_lock_pos})"
        )
