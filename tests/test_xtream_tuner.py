"""Test cases for Xtream Codes tuner functionality"""
import pytest
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db, init_tuners_db, add_xtream_tuner, get_tuners


class TestXtreamTuner:
    """Test Xtream Codes tuner add functionality"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
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

    def test_add_xtream_tuner_constructs_urls(self):
        """Xtream Codes tuner should store correct M3U and EPG URLs"""
        add_xtream_tuner("My Xtream", "http://xtream.example.com:8080", "user1", "pass1")

        tuners = get_tuners()
        assert "My Xtream" in tuners
        info = tuners["My Xtream"]
        assert "get.php" in info["m3u"]
        assert "username=user1" in info["m3u"]
        assert "password=pass1" in info["m3u"]
        assert "xmltv.php" in info["xml"]
        assert "username=user1" in info["xml"]
        assert "password=pass1" in info["xml"]
        assert info["tuner_type"] == "xtream"

    def test_add_xtream_tuner_strips_trailing_slash(self):
        """Server URL trailing slash should be stripped before building API URLs"""
        add_xtream_tuner("Xtream Slash", "http://xtream.example.com:8080/", "u", "p")

        tuners = get_tuners()
        info = tuners["Xtream Slash"]
        assert "http://xtream.example.com:8080/get.php" in info["m3u"]
        assert "http://xtream.example.com:8080/xmltv.php" in info["xml"]

    def test_add_xtream_tuner_duplicate_name_rejected(self):
        """Duplicate tuner names should raise ValueError"""
        add_xtream_tuner("DupXtream", "http://xtream.example.com:8080", "u", "p")
        with pytest.raises(ValueError, match="already exists"):
            add_xtream_tuner("DupXtream", "http://xtream.example.com:8080", "u", "p")

    def test_add_xtream_tuner_empty_username_rejected(self):
        """Empty username should raise ValueError"""
        with pytest.raises(ValueError, match="username cannot be empty"):
            add_xtream_tuner("XtreamTest", "http://xtream.example.com:8080", "", "pass")

    def test_add_xtream_tuner_empty_password_rejected(self):
        """Empty password should raise ValueError"""
        with pytest.raises(ValueError, match="password cannot be empty"):
            add_xtream_tuner("XtreamTest", "http://xtream.example.com:8080", "user", "")

    def test_add_xtream_tuner_invalid_server_url(self):
        """Non-http server URL should raise ValueError"""
        with pytest.raises(ValueError):
            add_xtream_tuner("XtreamTest", "ftp://invalid.example.com", "user", "pass")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
