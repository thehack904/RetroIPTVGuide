"""Tests for the Admin Diagnostics blueprint and utility modules."""
import io
import json
import os
import re
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Give every test its own empty SQLite databases + temp DATA_DIR."""
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    data_dir  = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(data_dir, "logs"), exist_ok=True)

    monkeypatch.setattr(app_module, "DATABASE",  users_db)
    monkeypatch.setattr(app_module, "TUNER_DB",  tuners_db)
    monkeypatch.setattr(app_module, "DATA_DIR",  data_dir)
    monkeypatch.setattr(app_module, "LOG_PATH",  os.path.join(data_dir, "logs", "activity.log"))

    # Update DIAG_ config keys that the blueprint reads from app.config
    app.config["DIAG_DATA_DIR"]   = data_dir
    app.config["DIAG_DATABASE"]   = users_db
    app.config["DIAG_TUNER_DB"]   = tuners_db

    # Also patch the log_reading allowlist so it points to the temp dir
    from utils import log_reading
    monkeypatch.setattr(
        log_reading, "ALLOWED_LOGS",
        {
            "app":      os.path.join(data_dir, "logs", "retroiptvguide.log"),
            "activity": os.path.join(data_dir, "logs", "activity.log"),
            "startup":  os.path.join(data_dir, "logs", "startup.log"),
        },
    )

    init_db()
    init_tuners_db()
    from app import add_user
    add_user("admin",    "adminpass")
    add_user("regular",  "regpass")
    yield tmp_path


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def login(client, username="admin", password="adminpass"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Tests: access control
# ---------------------------------------------------------------------------

class TestDiagnosticsAccessControl:
    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/admin/diagnostics")
        assert resp.status_code in (302, 401)

    def test_non_admin_gets_403(self, client):
        login(client, "regular", "regpass")
        resp = client.get("/admin/diagnostics")
        assert resp.status_code == 403

    def test_admin_can_access_index(self, client):
        login(client)
        resp = client.get("/admin/diagnostics")
        assert resp.status_code == 200
        assert b"Admin Diagnostics" in resp.data

    def test_no_post_route_on_logs(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/logs")
        assert resp.status_code == 405

    def test_no_post_route_on_health(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/health")
        assert resp.status_code == 405

    def test_no_post_route_on_system(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/system")
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# Tests: log reading endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsLogs:
    def _write_log(self, isolated_db, key, content):
        from utils.log_reading import ALLOWED_LOGS
        path = ALLOWED_LOGS[key]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)

    def test_unknown_key_returns_404(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/logs?key=../../etc/passwd")
        assert resp.status_code == 404

    def test_known_key_missing_file_returns_empty(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/logs?key=app")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["error"] == "Log file not found."
        assert data["lines"] == []

    def test_returns_log_lines(self, client, isolated_db):
        self._write_log(isolated_db, "app", "line1\nline2\nline3\n")
        login(client)
        resp = client.get("/admin/diagnostics/logs?key=app")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["count"] == 3
        assert "line1" in data["lines"][0]

    def test_html_escaped_in_output(self, client, isolated_db):
        self._write_log(isolated_db, "app", "<script>alert(1)</script>\n")
        login(client)
        resp = client.get("/admin/diagnostics/logs?key=app")
        data = json.loads(resp.data)
        assert "<script>" not in data["lines"][0]
        assert "&lt;script&gt;" in data["lines"][0]

    def test_secrets_redacted(self, client, isolated_db):
        self._write_log(isolated_db, "app", "token=supersecret123 info\n")
        login(client)
        resp = client.get("/admin/diagnostics/logs?key=app")
        data = json.loads(resp.data)
        assert "supersecret123" not in data["lines"][0]
        assert "***" in data["lines"][0]


# ---------------------------------------------------------------------------
# Tests: tail endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsTail:
    def _write_log(self, isolated_db, key, lines):
        from utils.log_reading import ALLOWED_LOGS
        path = ALLOWED_LOGS[key]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")

    def test_tail_returns_last_n_lines(self, client, isolated_db):
        # Use "app" log (not "activity") so login events don't affect the count
        from utils.log_reading import ALLOWED_LOGS
        path = ALLOWED_LOGS["app"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        all_lines = [f"line{i}" for i in range(50)]
        with open(path, "w") as fh:
            fh.write("\n".join(all_lines) + "\n")
        login(client)
        resp = client.get("/admin/diagnostics/logs/tail?key=app&n=10")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["count"] == 10
        assert "line49" in data["lines"][-1]

    def test_tail_unknown_key_404(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/logs/tail?key=doesnotexist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: download endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsDownload:
    def test_download_unknown_key_404(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/logs/download?key=badkey")
        assert resp.status_code == 404

    def test_download_returns_file(self, client, isolated_db):
        from utils.log_reading import ALLOWED_LOGS
        path = ALLOWED_LOGS["app"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("hello log\n")
        login(client)
        resp = client.get("/admin/diagnostics/logs/download?key=app")
        assert resp.status_code == 200
        assert b"hello log" in resp.data
        assert "text/plain" in resp.content_type

    def test_download_redacts_secrets(self, client, isolated_db):
        from utils.log_reading import ALLOWED_LOGS
        path = ALLOWED_LOGS["app"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("api_key=topsecret999\n")
        login(client)
        resp = client.get("/admin/diagnostics/logs/download?key=app")
        assert b"topsecret999" not in resp.data
        assert b"***" in resp.data


# ---------------------------------------------------------------------------
# Tests: health endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsHealth:
    def test_health_returns_all_checks(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/health")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        for key in ("db", "schema", "tuners", "xmltv", "disk_space", "write_permissions"):
            assert key in data
            assert "status" in data[key]
            assert "detail" in data[key]
            assert data[key]["status"] in ("PASS", "WARN", "FAIL")

    def test_health_db_passes(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/health")
        data = json.loads(resp.data)
        assert data["db"]["status"] == "PASS"

    def test_health_schema_passes(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/health")
        data = json.loads(resp.data)
        assert data["schema"]["status"] == "PASS"


# ---------------------------------------------------------------------------
# Tests: system info endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsSystem:
    def test_system_returns_expected_keys(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/system")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        for key in ("app_version", "python_version", "os_info", "uptime",
                    "data_dir", "install_mode", "safe_env"):
            assert key in data

    def test_system_no_secrets_in_safe_env(self, client, monkeypatch):
        """RETROIPTV_DATA_DIR is safe, PASSWORD is not."""
        monkeypatch.setenv("RETROIPTV_DATA_DIR", "/tmp/test-data")
        monkeypatch.setenv("SECRET_KEY", "definitely-secret")
        login(client)
        resp = client.get("/admin/diagnostics/system")
        data = json.loads(resp.data)
        # SECRET_KEY should not appear at all
        assert "SECRET_KEY" not in data.get("safe_env", {})
        assert "definitely-secret" not in json.dumps(data)


# ---------------------------------------------------------------------------
# Tests: support bundle endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsSupport:
    def test_support_returns_zip(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        assert resp.status_code == 200
        assert "application/zip" in resp.content_type

    def test_support_zip_contains_expected_files(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        names = zf.namelist()
        assert "health.json" in names
        assert "system.json" in names

    def test_support_zip_health_valid_json(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        health = json.loads(zf.read("health.json"))
        assert "db" in health

    def test_support_zip_excludes_secrets(self, client, isolated_db):
        from utils.log_reading import ALLOWED_LOGS
        path = ALLOWED_LOGS["app"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("password=hunter2\n")
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        all_content = b"".join(zf.read(n) for n in zf.namelist())
        assert b"hunter2" not in all_content

    def test_support_zip_contains_index_html(self, client, isolated_db):
        """Support bundle should include index.html for offline viewing."""
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        assert "index.html" in zf.namelist()

    def test_index_html_is_valid_html(self, client, isolated_db):
        """index.html should start with a doctype and contain expected landmarks."""
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        html_content = zf.read("index.html").decode("utf-8")
        assert html_content.startswith("<!DOCTYPE html>")
        assert "<html" in html_content
        assert "</html>" in html_content
        assert "RetroIPTVGuide Support Bundle" in html_content

    def test_index_html_embeds_health_data(self, client, isolated_db):
        """index.html should contain embedded JSON data from health.json."""
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        html_content = zf.read("index.html").decode("utf-8")
        # Viewer embeds the sections dict as a JS variable
        assert "var SECTIONS=" in html_content
        assert "health.json" in html_content

    def test_index_html_has_no_external_network_references(self, client, isolated_db):
        """index.html must be self-contained — no CDN or external resource links."""
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        html_content = zf.read("index.html").decode("utf-8")
        for external in ("cdn.jsdelivr", "cdnjs.cloudflare", "fonts.googleapis",
                         "unpkg.com", "ajax.googleapis"):
            assert external not in html_content, (
                f"index.html must not reference external resource: {external}"
            )

    def test_index_html_excludes_secrets_from_logs(self, client, isolated_db):
        """Secrets in log files must not appear in the embedded viewer HTML."""
        from utils.log_reading import ALLOWED_LOGS
        path = ALLOWED_LOGS["app"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write("token=verysecrettoken\nnormal startup line\n")
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        html_content = zf.read("index.html").decode("utf-8")
        assert "verysecrettoken" not in html_content
        # Normal content should still be present
        assert "normal startup line" in html_content


# ---------------------------------------------------------------------------
# Tests: utility functions (log_reading)
# ---------------------------------------------------------------------------

class TestLogReadingUtils:
    def test_redact_token(self, tmp_path):
        from utils.log_reading import _redact
        assert "***" in _redact("token=abc123")
        assert "abc123" not in _redact("token=abc123")

    def test_redact_password(self):
        from utils.log_reading import _redact
        assert "***" in _redact("password=secret")

    def test_redact_api_key(self):
        from utils.log_reading import _redact
        assert "***" in _redact("api_key=deadbeef")

    def test_safe_line_html_escapes(self):
        from utils.log_reading import _safe_line
        result = _safe_line("<b>test</b>")
        assert "&lt;b&gt;" in result
        assert "<b>" not in result

    def test_resource_cap_enforced(self, tmp_path, monkeypatch):
        from utils import log_reading
        # Write more lines than MAX_LINES
        path = tmp_path / "big.log"
        big = "\n".join(f"line{i}" for i in range(log_reading.MAX_LINES + 50))
        path.write_text(big)
        monkeypatch.setitem(log_reading.ALLOWED_LOGS, "big", str(path))
        lines, err = log_reading.read_log("big")
        # Should not exceed MAX_LINES + 1 (the truncation message)
        assert len(lines) <= log_reading.MAX_LINES + 1


# ---------------------------------------------------------------------------
# Tests: health_checks utilities
# ---------------------------------------------------------------------------

class TestHealthChecks:
    def test_check_db_pass(self, isolated_db):
        from utils.health_checks import check_db
        result = check_db(app_module.DATABASE)
        assert result["status"] == "PASS"

    def test_check_db_fail_missing(self, tmp_path):
        from utils.health_checks import check_db
        result = check_db(str(tmp_path / "nonexistent.db"))
        # SQLite creates new files, so it should pass even for non-existent
        # (or fail gracefully)
        assert result["status"] in ("PASS", "FAIL")

    def test_check_schema_pass(self, isolated_db):
        from utils.health_checks import check_schema
        result = check_schema(app_module.DATABASE)
        assert result["status"] == "PASS"

    def test_check_disk_space(self, isolated_db):
        from utils.health_checks import check_disk_space
        result = check_disk_space(app_module.DATA_DIR)
        assert result["status"] in ("PASS", "WARN", "FAIL")
        assert "detail" in result

    def test_check_write_permissions_pass(self, isolated_db):
        from utils.health_checks import check_write_permissions
        result = check_write_permissions(app_module.DATA_DIR)
        assert result["status"] == "PASS"

    def test_run_all_checks_returns_all_keys(self, isolated_db):
        from utils.health_checks import run_all_checks
        result = run_all_checks(app_module.DATA_DIR, app_module.DATABASE, app_module.TUNER_DB)
        for key in ("db", "schema", "tuners", "xmltv", "disk_space", "write_permissions",
                    "file_system", "cache_state"):
            assert key in result

    def test_check_db_includes_path_and_size(self, isolated_db):
        from utils.health_checks import check_db
        result = check_db(app_module.DATABASE)
        assert "path" in result
        assert "size_bytes" in result
        assert result["exists"] is True

    def test_check_schema_includes_table_list(self, isolated_db):
        from utils.health_checks import check_schema
        result = check_schema(app_module.DATABASE)
        assert "tables_found" in result
        assert "users" in result["tables_found"]

    def test_check_file_system_returns_db_paths(self, isolated_db):
        from utils.health_checks import check_file_system
        result = check_file_system(app_module.DATABASE, app_module.TUNER_DB, app_module.DATA_DIR)
        assert "users_db" in result
        assert "tuners_db" in result
        assert result["users_db"]["exists"] is True
        assert result["tuners_db"]["exists"] is True
        assert "data_dir" in result
        assert "logs_dir" in result
        assert "app_working_dir" in result

    def test_check_file_system_symlink_detection(self, isolated_db, tmp_path):
        """Symlink targets should be reported (critical for Docker volume debugging)."""
        from utils.health_checks import check_file_system
        # Create a symlink pointing to the real DB
        link_path = str(tmp_path / "link_users.db")
        os.symlink(app_module.DATABASE, link_path)
        result = check_file_system(link_path, app_module.TUNER_DB, app_module.DATA_DIR)
        assert result["users_db"]["is_symlink"] is True
        assert result["users_db"]["symlink_target"] is not None

    def test_check_cache_state_returns_expected_keys(self, isolated_db):
        from utils.health_checks import check_cache_state
        result = check_cache_state(app_module.TUNER_DB)
        for key in ("active_tuner", "channel_count", "epg_channel_count",
                    "epg_entry_count", "sample_channels"):
            assert key in result

    def test_check_cache_state_channel_count_is_int(self, isolated_db):
        from utils.health_checks import check_cache_state
        result = check_cache_state(app_module.TUNER_DB)
        assert isinstance(result["channel_count"], int)

    def test_check_tuner_connectivity_returns_list(self, isolated_db):
        from utils.health_checks import check_tuner_connectivity
        result = check_tuner_connectivity(app_module.TUNER_DB)
        assert isinstance(result, list)

    def test_check_tuner_connectivity_structure(self, isolated_db):
        from utils.health_checks import check_tuner_connectivity
        result = check_tuner_connectivity(app_module.TUNER_DB)
        for tuner in result:
            assert "name" in tuner
            assert "overall_status" in tuner
            assert tuner["overall_status"] in ("PASS", "WARN", "FAIL", "INFO")


# ---------------------------------------------------------------------------
# Tests: new endpoints (tuners, cache)
# ---------------------------------------------------------------------------

class TestDiagnosticsTunersEndpoint:
    def test_tuners_endpoint_admin_only(self, client):
        login(client, "regular", "regpass")
        resp = client.get("/admin/diagnostics/tuners")
        assert resp.status_code == 403

    def test_tuners_endpoint_returns_list(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/tuners")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_tuners_endpoint_no_post(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/tuners")
        assert resp.status_code == 405


class TestDiagnosticsCacheEndpoint:
    def test_cache_endpoint_admin_only(self, client):
        login(client, "regular", "regpass")
        resp = client.get("/admin/diagnostics/cache")
        assert resp.status_code == 403

    def test_cache_endpoint_returns_expected_keys(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/cache")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        for key in ("active_tuner", "channel_count", "epg_channel_count",
                    "epg_entry_count", "sample_channels"):
            assert key in data

    def test_cache_endpoint_no_post(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/cache")
        assert resp.status_code == 405


class TestDiagnosticsHealthEnhanced:
    def test_health_includes_file_system(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/health")
        data = json.loads(resp.data)
        assert "file_system" in data
        assert "users_db" in data["file_system"]
        assert "tuners_db" in data["file_system"]

    def test_health_includes_cache_state(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/health")
        data = json.loads(resp.data)
        assert "cache_state" in data
        assert "channel_count" in data["cache_state"]

    def test_health_db_includes_path(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/health")
        data = json.loads(resp.data)
        assert "path" in data["db"]
        assert data["db"]["path"]  # not empty


class TestSupportBundleEnhanced:
    def test_support_zip_includes_tuners_json(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        assert "tuners.json" in zf.namelist()

    def test_support_zip_includes_cache_state(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        assert "cache_state.json" in zf.namelist()

    def test_support_tuners_json_is_valid(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        tuners = json.loads(zf.read("tuners.json"))
        assert isinstance(tuners, list)


# ---------------------------------------------------------------------------
# Tests: system_info utilities
# ---------------------------------------------------------------------------

class TestSystemInfo:
    def test_returns_required_keys(self):
        from utils.system_info import get_system_info
        from datetime import datetime
        result = get_system_info("v4.8.0", datetime.now(), "/tmp/data")
        for key in ("app_version", "python_version", "os_info", "uptime",
                    "data_dir", "install_mode", "safe_env"):
            assert key in result

    def test_data_dir_reflected(self):
        from utils.system_info import get_system_info
        from datetime import datetime
        result = get_system_info("v1.0", datetime.now(), "/some/path")
        assert result["data_dir"] == "/some/path"

    def test_version_reflected(self):
        from utils.system_info import get_system_info
        from datetime import datetime
        result = get_system_info("v9.9.9", datetime.now(), "/tmp")
        assert result["app_version"] == "v9.9.9"


# ---------------------------------------------------------------------------
# Tests: app_config_diag utilities
# ---------------------------------------------------------------------------

class TestCheckUserAccounts:
    def test_returns_user_list(self, isolated_db):
        from utils.app_config_diag import check_user_accounts
        result = check_user_accounts(app_module.DATABASE)
        assert "users" in result
        assert isinstance(result["users"], list)
        usernames = [u["username"] for u in result["users"]]
        assert "admin" in usernames
        assert "regular" in usernames

    def test_pass_status_with_users(self, isolated_db):
        from utils.app_config_diag import check_user_accounts
        result = check_user_accounts(app_module.DATABASE)
        assert result["status"] == "PASS"

    def test_no_passwords_exposed(self, isolated_db):
        from utils.app_config_diag import check_user_accounts
        result = check_user_accounts(app_module.DATABASE)
        result_str = json.dumps(result)
        assert "password" not in result_str.lower()
        assert "adminpass" not in result_str
        assert "regpass" not in result_str

    def test_never_logged_in_tracked(self, isolated_db):
        from utils.app_config_diag import check_user_accounts
        result = check_user_accounts(app_module.DATABASE)
        # Fresh test accounts have never logged in
        assert len(result["never_logged_in"]) >= 1

    def test_last_login_field_present(self, isolated_db):
        from utils.app_config_diag import check_user_accounts
        result = check_user_accounts(app_module.DATABASE)
        for user in result["users"]:
            assert "last_login" in user
            assert "assigned_tuner" in user

    def test_fail_on_bad_db(self, tmp_path):
        from utils.app_config_diag import check_user_accounts
        result = check_user_accounts(str(tmp_path / "no_schema.db"))
        # SQLite creates a new empty file — query fails → FAIL status
        assert result["status"] in ("FAIL", "WARN")


class TestCheckVirtualChannels:
    def test_returns_all_channels(self, isolated_db):
        from utils.app_config_diag import check_virtual_channels
        result = check_virtual_channels(app_module.TUNER_DB)
        assert "channels" in result
        tvg_ids = [c["tvg_id"] for c in result["channels"]]
        for expected in ("virtual.news", "virtual.weather", "virtual.status", "virtual.traffic"):
            assert expected in tvg_ids

    def test_status_is_valid(self, isolated_db):
        from utils.app_config_diag import check_virtual_channels
        result = check_virtual_channels(app_module.TUNER_DB)
        assert result["status"] in ("PASS", "WARN", "FAIL")

    def test_weather_config_included(self, isolated_db):
        from utils.app_config_diag import check_virtual_channels
        result = check_virtual_channels(app_module.TUNER_DB)
        weather = next(c for c in result["channels"] if c["tvg_id"] == "virtual.weather")
        assert "weather_config" in weather

    def test_news_config_included(self, isolated_db):
        from utils.app_config_diag import check_virtual_channels
        result = check_virtual_channels(app_module.TUNER_DB)
        news = next(c for c in result["channels"] if c["tvg_id"] == "virtual.news")
        assert "news_config" in news

    def test_unconfigured_weather_warns(self, isolated_db):
        """With no lat/lon set, weather channel should report a config issue."""
        from utils.app_config_diag import check_virtual_channels
        result = check_virtual_channels(app_module.TUNER_DB)
        weather = next(c for c in result["channels"] if c["tvg_id"] == "virtual.weather")
        # Fresh DB has no weather lat/lon
        assert weather["config_ok"] is False
        assert len(weather["config_issues"]) >= 1

    def test_enabled_state_in_result(self, isolated_db):
        from utils.app_config_diag import check_virtual_channels
        result = check_virtual_channels(app_module.TUNER_DB)
        for ch in result["channels"]:
            assert "enabled" in ch
            assert isinstance(ch["enabled"], bool)


class TestCheckExternalServices:
    def test_returns_services_list(self, isolated_db):
        from utils.app_config_diag import check_external_services
        result = check_external_services(app_module.TUNER_DB)
        assert "services" in result
        assert isinstance(result["services"], list)

    def test_unconfigured_weather_not_probed(self, isolated_db):
        """With no lat/lon, weather API should be listed as not configured."""
        from utils.app_config_diag import check_external_services
        result = check_external_services(app_module.TUNER_DB)
        weather = next((s for s in result["services"] if s["id"] == "weather_api"), None)
        assert weather is not None
        assert weather["reachable"] is None  # not configured

    def test_unconfigured_news_not_probed(self, isolated_db):
        from utils.app_config_diag import check_external_services
        result = check_external_services(app_module.TUNER_DB)
        news = next((s for s in result["services"] if "news_feed" in s["id"]), None)
        assert news is not None
        assert news["reachable"] is None

    def test_status_field_present(self, isolated_db):
        from utils.app_config_diag import check_external_services
        result = check_external_services(app_module.TUNER_DB)
        assert result["status"] in ("PASS", "WARN", "FAIL")

    def test_no_secrets_in_response(self, isolated_db):
        from utils.app_config_diag import check_external_services
        result = check_external_services(app_module.TUNER_DB)
        result_str = json.dumps(result)
        for secret in ("api_key", "password", "token=", "Authorization"):
            assert secret not in result_str

    def test_overpass_api_included_when_traffic_enabled(self, isolated_db):
        """Overpass API should appear in services when traffic channel is enabled (default)."""
        from utils.app_config_diag import check_external_services
        result = check_external_services(app_module.TUNER_DB)
        overpass = next((s for s in result["services"] if s["id"] == "overpass_api"), None)
        assert overpass is not None, "Overpass API entry should be present"
        assert "overpass" in overpass["url"].lower()
        assert overpass["name"] != ""

    def test_overpass_api_not_probed_when_traffic_disabled(self, isolated_db):
        """When traffic channel is disabled, Overpass API should be listed but not probed."""
        import sqlite3
        with sqlite3.connect(app_module.TUNER_DB, timeout=5) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("virtual_channel.virtual.traffic.enabled", "0"),
            )
        from utils.app_config_diag import check_external_services
        result = check_external_services(app_module.TUNER_DB)
        overpass = next((s for s in result["services"] if s["id"] == "overpass_api"), None)
        assert overpass is not None
        assert overpass["reachable"] is None  # not probed

    def test_overpass_504_reported_as_fail(self, isolated_db, monkeypatch):
        """A 504 from Overpass should surface as a FAIL in the services list."""
        import requests as _req
        from utils import app_config_diag

        class _FakeResp:
            status_code = 504
            def raise_for_status(self):
                raise _req.exceptions.HTTPError("504 Gateway Timeout", response=self)

        def _fake_head(url, *args, **kwargs):
            if "overpass" in url:
                return _FakeResp()
            raise _req.exceptions.ConnectionError("unexpected URL in test")

        monkeypatch.setattr(_req, "head", _fake_head)
        monkeypatch.setattr(app_config_diag, "_probe_service",
                            lambda svc_id, name, url, timeout=8: {
                                "id": svc_id,
                                "name": name,
                                "url": url,
                                "reachable": False,
                                "status_code": 504,
                                "response_time_ms": 1000,
                                "error": "HTTP 504",
                                "resolved_ip": None,
                            })
        result = app_config_diag.check_external_services(app_module.TUNER_DB)
        overpass = next((s for s in result["services"] if s["id"] == "overpass_api"), None)
        assert overpass is not None
        assert overpass["reachable"] is False
        assert overpass["status_code"] == 504
        # Overall status should be FAIL because Overpass is unreachable
        assert result["status"] == "FAIL"

    def test_overpass_fail_appears_in_failing_list(self, isolated_db, monkeypatch):
        """An unreachable Overpass service should appear in the detail string."""
        from utils import app_config_diag

        monkeypatch.setattr(app_config_diag, "_probe_service",
                            lambda svc_id, name, url, timeout=8: {
                                "id": svc_id,
                                "name": name,
                                "url": url,
                                "reachable": False,
                                "status_code": 504,
                                "response_time_ms": 1000,
                                "error": "HTTP 504",
                                "resolved_ip": None,
                            })
        result = app_config_diag.check_external_services(app_module.TUNER_DB)
        assert "overpass" in result["detail"].lower()

    def test_runtime_429_overrides_probe_success(self, isolated_db, monkeypatch):
        """Even when /api/status probes OK, a 429 in _OVERPASS_LAST_ERROR should
        surface as reachable=False with status_code=429."""
        from utils import app_config_diag

        # _probe_service returns success (200 OK) — as if /api/status is fine
        monkeypatch.setattr(app_config_diag, "_probe_service",
                            lambda svc_id, name, url, timeout=8: {
                                "id": svc_id,
                                "name": name,
                                "url": url,
                                "reachable": True,
                                "status_code": 200,
                                "response_time_ms": 120,
                                "error": None,
                                "resolved_ip": "1.2.3.4",
                                "note": "",
                            })
        # Inject a runtime 429 error (as would be set by _fetch_overpass_roads)
        monkeypatch.setattr(app_module, "_OVERPASS_LAST_ERROR", {
            "status_code": 429,
            "lat": 40.7128,
            "lon": -74.006,
            "ts": 1_000_000,
            "message": "429 Client Error: Too Many Requests",
        })

        result = app_config_diag.check_external_services(app_module.TUNER_DB)
        overpass = next((s for s in result["services"] if s["id"] == "overpass_api"), None)
        assert overpass is not None
        assert overpass["reachable"] is False
        assert overpass["status_code"] == 429
        assert result["status"] == "FAIL"
        assert "429" in (overpass["error"] or "")

    def test_runtime_429_note_mentions_rate_limit(self, isolated_db, monkeypatch):
        """A runtime 429 should include a helpful rate-limiting note."""
        from utils import app_config_diag

        monkeypatch.setattr(app_config_diag, "_probe_service",
                            lambda svc_id, name, url, timeout=8: {
                                "id": svc_id, "name": name, "url": url,
                                "reachable": True, "status_code": 200,
                                "response_time_ms": 100, "error": None,
                                "resolved_ip": "1.2.3.4", "note": "",
                            })
        monkeypatch.setattr(app_module, "_OVERPASS_LAST_ERROR", {
            "status_code": 429,
            "lat": 33.4484, "lon": -112.074,
            "ts": 1_000_000,
            "message": "429 Client Error: Too Many Requests",
        })

        result = app_config_diag.check_external_services(app_module.TUNER_DB)
        overpass = next((s for s in result["services"] if s["id"] == "overpass_api"), None)
        assert overpass is not None
        assert "rate" in overpass.get("note", "").lower()

    def test_no_last_error_uses_probe_result(self, isolated_db, monkeypatch):
        """When _OVERPASS_LAST_ERROR is empty, the probe result is used as-is."""
        from utils import app_config_diag

        monkeypatch.setattr(app_config_diag, "_probe_service",
                            lambda svc_id, name, url, timeout=8: {
                                "id": svc_id, "name": name, "url": url,
                                "reachable": True, "status_code": 200,
                                "response_time_ms": 100, "error": None,
                                "resolved_ip": "1.2.3.4", "note": "",
                            })
        monkeypatch.setattr(app_module, "_OVERPASS_LAST_ERROR", {})

        result = app_config_diag.check_external_services(app_module.TUNER_DB)
        overpass = next((s for s in result["services"] if s["id"] == "overpass_api"), None)
        assert overpass is not None
        assert overpass["reachable"] is True
        assert overpass["status_code"] == 200


class TestCheckSystemResources:
    def test_returns_expected_keys(self):
        from utils.app_config_diag import check_system_resources
        result = check_system_resources()
        for key in ("thread_count", "python_version", "python_executable",
                    "packages", "requirements_check"):
            assert key in result

    def test_thread_count_positive(self):
        from utils.app_config_diag import check_system_resources
        result = check_system_resources()
        assert isinstance(result["thread_count"], int)
        assert result["thread_count"] >= 1

    def test_python_version_matches(self):
        from utils.app_config_diag import check_system_resources
        import sys
        result = check_system_resources()
        assert sys.version in result["python_version"]

    def test_packages_list_is_list(self):
        from utils.app_config_diag import check_system_resources
        result = check_system_resources()
        assert isinstance(result["packages"], list)

    def test_requirements_check_present(self):
        from utils.app_config_diag import check_system_resources
        result = check_system_resources()
        assert isinstance(result["requirements_check"], list)

    def test_status_valid(self):
        from utils.app_config_diag import check_system_resources
        result = check_system_resources()
        assert result["status"] in ("PASS", "WARN", "FAIL")


class TestRunConfigChecks:
    def test_returns_all_sections(self, isolated_db):
        from utils.app_config_diag import run_config_checks
        result = run_config_checks(app_module.DATABASE, app_module.TUNER_DB)
        for key in ("user_accounts", "virtual_channels", "external_services", "system_resources"):
            assert key in result

    def test_no_passwords_in_output(self, isolated_db):
        from utils.app_config_diag import run_config_checks
        result = run_config_checks(app_module.DATABASE, app_module.TUNER_DB)
        result_str = json.dumps(result)
        assert "adminpass" not in result_str
        assert "regpass" not in result_str


# ---------------------------------------------------------------------------
# Tests: /admin/diagnostics/config endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsConfigEndpoint:
    def test_config_endpoint_admin_only(self, client):
        login(client, "regular", "regpass")
        resp = client.get("/admin/diagnostics/config")
        assert resp.status_code == 403

    def test_config_endpoint_returns_json(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/config")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        for key in ("user_accounts", "virtual_channels", "external_services", "system_resources"):
            assert key in data

    def test_config_endpoint_no_post(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/config")
        assert resp.status_code == 405

    def test_config_endpoint_no_passwords(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/config")
        assert b"adminpass" not in resp.data
        assert b"regpass" not in resp.data

    def test_config_user_accounts_structure(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/config")
        data = json.loads(resp.data)
        ua = data["user_accounts"]
        assert "users" in ua
        assert "status" in ua
        assert "detail" in ua

    def test_config_virtual_channels_structure(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/config")
        data = json.loads(resp.data)
        vc = data["virtual_channels"]
        assert "channels" in vc
        assert len(vc["channels"]) >= 1


# ---------------------------------------------------------------------------
# Tests: support bundle now includes config.json
# ---------------------------------------------------------------------------

class TestSupportBundleWithConfig:
    def test_support_bundle_includes_config_json(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        assert "config.json" in zf.namelist()

    def test_config_json_is_valid_json(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        cfg = json.loads(zf.read("config.json"))
        assert "user_accounts" in cfg
        assert "virtual_channels" in cfg


# ---------------------------------------------------------------------------
# Tests: startup_diag utilities
# ---------------------------------------------------------------------------

class TestStartupDiag:
    def test_record_and_retrieve_events(self):
        from utils import startup_diag
        # Reset state for test isolation
        with startup_diag._LOCK:
            startup_diag._events.clear()
            startup_diag._startup_success = None
            startup_diag._startup_finished_at = None

        startup_diag.record_startup_event("info", "test_cat", "test detail")
        events = startup_diag.get_startup_events()
        assert any(e["category"] == "test_cat" for e in events)

    def test_summary_structure(self):
        from utils import startup_diag
        summary = startup_diag.get_startup_summary()
        for key in ("status", "finished_at", "event_count", "error_count",
                    "warning_count", "events", "errors"):
            assert key in summary

    def test_error_count_increments(self):
        from utils import startup_diag
        with startup_diag._LOCK:
            startup_diag._events.clear()
        startup_diag.record_startup_event("error", "db_init", "test error")
        summary = startup_diag.get_startup_summary()
        assert summary["error_count"] >= 1

    def test_finalise_sets_success(self):
        from utils import startup_diag
        with startup_diag._LOCK:
            startup_diag._startup_success = None
        startup_diag.finalise_startup(success=True)
        summary = startup_diag.get_startup_summary()
        assert summary["status"] in ("ok", "ok_with_errors")

    def test_finalise_failed_status(self):
        from utils import startup_diag
        with startup_diag._LOCK:
            startup_diag._startup_success = None
            startup_diag._events.clear()
        startup_diag.finalise_startup(success=False)
        summary = startup_diag.get_startup_summary()
        assert summary["status"] == "failed"

    def test_record_environment_adds_python_event(self):
        from utils import startup_diag
        with startup_diag._LOCK:
            startup_diag._events.clear()
        startup_diag.record_environment()
        cats = [e["category"] for e in startup_diag.get_startup_events()]
        assert "python" in cats

    def test_record_import_error(self):
        from utils import startup_diag
        with startup_diag._LOCK:
            startup_diag._events.clear()
        try:
            import no_such_module_xyz
        except ImportError as exc:
            startup_diag.record_import_error("no_such_module_xyz", exc)
        errors = [e for e in startup_diag.get_startup_events()
                  if e["level"] == "error" and e["category"] == "import_error"]
        assert len(errors) >= 1
        assert "no_such_module_xyz" in errors[0]["detail"]

    def test_ring_buffer_cap(self):
        from utils import startup_diag
        with startup_diag._LOCK:
            startup_diag._events.clear()
        for i in range(startup_diag._MAX_EVENTS + 50):
            startup_diag.record_startup_event("info", "flood", str(i))
        assert len(startup_diag.get_startup_events()) <= startup_diag._MAX_EVENTS

    def test_configure_startup_log_creates_file(self, tmp_path):
        from utils import startup_diag
        startup_diag.configure_startup_log(str(tmp_path))
        startup_diag.record_startup_event("info", "log_test", "should be on disk")
        log_file = tmp_path / "logs" / "startup.log"
        assert log_file.exists()
        assert "log_test" in log_file.read_text()


# ---------------------------------------------------------------------------
# Tests: /admin/diagnostics/startup endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsStartupEndpoint:
    def test_startup_endpoint_admin_only(self, client):
        login(client, "regular", "regpass")
        resp = client.get("/admin/diagnostics/startup")
        assert resp.status_code == 403

    def test_startup_endpoint_returns_json(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/startup")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        for key in ("status", "event_count", "error_count", "events"):
            assert key in data

    def test_startup_endpoint_no_post(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/startup")
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# Tests: public /startup-status endpoint
# ---------------------------------------------------------------------------

class TestPublicStartupStatus:
    def test_accessible_without_login(self, client):
        """Public endpoint must work even if the user is not logged in."""
        resp = client.get("/startup-status")
        assert resp.status_code == 200

    def test_returns_minimal_json(self, client):
        resp = client.get("/startup-status")
        data = json.loads(resp.data)
        assert "app" in data
        assert "version" in data
        assert "status" in data
        assert "error_count" in data

    def test_no_log_content_exposed(self, client):
        """Public endpoint must not reveal log line details."""
        resp = client.get("/startup-status")
        data = json.loads(resp.data)
        assert "events" not in data
        assert "errors" not in data  # only error_categories, not full error details

    def test_no_paths_exposed(self, client):
        resp = client.get("/startup-status")
        raw = resp.data.decode()
        # Should not contain filesystem paths
        assert "/var/lib" not in raw
        assert "C:\\Program" not in raw


# ---------------------------------------------------------------------------
# Tests: tuner_diag utilities
# ---------------------------------------------------------------------------

class TestTunerDiag:
    def test_parse_tuner_unknown_name(self, isolated_db):
        from utils.tuner_diag import parse_tuner_with_trace
        result = parse_tuner_with_trace("nonexistent_tuner", app_module.TUNER_DB)
        assert "error" in result
        assert result["m3u"] is None

    def test_parse_tuner_result_is_json_serialisable(self, isolated_db):
        """Result must be JSON-serialisable so jsonify() doesn't return an HTML 500.

        Previously raw_bytes (bytes) leaked into the fetch dict and caused
        'SyntaxError: Unexpected token <' in the browser because jsonify
        raised TypeError and Flask returned an HTML error page.
        """
        import json
        import sqlite3
        from utils.tuner_diag import parse_tuner_with_trace

        # Create a tuner with empty URLs (no real HTTP needed)
        with sqlite3.connect(app_module.TUNER_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tuners (name, xml, m3u, tuner_type)"
                " VALUES (?, ?, ?, ?)",
                ("serial_test_tuner", "", "", "standard"),
            )
            conn.commit()
        result = parse_tuner_with_trace("serial_test_tuner", app_module.TUNER_DB)
        # Should not raise TypeError
        serialised = json.dumps(result)
        assert len(serialised) > 0

    def test_strip_raw_bytes_removes_field(self):
        """_strip_raw_bytes must remove raw_bytes from the fetch sub-dict."""
        from utils.tuner_diag import _strip_raw_bytes
        trace = {
            "url": "http://example.com",
            "fetch": {"ok": True, "raw_bytes": b"binary data", "status_code": 200},
            "issues": [],
        }
        _strip_raw_bytes(trace)
        assert "raw_bytes" not in trace["fetch"]
        # Other keys must be preserved
        assert trace["fetch"]["ok"] is True
        assert trace["fetch"]["status_code"] == 200

    def test_strip_raw_bytes_none_trace_is_safe(self):
        from utils.tuner_diag import _strip_raw_bytes
        _strip_raw_bytes(None)  # must not raise

    def test_strip_raw_bytes_missing_fetch_is_safe(self):
        from utils.tuner_diag import _strip_raw_bytes
        _strip_raw_bytes({"url": "", "issues": []})  # must not raise

    def test_parse_tuner_empty_urls(self, isolated_db):
        """A tuner with no URLs should return descriptive not-configured issues."""
        from utils.tuner_diag import parse_tuner_with_trace
        import sqlite3
        # Create a tuner with empty URLs
        with sqlite3.connect(app_module.TUNER_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tuners (name, xml, m3u, tuner_type)"
                " VALUES (?, ?, ?, ?)",
                ("empty_tuner", "", "", "standard"),
            )
            conn.commit()
        result = parse_tuner_with_trace("empty_tuner", app_module.TUNER_DB)
        assert result["tuner_name"] == "empty_tuner"
        assert result["m3u"] is not None
        # Should report not-configured issue
        m3u_issues = result["m3u"].get("issues", [])
        assert len(m3u_issues) >= 1

    def test_analyse_m3u_text_valid(self):
        from utils.tuner_diag import _analyse_m3u_text
        m3u_text = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="ch1" tvg-logo="" group-title="News",CNN\n'
            "http://example.com/cnn.m3u8\n"
            '#EXTINF:-1 tvg-id="ch2" tvg-logo="" group-title="Sports",ESPN\n'
            "http://example.com/espn.m3u8\n"
        )
        result = _analyse_m3u_text(m3u_text)
        assert result["has_extm3u_header"] is True
        assert result["has_extinf_tags"] is True
        assert result["channel_count"] == 2
        assert result["quality"]["no_url_count"] == 0

    def test_analyse_m3u_text_empty(self):
        from utils.tuner_diag import _analyse_m3u_text
        result = _analyse_m3u_text("")
        assert result["channel_count"] == 0
        assert len(result["issues"]) >= 1

    def test_analyse_m3u_text_no_header_warn(self):
        from utils.tuner_diag import _analyse_m3u_text
        m3u_text = (
            '#EXTINF:-1 tvg-id="ch1",Channel 1\n'
            "http://example.com/ch1.m3u8\n"
        )
        result = _analyse_m3u_text(m3u_text)
        assert any("EXTM3U" in w for w in result["warnings"])

    def test_analyse_m3u_text_duplicate_tvg_ids(self):
        from utils.tuner_diag import _analyse_m3u_text
        m3u_text = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="dup_id",Channel A\n'
            "http://example.com/a.m3u8\n"
            '#EXTINF:-1 tvg-id="dup_id",Channel B\n'
            "http://example.com/b.m3u8\n"
        )
        result = _analyse_m3u_text(m3u_text)
        assert result["quality"]["duplicate_tvg_id_count"] >= 1

    def test_analyse_xmltv_valid(self):
        from utils.tuner_diag import _analyse_xmltv_bytes
        xmltv = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<tv><channel id="ch1"><display-name>CNN</display-name></channel>'
            b'<programme channel="ch1" start="20260101120000 +0000" stop="20260101130000 +0000">'
            b'<title>News Hour</title></programme></tv>'
        )
        result = _analyse_xmltv_bytes(xmltv)
        assert result["valid_xml"] is True
        assert result["valid_xmltv"] is True
        assert result["channel_count"] == 1
        assert result["programme_count"] == 1

    def test_analyse_xmltv_invalid_xml(self):
        from utils.tuner_diag import _analyse_xmltv_bytes
        result = _analyse_xmltv_bytes(b"this is not xml")
        assert result["valid_xml"] is False
        assert len(result["issues"]) >= 1

    def test_analyse_xmltv_html_response(self):
        from utils.tuner_diag import _analyse_xmltv_bytes
        result = _analyse_xmltv_bytes(b"<!DOCTYPE html><html><body>Login required</body></html>")
        assert len(result["issues"]) >= 1
        assert any("HTML" in i for i in result["issues"])

    def test_analyse_xmltv_empty(self):
        from utils.tuner_diag import _analyse_xmltv_bytes
        result = _analyse_xmltv_bytes(b"")
        assert len(result["issues"]) >= 1

    def test_epg_coverage_no_match(self):
        from utils.tuner_diag import _compute_epg_coverage
        m3u_trace = {
            "parse": {
                "channels": [
                    {"tvg_id": "abc", "name": "ABC", "url": "http://x.com/a.m3u8", "logo": "", "group": ""},
                ],
                "channel_count": 1,
            }
        }
        xmltv_trace = {
            "fetch": {"ok": False, "raw_bytes": b""},
            "parse": {
                "channels_sample": [{"id": "xyz", "display_name": "XYZ"}],
            },
        }
        result = _compute_epg_coverage(m3u_trace, xmltv_trace)
        assert result["match_pct"] == 0 or result["match_pct"] is None

    def test_epg_coverage_full_match(self):
        from utils.tuner_diag import _compute_epg_coverage
        xmltv_xml = (
            b'<?xml version="1.0"?><tv>'
            b'<channel id="ch1"><display-name>CNN</display-name></channel>'
            b'</tv>'
        )
        m3u_trace = {
            "parse": {
                "channels": [{"tvg_id": "ch1", "name": "CNN", "url": "http://x.com/cnn.m3u8", "logo": "", "group": ""}],
                "channel_count": 1,
            }
        }
        xmltv_trace = {
            "fetch": {"ok": True, "raw_bytes": xmltv_xml},
            "parse": {"channels_sample": [{"id": "ch1", "display_name": "CNN"}]},
        }
        result = _compute_epg_coverage(m3u_trace, xmltv_trace)
        assert result["match_pct"] == 100
        assert result["match_count"] == 1

    def test_safe_content_sample_escapes_html(self):
        from utils.tuner_diag import _safe_content_sample
        raw = b"<script>alert('xss')</script>"
        sample = _safe_content_sample(raw)
        assert "<script>" not in sample
        assert "&lt;script&gt;" in sample


# ---------------------------------------------------------------------------
# Tests: /admin/diagnostics/tuner-parse endpoint
# ---------------------------------------------------------------------------

class TestDiagnosticsTunerParseEndpoint:
    def test_requires_admin(self, client):
        login(client, "regular", "regpass")
        resp = client.get("/admin/diagnostics/tuner-parse?name=test")
        assert resp.status_code == 403

    def test_missing_name_param(self, client):
        login(client)
        resp = client.get("/admin/diagnostics/tuner-parse")
        assert resp.status_code == 400

    def test_unknown_tuner_returns_error(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/tuner-parse?name=doesnotexist")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "error" in data

    def test_no_post_method(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/tuner-parse")
        assert resp.status_code == 405

    def test_empty_tuner_returns_trace_structure(self, client, isolated_db):
        """A tuner with no URLs should still return a full trace dict."""
        import sqlite3
        with sqlite3.connect(app_module.TUNER_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tuners (name, xml, m3u, tuner_type)"
                " VALUES (?, ?, ?, ?)",
                ("diag_test_tuner", "", "", "standard"),
            )
            conn.commit()
        login(client)
        resp = client.get("/admin/diagnostics/tuner-parse?name=diag_test_tuner")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "tuner_name" in data
        assert "issues" in data
        assert "m3u" in data
        assert "xmltv" in data

    def test_response_content_type_is_json_not_html(self, client, isolated_db):
        """Endpoint must return application/json, not text/html.

        The original bug: raw_bytes (bytes) was left in the fetch dict,
        jsonify() raised TypeError, Flask returned an HTML 500 error page,
        and the browser got 'SyntaxError: Unexpected token <'.
        """
        import sqlite3
        with sqlite3.connect(app_module.TUNER_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tuners (name, xml, m3u, tuner_type)"
                " VALUES (?, ?, ?, ?)",
                ("json_type_tuner", "", "", "standard"),
            )
            conn.commit()
        login(client)
        resp = client.get("/admin/diagnostics/tuner-parse?name=json_type_tuner")
        assert resp.status_code == 200
        # Must be JSON, not an HTML error page
        assert "application/json" in resp.content_type
        # Must be parseable as JSON without raising
        data = json.loads(resp.data)
        assert isinstance(data, dict)

    def test_no_raw_bytes_in_response(self, client, isolated_db):
        """raw_bytes must never appear as a JSON key in the response."""
        import sqlite3
        with sqlite3.connect(app_module.TUNER_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tuners (name, xml, m3u, tuner_type)"
                " VALUES (?, ?, ?, ?)",
                ("bytescheck_tuner", "", "", "standard"),
            )
            conn.commit()
        login(client)
        resp = client.get("/admin/diagnostics/tuner-parse?name=bytescheck_tuner")
        assert resp.status_code == 200
        raw_text = resp.data.decode()
        # The key "raw_bytes" must not appear as a JSON property
        assert '"raw_bytes"' not in raw_text


# ---------------------------------------------------------------------------
# Tests: ALLOWED_LOGS now includes 'startup'
# ---------------------------------------------------------------------------

class TestStartupLogAllowlist:
    def test_startup_in_allowed_logs(self, isolated_db):
        from utils import log_reading
        from utils.log_reading import configure_allowed_logs
        configure_allowed_logs(app_module.DATA_DIR)
        assert "startup" in log_reading.ALLOWED_LOGS

    def test_startup_log_accessible_via_tail_endpoint(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/logs/tail?key=startup&n=50")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "lines" in data


# ---------------------------------------------------------------------------
# Tests: support bundle now includes startup.json
# ---------------------------------------------------------------------------

class TestSupportBundleWithStartup:
    def test_support_bundle_includes_startup_json(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        assert resp.status_code == 200
        import zipfile
        import io
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        assert "startup.json" in zf.namelist()

    def test_startup_json_is_valid_json(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/support")
        import zipfile
        import io
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        data = json.loads(zf.read("startup.json"))
        assert "status" in data
        assert "events" in data


# ---------------------------------------------------------------------------
# Tests: selectable support bundle (POST with include[] form values)
# ---------------------------------------------------------------------------

class TestSelectableSupportBundle:
    """Verify that POSTing include[] to /support honours the selection."""

    def _get_names(self, client, include_values):
        """POST to /support with the given include[] values and return ZIP namelist."""
        from urllib.parse import urlencode
        body = urlencode([("include[]", v) for v in include_values])
        resp = client.post(
            "/admin/diagnostics/support",
            data=body,
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 200
        assert "application/zip" in resp.content_type
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        return zf.namelist()

    def test_get_still_includes_all(self, client, isolated_db):
        """GET (no body) must still include every section — backwards compat."""
        login(client)
        resp = client.get("/admin/diagnostics/support")
        names = zipfile.ZipFile(io.BytesIO(resp.data)).namelist()
        for expected in ("health.json", "system.json", "config.json",
                         "startup.json", "index.html"):
            assert expected in names

    def test_post_only_selected_section_included(self, client, isolated_db):
        """Posting only health.json should produce a bundle with just that file."""
        login(client)
        names = self._get_names(client, ["health.json"])
        assert "health.json" in names
        assert "system.json" not in names
        assert "config.json" not in names
        assert "startup.json" not in names
        # index.html is always present regardless of selection
        assert "index.html" in names

    def test_post_multiple_sections(self, client, isolated_db):
        """Two selected sections should both appear; others should not."""
        login(client)
        names = self._get_names(client, ["health.json", "system.json"])
        assert "health.json" in names
        assert "system.json" in names
        assert "config.json" not in names

    def test_post_deselected_section_absent(self, client, isolated_db):
        """config.json must be absent when not listed in include[]."""
        login(client)
        names = self._get_names(client, ["health.json", "startup.json"])
        assert "config.json" not in names
        assert "tuners.json" not in names

    def test_post_empty_selection_produces_index_only(self, client, isolated_db):
        """An empty include[] list should yield a bundle containing only index.html."""
        login(client)
        names = self._get_names(client, [])
        assert names == ["index.html"]

    def test_post_unknown_include_value_ignored(self, client, isolated_db):
        """Unknown/injected values in include[] must be silently ignored."""
        login(client)
        names = self._get_names(client, ["health.json", "../../etc/passwd"])
        assert "health.json" in names
        # The injected path must never appear
        assert not any(".." in n for n in names)

    def test_build_support_bundle_include_param(self):
        """Unit-test build_support_bundle include= parameter directly."""
        from utils.log_reading import build_support_bundle
        health = {"db": "ok", "status": "PASS"}
        system = {"v": "1"}
        extra = {"config.json": {"x": 1}, "tuners.json": {"t": 2}}
        # Only request health.json
        zb = build_support_bundle("/tmp", health, system, extra,
                                  include={"health.json"})
        zf = zipfile.ZipFile(io.BytesIO(zb))
        names = zf.namelist()
        assert "health.json" in names
        assert "system.json" not in names
        assert "config.json" not in names
        assert "index.html" in names

    def test_build_support_bundle_none_includes_all(self):
        """include=None (default) must include every JSON section."""
        from utils.log_reading import build_support_bundle
        health = {"db": "ok"}
        system = {"v": "1"}
        extra = {"config.json": {}, "startup.json": {}}
        zb = build_support_bundle("/tmp", health, system, extra, include=None)
        zf = zipfile.ZipFile(io.BytesIO(zb))
        names = zf.namelist()
        for expected in ("health.json", "system.json", "config.json",
                         "startup.json", "index.html"):
            assert expected in names



class TestCacheEndpointAllTuners:
    def test_cache_endpoint_includes_all_tuners(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/cache")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "all_tuners" in data
        assert isinstance(data["all_tuners"], list)


# ---------------------------------------------------------------------------
# Tests: /admin/diagnostics/issue-draft endpoint
# ---------------------------------------------------------------------------

class TestIssueDraftEndpoint:
    def test_requires_admin(self, client):
        login(client, "regular", "regpass")
        resp = client.get("/admin/diagnostics/issue-draft")
        assert resp.status_code == 403

    def test_unauthenticated_redirects(self, client):
        resp = client.get("/admin/diagnostics/issue-draft")
        assert resp.status_code in (302, 401)

    def test_no_post_method(self, client):
        login(client)
        resp = client.post("/admin/diagnostics/issue-draft")
        assert resp.status_code == 405

    def test_returns_json(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        assert resp.status_code == 200
        assert "application/json" in resp.content_type

    def test_response_structure(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "suggested_title" in data
        assert "body_markdown" in data
        assert "github_new_url" in data
        assert "generated_at" in data
        assert "error_count" in data
        assert "warn_count" in data

    def test_body_markdown_contains_environment_section(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        data = json.loads(resp.data)
        body = data["body_markdown"]
        assert "## Environment" in body
        assert "## Health Check Summary" in body
        assert "## Tuner Status" in body
        assert "## Startup Events" in body
        assert "## Steps to Reproduce" in body

    def test_body_markdown_contains_app_version(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        data = json.loads(resp.data)
        body = data["body_markdown"]
        # App version should appear in the environment table
        assert "App Version" in body

    def test_suggested_title_is_non_empty_string(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        data = json.loads(resp.data)
        title = data["suggested_title"]
        assert isinstance(title, str)
        assert len(title.strip()) > 0

    def test_github_new_url_points_to_correct_repo(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        data = json.loads(resp.data)
        assert "github.com/thehack904/RetroIPTVGuide/issues/new" in data["github_new_url"]

    def test_github_new_url_contains_title_and_body_params(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        data = json.loads(resp.data)
        url = data["github_new_url"]
        assert "title=" in url
        assert "body=" in url

    def test_user_description_included_in_body(self, client, isolated_db):
        login(client)
        description = "Channels not loading after restart"
        resp = client.get(
            "/admin/diagnostics/issue-draft?description=" + description.replace(" ", "+")
        )
        data = json.loads(resp.data)
        assert description in data["body_markdown"]

    def test_description_param_optional(self, client, isolated_db):
        """Endpoint works fine without a description param."""
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["body_markdown"]  # non-empty

    def test_error_warn_counts_are_integers(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        data = json.loads(resp.data)
        assert isinstance(data["error_count"], int)
        assert isinstance(data["warn_count"], int)

    def test_report_issue_tab_in_diagnostics_page(self, client, isolated_db):
        """The main diagnostics page must include the Report Issue tab button."""
        login(client)
        resp = client.get("/admin/diagnostics")
        assert resp.status_code == 200
        assert b"Report Issue" in resp.data
        assert b"panel-issue" in resp.data


# ---------------------------------------------------------------------------
# Tests: utils.issue_draft module (unit tests)
# ---------------------------------------------------------------------------

class TestIssueDraftUtil:
    """Unit tests for utils.issue_draft — no HTTP, no Flask."""

    def _minimal_build(self, **overrides):
        from utils.issue_draft import build_issue_draft
        kwargs = dict(
            system_data={
                "app_version": "v4.8.0",
                "install_mode": "docker",
                "python_version": "3.11.2",
                "os_info": "Linux-6.1.0",
                "os_name": "Linux",
                "architecture": "x86_64",
                "hostname": "testhost",
                "uptime": "0d 1h 2m 3s",
            },
            health_data={
                "db": {"status": "PASS", "detail": "OK", "remediation": ""},
                "disk_space": {"status": "WARN", "detail": "Low disk", "remediation": "Free space"},
            },
            tuner_data=[
                {"name": "mytuner", "overall_status": "PASS",
                 "m3u_probe": {"reachable": True}, "xml_probe": {"reachable": True}},
            ],
            cache_data={"active_tuner": "mytuner", "channel_count": 500,
                        "epg_channel_count": 200, "epg_entry_count": 5000},
            startup_data={"status": "ok", "error_count": 0, "errors": [], "events": []},
            config_data={},
            recent_log_lines=["2026-03-07 INFO startup ok",
                               "2026-03-07 ERROR something failed"],
            user_description="",
        )
        kwargs.update(overrides)
        return build_issue_draft(**kwargs)

    def test_returns_required_keys(self):
        result = self._minimal_build()
        for key in ("suggested_title", "body_markdown", "generated_at", "error_count", "warn_count"):
            assert key in result, f"Missing key: {key}"

    def test_warn_count_reflects_health_data(self):
        result = self._minimal_build()
        assert result["warn_count"] == 1
        assert result["error_count"] == 0

    def test_fail_count_reflects_health_data(self):
        from utils.issue_draft import build_issue_draft
        result = self._minimal_build(
            health_data={
                "db":    {"status": "FAIL", "detail": "DB gone", "remediation": "restart"},
                "schema":{"status": "FAIL", "detail": "tables missing", "remediation": ""},
            }
        )
        assert result["error_count"] == 2

    def test_user_description_in_body(self):
        result = self._minimal_build(user_description="My guide is empty")
        assert "My guide is empty" in result["body_markdown"]

    def test_body_contains_sections(self):
        body = self._minimal_build()["body_markdown"]
        for section in (
            "## Description",
            "## Environment",
            "## Health Check Summary",
            "## Tuner Status",
            "## Startup Events",
            "## Steps to Reproduce",
            "## Expected Behavior",
            "## Actual Behavior",
        ):
            assert section in body, f"Missing section: {section}"

    def test_body_contains_system_info(self):
        body = self._minimal_build()["body_markdown"]
        assert "v4.8.0" in body
        assert "docker" in body
        # Hostname is always sanitized in the issue body
        assert "testhost" not in body
        assert "[HOSTNAME]" in body

    def test_health_warn_surfaces_in_body(self):
        body = self._minimal_build()["body_markdown"]
        assert "Low disk" in body

    def test_health_fail_surfaces_in_body(self):
        from utils.issue_draft import build_issue_draft
        result = self._minimal_build(
            health_data={"db": {"status": "FAIL", "detail": "DB gone", "remediation": ""}}
        )
        assert "DB gone" in result["body_markdown"]

    def test_startup_error_surfaces_in_body(self):
        result = self._minimal_build(
            startup_data={
                "status": "failed",
                "error_count": 1,
                "errors": [{"category": "db_init", "ts": "2026-03-07T00:00:00", "detail": "DB crash"}],
                "events": [],
            }
        )
        assert "DB crash" in result["body_markdown"]

    def test_startup_error_drives_title(self):
        result = self._minimal_build(
            startup_data={
                "status": "failed",
                "error_count": 1,
                "errors": [{"category": "import_error", "ts": "", "detail": "No module named x"}],
                "events": [],
            }
        )
        assert "import_error" in result["suggested_title"].lower() or "startup" in result["suggested_title"].lower()

    def test_health_fail_drives_title(self):
        result = self._minimal_build(
            startup_data={"status": "ok", "error_count": 0, "errors": [], "events": []},
            health_data={"db": {"status": "FAIL", "detail": "gone", "remediation": ""}},
        )
        assert "db" in result["suggested_title"].lower() or "health" in result["suggested_title"].lower()

    def test_log_errors_surface_in_body(self):
        body = self._minimal_build()["body_markdown"]
        assert "something failed" in body

    def test_log_info_not_included(self):
        body = self._minimal_build()["body_markdown"]
        # The INFO line should NOT appear in the log error section
        # (but may appear in other sections)
        # We verify by checking the log error block specifically
        assert "startup ok" not in body or body.count("startup ok") == 0

    def test_tuner_fail_surfaces_in_body(self):
        result = self._minimal_build(
            tuner_data=[{
                "name": "badtuner",
                "overall_status": "FAIL",
                "m3u_probe": {"error": "Connection refused"},
                "xml_probe": {"error": "DNS lookup failed"},
            }]
        )
        body = result["body_markdown"]
        assert "badtuner" in body
        assert "Connection refused" in body

    def test_config_problem_surfaces_in_body(self):
        result = self._minimal_build(
            config_data={
                "user_accounts": {"status": "WARN", "detail": "No users", "remediation": "Add user"},
            }
        )
        body = result["body_markdown"]
        assert "No users" in body

    def test_generate_title_fallback(self):
        """With no errors, title should mention app version."""
        result = self._minimal_build()
        title = result["suggested_title"]
        assert "v4.8.0" in title or "Issue report" in title

    def test_body_is_string(self):
        result = self._minimal_build()
        assert isinstance(result["body_markdown"], str)
        assert len(result["body_markdown"]) > 100

    def test_empty_inputs_do_not_crash(self):
        """All-empty inputs should still produce a valid (if sparse) draft."""
        from utils.issue_draft import build_issue_draft
        result = build_issue_draft(
            system_data={},
            health_data={},
            tuner_data=[],
            cache_data={},
            startup_data={},
            config_data={},
            recent_log_lines=[],
            user_description="",
        )
        assert isinstance(result["body_markdown"], str)
        assert isinstance(result["suggested_title"], str)


# ---------------------------------------------------------------------------
# Tests: utils.draft_sanitizer (unit tests)
# ---------------------------------------------------------------------------

class TestDraftSanitizer:
    """Unit tests for utils.draft_sanitizer — no HTTP, no Flask."""

    def setup_method(self):
        from utils.draft_sanitizer import sanitize_text, sanitize_hostname
        self.sanitize_text = sanitize_text
        self.sanitize_hostname = sanitize_hostname

    # ── IPv4 redaction ────────────────────────────────────────────────────

    def test_private_ipv4_class_a_redacted(self):
        assert "[IP-REDACTED]" in self.sanitize_text("server at 10.0.1.50 timed out")

    def test_private_ipv4_class_b_redacted(self):
        assert "[IP-REDACTED]" in self.sanitize_text("host 172.16.0.1 not reachable")

    def test_private_ipv4_class_c_redacted(self):
        assert "[IP-REDACTED]" in self.sanitize_text("resolved to 192.168.1.100")

    def test_loopback_ipv4_redacted(self):
        assert "[IP-REDACTED]" in self.sanitize_text("connecting to 127.0.0.1")

    def test_public_ipv4_redacted(self):
        assert "[IP-REDACTED]" in self.sanitize_text("server at 203.0.113.55")

    def test_multiple_ipv4_all_redacted(self):
        result = self.sanitize_text("from 192.168.1.1 to 10.0.0.2")
        assert "192.168.1.1" not in result
        assert "10.0.0.2" not in result
        assert result.count("[IP-REDACTED]") == 2

    def test_version_string_not_redacted(self):
        """3.11.2 should NOT be treated as an IP address."""
        result = self.sanitize_text("Python 3.11.2 installed")
        assert "[IP-REDACTED]" not in result
        assert "3.11.2" in result

    def test_os_version_not_redacted(self):
        """6.1.0 (kernel version) should not be redacted."""
        result = self.sanitize_text("Linux 6.1.0-26-amd64")
        assert "[IP-REDACTED]" not in result

    # ── IPv6 redaction ────────────────────────────────────────────────────

    def test_ipv6_loopback_redacted(self):
        result = self.sanitize_text("connected from ::1 port 5000")
        assert "::1" not in result or "[IP-REDACTED]" in result

    def test_ipv6_full_address_redacted(self):
        result = self.sanitize_text("addr 2001:db8:85a3::8a2e:370:7334")
        # Every segment of the address must be gone
        assert "2001:db8:85a3" not in result
        assert "8a2e" not in result

    # ── Hostname redaction ────────────────────────────────────────────────

    def test_sanitize_hostname_always_returns_placeholder(self):
        assert self.sanitize_hostname("myserver") == "[HOSTNAME]"
        assert self.sanitize_hostname("server01.company.local") == "[HOSTNAME]"
        assert self.sanitize_hostname("") == "[HOSTNAME]"

    def test_hostname_redacted_in_text(self):
        result = self.sanitize_text("running on myserver", server_hostname="myserver")
        assert "myserver" not in result
        assert "[HOSTNAME]" in result

    def test_hostname_case_insensitive(self):
        result = self.sanitize_text("MYSERVER is running", server_hostname="myserver")
        assert "MYSERVER" not in result

    def test_empty_hostname_no_crash(self):
        """Empty hostname should not cause errors or spurious replacements."""
        result = self.sanitize_text("some log text", server_hostname="")
        assert result == "some log text"

    def test_hostname_not_partial_match(self):
        """'server1' should not be redacted when hostname is 'server'."""
        result = self.sanitize_text("server1 is up", server_hostname="server")
        assert "server1" in result

    # ── URL credential redaction ─────────────────────────────────────────

    def test_url_credentials_redacted(self):
        result = self.sanitize_text("http://admin:secret@iptv.provider.com/playlist.m3u")
        assert "admin:secret" not in result
        assert "[CREDENTIALS]" in result

    def test_url_credentials_https(self):
        result = self.sanitize_text("https://user123:MyP@ss!@cdn.example.com/feed.xml")
        assert "user123" not in result
        assert "[CREDENTIALS]" in result

    def test_url_without_credentials_unchanged(self):
        result = self.sanitize_text("http://iptv.provider.com/playlist.m3u")
        assert "http://iptv.provider.com/playlist.m3u" in result

    # ── Home path redaction ───────────────────────────────────────────────

    def test_unix_home_path_redacted(self):
        result = self.sanitize_text("data at /home/alice/retroiptv/data")
        assert "/home/alice" not in result
        assert "~" in result

    def test_unix_users_path_redacted(self):
        result = self.sanitize_text("/Users/Bob/Library/retroiptv")
        assert "/Users/Bob" not in result
        assert "~" in result

    def test_windows_home_path_redacted(self):
        result = self.sanitize_text(r"C:\Users\Alice\AppData\retroiptv")
        assert "Alice" not in result

    def test_non_home_path_kept(self):
        result = self.sanitize_text("/opt/retroiptv/data")
        assert "/opt/retroiptv/data" in result

    # ── Secret key=value redaction ────────────────────────────────────────

    def test_token_redacted(self):
        result = self.sanitize_text("token=abc123secret")
        assert "abc123secret" not in result
        assert "***" in result

    def test_password_redacted(self):
        result = self.sanitize_text("password=Hunter2!")
        assert "Hunter2!" not in result

    def test_api_key_redacted(self):
        result = self.sanitize_text("api_key=sk-live-xyz")
        assert "sk-live-xyz" not in result

    # ── Non-string input ──────────────────────────────────────────────────

    def test_integer_input(self):
        result = self.sanitize_text(42)
        assert result == "42"

    def test_none_input(self):
        result = self.sanitize_text(None)
        assert result == "None"

    def test_dict_input(self):
        result = self.sanitize_text({"key": "val"})
        assert isinstance(result, str)

    # ── Combined ─────────────────────────────────────────────────────────

    def test_combined_ip_and_hostname(self):
        text = "Connection timed out after 8s (server at 192.168.1.100 did not respond)"
        result = self.sanitize_text(text, server_hostname="192.168.1.100")
        assert "192.168.1.100" not in result

    def test_combined_credentials_and_ip(self):
        text = "http://user:pass@192.168.1.5/m3u failed"
        result = self.sanitize_text(text)
        assert "pass" not in result
        assert "192.168.1.5" not in result


# ---------------------------------------------------------------------------
# Tests: sanitization applied in issue draft body
# ---------------------------------------------------------------------------

class TestIssueDraftSanitization:
    """Verify that sensitive data is not present in the generated body."""

    def _build_with_sensitive_data(self, **overrides):
        from utils.issue_draft import build_issue_draft
        kwargs = dict(
            system_data={
                "app_version": "v4.8.0",
                "install_mode": "docker",
                "python_version": "3.11.2",
                "os_info": "Linux-6.1.0",
                "os_name": "Linux",
                "architecture": "x86_64",
                "hostname": "internalserver01",
                "uptime": "1d 2h 3m 4s",
            },
            health_data={
                "db": {
                    "status": "FAIL",
                    "detail": "DB at /home/alice/retroiptv/data/users.db is missing",
                    "remediation": "Restart the app on internalserver01",
                },
            },
            tuner_data=[{
                "name": "My IPTV",
                "overall_status": "FAIL",
                "m3u_probe": {"error": "Connection timed out after 8s (server at 192.168.1.100 did not respond)"},
                "xml_probe": {"error": "DNS resolution failed for 'iptv.lan': [Errno -5] No address"},
            }],
            cache_data={"active_tuner": "My IPTV", "channel_count": 0,
                        "epg_channel_count": 0, "epg_entry_count": 0},
            startup_data={
                "status": "failed",
                "error_count": 1,
                "errors": [{"category": "db_init", "ts": "2026-03-07T00:00:00",
                             "detail": "DB at /home/alice/data/users.db not found on internalserver01"}],
                "events": [],
            },
            config_data={
                "user_accounts": {
                    "status": "WARN",
                    "detail": "Path /home/alice/retroiptv visible",
                    "remediation": "Check internalserver01 permissions",
                },
            },
            recent_log_lines=[
                "2026-03-07 ERROR connection to 10.0.1.50 failed",
                "2026-03-07 WARNING timeout contacting http://user:pass@192.168.2.1/feed",
                "2026-03-07 INFO startup ok on internalserver01",
            ],
            user_description="",
        )
        kwargs.update(overrides)
        return build_issue_draft(**kwargs)

    # ── Hostname never exposed ────────────────────────────────────────────

    def test_real_hostname_not_in_body(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "internalserver01" not in body

    def test_hostname_placeholder_in_body(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "[HOSTNAME]" in body

    # ── IP addresses ─────────────────────────────────────────────────────

    def test_private_ip_not_in_health_detail(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "192.168.1.100" not in body

    def test_private_ip_not_in_log_lines(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "10.0.1.50" not in body

    def test_ip_placeholder_present(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "[IP-REDACTED]" in body

    # ── URL credentials ───────────────────────────────────────────────────

    def test_url_password_not_in_log_lines(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "user:pass" not in body

    def test_credentials_placeholder_present(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "[CREDENTIALS]" in body

    # ── Home paths ────────────────────────────────────────────────────────

    def test_home_path_not_in_health_detail(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "/home/alice" not in body

    def test_home_path_not_in_startup_errors(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "/home/alice/data" not in body

    def test_home_path_not_in_config_issues(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "/home/alice/retroiptv" not in body

    # ── Safe data is preserved ────────────────────────────────────────────

    def test_app_version_preserved(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "v4.8.0" in body

    def test_python_version_not_mistaken_for_ip(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        # 3.11.2 is a version string — must NOT be replaced by [IP-REDACTED]
        assert "3.11.2" in body

    def test_os_info_preserved(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "Linux" in body

    def test_install_mode_preserved(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "docker" in body

    def test_tuner_name_preserved(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "My IPTV" in body

    def test_sanitization_notice_in_footer(self):
        body = self._build_with_sensitive_data()["body_markdown"]
        assert "redacted" in body.lower()

    # ── Endpoint returns sanitized body ───────────────────────────────────

    def test_issue_draft_endpoint_body_sanitized(self, client, isolated_db):
        """End-to-end: the endpoint's body_markdown must not contain IPs."""
        import sqlite3 as _sqlite3
        with _sqlite3.connect(app_module.TUNER_DB) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tuners (name,xml,m3u,tuner_type)"
                " VALUES (?,?,?,?)",
                ("sanitize_test", "http://192.168.55.1/guide.xml",
                 "http://192.168.55.1/playlist.m3u", "standard"),
            )
            conn.commit()
        login(client)
        resp = client.get("/admin/diagnostics/issue-draft")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        # The tuner probe may fail with "server at 192.168.55.1 did not respond"
        # That IP must be redacted in the body.
        assert "192.168.55.1" not in data["body_markdown"]


