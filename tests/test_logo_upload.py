"""Tests for virtual channel logo upload/reset API and helper functions."""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import (
    app, init_db, init_tuners_db, add_user,
    get_channel_custom_logo, save_channel_custom_logo,
    LOGO_UPLOAD_DIR, _ALLOWED_LOGO_EXTENSIONS, _DEFAULT_CHANNEL_LOGOS,
    VIRTUAL_CHANNELS,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    logo_dir  = str(tmp_path / "logos" / "virtual")
    monkeypatch.setattr(app_module, "DATABASE",         users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",         tuners_db)
    monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR",  logo_dir)
    init_db()
    init_tuners_db()
    add_user("admin", "adminpass")
    add_user("viewer", "viewerpass")
    yield


@pytest.fixture()
def client(isolated_env):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client, username="admin", password="adminpass"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


def _fake_png():
    """Minimal 1×1 PNG bytes."""
    return (
        b'\x89PNG\r\n\x1a\n'
        b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02'
        b'\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
        b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )


# ─── _DEFAULT_CHANNEL_LOGOS ──────────────────────────────────────────────────

class TestDefaultChannelLogos:
    def test_all_virtual_channels_have_defaults(self):
        ids = {ch['tvg_id'] for ch in VIRTUAL_CHANNELS}
        for tvg_id in ids:
            assert tvg_id in _DEFAULT_CHANNEL_LOGOS, f"No default logo for {tvg_id}"

    def test_default_logos_start_with_static(self):
        for tvg_id, path in _DEFAULT_CHANNEL_LOGOS.items():
            assert path.startswith('/static/'), f"Default logo for {tvg_id} should be a static path"


# ─── get/save_channel_custom_logo ────────────────────────────────────────────

class TestChannelCustomLogo:
    def test_default_is_empty(self):
        assert get_channel_custom_logo('virtual.news') == ''

    def test_save_and_reload(self, tmp_path, monkeypatch):
        d = tmp_path / "logos" / "virtual"
        d.mkdir(parents=True)
        monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR", str(d))
        (d / "virtual_news_logo.png").write_bytes(b'x')
        save_channel_custom_logo('virtual.news', 'virtual_news_logo.png')
        assert get_channel_custom_logo('virtual.news') == 'virtual_news_logo.png'

    def test_save_empty_clears(self, tmp_path, monkeypatch):
        d = tmp_path / "logos" / "virtual"
        d.mkdir(parents=True)
        monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR", str(d))
        (d / "virtual_news_logo.png").write_bytes(b'x')
        save_channel_custom_logo('virtual.news', 'virtual_news_logo.png')
        save_channel_custom_logo('virtual.news', '')
        assert get_channel_custom_logo('virtual.news') == ''

    def test_channels_isolated(self, tmp_path, monkeypatch):
        d = tmp_path / "logos" / "virtual"
        d.mkdir(parents=True)
        monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR", str(d))
        (d / "virtual_news_logo.png").write_bytes(b'x')
        (d / "virtual_weather_logo.png").write_bytes(b'x')
        save_channel_custom_logo('virtual.news',    'virtual_news_logo.png')
        save_channel_custom_logo('virtual.weather', 'virtual_weather_logo.png')
        assert get_channel_custom_logo('virtual.news')    == 'virtual_news_logo.png'
        assert get_channel_custom_logo('virtual.weather') == 'virtual_weather_logo.png'

    def test_invalid_extension_raises(self, tmp_path, monkeypatch):
        d = tmp_path / "logos" / "virtual"
        d.mkdir(parents=True)
        monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR", str(d))
        with pytest.raises(ValueError, match="Unsupported logo type"):
            save_channel_custom_logo('virtual.news', 'evil.exe')

    def test_file_not_found_raises(self, tmp_path, monkeypatch):
        d = tmp_path / "logos" / "virtual"
        d.mkdir(parents=True)
        monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR", str(d))
        with pytest.raises(ValueError, match="not found"):
            save_channel_custom_logo('virtual.news', 'missing.png')


# ─── get_virtual_channels reflects custom logo ───────────────────────────────

class TestGetVirtualChannelsCustomLogo:
    def test_custom_logo_applied(self, tmp_path, monkeypatch):
        d = tmp_path / "logos" / "virtual"
        d.mkdir(parents=True)
        monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR", str(d))
        (d / "virtual_news_logo.png").write_bytes(b'x')
        save_channel_custom_logo('virtual.news', 'virtual_news_logo.png')
        from app import get_virtual_channels
        channels = get_virtual_channels()
        news_ch = next(ch for ch in channels if ch['tvg_id'] == 'virtual.news')
        assert news_ch['logo'] == '/static/logos/virtual/virtual_news_logo.png'

    def test_no_custom_logo_uses_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR", str(tmp_path / "logos" / "virtual"))
        from app import get_virtual_channels
        channels = get_virtual_channels()
        news_ch = next(ch for ch in channels if ch['tvg_id'] == 'virtual.news')
        assert news_ch['logo'] == '/static/logos/virtual/news.svg'


# ─── /api/logo/upload ────────────────────────────────────────────────────────

class TestApiLogoUpload:
    def test_requires_login(self, client):
        data = {'logo_file': (io.BytesIO(_fake_png()), 'test.png'), 'tvg_id': 'virtual.news'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code in (302, 401)

    def test_non_admin_rejected(self, client):
        login(client, 'viewer', 'viewerpass')
        data = {'logo_file': (io.BytesIO(_fake_png()), 'test.png'), 'tvg_id': 'virtual.news'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 403

    def test_upload_png_succeeds(self, client):
        login(client)
        data = {'logo_file': (io.BytesIO(_fake_png()), 'mylogo.png'), 'tvg_id': 'virtual.news'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['ok'] is True
        assert body['filename'].endswith('.png')
        assert body['url'].startswith('/static/logos/virtual/')
        assert os.path.isfile(os.path.join(app_module.LOGO_UPLOAD_DIR, body['filename']))

    def test_upload_svg_succeeds(self, client):
        login(client)
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        data = {'logo_file': (io.BytesIO(svg_content), 'icon.svg'), 'tvg_id': 'virtual.weather'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['ok'] is True
        assert body['filename'].endswith('.svg')

    def test_upload_disallowed_extension_rejected(self, client):
        login(client)
        data = {'logo_file': (io.BytesIO(b'evil'), 'virus.exe'), 'tvg_id': 'virtual.news'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_upload_no_file_returns_400(self, client):
        login(client)
        data = {'tvg_id': 'virtual.news'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_upload_unknown_channel_returns_400(self, client):
        login(client)
        data = {'logo_file': (io.BytesIO(_fake_png()), 'test.png'), 'tvg_id': 'virtual.unknown'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_upload_persists_custom_logo(self, client):
        """Uploading a logo should cause get_channel_custom_logo to return the new filename."""
        login(client)
        data = {'logo_file': (io.BytesIO(_fake_png()), 'news_icon.png'), 'tvg_id': 'virtual.news'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 201
        saved_name = resp.get_json()['filename']
        assert get_channel_custom_logo('virtual.news') == saved_name

    def test_upload_uses_channel_slug_prefix(self, client):
        """The saved filename should be prefixed with the channel slug."""
        login(client)
        data = {'logo_file': (io.BytesIO(_fake_png()), 'myfile.png'), 'tvg_id': 'virtual.traffic'}
        resp = client.post('/api/logo/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 201
        filename = resp.get_json()['filename']
        assert filename.startswith('virtual_traffic_logo')


# ─── /api/logo/reset/<tvg_id> ────────────────────────────────────────────────

class TestApiLogoReset:
    def test_requires_login(self, client):
        resp = client.post('/api/logo/reset/virtual.news')
        assert resp.status_code in (302, 401)

    def test_non_admin_rejected(self, client):
        login(client, 'viewer', 'viewerpass')
        resp = client.post('/api/logo/reset/virtual.news')
        assert resp.status_code == 403

    def test_reset_unknown_channel_returns_400(self, client):
        login(client)
        resp = client.post('/api/logo/reset/virtual.unknown')
        assert resp.status_code == 400

    def test_reset_returns_default_url(self, client):
        login(client)
        resp = client.post('/api/logo/reset/virtual.news')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['ok'] is True
        assert body['url'] == _DEFAULT_CHANNEL_LOGOS['virtual.news']

    def test_reset_clears_custom_logo(self, client, tmp_path, monkeypatch):
        """After uploading a custom logo, reset should clear it."""
        d = tmp_path / "logos" / "virtual"
        d.mkdir(parents=True)
        monkeypatch.setattr(app_module, "LOGO_UPLOAD_DIR", str(d))
        (d / "virtual_news_logo.png").write_bytes(b'x')
        save_channel_custom_logo('virtual.news', 'virtual_news_logo.png')
        assert get_channel_custom_logo('virtual.news') == 'virtual_news_logo.png'
        login(client)
        resp = client.post('/api/logo/reset/virtual.news')
        assert resp.status_code == 200
        assert get_channel_custom_logo('virtual.news') == ''

    def test_all_channels_can_be_reset(self, client):
        """All virtual channels should support the reset endpoint."""
        login(client)
        for ch in VIRTUAL_CHANNELS:
            resp = client.post(f'/api/logo/reset/{ch["tvg_id"]}')
            assert resp.status_code == 200, f"Reset failed for {ch['tvg_id']}"


# ─── Virtual channels page shows logo UI ─────────────────────────────────────

class TestVirtualChannelPageLogoUI:
    def test_logo_upload_section_present(self, client):
        login(client)
        resp = client.get('/virtual_channels')
        assert resp.status_code == 200
        assert b'vc-logo-upload-section' in resp.data

    def test_logo_upload_btn_present(self, client):
        login(client)
        resp = client.get('/virtual_channels')
        assert b'vc-logo-upload-btn' in resp.data

    def test_logo_reset_btn_present(self, client):
        login(client)
        resp = client.get('/virtual_channels')
        assert b'vc-logo-reset-btn' in resp.data
