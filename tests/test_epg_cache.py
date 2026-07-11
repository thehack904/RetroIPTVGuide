"""Tests for EPG disk cache helpers (_epg_cache_path, _load_epg_from_disk,
_save_epg_to_disk) and the cache-aware load_tuner_data function."""
import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import app as app_module
from app import (
    _epg_cache_path,
    _serialize_epg,
    _deserialize_epg,
    _load_epg_from_disk,
    _save_epg_to_disk,
    load_tuner_data,
    init_db,
    init_tuners_db,
    add_tuner,
    add_combined_tuner,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def isolated_env(tmp_path):
    """Set up isolated databases for each test and clean up after.

    EPG_CACHE_DIR isolation is provided by the autouse ``isolated_epg_cache``
    fixture in conftest.py, which redirects ``app_module.EPG_CACHE_DIR`` to
    ``tmp_path / 'epg_cache'`` before this fixture runs.  The yielded path is
    that same directory so callers can assert on its contents without repeating
    the path construction.
    """
    tmp_db = tmp_path / "users.db"
    tmp_tuner_db = tmp_path / "tuners.db"

    orig_db = app_module.DATABASE
    orig_tuner_db = app_module.TUNER_DB

    app_module.DATABASE = str(tmp_db)
    app_module.TUNER_DB = str(tmp_tuner_db)

    init_db()
    init_tuners_db()

    yield tmp_path / "epg_cache"  # matches what conftest.py sets for EPG_CACHE_DIR

    app_module.DATABASE = orig_db
    app_module.TUNER_DB = orig_tuner_db


# ---------------------------------------------------------------------------
# _epg_cache_path
# ---------------------------------------------------------------------------

class TestEpgCachePath:
    def test_returns_json_file_in_cache_dir(self, isolated_env):
        path = _epg_cache_path("MyTuner")
        assert path.endswith(".json")
        assert os.path.normpath(str(isolated_env)) in path

    def test_sanitises_special_characters(self, isolated_env):
        path = _epg_cache_path("Tuner With Spaces & Symbols!")
        basename = os.path.basename(path)
        assert " " not in basename
        assert "&" not in basename
        assert "!" not in basename

    def test_raises_on_empty_name(self, isolated_env):
        with pytest.raises(ValueError):
            _epg_cache_path("")

    def test_traversal_attempt_is_sanitised_not_raised(self, isolated_env):
        """Path traversal characters are stripped during name sanitisation.

        ``../../etc/passwd`` is converted to ``______etc_passwd`` so the
        resulting file always stays inside EPG_CACHE_DIR.
        """
        path = _epg_cache_path("../../etc/passwd")
        safe_dir = os.path.normpath(os.path.abspath(str(isolated_env)))
        assert path.startswith(safe_dir + os.sep) or path == safe_dir


# ---------------------------------------------------------------------------
# _serialize_epg / _deserialize_epg round-trip
# ---------------------------------------------------------------------------

class TestEpgSerialisation:
    EPG = {
        "ch1": [
            {
                "title": "Morning News",
                "desc": "Latest headlines",
                "start": datetime(2024, 1, 1, 7, 0, 0, tzinfo=timezone.utc),
                "stop": datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
                "icon": "https://example.com/img.png",
                "categories": ["News"],
                "colors": [],
            }
        ],
        "ch2": [
            {
                "title": "No Guide Data Available",
                "desc": "",
                "start": None,
                "stop": None,
                "icon": "",
                "categories": [],
                "colors": [],
            }
        ],
    }

    def test_serialize_converts_datetimes_to_iso(self):
        serialized = _serialize_epg(self.EPG)
        prog = serialized["ch1"][0]
        assert isinstance(prog["start"], str)
        assert isinstance(prog["stop"], str)

    def test_serialize_keeps_none_as_none(self):
        serialized = _serialize_epg(self.EPG)
        assert serialized["ch2"][0]["start"] is None
        assert serialized["ch2"][0]["stop"] is None

    def test_round_trip_preserves_datetimes(self):
        serialized = _serialize_epg(self.EPG)
        restored = _deserialize_epg(serialized)
        prog = restored["ch1"][0]
        assert isinstance(prog["start"], datetime)
        assert prog["start"] == self.EPG["ch1"][0]["start"]
        assert prog["stop"] == self.EPG["ch1"][0]["stop"]

    def test_round_trip_preserves_none_dates(self):
        serialized = _serialize_epg(self.EPG)
        restored = _deserialize_epg(serialized)
        assert restored["ch2"][0]["start"] is None
        assert restored["ch2"][0]["stop"] is None

    def test_round_trip_preserves_text_fields(self):
        serialized = _serialize_epg(self.EPG)
        restored = _deserialize_epg(serialized)
        prog = restored["ch1"][0]
        assert prog["title"] == "Morning News"
        assert prog["desc"] == "Latest headlines"
        assert prog["icon"] == "https://example.com/img.png"
        assert prog["categories"] == ["News"]

    def test_round_trip_json_compatible(self):
        serialized = _serialize_epg(self.EPG)
        dumped = json.dumps(serialized)
        reloaded = json.loads(dumped)
        restored = _deserialize_epg(reloaded)
        assert restored["ch1"][0]["title"] == "Morning News"


# ---------------------------------------------------------------------------
# _save_epg_to_disk / _load_epg_from_disk
# ---------------------------------------------------------------------------

EPG_SAMPLE = {
    "chan1": [
        {
            "title": "Test Show",
            "desc": "A test",
            "start": datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc),
            "stop": datetime(2024, 6, 1, 11, 0, tzinfo=timezone.utc),
            "icon": "",
            "categories": [],
            "colors": [],
        }
    ]
}


