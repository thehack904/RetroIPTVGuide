#!/usr/bin/env python3
"""Reset the admin account password from the command line.

Usage
-----
    python scripts/reset_admin_password.py [--db PATH] [--password NEW_PASSWORD]

Options
-------
  --db PATH           Path to the users SQLite database.
                      Defaults to ``data/users.db`` relative to the project root.
  --password TEXT     New password to set. If omitted, an interactive prompt is used.

After the reset the admin account is flagged ``must_change_password=1`` so that
the admin is required to set a new personal password on next login.
"""

from __future__ import annotations

import argparse
import getpass
import glob
import os
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Allow running directly from the project root without installing the package.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# If werkzeug is not available on the current interpreter (e.g. when the
# script is run with the system python3 instead of the app's venv python),
# probe common virtual-environment locations relative to the project root and
# add their site-packages directories to sys.path before importing.
# ---------------------------------------------------------------------------
def _probe_venv() -> None:
    """Add venv site-packages to sys.path if werkzeug is not yet importable."""
    try:
        import werkzeug  # noqa: F401
        return  # already importable — nothing to do
    except ImportError:
        pass

    _VENV_NAMES = ("venv", ".venv", "env", ".env")
    for name in _VENV_NAMES:
        candidate = os.path.join(_PROJECT_ROOT, name)
        if not os.path.isdir(candidate):
            continue
        # site-packages lives under lib/pythonX.Y/site-packages on POSIX
        # and under Lib/site-packages on Windows.
        patterns = [
            os.path.join(candidate, "lib", "python*", "site-packages"),
            os.path.join(candidate, "Lib", "site-packages"),
        ]
        for pattern in patterns:
            for sp in glob.glob(pattern):
                if sp not in sys.path:
                    sys.path.insert(0, sp)

_probe_venv()

try:
    from werkzeug.security import generate_password_hash  # noqa: E402
except ImportError:
    print(
        "ERROR: The 'werkzeug' package is not available.\n"
        "Run this script with the same Python interpreter used by the app, e.g.:\n"
        "  venv/bin/python scripts/reset_admin_password.py\n"
        "or activate the virtual environment first:\n"
        "  source venv/bin/activate && python scripts/reset_admin_password.py",
        file=sys.stderr,
    )
    sys.exit(1)


_DEFAULT_DB = os.path.join(_PROJECT_ROOT, "data", "users.db")
_MIN_PASSWORD_LEN = 8


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset the RetroIPTVGuide admin account password.",
    )
    parser.add_argument(
        "--db",
        default=_DEFAULT_DB,
        metavar="PATH",
        help=f"Path to the users SQLite database (default: {_DEFAULT_DB})",
    )
    parser.add_argument(
        "--password",
        default=None,
        metavar="NEW_PASSWORD",
        help="New password. If omitted, an interactive secure prompt is used.",
    )
    return parser.parse_args(argv)


class _PasswordTooShortError(ValueError):
    """Raised when the supplied password does not meet the minimum length."""


def _validate_password_strength(pw: str) -> None:
    """Raise :exc:`_PasswordTooShortError` if *pw* is too short."""
    if len(pw) < _MIN_PASSWORD_LEN:
        raise _PasswordTooShortError(
            f"Password must be at least {_MIN_PASSWORD_LEN} characters."
        )


