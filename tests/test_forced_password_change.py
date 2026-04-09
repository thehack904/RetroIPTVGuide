"""Tests for the admin first-login forced password change and CLI reset tool."""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app, init_db, init_tuners_db


# ---------------------------------------------------------------------------
# Fixtures (mirrors the pattern used in other test files)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    users_db  = str(tmp_path / "users_test.db")
    tuners_db = str(tmp_path / "tuners_test.db")
    data_dir  = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)

    monkeypatch.setattr(app_module, "DATABASE", users_db)
    monkeypatch.setattr(app_module, "TUNER_DB", tuners_db)
    monkeypatch.setattr(app_module, "DATA_DIR", data_dir)

    init_db()
    init_tuners_db()
    yield tmp_path


@pytest.fixture()
def client(isolated_db):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def _add_user(username, password, must_change=0):
    from app import add_user
    add_user(username, password, must_change_password=must_change)


def login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Tests: must_change_password DB column and User model
# ---------------------------------------------------------------------------

class TestMustChangePasswordColumn:
    def test_column_exists_after_init_db(self, isolated_db):
        db_path = str(isolated_db / "users_test.db")
        with sqlite3.connect(db_path) as conn:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        assert "must_change_password" in cols

    def test_add_user_default_flag_is_zero(self, isolated_db):
        from app import DATABASE
        _add_user("normaluser", "pass1234")
        with sqlite3.connect(DATABASE) as conn:
            row = conn.execute(
                "SELECT must_change_password FROM users WHERE username='normaluser'"
            ).fetchone()
        assert row is not None
        assert row[0] == 0

    def test_add_user_with_forced_flag(self, isolated_db):
        from app import DATABASE
        _add_user("forceduser", "pass1234", must_change=1)
        with sqlite3.connect(DATABASE) as conn:
            row = conn.execute(
                "SELECT must_change_password FROM users WHERE username='forceduser'"
            ).fetchone()
        assert row is not None
        assert row[0] == 1

    def test_get_user_returns_must_change_false_by_default(self, isolated_db):
        from app import get_user
        _add_user("testuser", "pass1234")
        user = get_user("testuser")
        assert user is not None
        assert user.must_change_password is False

    def test_get_user_returns_must_change_true_when_set(self, isolated_db):
        from app import get_user
        _add_user("admintest", "pass1234", must_change=1)
        user = get_user("admintest")
        assert user is not None
        assert user.must_change_password is True


# ---------------------------------------------------------------------------
# Tests: first-login redirect
# ---------------------------------------------------------------------------

class TestFirstLoginRedirect:
    def test_login_without_flag_goes_to_guide(self, client):
        _add_user("normaladmin", "pass1234", must_change=0)
        resp = login(client, "normaladmin", "pass1234")
        assert resp.status_code == 302
        assert "guide" in resp.headers["Location"]

    def test_login_with_forced_flag_redirects_to_change_password(self, client):
        _add_user("forcedadmin", "pass1234", must_change=1)
        resp = login(client, "forcedadmin", "pass1234")
        assert resp.status_code == 302
        assert "change_password" in resp.headers["Location"]

    def test_change_password_page_shows_forced_notice(self, client):
        _add_user("forcedadmin2", "pass1234", must_change=1)
        login(client, "forcedadmin2", "pass1234")
        resp = client.get("/change_password", follow_redirects=True)
        assert resp.status_code == 200
        assert b"must change your password" in resp.data

    def test_change_password_page_no_notice_for_normal_user(self, client):
        _add_user("normaluser2", "pass1234", must_change=0)
        login(client, "normaluser2", "pass1234")
        resp = client.get("/change_password", follow_redirects=True)
        assert resp.status_code == 200
        assert b"must change your password" not in resp.data


# ---------------------------------------------------------------------------
# Tests: clearing must_change_password after successful change
# ---------------------------------------------------------------------------