# ===========================================================================
# Tests: utils.dependency_check
# ===========================================================================

class TestDependencyCheck:
    """Unit tests for the external binary + Python package checker."""

    def test_check_external_binaries_returns_expected_keys(self):
        from utils.dependency_check import check_external_binaries
        result = check_external_binaries()
        assert "status" in result
        assert "binaries" in result
        assert isinstance(result["binaries"], list)

    def test_check_external_binaries_status_is_valid(self):
        from utils.dependency_check import check_external_binaries
        result = check_external_binaries()
        assert result["status"] in ("PASS", "WARN", "FAIL")

    def test_check_external_binaries_each_has_required_fields(self):
        from utils.dependency_check import check_external_binaries
        for entry in check_external_binaries()["binaries"]:
            assert "name" in entry
            assert "found" in entry
            assert "severity" in entry
            assert isinstance(entry["found"], bool)

    def test_check_external_binaries_python_itself_not_listed(self):
        """The binaries list should not include python — it's checked separately."""
        from utils.dependency_check import check_external_binaries
        names = [e["name"] for e in check_external_binaries()["binaries"]]
        assert "python" not in names

    def test_check_python_packages_returns_expected_keys(self):
        from utils.dependency_check import check_python_packages
        result = check_python_packages()
        assert "status" in result
        assert "packages" in result
        assert "python_version" in result
        assert "python_executable" in result

    def test_check_python_packages_status_is_valid(self):
        from utils.dependency_check import check_python_packages
        assert check_python_packages()["status"] in ("PASS", "WARN", "FAIL")

    def test_check_python_packages_flask_installed(self):
        from utils.dependency_check import check_python_packages
        packages = check_python_packages()["packages"]
        flask_entries = [p for p in packages if p["package"].lower() == "flask"]
        assert flask_entries, "Flask should be found in installed packages"
        assert flask_entries[0]["ok"] is True

    def test_dependencies_endpoint_accessible(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/dependencies")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "external_binaries" in data
        assert "python_packages" in data

    def test_dependencies_endpoint_requires_admin(self, client, isolated_db):
        resp = client.get("/admin/diagnostics/dependencies")
        assert resp.status_code in (302, 401, 403)


# ===========================================================================
# Tests: utils.conflict_detector
# ===========================================================================

class TestConflictDetector:
    """Unit tests for the channel conflict detection utility."""

    def _make_channels(self, entries):
        """Inject a list of channel dicts into the app module's cache."""
        import app as app_module
        app_module.cached_channels = entries

    def setup_method(self):
        """Reset cached_channels before each test."""
        import app as app_module
        app_module.cached_channels = []

    def teardown_method(self):
        """Clean up cached_channels after each test."""
        import app as app_module
        app_module.cached_channels = []

    def test_no_channels_returns_pass(self):
        from utils.conflict_detector import detect_channel_conflicts
        self._make_channels([])
        result = detect_channel_conflicts()
        assert result["status"] == "PASS"
        assert result["channel_count"] == 0

    def test_unique_channels_returns_pass(self):
        from utils.conflict_detector import detect_channel_conflicts
        self._make_channels([
            {"name": "CNN", "tvg_id": "cnn.us", "url": "http://stream1.com/cnn"},
            {"name": "BBC", "tvg_id": "bbc.uk", "url": "http://stream1.com/bbc"},
        ])
        result = detect_channel_conflicts()
        assert result["status"] == "PASS"
        assert result["duplicate_names"] == []
        assert result["duplicate_tvg_ids"] == []
        assert result["duplicate_urls"] == []

    def test_duplicate_name_detected(self):
        from utils.conflict_detector import detect_channel_conflicts
        self._make_channels([
            {"name": "CNN", "tvg_id": "cnn.us.1", "url": "http://a.com/1"},
            {"name": "cnn", "tvg_id": "cnn.us.2", "url": "http://a.com/2"},
        ])
        result = detect_channel_conflicts()
        assert result["status"] == "WARN"
        assert len(result["duplicate_names"]) == 1
        assert result["duplicate_names"][0]["count"] == 2

    def test_duplicate_tvg_id_detected(self):
        from utils.conflict_detector import detect_channel_conflicts
        self._make_channels([
            {"name": "CNN HD", "tvg_id": "cnn.us", "url": "http://a.com/1"},
            {"name": "CNN SD", "tvg_id": "cnn.us", "url": "http://a.com/2"},
        ])
        result = detect_channel_conflicts()
        assert result["status"] == "WARN"
        assert len(result["duplicate_tvg_ids"]) == 1
        assert result["duplicate_tvg_ids"][0]["tvg_id"] == "cnn.us"

    def test_duplicate_url_detected(self):
        from utils.conflict_detector import detect_channel_conflicts
        self._make_channels([
            {"name": "Channel A", "tvg_id": "a.tv", "url": "http://same.com/stream"},
            {"name": "Channel B", "tvg_id": "b.tv", "url": "http://same.com/stream"},
        ])
        result = detect_channel_conflicts()
        assert result["status"] == "WARN"
        assert len(result["duplicate_urls"]) == 1

    def test_missing_tvg_id_not_grouped(self):
        """Empty TVG-IDs should not be grouped as a conflict."""
        from utils.conflict_detector import detect_channel_conflicts
        self._make_channels([
            {"name": "A", "tvg_id": "", "url": "http://a.com/1"},
            {"name": "B", "tvg_id": "", "url": "http://b.com/2"},
        ])
        result = detect_channel_conflicts()
        assert result["duplicate_tvg_ids"] == []

    def test_result_has_channel_count(self):
        from utils.conflict_detector import detect_channel_conflicts
        self._make_channels([
            {"name": "X", "tvg_id": "x.tv", "url": "http://x.com/s"},
            {"name": "Y", "tvg_id": "y.tv", "url": "http://y.com/s"},
            {"name": "Z", "tvg_id": "z.tv", "url": "http://z.com/s"},
        ])
        assert detect_channel_conflicts()["channel_count"] == 3

    def test_conflicts_endpoint_accessible(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/conflicts")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "status" in data
        assert "channel_count" in data

    def test_conflicts_endpoint_requires_admin(self, client, isolated_db):
        resp = client.get("/admin/diagnostics/conflicts")
        assert resp.status_code in (302, 401, 403)


# ===========================================================================
# Tests: utils.security_diag
# ===========================================================================

class TestSecurityDiag:
    """Unit tests for the security diagnostics module."""

    def test_strong_secret_key_passes(self):
        import os
        import sqlite3
        import tempfile
        from utils.security_diag import run_security_checks
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "CREATE TABLE users (username TEXT, password TEXT)"
                )
                conn.execute(
                    "INSERT INTO users VALUES ('admin', 'scrypt:abc123')"
                )
            result = run_security_checks(
                db_path=db_path,
                secret_key="a" * 32 + "!@#$%^&*ABCDEF1234",
                debug_mode=False,
                bind_host="127.0.0.1",
            )
            sk_check = next(c for c in result["checks"] if c["name"] == "secret_key")
            assert sk_check["status"] == "PASS"
        finally:
            os.unlink(db_path)

    def test_empty_secret_key_fails(self):
        from utils.security_diag import _check_secret_key
        result = _check_secret_key("")
        assert result["status"] == "FAIL"

    def test_short_secret_key_warns(self):
        from utils.security_diag import _check_secret_key
        result = _check_secret_key("short")
        assert result["status"] in ("WARN", "FAIL")

    def test_known_default_secret_fails(self):
        from utils.security_diag import _check_secret_key
        for val in ["dev", "secret", "changeme", "flask"]:
            assert _check_secret_key(val)["status"] == "FAIL", f"Expected FAIL for {val!r}"

    def test_debug_mode_on_fails(self):
        from utils.security_diag import _check_debug_mode
        assert _check_debug_mode(True)["status"] == "FAIL"

    def test_debug_mode_off_passes(self):
        from utils.security_diag import _check_debug_mode
        assert _check_debug_mode(False)["status"] == "PASS"

    def test_bind_all_interfaces_warns(self):
        from utils.security_diag import _check_bind_address
        assert _check_bind_address("0.0.0.0")["status"] == "WARN"
        assert _check_bind_address("::")["status"] == "WARN"

    def test_bind_loopback_passes(self):
        from utils.security_diag import _check_bind_address
        assert _check_bind_address("127.0.0.1")["status"] == "PASS"
        assert _check_bind_address("localhost")["status"] == "PASS"

    def test_scrypt_hash_passes(self):
        import os
        import sqlite3
        import tempfile
        from utils.security_diag import _check_admin_password_hash
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE users (username TEXT, password TEXT)")
                conn.execute("INSERT INTO users VALUES ('admin', 'scrypt:32768:8:1$...hash...')")
            result = _check_admin_password_hash(db_path)
            assert result["status"] == "PASS"
        finally:
            os.unlink(db_path)

    def test_md5_hash_fails(self):
        import os
        import sqlite3
        import tempfile
        from utils.security_diag import _check_admin_password_hash
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE users (username TEXT, password TEXT)")
                # MD5 hex hash
                conn.execute("INSERT INTO users VALUES ('admin', 'ab56b4d92b40713acc5af89985d4b786')")
            result = _check_admin_password_hash(db_path)
            assert result["status"] == "FAIL"
        finally:
            os.unlink(db_path)

    def test_run_security_checks_returns_expected_keys(self):
        import os
        import sqlite3
        import tempfile
        from utils.security_diag import run_security_checks
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE users (username TEXT, password TEXT)")
                conn.execute("INSERT INTO users VALUES ('admin', 'pbkdf2:sha256:...hash...')")
            result = run_security_checks(
                db_path=db_path,
                secret_key="x" * 40,
                debug_mode=False,
                bind_host="0.0.0.0",
            )
            assert "status" in result
            assert "checks" in result
            assert "detail" in result
            assert isinstance(result["checks"], list)
            assert len(result["checks"]) == 4  # sk, pw, debug, bind
        finally:
            os.unlink(db_path)

    def test_security_endpoint_accessible(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/security")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "status" in data
        assert "checks" in data

    def test_security_endpoint_requires_admin(self, client, isolated_db):
        resp = client.get("/admin/diagnostics/security")
        assert resp.status_code in (302, 401, 403)

    def test_security_in_config_endpoint(self, client, isolated_db):
        """The /config endpoint should now include security check results."""
        login(client)
        resp = client.get("/admin/diagnostics/config")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "security" in data

    def test_dependencies_in_config_endpoint(self, client, isolated_db):
        """The /config endpoint should include dependency check results."""
        login(client)
        resp = client.get("/admin/diagnostics/config")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "external_binaries" in data
        assert "python_packages" in data

    def test_conflicts_in_config_endpoint(self, client, isolated_db):
        """The /config endpoint should include channel conflict results."""
        login(client)
        resp = client.get("/admin/diagnostics/config")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "channel_conflicts" in data


# ===========================================================================
# Tests: Stream Type Detector
# ===========================================================================

class TestStreamDetectUnit:
    """Unit tests for utils.stream_detect — no live network calls."""

    def test_classify_hls_segmenter_by_content(self):
        """M3U8 with EXT-X-MEDIA-SEQUENCE → HLS Segmenter."""
        from utils.stream_detect import _classify
        body = b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:1\n#EXT-X-TARGETDURATION:5\n"
        signals = []
        st, conf, desc, tips = _classify("http://example.com/live.m3u8", "application/vnd.apple.mpegurl", body, signals)
        assert st == "HLS Segmenter"
        assert conf == "high"
        assert "#EXT-X-MEDIA-SEQUENCE" in " ".join(signals)

    def test_classify_hls_direct_master_playlist(self):
        """M3U8 with EXT-X-STREAM-INF and no media-sequence → HLS Direct."""
        from utils.stream_detect import _classify
        body = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500000\nhttp://example.com/low.m3u8\n"
        signals = []
        st, conf, desc, tips = _classify("http://example.com/master.m3u8", "application/vnd.apple.mpegurl", body, signals)
        assert st == "HLS Direct"
        assert conf == "high"

    def test_classify_mpeg_ts_by_sync_bytes(self):
        """Binary data starting with 0x47 every 188 bytes → MPEG-TS."""
        from utils.stream_detect import _classify
        # Construct a minimal fake TS stream: sync byte at 0, 188, 376, 564, 752
        raw = bytearray(188 * 6)
        for i in range(6):
            raw[i * 188] = 0x47
        signals = []
        st, conf, desc, tips = _classify("http://example.com/stream", "video/mp2t", bytes(raw), signals)
        assert "MPEG-TS" in st
        assert conf in ("high", "medium")

    def test_classify_dash_by_content_type(self):
        """Content-Type application/dash+xml → DASH."""
        from utils.stream_detect import _classify
        body = b'<?xml version="1.0"?><MPD xmlns="urn:mpeg:dash:schema:mpd:2011"></MPD>'
        signals = []
        st, conf, desc, tips = _classify("http://example.com/manifest.mpd", "application/dash+xml", body, signals)
        assert st == "DASH"
        assert conf in ("high", "medium")

    def test_classify_mp4_by_ftyp_box(self):
        """MP4 ftyp box at offset 4 → MP4."""
        from utils.stream_detect import _classify
        # ftyp box layout: 4-byte size (0x20=32), 4-byte type ('ftyp'), 4-byte brand, 4-byte version, 16-byte compat brands
        raw = b'\x00\x00\x00\x20ftypisom' + b'\x00' * 24  # 0x20 = 32 = ftyp box size
        signals = []
        st, conf, desc, tips = _classify("http://example.com/video.mp4", "video/mp4", raw, signals)
        assert st == "MP4"

    def test_classify_rtmp_url_scheme(self):
        """rtmp:// URL → RTMP without HTTP fetch."""
        from utils.stream_detect import detect_stream_type
        result = detect_stream_type("rtmp://example.com/live/stream")
        assert result["stream_type"] == "RTMP"
        assert result["confidence"] == "high"
        assert result["fetch"] is None  # no HTTP fetch for RTMP

    def test_classify_unknown_no_signals(self):
        """Text/HTML response with no stream signals → Unknown."""
        from utils.stream_detect import _classify
        body = b"<html><body>Hello world</body></html>"
        signals = []
        st, conf, desc, tips = _classify("http://example.com/page.html", "text/html", body, signals)
        assert st == "Unknown"
        assert conf == "none"

    def test_detect_empty_url_returns_error(self):
        """Empty URL → error in fetch, no crash."""
        from utils.stream_detect import detect_stream_type
        result = detect_stream_type("")
        assert result["stream_type"] == "Unknown"
        assert result["fetch"]["error"] == "No URL provided"

    def test_detect_unsupported_scheme(self):
        """Unsupported scheme (ftp://) → Unknown, no HTTP attempt."""
        from utils.stream_detect import detect_stream_type
        result = detect_stream_type("ftp://example.com/file.ts")
        assert result["stream_type"] == "Unknown"

    def test_count_ts_sync_bytes_valid(self):
        """_count_ts_sync_bytes correctly counts packets."""
        from utils.stream_detect import _count_ts_sync_bytes
        raw = bytearray(188 * 5)
        for i in range(5):
            raw[i * 188] = 0x47
        count = _count_ts_sync_bytes(bytes(raw))
        assert count == 5

    def test_count_ts_sync_bytes_too_short(self):
        """Data shorter than one packet → 0."""
        from utils.stream_detect import _count_ts_sync_bytes
        assert _count_ts_sync_bytes(b"\x47" * 100) == 0

    def test_is_mp4_ftyp(self):
        """MP4 ftyp box correctly identified."""
        from utils.stream_detect import _is_mp4
        # 0x20 = 32 = the ftyp box size field; bytes 4-7 are the box type
        raw = b'\x00\x00\x00\x20ftypisom' + b'\x00' * 24
        assert _is_mp4(raw) is True

    def test_is_mp4_non_mp4(self):
        """Non-MP4 data not identified as MP4."""
        from utils.stream_detect import _is_mp4
        assert _is_mp4(b"#EXTM3U\n#EXT-X-MEDIA") is False

    def test_hls_vod_endlist_tip(self):
        """HLS Segmenter with EXT-X-ENDLIST mentions VOD in tips."""
        from utils.stream_detect import _classify
        body = (
            b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-TARGETDURATION:5\n"
            b"seg0.ts\n#EXT-X-ENDLIST\n"
        )
        signals = []
        st, conf, desc, tips = _classify("http://example.com/vod.m3u8", "application/vnd.apple.mpegurl", body, signals)
        assert st == "HLS Segmenter"
        tip_text = " ".join(tips).lower()
        assert "vod" in tip_text or "completed" in tip_text

    def test_ts_segment_url_medium_confidence(self):
        """URL ending in .ts with no other signals → MPEG-TS segment, medium."""
        from utils.stream_detect import _classify
        signals = []
        st, conf, desc, tips = _classify("http://example.com/segment0001.ts", "application/octet-stream", b"", signals)
        assert "ts" in st.lower() or "mpeg" in st.lower()
        assert conf in ("medium", "low")


class TestStreamDetectEndpoint:
    """Integration tests for the /admin/diagnostics/stream-detect endpoint."""

    def test_endpoint_requires_login(self, client, isolated_db):
        """Unauthenticated request is redirected."""
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "http://example.com/stream.m3u8"},
        )
        assert resp.status_code in (302, 401, 403)

    def test_endpoint_requires_admin(self, client, isolated_db):
        """Regular user gets 403."""
        client.post("/login", data={"username": "regular", "password": "regpass"}, follow_redirects=True)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "http://example.com/stream.m3u8"},
        )
        assert resp.status_code == 403

    def test_endpoint_rejects_invalid_scheme(self, client, isolated_db):
        """ftp:// URL is rejected with 400."""
        login(client)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "ftp://example.com/stream.ts"},
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data

    def test_endpoint_returns_json_for_rtmp(self, client, isolated_db):
        """RTMP URL is classified without a live HTTP fetch."""
        login(client)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "rtmp://example.com/live/stream"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["stream_type"] == "RTMP"
        assert data["confidence"] == "high"
        assert data["fetch"] is None

    def test_endpoint_returns_required_keys(self, client, isolated_db, monkeypatch):
        """Result always contains the required top-level keys."""
        # Mock out the actual HTTP call so the test doesn't require network
        def _mock_detect(url):
            return {
                "url": url,
                "stream_type": "HLS Segmenter",
                "confidence": "high",
                "description": "Mock description",
                "tips": [],
                "fetch": {"ok": True, "status_code": 200, "content_type": "application/vnd.apple.mpegurl",
                          "content_length": None, "response_time_ms": 42, "error": None},
                "dns": {"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None},
                "signals": ["Mock signal"],
            }

        import utils.stream_detect as sd_mod
        monkeypatch.setattr(sd_mod, "detect_stream_type", _mock_detect)

        login(client)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "http://example.com/live.m3u8"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        for key in ("stream_type", "confidence", "description", "tips", "fetch", "dns", "signals", "url"):
            assert key in data, f"Missing key: {key}"

    def test_endpoint_empty_url_returns_result(self, client, isolated_db):
        """Empty URL returns a safe result (no crash, no 500)."""
        login(client)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": ""},
        )
        # Should return 200 with Unknown type (no network call made)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["stream_type"] == "Unknown"

    def test_stream_tab_visible_on_diagnostics_page(self, client, isolated_db):
        """The Stream Detect tab button appears in the diagnostics HTML."""
        login(client)
        resp = client.get("/admin/diagnostics")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "stream" in html.lower()
        assert "Stream Detect" in html or "stream-detect" in html.lower()