class TestSaveLoadEpg:
    def test_save_creates_file(self, isolated_env):
        _save_epg_to_disk("Tuner1", EPG_SAMPLE)
        path = _epg_cache_path("Tuner1")
        assert os.path.isfile(path)

    def test_load_returns_epg_dict(self, isolated_env):
        _save_epg_to_disk("Tuner1", EPG_SAMPLE)
        loaded = _load_epg_from_disk("Tuner1")
        assert loaded is not None
        assert "chan1" in loaded
        assert loaded["chan1"][0]["title"] == "Test Show"

    def test_load_restores_datetimes(self, isolated_env):
        _save_epg_to_disk("Tuner1", EPG_SAMPLE)
        loaded = _load_epg_from_disk("Tuner1")
        prog = loaded["chan1"][0]
        assert isinstance(prog["start"], datetime)
        assert prog["start"] == EPG_SAMPLE["chan1"][0]["start"]

    def test_load_returns_none_when_missing(self, isolated_env):
        result = _load_epg_from_disk("NonExistentTuner")
        assert result is None

    def test_load_returns_none_when_stale(self, isolated_env):
        _save_epg_to_disk("Tuner1", EPG_SAMPLE)
        path = _epg_cache_path("Tuner1")
        # Back-date the file mtime by more than the TTL
        old_mtime = time.time() - (app_module.EPG_DISK_CACHE_TTL + 3600)
        os.utime(path, (old_mtime, old_mtime))
        result = _load_epg_from_disk("Tuner1")
        assert result is None

    def test_load_ignores_ttl_when_max_age_none(self, isolated_env):
        _save_epg_to_disk("Tuner1", EPG_SAMPLE)
        path = _epg_cache_path("Tuner1")
        old_mtime = time.time() - (app_module.EPG_DISK_CACHE_TTL + 3600)
        os.utime(path, (old_mtime, old_mtime))
        result = _load_epg_from_disk("Tuner1", max_age=None)
        assert result is not None
        assert "chan1" in result

    def test_load_returns_none_on_corrupt_file(self, isolated_env):
        os.makedirs(str(isolated_env), exist_ok=True)
        path = _epg_cache_path("Tuner1")
        with open(path, "w") as fh:
            fh.write("not valid json{{{{")
        result = _load_epg_from_disk("Tuner1")
        assert result is None

    def test_save_does_nothing_on_unsafe_name(self, isolated_env):
        # Should not raise — just log and return
        _save_epg_to_disk("", EPG_SAMPLE)
        # The cache dir may not have been created at all when the name is
        # rejected before os.makedirs() is reached.
        files = list(isolated_env.iterdir()) if isolated_env.exists() else []
        assert len(files) == 0


# ---------------------------------------------------------------------------
# load_tuner_data with disk cache
# ---------------------------------------------------------------------------