def _print_write_error(db_path: str) -> None:
    """Print a detailed, actionable error message when the DB cannot be written."""
    import stat

    lines = [f"ERROR: Cannot write to the database: {db_path}"]

    try:
        st = os.stat(db_path)
        file_uid = st.st_uid
        file_owner = _uid_to_name(file_uid)
        current_uid = os.getuid()
        current_user = _uid_to_name(current_uid)
        mode = stat.filemode(st.st_mode)

        lines.append(f"       File permissions : {mode}  owner={file_owner} (uid={file_uid})")
        lines.append(f"       Running as       : {current_user} (uid={current_uid})")

        if current_uid != file_uid and current_uid != 0:
            lines.append("")
            lines.append(
                f"       The file is owned by '{file_owner}' but you are running as "
                f"'{current_user}'."
            )
            lines.append(
                f"       Run the script as the file owner, e.g.:"
            )
            lines.append(
                f"         sudo -u {file_owner} python3 {os.path.abspath(__file__)} --db {db_path}"
            )
        else:
            lines.append("")
            lines.append(
                "       The file or its parent directory is not writable by the current user."
            )
            lines.append(f"       Try:  chmod u+w {db_path}")
    except OSError:
        pass

    lines.append("")
    lines.append(
        "       If permissions look correct but writes still fail, the file may have"
    )
    lines.append(
        "       the immutable attribute set.  Check with:"
    )
    lines.append(f"         lsattr {db_path}")
    lines.append(
        "       If the output shows 'i' (e.g. '----i---------'), remove it with:"
    )
    lines.append(f"         sudo chattr -i {db_path}")

    print("\n".join(lines), file=sys.stderr)


def _uid_to_name(uid: int) -> str:
    """Return the username for *uid*, falling back to the numeric string."""
    try:
        import pwd
        return pwd.getpwuid(uid).pw_name
    except (ImportError, KeyError):
        return str(uid)


def reset_password(db_path: str, new_password: str) -> None:
    """Reset the admin password and set must_change_password=1."""
    if not os.path.isfile(db_path):
        print(f"ERROR: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    try:
        _validate_password_strength(new_password)
    except _PasswordTooShortError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    pw_hash = generate_password_hash(new_password)

    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            # Ensure the users table exists before running column migrations.
            # A database pointed to by --db may have been created but never fully
            # initialised by the application (e.g. a brand-new install where the app
            # hasn't been started yet).  Without this, all ALTER TABLE statements
            # silently swallow "no such table: users" and the subsequent SELECT
            # then raises an unhandled OperationalError.
            conn.execute(
                "CREATE TABLE IF NOT EXISTS users "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)"
            )
            conn.commit()

            # Apply all known column migrations so the DB is fully up to date after
            # running this script.  This list must stay in sync with
            # _apply_users_schema_migrations() in app.py; importing app directly is
            # intentionally avoided here to keep this script self-contained and
            # free of Flask initialisation overhead.
            _COLUMN_MIGRATIONS = [
                'ALTER TABLE users ADD COLUMN last_login TEXT',
                'ALTER TABLE users ADD COLUMN assigned_tuner TEXT',
                'ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0',
            ]
            for _stmt in _COLUMN_MIGRATIONS:
                try:
                    conn.execute(_stmt)
                    conn.commit()
                except sqlite3.OperationalError as _exc:
                    # Only suppress "duplicate column name" — the column was already
                    # added by a previous run or the app's own migration.  Any other
                    # OperationalError (e.g. "attempt to write a readonly database")
                    # must propagate so it is reported to the user.
                    if "duplicate column name" not in str(_exc).lower():
                        raise

            row = conn.execute(
                "SELECT id FROM users WHERE username = 'admin' LIMIT 1"
            ).fetchone()
            if row is None:
                print("ERROR: No admin account found in the database.", file=sys.stderr)
                sys.exit(1)

            conn.execute(
                "UPDATE users SET password = ?, must_change_password = 1 WHERE username = 'admin'",
                (pw_hash,),
            )
            conn.commit()

    except PermissionError:
        _print_write_error(db_path)
        sys.exit(1)
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if "readonly" in msg or "read-only" in msg:
            _print_write_error(db_path)
        else:
            print(f"ERROR: Database error: {exc}", file=sys.stderr)
        sys.exit(1)

    print("✅ Admin password reset successfully.")
    print("   The admin will be required to change their password on next login.")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.password:
        new_password = args.password
    else:
        try:
            new_password = getpass.getpass("New admin password: ")
            confirm = getpass.getpass("Confirm new password: ")
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)
        if new_password != confirm:
            print("ERROR: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    reset_password(args.db, new_password)


if __name__ == "__main__":
    main()
