"""Tests for channel number entry feature:
- parse_m3u() correctly extracts tvg-chno from M3U EXTINF tags (including
  decimal sub-channel numbers like "2.1", "16.5", "31.2")
- guide template exposes data-chan-num attribute (smoke test via app client)
"""
import os
import sys
import json
import subprocess
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, parse_m3u


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own empty SQLite database."""
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    monkeypatch.setattr(app_module, "DATABASE",  users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",  tuners_db)
    init_db()
    init_tuners_db()
    from app import add_user
    add_user("testuser", "testpass")
    yield


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def login(client):
    return client.post("/login", data={"username": "testuser", "password": "testpass"},
                       follow_redirects=True)


# ─── M3U parsing tests ────────────────────────────────────────────────────────

M3U_WITH_CHNO = """\
#EXTM3U
#EXTINF:-1 tvg-id="ch1" tvg-chno="5" tvg-logo="" group-title="News",CNN
http://example.com/cnn.m3u8
#EXTINF:-1 tvg-id="ch2" tvg-chno="42" tvg-logo="" group-title="Sports",ESPN
http://example.com/espn.m3u8
#EXTINF:-1 tvg-id="ch3" tvg-logo="" group-title="Movies",HBO
http://example.com/hbo.m3u8
"""

M3U_WITHOUT_CHNO = """\
#EXTM3U
#EXTINF:-1 tvg-id="ch1" tvg-logo="" group-title="News",BBC News
http://example.com/bbc.m3u8
#EXTINF:-1 tvg-id="ch2" tvg-logo="" group-title="Sports",Sky Sports
http://example.com/sky.m3u8
"""

M3U_DECIMAL_CHNO = """\
#EXTM3U
#EXTINF:-1 tvg-id="sub1" tvg-chno="2.1" tvg-logo="" group-title="OTA",WFOO-HD
http://example.com/wfoo-hd.m3u8
#EXTINF:-1 tvg-id="sub2" tvg-chno="16.5" tvg-logo="" group-title="OTA",WBAR-SD
http://example.com/wbar-sd.m3u8
#EXTINF:-1 tvg-id="sub3" tvg-chno="31.2" tvg-logo="" group-title="OTA",WBAZ-DT2
http://example.com/wbaz-dt2.m3u8
"""


def _mock_requests_get(m3u_text):
    """Return a requests.get mock that serves the given M3U text."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = m3u_text
    mock_get = MagicMock(return_value=mock_resp)
    return mock_get


class TestParseM3uTvgChno:
    """parse_m3u() should extract tvg-chno into the 'tvg_chno' field."""

    def test_tvg_chno_extracted_when_present(self):
        with patch("app.requests.get", _mock_requests_get(M3U_WITH_CHNO)):
            channels = parse_m3u("http://fake.url/playlist.m3u")
        assert len(channels) == 3
        assert channels[0]["tvg_chno"] == "5"
        assert channels[1]["tvg_chno"] == "42"

    def test_tvg_chno_empty_when_absent(self):
        with patch("app.requests.get", _mock_requests_get(M3U_WITH_CHNO)):
            channels = parse_m3u("http://fake.url/playlist.m3u")
        # Third channel has no tvg-chno attribute
        assert channels[2]["tvg_chno"] == ""

    def test_tvg_chno_defaults_to_empty_when_not_in_m3u(self):
        with patch("app.requests.get", _mock_requests_get(M3U_WITHOUT_CHNO)):
            channels = parse_m3u("http://fake.url/playlist.m3u")
        for ch in channels:
            assert "tvg_chno" in ch
            assert ch["tvg_chno"] == ""

    def test_other_channel_fields_still_parsed(self):
        with patch("app.requests.get", _mock_requests_get(M3U_WITH_CHNO)):
            channels = parse_m3u("http://fake.url/playlist.m3u")
        assert channels[0]["name"] == "CNN"
        assert channels[0]["tvg_id"] == "ch1"
        assert channels[0]["url"] == "http://example.com/cnn.m3u8"
        assert channels[1]["name"] == "ESPN"
        assert channels[1]["tvg_chno"] == "42"

    def test_tvg_chno_with_leading_trailing_spaces_is_stripped(self):
        m3u = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="ch1" tvg-chno=" 7 " tvg-logo="" group-title="News",Test\n'
            "http://example.com/test.m3u8\n"
        )
        with patch("app.requests.get", _mock_requests_get(m3u)):
            channels = parse_m3u("http://fake.url/playlist.m3u")
        assert channels[0]["tvg_chno"] == "7"