class TestClearFlagAfterPasswordChange:
    def test_flag_cleared_after_successful_change(self, client, isolated_db):
        from app import DATABASE, get_user
        _add_user("resetuser", "oldpass1", must_change=1)
        login(client, "resetuser", "oldpass1")
        resp = client.post(
            "/change_password",
            data={
                "old_password": "oldpass1",
                "new_password": "newpass2",
                "confirm_password": "newpass2",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "guide" in resp.headers["Location"]

        with sqlite3.connect(DATABASE) as conn:
            row = conn.execute(
                "SELECT must_change_password FROM users WHERE username='resetuser'"
            ).fetchone()
        assert row[0] == 0

    def test_wrong_old_password_keeps_flag(self, client, isolated_db):
        from app import DATABASE
        _add_user("resetuser2", "oldpass1", must_change=1)
        login(client, "resetuser2", "oldpass1")
        client.post(
            "/change_password",
            data={
                "old_password": "WRONGPASS",
                "new_password": "newpass2",
                "confirm_password": "newpass2",
            },
            follow_redirects=False,
        )
        with sqlite3.connect(DATABASE) as conn:
            row = conn.execute(
                "SELECT must_change_password FROM users WHERE username='resetuser2'"
            ).fetchone()
        assert row[0] == 1


# ---------------------------------------------------------------------------
# Tests: CLI reset script
# ---------------------------------------------------------------------------

class TestResetAdminPasswordScript:
    def test_reset_updates_password_and_sets_flag(self, isolated_db):
        from app import DATABASE, get_user
        from werkzeug.security import check_password_hash

        _add_user("admin", "oldpass1")

        import scripts.reset_admin_password as reset_script
        reset_script.reset_password(DATABASE, "newSecurePass1")

        user = get_user("admin")
        assert user is not None
        assert check_password_hash(user.password_hash, "newSecurePass1")
        assert user.must_change_password is True

    def test_reset_rejects_short_password(self, isolated_db):
        from app import DATABASE
        _add_user("admin", "oldpass1")

        import scripts.reset_admin_password as reset_script
        with pytest.raises(SystemExit):
            reset_script.reset_password(DATABASE, "short")

    def test_reset_fails_on_missing_db(self, tmp_path):
        import scripts.reset_admin_password as reset_script
        with pytest.raises(SystemExit):
            reset_script.reset_password(str(tmp_path / "nonexistent.db"), "goodpassword")

    def test_reset_fails_when_no_admin_account(self, isolated_db):
        from app import DATABASE
        import scripts.reset_admin_password as reset_script
        with pytest.raises(SystemExit):
            reset_script.reset_password(DATABASE, "goodpassword")

    def test_reset_on_empty_db_fails_cleanly(self, tmp_path):
        """reset_password() must not crash with OperationalError on an uninitialised DB."""
        import scripts.reset_admin_password as reset_script

        db = str(tmp_path / "empty.db")
        # Create a valid SQLite file with no tables at all.
        with sqlite3.connect(db) as conn:
            pass

        # Should exit cleanly (no admin account) rather than raising OperationalError.
        with pytest.raises(SystemExit) as exc_info:
            reset_script.reset_password(db, "goodpassword")
        assert exc_info.value.code == 1

    def test_reset_migrates_legacy_schema(self, tmp_path):
        """reset_password() must work against a DB that has no extra columns."""
        import scripts.reset_admin_password as reset_script

        db = str(tmp_path / "legacy.db")
        with sqlite3.connect(db) as conn:
            conn.execute(
                "CREATE TABLE users "
                "(id INTEGER PRIMARY KEY, username TEXT, password TEXT)"
            )
            conn.execute(
                "INSERT INTO users (username, password) VALUES ('admin', 'oldhash')"
            )
            conn.commit()

        # Should not raise even though last_login / assigned_tuner /
        # must_change_password columns are absent from the legacy table.
        reset_script.reset_password(db, "newpassword1")

        with sqlite3.connect(db) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
            row = conn.execute(
                "SELECT must_change_password FROM users WHERE username='admin'"
            ).fetchone()

        assert "last_login" in cols
        assert "assigned_tuner" in cols
        assert "must_change_password" in cols
        assert row[0] == 1

    def test_reset_fails_cleanly_on_readonly_db(self, tmp_path):
        """reset_password() must print a clear error (not a traceback) for a read-only DB."""
        import scripts.reset_admin_password as reset_script

        db = str(tmp_path / "readonly.db")
        with sqlite3.connect(db) as conn:
            conn.execute(
                "CREATE TABLE users "
                "(id INTEGER PRIMARY KEY, username TEXT, password TEXT)"
            )
            conn.execute(
                "INSERT INTO users (username, password) VALUES ('admin', 'oldhash')"
            )
            conn.commit()

        os.chmod(db, 0o444)
        try:
            with pytest.raises(SystemExit) as exc_info:
                reset_script.reset_password(db, "goodpassword")
            assert exc_info.value.code == 1
        finally:
            os.chmod(db, 0o644)

    def test_reset_fails_cleanly_on_readonly_directory(self, tmp_path):
        """reset_password() must handle a read-only parent directory gracefully."""
        import scripts.reset_admin_password as reset_script

        db_dir = tmp_path / "rodir"
        db_dir.mkdir()
        db = str(db_dir / "users.db")
        with sqlite3.connect(db) as conn:
            conn.execute(
                "CREATE TABLE users "
                "(id INTEGER PRIMARY KEY, username TEXT, password TEXT)"
            )
            conn.execute(
                "INSERT INTO users (username, password) VALUES ('admin', 'oldhash')"
            )
            conn.commit()

        os.chmod(str(db_dir), 0o555)
        try:
            with pytest.raises(SystemExit) as exc_info:
                reset_script.reset_password(db, "goodpassword")
            assert exc_info.value.code == 1
        finally:
            os.chmod(str(db_dir), 0o755)
