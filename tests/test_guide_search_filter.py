import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, add_user, parse_epg


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


class _MockResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class TestGuideSearchFilter:
    def test_guide_search_panel_is_hidden_by_default_and_has_toggle_hooks(self, client):
        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        assert b'id="guideSearchToggle"' in resp.data
        assert b'id="mobileGuideSearchToggle"' in resp.data
        assert b'id="guideSearchPanel"' in resp.data
        assert b'id="guideSearchPanel" class="guide-filter-panel" role="search" hidden' in resp.data
        assert b'id="guideSearchInput"' in resp.data
        assert b'id="guideTypeFilter"' in resp.data
        assert b"toggleGuideSearchPanel" in resp.data

    def test_guide_search_toggle_renders_between_home_and_settings(self, client):
        login(client)
        resp = client.get("/guide")
        html = resp.data.decode("utf-8")
        home_pos = html.find(">HOME</a>")
        search_pos = html.find('id="guideSearchToggle"')
        settings_pos = html.find('id="settingsMenu"')
        assert home_pos != -1
        assert search_pos != -1
        assert settings_pos != -1
        assert home_pos < search_pos < settings_pos

    def test_parse_epg_includes_category_and_color_metadata(self, monkeypatch):
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="ch1"><display-name>Channel One</display-name></channel>
  <programme channel="ch1" start="20260101010000 +0000" stop="20260101020000 +0000">
    <title>Movie Night</title>
    <category>Movies</category>
    <colour>Blue</colour>
    <color>Gold</color>
  </programme>
</tv>
"""

        monkeypatch.setattr(app_module.requests, "get", lambda *_args, **_kwargs: _MockResponse(xml))
        epg = parse_epg("http://example.test/guide.xml")
        assert epg["ch1"][0]["categories"] == ["Movies"]
        assert epg["ch1"][0]["colors"] == ["Blue", "Gold"]

    def test_guide_program_blocks_render_category_and_color_data(self, client, monkeypatch):
        now = datetime.now(timezone.utc)
        monkeypatch.setattr(app_module, "cached_channels", [
            {
                "name": "Channel One",
                "logo": "",
                "url": "http://example.test/ch1.m3u8",
                "tvg_id": "ch1",
                "group": "Movies",
                "tvg_chno": "101",
            }
        ])
        monkeypatch.setattr(app_module, "cached_epg", {
            "ch1": [{
                "title": "Movie Night",
                "desc": "Feature film",
                "start": now - timedelta(minutes=10),
                "stop": now + timedelta(minutes=50),
                "icon": "",
                "categories": ["Movies", "Drama"],
                "colors": ["Blue"],
            }]
        })

        login(client)
        resp = client.get("/guide")
        assert resp.status_code == 200
        assert b'data-categories="Movies | Drama"' in resp.data
        assert b'data-colors="Blue"' in resp.data