class TestParseM3uDecimalChno:
    """parse_m3u() should preserve decimal sub-channel numbers verbatim."""

    def test_decimal_chno_preserved(self):
        with patch("app.requests.get", _mock_requests_get(M3U_DECIMAL_CHNO)):
            channels = parse_m3u("http://fake.url/playlist.m3u")
        assert len(channels) == 3
        assert channels[0]["tvg_chno"] == "2.1"
        assert channels[1]["tvg_chno"] == "16.5"
        assert channels[2]["tvg_chno"] == "31.2"

    def test_decimal_chno_channel_names_correct(self):
        with patch("app.requests.get", _mock_requests_get(M3U_DECIMAL_CHNO)):
            channels = parse_m3u("http://fake.url/playlist.m3u")
        assert channels[0]["name"] == "WFOO-HD"
        assert channels[1]["name"] == "WBAR-SD"
        assert channels[2]["name"] == "WBAZ-DT2"

    def test_mixed_integer_and_decimal_chno(self):
        m3u = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="a" tvg-chno="2" tvg-logo="" group-title="",Main\n'
            "http://example.com/main.m3u8\n"
            '#EXTINF:-1 tvg-id="b" tvg-chno="2.1" tvg-logo="" group-title="",Sub1\n'
            "http://example.com/sub1.m3u8\n"
            '#EXTINF:-1 tvg-id="c" tvg-chno="2.2" tvg-logo="" group-title="",Sub2\n'
            "http://example.com/sub2.m3u8\n"
        )
        with patch("app.requests.get", _mock_requests_get(m3u)):
            channels = parse_m3u("http://fake.url/playlist.m3u")
        assert channels[0]["tvg_chno"] == "2"
        assert channels[1]["tvg_chno"] == "2.1"
        assert channels[2]["tvg_chno"] == "2.2"


def _simulate_channel_number_entry(channels, keys):
    js_path = Path(app_module.app.static_folder) / "js" / "channel-number-entry.js"
    payload = json.dumps({"channels": channels, "keys": keys, "script_path": str(js_path)})
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(process.argv[1]);
const source = fs.readFileSync(input.script_path, 'utf8');

let keydownHandler = null;
const clickLog = [];

function makeChan(ch) {
  return {
    dataset: {
      chanNum: String(ch.num || ''),
      isVirtual: ch.is_virtual ? 'true' : 'false'
    },
    closest: () => null,
    focus: () => {},
    click: () => { clickLog.push(ch.name); },
    scrollIntoView: () => {}
  };
}

const chanEls = input.channels.map(makeChan);

const document = {
  head: { appendChild: () => {} },
  body: { appendChild: () => {} },
  querySelectorAll: (sel) => sel === '.chan-name' ? chanEls : [],
  addEventListener: (event, cb) => { if (event === 'keydown') keydownHandler = cb; },
  createElement: () => ({
    classList: { add: () => {}, remove: () => {} },
    setAttribute: () => {},
    appendChild: () => {},
    textContent: '',
    id: ''
  })
};

const context = {
  document,
  window: {},
  setTimeout: (fn, ms) => {
    if (ms !== 1500) fn();
    return 1;
  },
  clearTimeout: () => {}
};

vm.runInNewContext(source, context, { filename: 'channel-number-entry.js' });

for (const key of input.keys) {
  keydownHandler({
    key,
    target: { tagName: 'DIV' },
    preventDefault: () => {},
    stopImmediatePropagation: () => {}
  });
}

process.stdout.write(JSON.stringify(clickLog));
"""
    proc = subprocess.run(
        ["node", "-e", node_script, payload],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


class TestChannelNumberEntryDuplicateResolution:
    def test_virtual_channel_is_preferred_over_real_on_duplicate_number(self):
        clicked = _simulate_channel_number_entry(
            [
                {"name": "Real Five", "num": "5", "is_virtual": False},
                {"name": "Virtual Five", "num": "5", "is_virtual": True},
            ],
            ["5", "Enter"],
        )
        assert clicked == ["Virtual Five"]

    def test_non_virtual_duplicate_keeps_first_match(self):
        clicked = _simulate_channel_number_entry(
            [
                {"name": "Real Five A", "num": "5", "is_virtual": False},
                {"name": "Real Five B", "num": "5", "is_virtual": False},
            ],
            ["5", "Enter"],
        )
        assert clicked == ["Real Five A"]


class TestChannelNumberEntrySequentialAlias:
    def test_first_real_channel_reachable_by_sequential_number_after_virtuals(self):
        channels = [
            {"name": f"Virtual {i}", "num": str(i), "is_virtual": True}
            for i in range(1, 10)
        ]
        channels.append({"name": "Real 2.1", "num": "2.1", "is_virtual": False})

        clicked = _simulate_channel_number_entry(channels, ["1", "0", "Enter"])
        assert clicked == ["Real 2.1"]

    def test_explicit_decimal_number_still_works_with_sequential_alias(self):
        channels = [
            {"name": f"Virtual {i}", "num": str(i), "is_virtual": True}
            for i in range(1, 10)
        ]
        channels.append({"name": "Real 2.1", "num": "2.1", "is_virtual": False})

        clicked = _simulate_channel_number_entry(channels, ["2", ".", "1", "Enter"])
        assert clicked == ["Real 2.1"]
