"""Test cases for combined tuner functionality"""
import pytest
import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import (
    app, init_db, init_tuners_db, add_tuner, add_combined_tuner,
    get_tuners, load_tuner_data
)
from unittest.mock import patch, Mock
import tempfile
import sqlite3


class TestCombinedTuner:
    """Test combined tuner functionality"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up test database before each test and clean up after"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_tuner_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')

        import app as app_module
        self.orig_db = app_module.DATABASE
        self.orig_tuner_db = app_module.TUNER_DB

        app_module.DATABASE = self.temp_db.name
        app_module.TUNER_DB = self.temp_tuner_db.name

        init_db()
        init_tuners_db()

        yield

        app_module.DATABASE = self.orig_db
        app_module.TUNER_DB = self.orig_tuner_db
        os.unlink(self.temp_db.name)
        os.unlink(self.temp_tuner_db.name)

    def _add_source_tuners(self):
        """Helper: add two standard source tuners."""
        add_tuner("Source A", "https://example.com/a.xml", "https://example.com/a.m3u")
        add_tuner("Source B", "https://example.com/b.xml", "https://example.com/b.m3u")

    # ------------------------------------------------------------------ #
    # add_combined_tuner                                                   #
    # ------------------------------------------------------------------ #

    def test_add_combined_tuner_stored_correctly(self):
        """Combined tuner is persisted with tuner_type='combined' and sources list."""
        self._add_source_tuners()
        add_combined_tuner("My Combined", ["Source A", "Source B"])

        tuners = get_tuners()
        assert "My Combined" in tuners
        info = tuners["My Combined"]
        assert info["tuner_type"] == "combined"
        assert "Source A" in info["sources"]
        assert "Source B" in info["sources"]

    def test_add_combined_tuner_no_sources_raises(self):
        """Creating a combined tuner with no sources raises ValueError."""
        with pytest.raises(ValueError, match="at least one source"):
            add_combined_tuner("Empty Combined", [])

    def test_add_combined_tuner_duplicate_name_raises(self):
        """Creating a combined tuner with a duplicate name raises ValueError."""
        self._add_source_tuners()
        add_combined_tuner("Dup", ["Source A"])
        with pytest.raises(ValueError, match="already exists"):
            add_combined_tuner("Dup", ["Source B"])

    # ------------------------------------------------------------------ #
    # Standard tuners still have correct tuner_type                       #
    # ------------------------------------------------------------------ #

    def test_standard_tuner_has_correct_type(self):
        """Standard tuners should report tuner_type='standard'."""
        add_tuner("Std", "https://example.com/g.xml", "https://example.com/p.m3u")
        tuners = get_tuners()
        assert tuners["Std"]["tuner_type"] == "standard"

    # ------------------------------------------------------------------ #
    # load_tuner_data — combined path                                     #
    # ------------------------------------------------------------------ #

    @patch('app.parse_m3u')
    @patch('app.parse_epg')
    def test_load_tuner_data_combined_merges_channels(self, mock_epg, mock_m3u):
        """load_tuner_data merges channels from all source tuners."""
        self._add_source_tuners()
        add_combined_tuner("Merged", ["Source A", "Source B"])

        mock_m3u.side_effect = [
            [{"name": "Ch1", "url": "http://a/1.m3u8", "logo": "", "tvg_id": "ch1"}],
            [{"name": "Ch2", "url": "http://b/2.m3u8", "logo": "", "tvg_id": "ch2"}],
        ]
        mock_epg.return_value = {}

        channels, epg = load_tuner_data("Merged")

        assert len(channels) == 2
        names = {c["name"] for c in channels}
        assert "Ch1" in names
        assert "Ch2" in names

    @patch('app.parse_m3u')
    @patch('app.parse_epg')
    def test_load_tuner_data_combined_merges_epg(self, mock_epg, mock_m3u):
        """load_tuner_data merges EPG data from all source tuners."""
        self._add_source_tuners()
        add_combined_tuner("Merged", ["Source A", "Source B"])

        mock_m3u.return_value = []
        mock_epg.side_effect = [
            {"ch1": [{"title": "Show A", "desc": "", "start": None, "stop": None}]},
            {"ch2": [{"title": "Show B", "desc": "", "start": None, "stop": None}]},
        ]

        channels, epg = load_tuner_data("Merged")

        assert "ch1" in epg
        assert "ch2" in epg

    @patch('app.parse_m3u')
    @patch('app.parse_epg')
    def test_load_tuner_data_standard(self, mock_epg, mock_m3u):
        """load_tuner_data delegates to parse_m3u / parse_epg for standard tuners."""
        add_tuner("Std", "https://example.com/g.xml", "https://example.com/p.m3u")

        mock_m3u.return_value = [{"name": "Ch", "url": "http://x/s.m3u8", "logo": "", "tvg_id": "ch"}]
        mock_epg.return_value = {"ch": []}

        channels, epg = load_tuner_data("Std")

        mock_m3u.assert_called_once_with("https://example.com/p.m3u")
        mock_epg.assert_called_once_with("https://example.com/g.xml")
        assert len(channels) == 1

    @patch('app.parse_m3u')
    @patch('app.parse_epg')
    def test_load_tuner_data_combined_skips_missing_source(self, mock_epg, mock_m3u):
        """load_tuner_data skips source tuners that no longer exist."""
        add_tuner("Source A", "https://example.com/a.xml", "https://example.com/a.m3u")
        add_combined_tuner("Merged", ["Source A", "Ghost Tuner"])

        mock_m3u.return_value = [{"name": "Ch1", "url": "http://a/1.m3u8", "logo": "", "tvg_id": "ch1"}]
        mock_epg.return_value = {}

        channels, epg = load_tuner_data("Merged")

        # Only Source A channels should be present; Ghost Tuner is silently skipped
        assert len(channels) == 1
        assert channels[0]["name"] == "Ch1"

    # ------------------------------------------------------------------ #
    # /api/health — combined tuner returns N/A fields                     #
    # ------------------------------------------------------------------ #

    def test_api_health_combined_tuner_returns_na_fields(self):
        """api_health returns null for reachability fields when active tuner is combined."""
        import app as app_module
        self._add_source_tuners()
        add_combined_tuner("My Combined", ["Source A", "Source B"])
        app_module.set_current_tuner("My Combined")

        # Create a test user and log in
        app_module.add_user("testuser", "testpass")
        app.config["TESTING"] = True

        with app.test_client() as client:
            client.post("/login", data={"username": "testuser", "password": "testpass"},
                        follow_redirects=True)
            resp = client.get("/api/health")
            assert resp.status_code == 200
            data = resp.get_json()

        assert data["tuner_type"] == "combined"
        assert data["m3u_reachable"] is None
        assert data["xml_reachable"] is None
        assert data["xmltv_fresh"] is None
        assert data["tuner_m3u"] is None
        assert data["tuner_xml"] is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
