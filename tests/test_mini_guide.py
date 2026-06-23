"""Tests for the mini guide overlay on the guide page."""
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


@pytest.fixture()
def guide_html(client):
    client.post(
        "/login",
        data={"username": "admin", "password": "adminpass"},
        follow_redirects=True,
    )
    resp = client.get("/guide")
    assert resp.status_code == 200
    return resp.data.decode("utf-8")


@pytest.fixture()
def mini_guide_js():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static",
        "js",
        "mini-guide.js",
    )
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestMiniGuideMarkup:
    def test_guide_renders_mini_guide_button(self, guide_html):
        assert 'id="miniGuideBtn"' in guide_html
        assert 'aria-label="Toggle mini guide"' in guide_html
        assert 'title="Mini Guide"' in guide_html

    def test_guide_renders_mini_guide_panel(self, guide_html):
        assert 'id="miniGuide"' in guide_html
        assert 'class="mini-guide"' in guide_html
        assert 'id="mgChannelList"' in guide_html

    def test_guide_sets_dialog_aria_attributes(self, guide_html):
        assert 'role="dialog"' in guide_html
        assert 'aria-modal="false"' in guide_html
        assert 'aria-label="Mini guide"' in guide_html
        assert 'aria-hidden="true"' in guide_html

    def test_guide_sets_channel_list_aria_attributes(self, guide_html):
        assert 'role="listbox"' in guide_html
        assert 'aria-label="Channels near current channel"' in guide_html

    def test_guide_renders_close_button(self, guide_html):
        assert 'id="miniGuideClose"' in guide_html
        assert 'aria-label="Close mini guide"' in guide_html

    def test_guide_loads_mini_guide_script(self, guide_html):
        assert "js/mini-guide.js" in guide_html

    def test_guide_renders_mini_guide_layout_container(self, guide_html):
        assert 'id="miniGuidePage"' in guide_html
        assert 'id="miniGuidePageList"' in guide_html
        assert 'aria-label="Mini guide layout"' in guide_html

    def test_header_renders_guide_layout_toggles(self, guide_html):
        assert 'id="toggleGuideLayout"' in guide_html
        assert 'id="mobileToggleGuideLayout"' in guide_html
        assert "Mini Guide Layout" in guide_html


class TestMiniGuideScript:
    def test_script_exposes_public_api(self, mini_guide_js):
        assert "window.openMiniGuide = openMiniGuide;" in mini_guide_js
        assert "window.closeMiniGuide = closeMiniGuide;" in mini_guide_js
        assert "window.toggleMiniGuide = toggleMiniGuide;" in mini_guide_js

    def test_script_uses_dom_source_for_channels(self, mini_guide_js):
        assert "document.querySelectorAll('.guide-row[data-cid]')" in mini_guide_js
        assert "row.querySelector('.chan-name')" in mini_guide_js
        assert 'fetch("/api/channels"' not in mini_guide_js
        assert "fetch('/api/channels'" not in mini_guide_js

    def test_script_limits_overlay_to_seven_rows(self, mini_guide_js):
        assert "MINI_GUIDE_ROW_COUNT = 7" in mini_guide_js
        assert "selectedWindow()" in mini_guide_js

    def test_script_sets_eight_second_autodismiss(self, mini_guide_js):
        assert "MINI_GUIDE_AUTODISMISS_MS = 8000" in mini_guide_js
        assert "setTimeout(closeMiniGuide, MINI_GUIDE_AUTODISMISS_MS)" in mini_guide_js

    def test_script_defines_keyboard_shortcuts(self, mini_guide_js):
        assert "MINI_GUIDE_TOGGLE_KEY = 'g'" in mini_guide_js
        assert "event.key === 'ArrowUp'" in mini_guide_js
        assert "event.key === 'ArrowDown'" in mini_guide_js
        assert "event.key === 'Enter'" in mini_guide_js
        assert "event.key === 'Escape'" in mini_guide_js

    def test_script_tunes_selected_channel_with_existing_player(self, mini_guide_js):
        assert "typeof window.playChannel !== 'function'" in mini_guide_js
        assert "window.playChannel(channel.url, channel.cid, channel.name)" in mini_guide_js

    def test_script_exposes_layout_api_and_pref_key(self, mini_guide_js):
        assert "guide_layout" in mini_guide_js
        assert "window.setGuideLayout" in mini_guide_js
        assert "window.toggleGuideLayout = toggleGuideLayout;" in mini_guide_js
        assert "applyGuideLayout" in mini_guide_js


class TestMiniGuideStyles:
    def test_styles_include_slide_in_panel_and_open_state(self, guide_html):
        assert ".mini-guide {" in guide_html
        assert "transform: translate(-110%, -50%);" in guide_html
        assert ".mini-guide.is-open {" in guide_html
        assert "transform: translate(0, -50%);" in guide_html

    def test_styles_include_selected_row_and_progress_bar(self, guide_html):
        assert ".mini-guide-row.is-selected" in guide_html
        assert ".mg-progress-wrap" in guide_html
        assert ".mg-progress-bar" in guide_html

    def test_styles_include_main_layout_swap_rules(self, guide_html):
        assert "body.guide-layout-mini #guideOuter" in guide_html
        assert "body.guide-layout-mini #fixedTimeBar" in guide_html
        assert "body.guide-layout-mini .mini-guide-page" in guide_html


class TestMiniGuidePrefs:
    def test_default_prefs_include_full_guide_layout(self):
        prefs = app_module.get_user_prefs("missing-user")
        assert prefs["guide_layout"] == "full"

    def test_user_prefs_api_accepts_mini_guide_layout(self, client):
        client.post(
            "/login",
            data={"username": "admin", "password": "adminpass"},
            follow_redirects=True,
        )
        resp = client.post("/api/user_prefs", json={"guide_layout": "mini"})
        assert resp.status_code == 200
        assert resp.get_json()["prefs"]["guide_layout"] == "mini"

    def test_saved_mini_layout_is_applied_on_initial_guide_render(self, client):
        app_module.save_user_prefs("admin", {"guide_layout": "mini"})
        client.post(
            "/login",
            data={"username": "admin", "password": "adminpass"},
            follow_redirects=True,
        )
        resp = client.get("/guide")
        html = resp.data.decode("utf-8")
        assert 'class="guide-page guide-layout-mini"' in html
        assert 'id="miniGuidePage" class="mini-guide-page"' in html
        assert 'id="miniGuidePage" class="mini-guide-page" hidden' not in html
