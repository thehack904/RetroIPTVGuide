"""Health-check utilities for the Diagnostics subsystem.

Each check returns a dict with:
  ``status``      – "PASS" | "WARN" | "FAIL"
  ``detail``      – human-readable description (no secrets)
  ``remediation`` – suggested fix (empty string when PASS/WARN is fine)
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from typing import Any, Dict


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_db(db_path: str) -> Dict[str, Any]:
    """Verify that the main users database is reachable and readable."""
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            conn.execute("SELECT 1")
        return {
            "status": "PASS",
            "detail": "Database connection successful.",
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "FAIL",
            "detail": f"Database connection failed: {type(exc).__name__}",
            "remediation": (
                "Check that the database file exists and has correct permissions. "
                "Restart the application to trigger re-initialisation."
            ),
        }


def check_schema(db_path: str) -> Dict[str, Any]:
    """Verify that expected tables exist in the users database."""
    required = {"users", "user_preferences"}
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            found = {row[0] for row in cur.fetchall()}
        missing = required - found
        if missing:
            return {
                "status": "FAIL",
                "detail": f"Missing tables: {', '.join(sorted(missing))}",
                "remediation": (
                    "Run the application once with --init-db or restart to trigger "
                    "automatic schema migration."
                ),
            }
        return {
            "status": "PASS",
            "detail": "All required tables present.",
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "FAIL",
            "detail": f"Schema check failed: {type(exc).__name__}",
            "remediation": "See database check for more information.",
        }


def check_tuners(tuner_db_path: str) -> Dict[str, Any]:
    """Verify that the tuner database has at least one configured tuner."""
    try:
        with sqlite3.connect(tuner_db_path, timeout=5) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM tuners")
            count = cur.fetchone()[0]
        if count == 0:
            return {
                "status": "WARN",
                "detail": "No tuners configured.",
                "remediation": "Add at least one tuner in Settings → Tuner Management.",
            }
        return {
            "status": "PASS",
            "detail": f"{count} tuner(s) configured.",
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "FAIL",
            "detail": f"Tuner database error: {type(exc).__name__}",
            "remediation": "Check that tuners.db exists and is readable.",
        }


def check_xmltv(tuner_db_path: str) -> Dict[str, Any]:
    """Check whether any tuner has a non-empty XMLTV URL configured."""
    try:
        with sqlite3.connect(tuner_db_path, timeout=5) as conn:
            cur = conn.execute("SELECT name, xml FROM tuners")
            rows = cur.fetchall()

        if not rows:
            return {
                "status": "WARN",
                "detail": "No tuners present; cannot check XMLTV.",
                "remediation": "Add a tuner with an XMLTV URL.",
            }

        missing = [name for name, xml in rows if not xml or not xml.strip()]
        if missing:
            return {
                "status": "WARN",
                "detail": (
                    f"Tuner(s) missing XMLTV URL: {', '.join(missing)}"
                ),
                "remediation": "Set an XMLTV URL in Settings → Tuner Management.",
            }
        return {
            "status": "PASS",
            "detail": "All tuners have XMLTV URLs configured.",
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "FAIL",
            "detail": f"XMLTV check failed: {type(exc).__name__}",
            "remediation": "Check tuner database integrity.",
        }


def check_disk_space(data_dir: str, warn_threshold_mb: int = 500) -> Dict[str, Any]:
    """Check that DATA_DIR has sufficient free disk space."""
    try:
        usage = shutil.disk_usage(data_dir)
        free_mb = usage.free // (1024 * 1024)
        total_mb = usage.total // (1024 * 1024)
        if free_mb < 50:
            return {
                "status": "FAIL",
                "detail": f"Critical: only {free_mb} MB free of {total_mb} MB.",
                "remediation": (
                    "Free disk space immediately. Rotate or delete old log files."
                ),
            }
        if free_mb < warn_threshold_mb:
            return {
                "status": "WARN",
                "detail": f"Low disk space: {free_mb} MB free of {total_mb} MB.",
                "remediation": (
                    f"Consider freeing disk space. Warning threshold is {warn_threshold_mb} MB."
                ),
            }
        return {
            "status": "PASS",
            "detail": f"{free_mb} MB free of {total_mb} MB.",
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "WARN",
            "detail": f"Could not check disk space: {type(exc).__name__}",
            "remediation": "Verify that DATA_DIR is mounted correctly.",
        }


def check_write_permissions(data_dir: str) -> Dict[str, Any]:
    """Verify that the application can write to DATA_DIR."""
    probe = os.path.join(data_dir, ".write_probe")
    try:
        with open(probe, "w") as fh:
            fh.write("ok")
        os.unlink(probe)
        return {
            "status": "PASS",
            "detail": f"Write access confirmed for {data_dir}.",
            "remediation": "",
        }
    except (PermissionError, OSError) as exc:
        return {
            "status": "FAIL",
            "detail": f"Cannot write to DATA_DIR: {exc}",
            "remediation": (
                f"Grant the application process write access to {data_dir}. "
                "Check directory ownership and permissions."
            ),
        }


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------

def run_all_checks(data_dir: str, db_path: str, tuner_db_path: str) -> Dict[str, Any]:
    """Run all health checks and return a structured result dict.

    Parameters
    ----------
    data_dir:     Resolved DATA_DIR path.
    db_path:      Path to users.db.
    tuner_db_path: Path to tuners.db.
    """
    return {
        "db": check_db(db_path),
        "schema": check_schema(db_path),
        "tuners": check_tuners(tuner_db_path),
        "xmltv": check_xmltv(tuner_db_path),
        "disk_space": check_disk_space(data_dir),
        "write_permissions": check_write_permissions(data_dir),
    }