# ===========================================================================
# Tests: M3U Channel List detection and channel dropdown data
# ===========================================================================

class TestM3UChannelListDetection:
    """Unit tests for M3U channel list detection in utils.stream_detect."""

    def _m3u_body(self, channels):
        """Build a minimal IPTV M3U playlist text from a list of (name, url, group) tuples."""
        lines = ["#EXTM3U"]
        for name, url, group in channels:
            lines.append(f'#EXTINF:-1 tvg-id="{name.lower()}" group-title="{group}",{name}')
            lines.append(url)
        return "\n".join(lines).encode("utf-8")

    def test_classify_m3u_channel_list_tvg_id(self):
        """M3U with tvg-id attributes and no HLS tags → M3U Channel List."""
        from utils.stream_detect import _classify
        body = self._m3u_body([
            ("CNN", "http://example.com/cnn/stream", "News"),
            ("BBC", "http://example.com/bbc/stream", "News"),
        ])
        signals = []
        st, conf, desc, tips = _classify(
            "http://example.com/playlist.m3u",
            "application/vnd.apple.mpegurl",
            body, signals
        )
        assert st == "M3U Channel List"
        assert conf == "high"

    def test_classify_m3u_channel_list_group_title(self):
        """group-title attribute alone (no tvg-id) still triggers channel list."""
        from utils.stream_detect import _classify
        body = b'#EXTM3U\n#EXTINF:-1 group-title="Sports",ESPN\nhttp://example.com/espn\n'
        signals = []
        st, conf, _, _ = _classify("http://example.com/list.m3u", "audio/x-mpegurl", body, signals)
        assert st == "M3U Channel List"

    def test_classify_m3u_extinf_minus1_duration(self):
        """#EXTINF:-1 (no other attrs) is the IPTV live-stream convention → channel list."""
        from utils.stream_detect import _classify
        body = b'#EXTM3U\n#EXTINF:-1,Channel One\nhttp://example.com/ch1\n'
        signals = []
        st, conf, _, _ = _classify("http://example.com/ch.m3u", "audio/x-mpegurl", body, signals)
        assert st == "M3U Channel List"

    def test_hls_segmenter_not_confused_with_channel_list(self):
        """HLS Segmenter with #EXT-X-MEDIA-SEQUENCE is NOT classified as channel list."""
        from utils.stream_detect import _classify
        body = (
            b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:1\n#EXT-X-TARGETDURATION:5\n"
            b"seg001.ts\nseg002.ts\n"
        )
        signals = []
        st, conf, _, _ = _classify("http://example.com/live.m3u8", "application/vnd.apple.mpegurl", body, signals)
        assert st == "HLS Segmenter"

    def test_hls_direct_not_confused_with_channel_list(self):
        """HLS master playlist with #EXT-X-STREAM-INF is NOT classified as channel list."""
        from utils.stream_detect import _classify
        body = (
            b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500000\n"
            b"http://example.com/low.m3u8\n"
        )
        signals = []
        st, _, _, _ = _classify("http://example.com/master.m3u8", "application/vnd.apple.mpegurl", body, signals)
        assert st == "HLS Direct"


