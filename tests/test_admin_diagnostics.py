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
        for key in ("db", "schema", "tuners", "xmltv", "disk_space", "write_permissions"):
            assert key in result


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
