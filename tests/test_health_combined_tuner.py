"""Test cases for /api/health with combined (single-stream) tuners"""
import pytest
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db, init_tuners_db, add_tuner, set_current_tuner
import app as app_module


@pytest.fixture
def client():
    """Set up a test Flask client with isolated databases."""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_tuner_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')

    orig_db = app_module.DATABASE
    orig_tuner_db = app_module.TUNER_DB

    app_module.DATABASE = temp_db.name
    app_module.TUNER_DB = temp_tuner_db.name

    init_db()
    init_tuners_db()
    app_module.add_user('admin', 'testpassword')

    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as c:
        # Log in by setting the session user ID (user ID 1 created by add_user above)
        with c.session_transaction() as sess:
            sess['_user_id'] = '1'
            sess['_fresh'] = True
        yield c

    app_module.DATABASE = orig_db
    app_module.TUNER_DB = orig_tuner_db
    os.unlink(temp_db.name)
    os.unlink(temp_tuner_db.name)


class TestHealthCombinedTuner:
    """Test /api/health endpoint behaviour for combined (single-stream) tuners."""

    def test_combined_tuner_returns_na_fields(self, client):
        """When m3u_url == xml_url the health endpoint must return null for
        m3u_reachable, xml_reachable, xmltv_fresh, and xmltv_age_hours,
        and is_combined_tuner must be True."""
        stream_url = "https://example.com/live/stream.m3u8"
        add_tuner("SingleStream", stream_url, stream_url)
        set_current_tuner("SingleStream")

        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.get_json()

        assert data["is_combined_tuner"] is True
        assert data["m3u_reachable"] is None
        assert data["xml_reachable"] is None
        assert data["xmltv_fresh"] is None
        assert data["xmltv_age_hours"] is None
        assert data["tuner_m3u"] == stream_url
        assert data["tuner_xml"] == stream_url

    def test_standard_tuner_returns_is_combined_false(self, client):
        """When m3u_url != xml_url is_combined_tuner must be False."""
        xml_url = "https://example.com/guide.xml"
        m3u_url = "https://example.com/playlist.m3u"
        add_tuner("Standard", xml_url, m3u_url)
        set_current_tuner("Standard")

        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.get_json()

        assert data["is_combined_tuner"] is False
        # Values may be False (unreachable in test env) but must not be None
        assert data["m3u_reachable"] is not None
        assert data["xml_reachable"] is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