class TestParseM3UChannels:
    """Unit tests for the _parse_m3u_channels helper."""

    def test_basic_channel_parse(self):
        """Parses name, url, group, tvg_id correctly."""
        from utils.stream_detect import _parse_m3u_channels
        text = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="cnn" tvg-name="CNN" group-title="News",CNN International\n'
            "http://example.com/cnn\n"
            '#EXTINF:-1 tvg-id="bbc" group-title="News",BBC One\n'
            "http://example.com/bbc\n"
        )
        channels = _parse_m3u_channels(text)
        assert len(channels) == 2
        assert channels[0]["name"] == "CNN International"
        assert channels[0]["url"] == "http://example.com/cnn"
        assert channels[0]["group"] == "News"
        assert channels[0]["tvg_id"] == "cnn"
        assert channels[1]["name"] == "BBC One"
        assert channels[1]["tvg_id"] == "bbc"

    def test_empty_text_returns_empty_list(self):
        from utils.stream_detect import _parse_m3u_channels
        assert _parse_m3u_channels("") == []

    def test_no_extinf_returns_empty_list(self):
        from utils.stream_detect import _parse_m3u_channels
        text = "#EXTM3U\nhttp://example.com/stream\n"
        assert _parse_m3u_channels(text) == []

    def test_channel_without_group_has_empty_group(self):
        from utils.stream_detect import _parse_m3u_channels
        text = "#EXTM3U\n#EXTINF:-1 tvg-id=\"ch1\",My Channel\nhttp://example.com/ch1\n"
        channels = _parse_m3u_channels(text)
        assert channels[0]["group"] == ""

    def test_channel_without_tvg_id_has_empty_tvg_id(self):
        from utils.stream_detect import _parse_m3u_channels
        text = "#EXTM3U\n#EXTINF:-1 group-title=\"Movies\",Action Film\nhttp://example.com/film\n"
        channels = _parse_m3u_channels(text)
        assert channels[0]["tvg_id"] == ""

    def test_cap_at_max_channels(self):
        """Parser caps output at _MAX_CHANNELS entries."""
        from utils.stream_detect import _parse_m3u_channels, _MAX_CHANNELS
        lines = ["#EXTM3U"]
        for i in range(_MAX_CHANNELS + 50):
            lines.append(f'#EXTINF:-1 tvg-id="ch{i}",Channel {i}')
            lines.append(f"http://example.com/ch{i}")
        channels = _parse_m3u_channels("\n".join(lines))
        assert len(channels) == _MAX_CHANNELS

    def test_url_on_next_line(self):
        """Stream URL is correctly picked from the line following #EXTINF."""
        from utils.stream_detect import _parse_m3u_channels
        text = "#EXTM3U\n#EXTINF:-1 tvg-id=\"x\",X\nhttp://example.com/x\n"
        channels = _parse_m3u_channels(text)
        assert channels[0]["url"] == "http://example.com/x"

    def test_skips_comment_lines_between_extinf_and_url(self):
        """A comment line between #EXTINF and the URL should be skipped."""
        from utils.stream_detect import _parse_m3u_channels
        text = "#EXTM3U\n#EXTINF:-1 tvg-id=\"y\",Y\n#EXTVLCOPT:network-caching=1000\nhttp://example.com/y\n"
        channels = _parse_m3u_channels(text)
        assert channels[0]["url"] == "http://example.com/y"


