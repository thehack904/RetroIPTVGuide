"""Tests for command-injection prevention in /api/start_stream and /api/stop_stream.

Covers CWE-078 / CWE-088 (py/command-line-injection) for the two endpoints that
invoke helper shell scripts via subprocess.  All tests exercise the validation
helpers and the Flask endpoints directly without actually running any subprocess
(subprocess.check_call is mocked).
"""
import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db, add_user
from app import is_valid_stream_url, is_valid_instance_id, _STREAM_URL_RE, _INSTANCE_ID_RE


# ---------------------------------------------------------------------------
# Unit tests for the validation helpers
# ---------------------------------------------------------------------------

class TestIsValidStreamUrl:
    """Test is_valid_stream_url() – the URL allowlist validator."""

    def test_valid_http_url(self):
        assert is_valid_stream_url("http://example.com/stream.m3u8")

    def test_valid_https_url(self):
        assert is_valid_stream_url("https://cdn.example.com/live/stream?token=abc123&fmt=ts")

    def test_rejects_non_string(self):
        assert not is_valid_stream_url(None)
        assert not is_valid_stream_url(123)

    def test_rejects_empty_string(self):
        assert not is_valid_stream_url("")

    def test_rejects_ftp_scheme(self):
        assert not is_valid_stream_url("ftp://example.com/stream")

    def test_rejects_shell_metacharacters_semicolon(self):
        assert not is_valid_stream_url("http://example.com/;rm -rf /")

    def test_rejects_shell_metacharacters_backtick(self):
        assert not is_valid_stream_url("http://example.com/`id`")

    def test_rejects_shell_metacharacters_pipe(self):
        assert not is_valid_stream_url("http://example.com/stream|bash")

    def test_allows_valid_query_string_with_ampersand(self):
        assert is_valid_stream_url("http://example.com/stream?a=1&b=2")

    def test_rejects_newlines(self):
        assert not is_valid_stream_url("http://example.com/\nmalicious")

    def test_rejects_no_netloc(self):
        assert not is_valid_stream_url("http:///path/only")

    def test_url_too_long(self):
        long_path = "a" * 3000
        assert not is_valid_stream_url(f"http://example.com/{long_path}")

    def test_valid_url_with_port(self):
        assert is_valid_stream_url("http://example.com:8080/stream.m3u8")

    def test_valid_url_with_path_and_query(self):
        assert is_valid_stream_url(
            "https://cdn.example.com/hls/channel1/index.m3u8?auth=token123"
        )


class TestIsValidInstanceId:
    """Test is_valid_instance_id() – the instance-id allowlist validator."""

    def test_valid_default(self):
        assert is_valid_instance_id("default")

    def test_valid_alphanumeric(self):
        assert is_valid_instance_id("stream1")

    def test_valid_with_underscore_and_hyphen(self):
        assert is_valid_instance_id("my_stream-01")

    def test_rejects_empty_string(self):
        assert not is_valid_instance_id("")

    def test_rejects_semicolon(self):
        assert not is_valid_instance_id("default; rm -rf /")

    def test_rejects_space(self):
        assert not is_valid_instance_id("default instance")

    def test_rejects_shell_substitution(self):
        assert not is_valid_instance_id("$(id)")

    def test_rejects_backtick(self):
        assert not is_valid_instance_id("`id`")

    def test_rejects_pipe(self):
        assert not is_valid_instance_id("stream|bash")

    def test_rejects_too_long(self):
        assert not is_valid_instance_id("a" * 65)

    def test_accepts_max_length(self):
        assert is_valid_instance_id("a" * 64)

    def test_rejects_newline(self):
        assert not is_valid_instance_id("default\n")

    def test_rejects_null_byte(self):
        assert not is_valid_instance_id("default\x00")


# ---------------------------------------------------------------------------
# Integration tests via Flask test client
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Create a Flask test client with temporary databases."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    users_db = str(tmp_path / "users.db")
    tuners_db = str(tmp_path / "tuners.db")

    monkeypatch.setattr(app_module, "DATABASE", users_db)
    monkeypatch.setattr(app_module, "TUNER_DB", tuners_db)

    init_db()
    init_tuners_db()
    add_user("testuser", "testpass")

    with app.test_client() as c:
        c.post(
            "/login",
            data={"username": "testuser", "password": "testpass"},
            follow_redirects=True,
        )
        yield c


class TestStartStreamEndpoint:
    """Test /api/start_stream rejects unsafe inputs before any subprocess call."""

    def test_missing_url_returns_400(self, client):
        resp = client.post("/api/start_stream", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "missing url"

    def test_invalid_url_scheme_returns_400(self, client):
        resp = client.post("/api/start_stream", json={"url": "ftp://example.com/stream"})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid url"

    def test_url_with_shell_injection_returns_400(self, client):
        resp = client.post(
            "/api/start_stream",
            json={"url": "http://example.com/;rm -rf /"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid url"

    def test_url_with_backtick_injection_returns_400(self, client):
        resp = client.post(
            "/api/start_stream",
            json={"url": "http://example.com/`id`"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid url"

    def test_invalid_instance_id_returns_400(self, client):
        resp = client.post(
            "/api/start_stream",
            json={
                "url": "http://example.com/stream.m3u8",
                "id": "bad id; rm -rf /",
            },
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid instance id"

    def test_valid_inputs_call_subprocess(self, client):
        with patch("app.subprocess.check_call") as mock_call:
            mock_call.return_value = 0
            resp = client.post(
                "/api/start_stream",
                json={"url": "http://example.com/stream.m3u8", "id": "default"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        # Verify subprocess was called with the validated (safe) values only
        called_cmd = mock_call.call_args[0][0]
        assert called_cmd[2] == "http://example.com/stream.m3u8"
        assert called_cmd[3] == "default"
        # No shell metacharacters in the arguments
        for arg in called_cmd:
            assert ";" not in arg
            assert "|" not in arg
            assert "`" not in arg

    def test_hide_cursor_appends_hide_arg(self, client):
        with patch("app.subprocess.check_call") as mock_call:
            mock_call.return_value = 0
            resp = client.post(
                "/api/start_stream",
                json={
                    "url": "http://example.com/stream.m3u8",
                    "id": "default",
                    "hide_cursor": True,
                },
            )
        assert resp.status_code == 200
        called_cmd = mock_call.call_args[0][0]
        assert called_cmd[-1] == "hide"


class TestStopStreamEndpoint:
    """Test /api/stop_stream rejects unsafe instance IDs before any subprocess call."""

    def test_invalid_instance_id_returns_400(self, client):
        resp = client.post(
            "/api/stop_stream",
            json={"id": "default; rm -rf /"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid instance id"

    def test_shell_substitution_returns_400(self, client):
        resp = client.post(
            "/api/stop_stream",
            json={"id": "$(id)"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid instance id"

    def test_valid_instance_calls_subprocess(self, client):
        with patch("app.subprocess.check_call") as mock_call:
            mock_call.return_value = 0
            resp = client.post(
                "/api/stop_stream",
                json={"id": "default"},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        called_cmd = mock_call.call_args[0][0]
        assert called_cmd[2] == "default"

    def test_default_instance_used_when_id_omitted(self, client):
        with patch("app.subprocess.check_call") as mock_call:
            mock_call.return_value = 0
            resp = client.post("/api/stop_stream", json={})
        assert resp.status_code == 200
        called_cmd = mock_call.call_args[0][0]
        # Should fall back to INSTANCE_ID ("default")
        assert called_cmd[2] == app_module.INSTANCE_ID

