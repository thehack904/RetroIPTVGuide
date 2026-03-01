"""Tests for audio file upload/delete/list and per-channel music file selection."""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import (
    app, init_db, init_tuners_db, add_user,
    get_channel_music_file, save_channel_music_file, list_audio_files,
    AUDIO_UPLOAD_DIR, _ALLOWED_AUDIO_EXTENSIONS,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    audio_dir = str(tmp_path / "audio")
    monkeypatch.setattr(app_module, "DATABASE",         users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",         tuners_db)
    monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", audio_dir)
    init_db()
    init_tuners_db()
    add_user("admin", "adminpass")
    yield


@pytest.fixture()
def client(isolated_env):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def login(client, username="admin", password="adminpass"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


def _fake_mp3():
    """Return a minimal valid-ish MP3 byte payload (just enough for upload tests)."""
    return b'\xff\xfb\x90\x00' + b'\x00' * 128


# ─── list_audio_files ────────────────────────────────────────────────────────

class TestListAudioFiles:
    def test_empty_when_no_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(tmp_path / "audio"))
        assert list_audio_files() == []

    def test_returns_allowed_extensions_only(self, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "track.mp3").write_bytes(b'x')
        (d / "song.ogg").write_bytes(b'x')
        (d / "readme.txt").write_bytes(b'x')   # should be excluded
        (d / ".gitkeep").write_bytes(b'')       # should be excluded
        files = list_audio_files()
        assert "track.mp3" in files
        assert "song.ogg"  in files
        assert "readme.txt" not in files
        assert ".gitkeep"   not in files

    def test_returns_sorted_list(self, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        for name in ("zzz.mp3", "aaa.mp3", "mmm.ogg"):
            (d / name).write_bytes(b'x')
        files = list_audio_files()
        assert files == sorted(files)


# ─── get/save_channel_music_file ────────────────────────────────────────────

class TestChannelMusicFile:
    def test_default_is_empty(self):
        assert get_channel_music_file('virtual.weather') == ''

    def test_save_and_reload(self, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "rain.mp3").write_bytes(b'x')
        save_channel_music_file('virtual.weather', 'rain.mp3')
        assert get_channel_music_file('virtual.weather') == 'rain.mp3'

    def test_save_empty_clears(self, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "rain.mp3").write_bytes(b'x')
        save_channel_music_file('virtual.weather', 'rain.mp3')
        save_channel_music_file('virtual.weather', '')
        assert get_channel_music_file('virtual.weather') == ''

    def test_channels_isolated(self, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "rain.mp3").write_bytes(b'x')
        (d / "jazz.mp3").write_bytes(b'x')
        save_channel_music_file('virtual.weather', 'rain.mp3')
        save_channel_music_file('virtual.news',    'jazz.mp3')
        assert get_channel_music_file('virtual.weather') == 'rain.mp3'
        assert get_channel_music_file('virtual.news')    == 'jazz.mp3'

    def test_invalid_extension_raises(self, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        with pytest.raises(ValueError, match="Unsupported audio type"):
            save_channel_music_file('virtual.weather', 'evil.exe')

    def test_file_not_found_raises(self, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        with pytest.raises(ValueError, match="not found"):
            save_channel_music_file('virtual.weather', 'missing.mp3')


# ─── /api/audio/files ───────────────────────────────────────────────────────

class TestApiAudioFiles:
    def test_requires_login(self, client):
        resp = client.get('/api/audio/files')
        assert resp.status_code in (302, 401)

    def test_returns_empty_list_initially(self, client):
        login(client)
        resp = client.get('/api/audio/files')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['files'] == []

    def test_returns_uploaded_files(self, client, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "tune.mp3").write_bytes(b'x')
        login(client)
        resp = client.get('/api/audio/files')
        assert "tune.mp3" in resp.get_json()['files']


# ─── /api/audio/upload ───────────────────────────────────────────────────────

class TestApiAudioUpload:
    def test_requires_login(self, client):
        data = {'audio_file': (io.BytesIO(_fake_mp3()), 'test.mp3')}
        resp = client.post('/api/audio/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code in (302, 401)

    def test_upload_mp3_succeeds(self, client):
        login(client)
        data = {'audio_file': (io.BytesIO(_fake_mp3()), 'mysong.mp3')}
        resp = client.post('/api/audio/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['ok'] is True
        assert body['filename'] == 'mysong.mp3'
        assert os.path.isfile(os.path.join(app_module.AUDIO_UPLOAD_DIR, 'mysong.mp3'))

    def test_upload_disallowed_extension_rejected(self, client):
        login(client)
        data = {'audio_file': (io.BytesIO(b'evil'), 'virus.exe')}
        resp = client.post('/api/audio/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_upload_no_file_returns_400(self, client):
        login(client)
        resp = client.post('/api/audio/upload', data={},
                           content_type='multipart/form-data')
        assert resp.status_code == 400

    def test_upload_ogg_succeeds(self, client):
        login(client)
        data = {'audio_file': (io.BytesIO(b'OggS'), 'ambient.ogg')}
        resp = client.post('/api/audio/upload', data=data,
                           content_type='multipart/form-data')
        assert resp.status_code == 201
        assert resp.get_json()['filename'] == 'ambient.ogg'


# ─── /api/audio/delete ───────────────────────────────────────────────────────

class TestApiAudioDelete:
    def test_requires_login(self, client):
        resp = client.post('/api/audio/delete/test.mp3')
        assert resp.status_code in (302, 401)

    def test_delete_existing_file(self, client):
        login(client)
        # Upload first
        client.post('/api/audio/upload',
                    data={'audio_file': (io.BytesIO(_fake_mp3()), 'del_me.mp3')},
                    content_type='multipart/form-data')
        assert os.path.isfile(os.path.join(app_module.AUDIO_UPLOAD_DIR, 'del_me.mp3'))
        resp = client.post('/api/audio/delete/del_me.mp3')
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        assert not os.path.isfile(os.path.join(app_module.AUDIO_UPLOAD_DIR, 'del_me.mp3'))

    def test_delete_nonexistent_returns_404(self, client):
        login(client)
        resp = client.post('/api/audio/delete/nope.mp3')
        assert resp.status_code == 404

    def test_delete_disallowed_extension_rejected(self, client):
        login(client)
        resp = client.post('/api/audio/delete/evil.exe')
        assert resp.status_code == 400


# ─── /api/weather includes music_file ────────────────────────────────────────

class TestApiWeatherMusicFile:
    def test_music_file_absent_when_not_set(self, client):
        login(client)
        resp = client.get('/api/weather')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'music_file' in data
        assert data['music_file'] == ''

    def test_music_file_present_when_set(self, client, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "chill.mp3").write_bytes(b'x')
        save_channel_music_file('virtual.weather', 'chill.mp3')
        login(client)
        resp = client.get('/api/weather')
        data = resp.get_json()
        assert data['music_file'] == '/static/audio/chill.mp3'


# ─── change_tuner page includes audio UI ─────────────────────────────────────

class TestChangeTunerAudioUI:
    def test_audio_upload_section_present(self, client):
        login(client)
        resp = client.get('/change_tuner')
        assert resp.status_code == 200
        assert b'audio-upload-section' in resp.data
        assert b'audio_file' in resp.data

    def test_music_dropdown_present(self, client):
        login(client)
        resp = client.get('/change_tuner')
        assert b'ch_music_file' in resp.data

    def test_save_music_file_via_change_tuner(self, client, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "loop.mp3").write_bytes(b'x')
        login(client)
        resp = client.post('/change_tuner', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '',
            'ch_bg_color': '',
            'ch_test_text': '',
            'ch_weather_location': 'Miami, FL',
            'ch_weather_lat': '25.77',
            'ch_weather_lon': '-80.19',
            'ch_weather_units': 'F',
            'ch_music_file': 'loop.mp3',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert get_channel_music_file('virtual.weather') == 'loop.mp3'

    def test_save_empty_music_file_clears(self, client, tmp_path, monkeypatch):
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "loop.mp3").write_bytes(b'x')
        save_channel_music_file('virtual.weather', 'loop.mp3')
        login(client)
        client.post('/change_tuner', data={
            'action': 'update_channel_overlay_appearance',
            'tvg_id': 'virtual.weather',
            'ch_text_color': '',
            'ch_bg_color': '',
            'ch_test_text': '',
            'ch_weather_location': '',
            'ch_weather_lat': '',
            'ch_weather_lon': '',
            'ch_weather_units': 'F',
            'ch_music_file': '',
        }, follow_redirects=True)
        assert get_channel_music_file('virtual.weather') == ''


# ─── Guide page includes data-music-file ─────────────────────────────────────

class TestGuideMusicFile:
    def test_guide_has_data_music_file_attribute(self, client):
        """Guide page HTML includes the data-music-file attribute on virtual channels."""
        login(client)
        resp = client.get('/guide')
        assert resp.status_code == 200
        assert b'data-music-file' in resp.data

    def test_guide_includes_music_src_when_set(self, client, tmp_path, monkeypatch):
        """When a music file is saved for a channel, the guide page embeds its path."""
        d = tmp_path / "audio"
        d.mkdir()
        monkeypatch.setattr(app_module, "AUDIO_UPLOAD_DIR", str(d))
        (d / "chill.mp3").write_bytes(b'x')
        save_channel_music_file('virtual.weather', 'chill.mp3')
        login(client)
        resp = client.get('/guide')
        assert b'chill.mp3' in resp.data

    def test_guide_music_file_empty_when_not_set(self, client):
        """With no music file configured, the data-music-file attribute is empty."""
        login(client)
        resp = client.get('/guide')
        assert b'data-music-file=""' in resp.data