class TestM3UChannelListEndpoint:
    """Integration tests for the stream-detect endpoint with M3U channel lists."""

    def _make_m3u_body(self):
        return (
            b"#EXTM3U\n"
            b'#EXTINF:-1 tvg-id="cnn" group-title="News",CNN\n'
            b"http://example.com/cnn\n"
            b'#EXTINF:-1 tvg-id="bbc" group-title="News",BBC\n'
            b"http://example.com/bbc\n"
            b'#EXTINF:-1 tvg-id="espn" group-title="Sports",ESPN\n'
            b"http://example.com/espn\n"
        )

    def test_m3u_result_has_channels_key(self, client, isolated_db, monkeypatch):
        """When an M3U channel list is detected, result includes 'channels'."""
        from utils import stream_detect as sd_mod

        def _mock_detect(url):
            from utils.stream_detect import _parse_m3u_channels
            text = self._make_m3u_body().decode("utf-8")
            channels = _parse_m3u_channels(text)
            return {
                "url": url,
                "stream_type": "M3U Channel List",
                "confidence": "high",
                "description": "Mock M3U channel list",
                "tips": [],
                "channels": channels,
                "channel_count": len(channels),
                "fetch": {"ok": True, "status_code": 200, "content_type": "audio/x-mpegurl",
                          "content_length": None, "response_time_ms": 10, "error": None},
                "dns": {"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None},
                "signals": [],
            }

        monkeypatch.setattr(sd_mod, "detect_stream_type", _mock_detect)
        login(client)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "http://example.com/playlist.m3u"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["stream_type"] == "M3U Channel List"
        assert "channels" in data
        assert isinstance(data["channels"], list)
        assert len(data["channels"]) == 3
        assert "channel_count" in data
        assert data["channel_count"] == 3

    def test_m3u_channels_have_required_keys(self, client, isolated_db, monkeypatch):
        """Each channel dict has name, url, group, tvg_id keys."""
        from utils import stream_detect as sd_mod
        from utils.stream_detect import _parse_m3u_channels

        text = self._make_m3u_body().decode("utf-8")

        def _mock_detect(url):
            channels = _parse_m3u_channels(text)
            return {
                "url": url, "stream_type": "M3U Channel List", "confidence": "high",
                "description": "", "tips": [],
                "channels": channels, "channel_count": len(channels),
                "fetch": {"ok": True, "status_code": 200, "content_type": "audio/x-mpegurl",
                          "content_length": None, "response_time_ms": 5, "error": None},
                "dns": {"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None},
                "signals": [],
            }

        monkeypatch.setattr(sd_mod, "detect_stream_type", _mock_detect)
        login(client)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "http://example.com/playlist.m3u"},
        )
        data = json.loads(resp.data)
        for ch in data["channels"]:
            for k in ("name", "url", "group", "tvg_id"):
                assert k in ch, f"Channel missing key: {k}"

    def test_non_m3u_result_has_no_channels_key(self, client, isolated_db, monkeypatch):
        """Non-M3U results do NOT include a 'channels' key."""
        from utils import stream_detect as sd_mod

        def _mock_detect(url):
            return {
                "url": url, "stream_type": "HLS Segmenter", "confidence": "high",
                "description": "", "tips": [],
                "fetch": {"ok": True, "status_code": 200, "content_type": "application/vnd.apple.mpegurl",
                          "content_length": None, "response_time_ms": 5, "error": None},
                "dns": {"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None},
                "signals": [],
            }

        monkeypatch.setattr(sd_mod, "detect_stream_type", _mock_detect)
        login(client)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "http://example.com/live.m3u8"},
        )
        data = json.loads(resp.data)
        assert data["stream_type"] == "HLS Segmenter"
        assert "channels" not in data

    def test_channel_dropdown_elements_in_html(self, client, isolated_db):
        """The diagnostics page HTML includes the channel dropdown elements."""
        login(client)
        resp = client.get("/admin/diagnostics")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "streamChannelSelect" in html
        assert "btnTestChannel" in html
        assert "streamChannelSection" in html
        assert "channelStreamResult" in html


