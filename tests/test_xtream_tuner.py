"""Test cases for Xtream Codes tuner functionality"""
import pytest
import sys
import os
import tempfile
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db, init_tuners_db, add_xtream_tuner, update_xtream_tuner, get_tuners


def _parsed_qs(url):
    """Return query-string dict for url."""
    return parse_qs(urlparse(url).query)


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
        m3u_parsed = urlparse(info["m3u"])
        xml_parsed = urlparse(info["xml"])
        m3u_qs = _parsed_qs(info["m3u"])
        xml_qs = _parsed_qs(info["xml"])
        assert m3u_parsed.path == "/get.php"
        assert m3u_qs.get("username") == ["user1"]
        assert m3u_qs.get("password") == ["pass1"]
        assert xml_parsed.path == "/xmltv.php"
        assert xml_qs.get("username") == ["user1"]
        assert xml_qs.get("password") == ["pass1"]
        assert info["tuner_type"] == "xtream"

    def test_add_xtream_tuner_strips_trailing_slash(self):
        """Server URL trailing slash should be stripped before building API URLs"""
        add_xtream_tuner("Xtream Slash", "http://xtream.example.com:8080/", "u", "p")

        tuners = get_tuners()
        info = tuners["Xtream Slash"]
        m3u_parsed = urlparse(info["m3u"])
        xml_parsed = urlparse(info["xml"])
        assert m3u_parsed.netloc == "xtream.example.com:8080"
        assert m3u_parsed.path == "/get.php"
        assert xml_parsed.netloc == "xtream.example.com:8080"
        assert xml_parsed.path == "/xmltv.php"

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


class TestUpdateXtreamTuner:
    """Test Xtream Codes tuner update functionality"""

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

    def test_update_xtream_tuner_changes_credentials(self):
        """update_xtream_tuner should rebuild URLs with new credentials"""
        add_xtream_tuner("EditXtream", "http://xtream.example.com:8080", "olduser", "oldpass")
        update_xtream_tuner("EditXtream", "http://newserver.example.com:9000", "newuser", "newpass")

        tuners = get_tuners()
        info = tuners["EditXtream"]
        m3u_parsed = urlparse(info["m3u"])
        xml_parsed = urlparse(info["xml"])
        m3u_qs = _parsed_qs(info["m3u"])
        xml_qs = _parsed_qs(info["xml"])
        assert m3u_parsed.netloc == "newserver.example.com:9000"
        assert m3u_qs.get("username") == ["newuser"]
        assert m3u_qs.get("password") == ["newpass"]
        assert xml_parsed.netloc == "newserver.example.com:9000"
        assert xml_qs.get("username") == ["newuser"]
        assert xml_qs.get("password") == ["newpass"]

    def test_update_xtream_tuner_strips_trailing_slash(self):
        """Trailing slash in updated server URL should be stripped"""
        add_xtream_tuner("SlashXtream", "http://xtream.example.com:8080", "u", "p")
        update_xtream_tuner("SlashXtream", "http://newserver.example.com/", "u", "p")

        tuners = get_tuners()
        info = tuners["SlashXtream"]
        m3u_parsed = urlparse(info["m3u"])
        assert m3u_parsed.netloc == "newserver.example.com"
        assert m3u_parsed.path == "/get.php"

    def test_update_xtream_tuner_empty_username_rejected(self):
        """Empty username should raise ValueError on update"""
        add_xtream_tuner("EditXtream2", "http://xtream.example.com:8080", "user", "pass")
        with pytest.raises(ValueError, match="username cannot be empty"):
            update_xtream_tuner("EditXtream2", "http://xtream.example.com:8080", "", "pass")

    def test_update_xtream_tuner_empty_password_rejected(self):
        """Empty password should raise ValueError on update"""
        add_xtream_tuner("EditXtream3", "http://xtream.example.com:8080", "user", "pass")
        with pytest.raises(ValueError, match="password cannot be empty"):
            update_xtream_tuner("EditXtream3", "http://xtream.example.com:8080", "user", "")

    def test_update_xtream_tuner_invalid_server_url(self):
        """Non-http server URL should raise ValueError on update"""
        add_xtream_tuner("EditXtream4", "http://xtream.example.com:8080", "user", "pass")
        with pytest.raises(ValueError):
            update_xtream_tuner("EditXtream4", "ftp://invalid.example.com", "user", "pass")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
