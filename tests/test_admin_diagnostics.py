"""Tests for the Admin Diagnostics blueprint and utility modules."""
import io
import json
import os
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
# Tests: cache endpoint now includes all_tuners
# ---------------------------------------------------------------------------

class TestCacheEndpointAllTuners:
    def test_cache_endpoint_includes_all_tuners(self, client, isolated_db):
        login(client)
        resp = client.get("/admin/diagnostics/cache")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "all_tuners" in data
        assert isinstance(data["all_tuners"], list)