# ===========================================================================
# Tests: esc scope fix and tuner-sources endpoint
# ===========================================================================

class TestEscScopeInTemplate:
    """Verify that the esc() function is defined in the second <script> block
    so the stream detect IIFE can use it without a ReferenceError."""

    def test_esc_defined_in_stream_detect_script_block(self, client, isolated_db):
        """The esc() function definition must appear in the same inline <script>
        block as the stream detect IIFE so it is in scope.

        Previously esc() was only defined inside the FIRST script block's IIFE,
        making it inaccessible to the stream detect code in the second block,
        causing: ReferenceError: esc is not defined.
        """
        login(client)
        resp = client.get("/admin/diagnostics")
        assert resp.status_code == 200
        html = resp.data.decode()

        # Extract every inline <script> ... </script> block.
        script_blocks = re.findall(
            r'<script(?:\s[^>]*)?>(.+?)</script>',
            html, re.DOTALL | re.IGNORECASE
        )
        # Filter to inline scripts only (no src="...").
        inline_blocks = [
            b for b in script_blocks
            if 'btnDetectStream' in b or 'function esc(' in b
        ]
        # There must be at least one block that contains BOTH esc() and btnDetectStream.
        combined = any(
            'function esc(' in b and 'btnDetectStream' in b
            for b in inline_blocks
        )
        # Alternatively, esc() must appear in a block that PRECEDES or IS the
        # block containing btnDetectStream.  To keep it simple: just ensure that
        # all occurrences of 'btnDetectStream' (as a JS identifier) come after
        # at least one 'function esc(' definition in the full page.
        full_js = '\n'.join(inline_blocks)
        assert 'function esc(' in full_js, "esc() helper is missing from all inline <script> blocks"
        assert 'btnDetectStream' in full_js, "stream detect button is missing from inline <script> blocks"

        esc_pos  = full_js.index('function esc(')
        # Find the JS reference to btnDetectStream (not the HTML attribute).
        # The JS references the element by id, so look for getElementById or var btn references.
        js_ref = "getElementById('btnDetectStream')"
        assert js_ref in full_js, f"Could not find JS reference to btnDetectStream: {js_ref!r}"
        ref_pos = full_js.index(js_ref)
        assert esc_pos < ref_pos, (
            "esc() definition must appear before the stream detect IIFE to be in scope.\n"
            f"esc pos: {esc_pos}, stream detect IIFE start: {ref_pos}"
        )


