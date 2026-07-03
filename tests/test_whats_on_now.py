"""Tests for the /api/whats_on_now endpoint and /whats-on-now page (issue #365)."""
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

def _make_channels():
    return [
        {"tvg_id": "ch.news",    "name": "News Channel",    "logo": "https://example.com/news.png",    "number": "1", "group": "News"},
        {"tvg_id": "ch.sports",  "name": "Sports Channel",  "logo": "https://example.com/sports.png",  "number": "2", "group": "Sports"},
        {"tvg_id": "ch.movies",  "name": "Movies Channel",  "logo": "",                                "number": "3", "group": "Movies"},
    ]


def _make_epg():
    now = datetime.now(timezone.utc)
    return {
        "ch.news": [
            {
                "title": "Evening News",
                "desc":  "Top stories of the day",
                "start": now - timedelta(minutes=10),
                "stop":  now + timedelta(minutes=50),
            }
        ],
        "ch.sports": [
            {
                "title": "Game Night",
                "desc":  "Live coverage",
                "start": now - timedelta(minutes=5),
                "stop":  now + timedelta(minutes=55),
            }
        ],
        # ch.movies has no EPG — will get fallback
    }


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestWhatsOnNowAPI:
    """Tests for the /api/whats_on_now endpoint."""

    def test_requires_login(self, client):
        """Unauthenticated requests are redirected to login."""
        resp = client.get("/api/whats_on_now")
        assert resp.status_code in (302, 401)

    def test_ok_shape(self, client, monkeypatch):
        """Response has ok=True and a channels list."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/api/whats_on_now")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert "channels" in body
        assert "timestamp" in body

    def test_includes_all_cached_channels(self, client, monkeypatch):
        """Every channel in cached_channels appears in the response."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        body = client.get("/api/whats_on_now").get_json()
        tvg_ids = [ch["tvg_id"] for ch in body["channels"]]
        assert "ch.news"   in tvg_ids
        assert "ch.sports" in tvg_ids
        assert "ch.movies" in tvg_ids

    def test_channel_fields_present(self, client, monkeypatch):
        """Each channel entry contains the expected fields."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        body = client.get("/api/whats_on_now").get_json()
        ch = next(c for c in body["channels"] if c["tvg_id"] == "ch.news")
        assert ch["name"]  == "News Channel"
        assert ch["logo"]  == "https://example.com/news.png"
        assert ch["group"] == "News"
        prog = ch["program"]
        assert "title"        in prog
        assert "desc"         in prog
        assert "start_iso"    in prog
        assert "stop_iso"     in prog
        assert "progress_pct" in prog

    def test_current_program_matched(self, client, monkeypatch):
        """The currently-airing program is selected for each channel."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        body = client.get("/api/whats_on_now").get_json()
        news_ch = next(c for c in body["channels"] if c["tvg_id"] == "ch.news")
        assert news_ch["program"]["title"] == "Evening News"

    def test_progress_pct_in_range(self, client, monkeypatch):
        """progress_pct is between 0 and 100 inclusive."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        body = client.get("/api/whats_on_now").get_json()
        for ch in body["channels"]:
            pct = ch["program"]["progress_pct"]
            assert 0 <= pct <= 100, f"progress_pct out of range for {ch['tvg_id']}: {pct}"

    def test_empty_channels(self, client, monkeypatch):
        """Response is ok with an empty channels list when no channels are loaded."""
        monkeypatch.setattr(app_module, "cached_channels", [])
        monkeypatch.setattr(app_module, "cached_epg",      {})
        login(client)
        body = client.get("/api/whats_on_now").get_json()
        assert body["ok"] is True
        # virtual channels may still be included; the real channels list is empty
        for ch in body["channels"]:
            assert ch["tvg_id"].startswith("virtual.")

    def test_logo_empty_string_when_missing(self, client, monkeypatch):
        """Channels without a logo return an empty string for logo."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        body = client.get("/api/whats_on_now").get_json()
        movies_ch = next(c for c in body["channels"] if c["tvg_id"] == "ch.movies")
        assert movies_ch["logo"] == ""


class TestWhatsOnNowPage:
    """Tests for the /whats-on-now page route."""

    def test_requires_login(self, client):
        """Unauthenticated requests are redirected to login."""
        resp = client.get("/whats-on-now")
        assert resp.status_code in (302, 401)

    def test_page_loads(self, client, monkeypatch):
        """Page renders successfully for logged-in users."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/whats-on-now")
        assert resp.status_code == 200
        text = resp.data.decode()
        assert "What's On Now" in text

    def test_page_contains_api_call(self, client, monkeypatch):
        """Page HTML references the /api/whats_on_now endpoint."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/whats-on-now")
        assert b"/api/whats_on_now" in resp.data

    def test_page_stores_pending_play_in_session_storage(self, client, monkeypatch):
        """Clicking a card stores wonPendingPlay in sessionStorage before navigating."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/whats-on-now")
        text = resp.data.decode()
        # The page must emit JS that writes to sessionStorage when a card is activated
        assert "wonPendingPlay" in text
        assert "sessionStorage.setItem" in text

    def test_guide_reads_pending_play_from_session_storage(self, client, monkeypatch):
        """The guide page includes the wonPendingPlay auto-play handler."""
        monkeypatch.setattr(app_module, "cached_channels", _make_channels())
        monkeypatch.setattr(app_module, "cached_epg",      _make_epg())
        login(client)
        resp = client.get("/guide")
        text = resp.data.decode()
        assert "wonPendingPlay" in text
        assert "sessionStorage.getItem" in text