class TestLoadTunerDataCache:
    """Verify that load_tuner_data uses the disk cache correctly."""

    def test_standard_tuner_uses_fresh_cache(self, isolated_env):
        """load_tuner_data should use the disk cache when it is fresh."""
        add_tuner("T1", "https://example.com/g.xml", "https://example.com/p.m3u")
        _save_epg_to_disk("T1", EPG_SAMPLE)

        with patch("app.parse_m3u", return_value=[]) as mock_m3u, \
             patch("app.parse_epg") as mock_epg:
            channels, epg = load_tuner_data("T1")

        mock_epg.assert_not_called()  # cache hit — no network fetch
        assert "chan1" in epg

    def test_standard_tuner_fetches_when_cache_stale(self, isolated_env):
        """load_tuner_data should fetch from network when cache is stale."""
        add_tuner("T1", "https://example.com/g.xml", "https://example.com/p.m3u")
        _save_epg_to_disk("T1", EPG_SAMPLE)

        # Back-date the cache to make it stale
        path = _epg_cache_path("T1")
        old_mtime = time.time() - (app_module.EPG_DISK_CACHE_TTL + 3600)
        os.utime(path, (old_mtime, old_mtime))

        fresh_epg = {"ch_fresh": [{"title": "Fresh", "desc": "", "start": None, "stop": None, "icon": "", "categories": [], "colors": []}]}
        with patch("app.parse_m3u", return_value=[]), \
             patch("app.parse_epg", return_value=fresh_epg):
            channels, epg = load_tuner_data("T1")

        assert "ch_fresh" in epg

    def test_standard_tuner_force_refresh_bypasses_cache(self, isolated_env):
        """force_refresh=True should skip the disk cache."""
        add_tuner("T1", "https://example.com/g.xml", "https://example.com/p.m3u")
        _save_epg_to_disk("T1", EPG_SAMPLE)

        fresh_epg = {"forced": [{"title": "Forced", "desc": "", "start": None, "stop": None, "icon": "", "categories": [], "colors": []}]}
        with patch("app.parse_m3u", return_value=[]), \
             patch("app.parse_epg", return_value=fresh_epg):
            channels, epg = load_tuner_data("T1", force_refresh=True)

        assert "forced" in epg
        assert "chan1" not in epg

    def test_standard_tuner_saves_cache_after_fetch(self, isolated_env):
        """After a successful network fetch, the EPG should be persisted to disk."""
        add_tuner("T1", "https://example.com/g.xml", "https://example.com/p.m3u")
        fresh_epg = {"ch_new": [{"title": "New", "desc": "", "start": None, "stop": None, "icon": "", "categories": [], "colors": []}]}

        with patch("app.parse_m3u", return_value=[]), \
             patch("app.parse_epg", return_value=fresh_epg):
            load_tuner_data("T1")

        path = _epg_cache_path("T1")
        assert os.path.isfile(path)

    def test_standard_tuner_stale_fallback_when_network_empty(self, isolated_env):
        """When the network returns empty EPG, stale cache should be used as fallback."""
        add_tuner("T1", "https://example.com/g.xml", "https://example.com/p.m3u")
        _save_epg_to_disk("T1", EPG_SAMPLE)

        # Make cache stale
        path = _epg_cache_path("T1")
        old_mtime = time.time() - (app_module.EPG_DISK_CACHE_TTL + 3600)
        os.utime(path, (old_mtime, old_mtime))

        with patch("app.parse_m3u", return_value=[]), \
             patch("app.parse_epg", return_value={}):
            channels, epg = load_tuner_data("T1")

        # Should fall back to stale cache
        assert "chan1" in epg

    def test_combined_tuner_uses_fresh_cache(self, isolated_env):
        """Combined load_tuner_data should use cache for the combined EPG."""
        add_tuner("Src", "https://example.com/g.xml", "https://example.com/p.m3u")
        add_combined_tuner("Combined", ["Src"])
        _save_epg_to_disk("Combined", EPG_SAMPLE)

        with patch("app.parse_m3u", return_value=[]) as mock_m3u, \
             patch("app.parse_epg") as mock_epg:
            channels, epg = load_tuner_data("Combined")

        mock_epg.assert_not_called()
        assert "chan1" in epg

    def test_combined_tuner_force_refresh_bypasses_cache(self, isolated_env):
        """Combined tuner with force_refresh=True should not use cache."""
        add_tuner("Src", "https://example.com/g.xml", "https://example.com/p.m3u")
        add_combined_tuner("Combined", ["Src"])
        _save_epg_to_disk("Combined", EPG_SAMPLE)

        fresh_epg = {"combined_fresh": [{"title": "CF", "desc": "", "start": None, "stop": None, "icon": "", "categories": [], "colors": []}]}
        with patch("app.parse_m3u", return_value=[]), \
             patch("app.parse_epg", return_value=fresh_epg):
            channels, epg = load_tuner_data("Combined", force_refresh=True)

        assert "combined_fresh" in epg
        assert "chan1" not in epg

    def test_combined_tuner_cached_epg_dedupes_duplicate_tvg_ids(self, isolated_env):
        """Cache path should not return duplicate channel rows for the same tvg_id."""
        add_tuner("SrcA", "https://example.com/a.xml", "https://example.com/a.m3u")
        add_tuner("SrcB", "https://example.com/b.xml", "https://example.com/b.m3u")
        add_combined_tuner("Combined", ["SrcA", "SrcB"])
        _save_epg_to_disk("Combined", EPG_SAMPLE)

        with patch("app.parse_m3u") as mock_m3u, patch("app.parse_epg") as mock_epg:
            mock_m3u.side_effect = [
                [{"name": "News A", "url": "http://a/news.m3u8", "logo": "", "tvg_id": "news"}],
                [{"name": "News B", "url": "http://b/news.m3u8", "logo": "", "tvg_id": "news"}],
            ]
            channels, epg = load_tuner_data("Combined")

        mock_epg.assert_not_called()
        assert len(channels) == 1
        assert channels[0]["tvg_id"] == "news"
        assert "chan1" in epg

    def test_load_nonexistent_tuner_returns_empty(self, isolated_env):
        channels, epg = load_tuner_data("DoesNotExist")
        assert channels == []
        assert epg == {}