class TestTunerSourcesEndpoint:
    """Tests for GET /admin/diagnostics/tuner-sources."""

    def test_returns_tuners_list_key(self, client, isolated_db):
        """Response is JSON with a 'tuners' list key."""
        login(client)
        resp = client.get("/admin/diagnostics/tuner-sources")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "tuners" in data
        assert isinstance(data["tuners"], list)

    def test_requires_login(self, client, isolated_db):
        """Endpoint requires authentication."""
        resp = client.get("/admin/diagnostics/tuner-sources")
        assert resp.status_code in (302, 401)

    def test_tuner_with_m3u_url_returned(self, client, isolated_db):
        """A tuner that has an M3U URL appears in the result."""
        import sqlite3

        db_path = app_module.TUNER_DB
        # Insert a test tuner with an M3U URL
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tuners (name, m3u, xml, tuner_type, sources) "
                "VALUES (?, ?, ?, ?, ?)",
                ("TestTuner", "http://example.com/test.m3u", "", "standard", "[]"),
            )

        login(client)
        resp = client.get("/admin/diagnostics/tuner-sources")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        names = [t["name"] for t in data["tuners"]]
        assert "TestTuner" in names

        # Verify m3u_url key is present and correct
        tuner = next(t for t in data["tuners"] if t["name"] == "TestTuner")
        assert tuner["m3u_url"] == "http://example.com/test.m3u"

    def test_tuner_without_m3u_url_excluded(self, client, isolated_db):
        """A tuner without an M3U URL is excluded from the result."""
        import sqlite3

        db_path = app_module.TUNER_DB
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tuners (name, m3u, xml, tuner_type, sources) "
                "VALUES (?, ?, ?, ?, ?)",
                ("NoM3UTuner", "", "", "standard", "[]"),
            )

        login(client)
        resp = client.get("/admin/diagnostics/tuner-sources")
        data = json.loads(resp.data)
        names = [t["name"] for t in data["tuners"]]
        assert "NoM3UTuner" not in names

    def test_tuner_picker_html_elements_present(self, client, isolated_db):
        """The stream detect tab includes tuner picker radio buttons and elements."""
        login(client)
        resp = client.get("/admin/diagnostics")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "srcPasteUrl" in html
        assert "srcTuner" in html
        assert "streamTunerSelect" in html
        assert "btnDetectTuner" in html
        assert "streamSourceTunerRow" in html
        assert "streamSourceUrlRow" in html


# ===========================================================================
# Tests: compatible field and tip color scheme
# ===========================================================================

class TestStreamDetectCompatibleField:
    """Verify the 'compatible' field is set correctly for each stream type
    so the UI can render incompatibility tips in amber rather than green."""

    def test_hls_direct_is_caution(self):
        """HLS Direct → compatible = None (should play but not guaranteed; shown as yellow caution)."""
        from utils.stream_detect import _classify
        body = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500000\nhttp://example.com/low.m3u8\n"
        signals = []
        st, conf, desc, tips = _classify(
            "http://example.com/master.m3u8",
            "application/vnd.apple.mpegurl", body, signals
        )
        assert st == "HLS Direct"
        # Verify via detect_stream_type result dict that compatible is None (yellow caution)
        from unittest.mock import patch
        import utils.stream_detect as sd
        fake_fetch = {
            "ok": True, "status_code": 200,
            "content_type": "application/vnd.apple.mpegurl",
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://example.com/master.m3u8")
        assert r["stream_type"] == "HLS Direct"
        assert r["compatible"] is None, (
            "HLS Direct must be None (yellow caution) — HLS.js can play master playlists "
            "but playback is not guaranteed; shown as yellow in the UI, not green"
        )

    def test_hls_segmenter_is_compatible(self):
        """HLS Segmenter → compatible = True."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        body = b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:1\n#EXT-X-TARGETDURATION:5\nseg0.ts\n"
        fake_fetch = {
            "ok": True, "status_code": 200,
            "content_type": "application/vnd.apple.mpegurl",
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://example.com/live.m3u8")
        assert r["stream_type"] == "HLS Segmenter"
        assert r["compatible"] is True

    def test_mpeg_ts_is_not_compatible(self):
        """MPEG-TS → compatible = False (cannot play in HLS.js)."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        raw = bytearray(188 * 6)
        for i in range(6):
            raw[i * 188] = 0x47
        body = bytes(raw)
        fake_fetch = {
            "ok": True, "status_code": 200,
            "content_type": "video/mp2t",
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://example.com/stream")
        assert "mpeg-ts" in r["stream_type"].lower()
        assert r["compatible"] is False

    def test_rtmp_is_not_compatible(self):
        """RTMP → compatible = False (not supported by HLS.js)."""
        from utils.stream_detect import detect_stream_type
        r = detect_stream_type("rtmp://example.com/live/stream")
        assert r["stream_type"] == "RTMP"
        assert r["compatible"] is False

    def test_dash_is_not_compatible(self):
        """DASH → compatible = False."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        body = b'<?xml version="1.0"?><MPD xmlns="urn:mpeg:dash:schema:mpd:2011"></MPD>'
        fake_fetch = {
            "ok": True, "status_code": 200,
            "content_type": "application/dash+xml",
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://example.com/manifest.mpd")
        assert r["stream_type"] == "DASH"
        assert r["compatible"] is False

    def test_m3u_channel_list_compatible_is_none(self):
        """M3U Channel List → compatible = None (neutral, it's a list not a stream)."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        body = (
            b'#EXTM3U\n'
            b'#EXTINF:-1 tvg-id="ch1" group-title="News",Channel 1\n'
            b'http://example.com/ch1.m3u8\n'
        )
        fake_fetch = {
            "ok": True, "status_code": 200,
            "content_type": "application/x-mpegurl",
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://example.com/channels.m3u")
        assert r["stream_type"] == "M3U Channel List"
        assert r["compatible"] is None

    def test_compatible_field_present_in_result_keys(self):
        """The 'compatible' key is always present in the result dict."""
        from utils.stream_detect import detect_stream_type
        r = detect_stream_type("")
        assert "compatible" in r

    def test_rtmp_endpoint_returns_compatible_false(self, client, isolated_db):
        """Stream-detect endpoint includes compatible=false for RTMP."""
        login(client)
        resp = client.post(
            "/admin/diagnostics/stream-detect",
            json={"url": "rtmp://example.com/live/stream"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["compatible"] is False

    def test_tip_css_classes_in_template(self, client, isolated_db):
        """The template contains the CSS classes for warn and ok tips."""
        login(client)
        resp = client.get("/admin/diagnostics")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "sd-tip-warn" in html
        assert "sd-tip-ok" in html


# ===========================================================================
# Tests: URL query string signal detection + HLS Direct incompatibility
# ===========================================================================

class TestStreamDetectQueryStringSignals:
    """Verify that URL query parameters (e.g. ?mode=hls-direct) are used as
    authoritative overrides when the mode is recognised, and as informational
    signals when unrecognised."""

    def _make_fake_fetch(self, body, ct="application/vnd.apple.mpegurl"):
        return {
            "ok": True, "status_code": 200,
            "content_type": ct,
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }

    def test_mode_hls_direct_overrides_to_hls_direct(self):
        """?mode=hls-direct overrides classification to 'HLS Direct' (yellow caution)."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        # Body would normally classify as HLS Segmenter (media playlist), but
        # ?mode=hls-direct is authoritative — the server says it's direct passthrough.
        body = b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:1\n#EXT-X-TARGETDURATION:5\nseg0.ts\n"
        fake_fetch = self._make_fake_fetch(body)
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "iptv.lan", "resolved_ip": "192.168.1.1", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://iptv.lan:8409/iptv/channel/1.m3u8?mode=hls-direct")
        # mode= override takes priority over body content
        assert r["stream_type"] == "HLS Direct", (
            f"Expected 'HLS Direct' from mode=hls-direct override, got {r['stream_type']!r}"
        )
        assert r["compatible"] is None, (
            "HLS Direct must be None (yellow caution) — should play but not guaranteed"
        )
        # Signal must mention the mode override
        signal_text = " ".join(r["signals"]).lower()
        assert "hls-direct" in signal_text, "Expected a signal mentioning mode=hls-direct"

    def test_mode_segmenter_overrides_to_hls_segmenter(self):
        """?mode=segmenter overrides classification to 'HLS Segmenter' (compatible)."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        # ErsatzTV ?mode=segmenter returns a master playlist body (which body
        # detection would classify as HLS Direct), but the mode is authoritative.
        body = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500000\nhttp://iptv.lan/low.m3u8\n"
        fake_fetch = self._make_fake_fetch(body)
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "iptv.lan", "resolved_ip": "192.168.1.1", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://iptv.lan:8409/iptv/channel/2.7.m3u8?mode=segmenter")
        assert r["stream_type"] == "HLS Segmenter", (
            f"Expected 'HLS Segmenter' from mode=segmenter override, got {r['stream_type']!r}"
        )
        assert r["compatible"] is True
        signal_text = " ".join(r["signals"]).lower()
        assert "segmenter" in signal_text, "Expected a signal mentioning mode=segmenter"

    def test_unrecognised_mode_falls_back_to_body_classification(self):
        """An unrecognised mode value does not override body-content classification."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        # Body is a master playlist → HLS Direct (body-based); mode=custom is unrecognised
        body = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500000\nhttp://iptv.lan/low.m3u8\n"
        fake_fetch = self._make_fake_fetch(body)
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "iptv.lan", "resolved_ip": "192.168.1.1", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://iptv.lan:8409/channel/1.m3u8?mode=custom")
        # Unrecognised mode → body wins
        assert r["stream_type"] == "HLS Direct"
        # Signal should note it's unrecognised
        signal_text = " ".join(r["signals"]).lower()
        assert "unrecognised" in signal_text or "mode=" in signal_text

    def test_url_without_query_string_no_mode_signal(self):
        """URLs without query strings don't produce a mode signal."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        body = b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:1\n#EXT-X-TARGETDURATION:5\nseg0.ts\n"
        fake_fetch = self._make_fake_fetch(body)
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "example.com", "resolved_ip": "1.2.3.4", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://example.com/live.m3u8")
        signal_text = " ".join(r["signals"]).lower()
        assert "mode=" not in signal_text

    def test_hls_direct_tips_are_informational_not_warnings(self):
        """HLS Direct tips must be cautionary, must not recommend ?mode=segmenter."""
        from utils.stream_detect import _classify
        body = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500000\nhttp://example.com/low.m3u8\n"
        signals = []
        st, conf, desc, tips = _classify(
            "http://example.com/master.m3u8",
            "application/vnd.apple.mpegurl", body, signals
        )
        assert st == "HLS Direct"
        tip_text = " ".join(tips).lower()
        desc_text = desc.lower()
        # Must not use alarming language implying it will definitely fail
        assert "spin without playing" not in tip_text
        assert "will spin" not in tip_text
        assert "will not play" not in desc_text
        # Must NOT recommend ?mode=segmenter — not all servers support it
        assert "mode=segmenter" not in tip_text, (
            "HLS Direct tips must not tell users to try ?mode=segmenter "
            "— this parameter is ErsatzTV-specific and not universally available"
        )
        # Must convey that HLS.js can handle master playlists, with cautionary nuance
        assert any(
            kw in tip_text or kw in desc_text
            for kw in ("should play", "hls.js", "master playlist", "play", "most")
        ), f"Expected cautionary-but-positive HLS Direct tips, got tips={tip_text!r} desc={desc_text!r}"
        # Must tell the user what to do when it doesn't work
        assert "not supported" in tip_text or "spinner" in tip_text, (
            "HLS Direct tips must explain what persistent buffering/spinner means: "
            "the stream is not supported"
        )

    def test_hls_direct_is_in_compatible_types_none(self):
        """_COMPATIBLE_TYPES must have HLS Direct mapped to None (caution — shown yellow in UI)."""
        from utils.stream_detect import _COMPATIBLE_TYPES
        assert _COMPATIBLE_TYPES.get("HLS Direct") is None, (
            "HLS Direct must be None in _COMPATIBLE_TYPES — it may play via HLS.js "
            "but is not guaranteed; shown as yellow caution, not green"
        )


# ===========================================================================
# Tests: M3U channel list pre-classification + body-mismatch signal
# ===========================================================================

class TestStreamDetectModeHintParsing:
    """Verify that _mode_hint_from_url and _parse_m3u_channels correctly
    pre-classify channels from their URL mode= parameters."""

    def test_mode_hint_segmenter(self):
        """_mode_hint_from_url returns 'segmenter' for ?mode=segmenter."""
        from utils.stream_detect import _mode_hint_from_url
        assert _mode_hint_from_url("http://iptv.lan/ch.m3u8?mode=segmenter") == "segmenter"

    def test_mode_hint_hls_direct(self):
        """_mode_hint_from_url returns 'hls-direct' for ?mode=hls-direct."""
        from utils.stream_detect import _mode_hint_from_url
        assert _mode_hint_from_url("http://iptv.lan/ch.m3u8?mode=hls-direct") == "hls-direct"

    def test_mode_hint_no_query_string(self):
        """_mode_hint_from_url returns '' for URLs without a query string."""
        from utils.stream_detect import _mode_hint_from_url
        assert _mode_hint_from_url("http://iptv.lan/ch.m3u8") == ""

    def test_mode_hint_unrecognised_mode(self):
        """_mode_hint_from_url returns '' for unrecognised mode values."""
        from utils.stream_detect import _mode_hint_from_url
        assert _mode_hint_from_url("http://iptv.lan/ch.m3u8?mode=custom") == ""

    def test_parse_m3u_channels_adds_stream_type_hint(self):
        """_parse_m3u_channels adds stream_type_hint from channel URL mode= param."""
        from utils.stream_detect import _parse_m3u_channels
        m3u = (
            "#EXTM3U\n"
            "#EXTINF:-1 tvg-id=\"ch1\" group-title=\"Test\",Channel 1 (MPEG)\n"
            "http://iptv.lan:8409/iptv/channel/1.ts\n"
            "#EXTINF:-1 tvg-id=\"ch2\" group-title=\"Test\",Channel 2 (HLS Direct)\n"
            "http://iptv.lan:8409/iptv/channel/2.m3u8?mode=hls-direct\n"
            "#EXTINF:-1 tvg-id=\"ch3\" group-title=\"Test\",Channel 3 (HLS Segmenter)\n"
            "http://iptv.lan:8409/iptv/channel/3.m3u8?mode=segmenter\n"
        )
        channels = _parse_m3u_channels(m3u)
        assert len(channels) == 3

        ch1, ch2, ch3 = channels
        # MPEG-TS channel — no recognised mode param → no hint
        assert ch1["stream_type_hint"] == "", f"Expected no hint for ch1, got {ch1['stream_type_hint']!r}"
        assert ch1["compatible_hint"] is None

        # HLS Direct channel — caution (yellow 🟡), not green ✅
        assert ch2["stream_type_hint"] == "HLS Direct"
        assert ch2["compatible_hint"] is None, (
            "HLS Direct must be None (yellow caution) — should play but not guaranteed"
        )

        # HLS Segmenter channel
        assert ch3["stream_type_hint"] == "HLS Segmenter"
        assert ch3["compatible_hint"] is True, "HLS Segmenter must be compatible"

    def test_parse_m3u_channels_no_mode_no_hint(self):
        """Channels without ?mode= have empty stream_type_hint and None compatible_hint."""
        from utils.stream_detect import _parse_m3u_channels
        m3u = (
            "#EXTM3U\n"
            "#EXTINF:-1,Plain Stream\n"
            "http://server.example.com/live.m3u8\n"
        )
        channels = _parse_m3u_channels(m3u)
        assert len(channels) == 1
        assert channels[0]["stream_type_hint"] == ""
        assert channels[0]["compatible_hint"] is None

    def test_body_mismatch_signal_when_mode_overrides(self):
        """When mode= override differs from body classification, a mismatch signal is added."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        # mode=segmenter but body is a master playlist (HLS Direct) — they differ
        body = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500000\nhttp://iptv.lan/low.m3u8\n"
        fake_fetch = {
            "ok": True, "status_code": 200,
            "content_type": "application/vnd.apple.mpegurl",
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "iptv.lan", "resolved_ip": "192.168.1.1", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://iptv.lan:8409/iptv/channel/2.m3u8?mode=segmenter")
        # mode= wins
        assert r["stream_type"] == "HLS Segmenter"
        # A mismatch signal should be present because body says HLS Direct
        signal_text = " ".join(r["signals"]).lower()
        assert "body content" in signal_text or "hls direct" in signal_text or "takes precedence" in signal_text, (
            f"Expected a body-mismatch signal in signals: {r['signals']}"
        )

    def test_body_disagrees_with_hls_direct_mode_result_still_hls_direct(self):
        """When body says HLS Segmenter but mode=hls-direct, result is HLS Direct (yellow caution)."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        # Body is a media playlist (body classification: HLS Segmenter), but
        # mode=hls-direct overrides to HLS Direct (yellow caution — may play, not guaranteed).
        body = b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:1\n#EXT-X-TARGETDURATION:5\nseg0.ts\n"
        fake_fetch = {
            "ok": True, "status_code": 200,
            "content_type": "application/vnd.apple.mpegurl",
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "iptv.lan", "resolved_ip": "192.168.1.1", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://iptv.lan:8409/ch.m3u8?mode=hls-direct")
        # mode= override wins even though body looks like HLS Segmenter
        assert r["stream_type"] == "HLS Direct"
        assert r["compatible"] is None, (
            "HLS Direct must be None (yellow caution) — should play but not guaranteed"
        )

    def test_no_mode_param_uses_body_only(self):
        """Without ?mode=, classification is purely body-content based."""
        import utils.stream_detect as sd
        from unittest.mock import patch
        body = b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:1\n#EXT-X-TARGETDURATION:5\nseg0.ts\n"
        fake_fetch = {
            "ok": True, "status_code": 200,
            "content_type": "application/vnd.apple.mpegurl",
            "content_length": len(body), "response_time_ms": 10,
            "error": None, "raw_bytes": body,
        }
        with patch.object(sd, "_fetch_partial", return_value=fake_fetch), \
             patch.object(sd, "_check_dns", return_value={"hostname": "server.example.com", "resolved_ip": "1.2.3.4", "error": None}), \
             patch.object(sd, "_check_ssrf_risk", return_value=None):
            r = sd.detect_stream_type("http://server.example.com/live.m3u8")
        # Body is a media playlist → HLS Segmenter
        assert r["stream_type"] == "HLS Segmenter"
        assert r["compatible"] is True
        # No mode override signal present
        signal_text = " ".join(r["signals"]).lower()
        assert "mode=" not in signal_text
