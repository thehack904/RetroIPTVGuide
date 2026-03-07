"""Startup diagnostics for RetroIPTVGuide.

Records events from the very first lines of ``app.py`` startup — before Flask
is running and before any admin login is possible.  This gives a way to
diagnose why the app is crashing or refusing to start.

Usage (called once, early in app.py):
    from utils.startup_diag import record_startup_event, finalise_startup
    record_startup_event("info", "Python version", sys.version)
    ...
    finalise_startup(success=True)

Public read API (called from blueprint / startup-status endpoint):
    from utils.startup_diag import get_startup_events, get_startup_summary
"""

from __future__ import annotations

import os
import platform
import sys
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# In-memory ring buffer — survives even if the log file is unwritable
# ---------------------------------------------------------------------------

_LOCK = threading.Lock()

_events: List[Dict[str, Any]] = []
_MAX_EVENTS = 500
_startup_success: Optional[bool] = None
_startup_finished_at: Optional[str] = None
_startup_log_path: Optional[str] = None   # set when configure_startup_log() is called


# ---------------------------------------------------------------------------
# Public recording API
# ---------------------------------------------------------------------------

def record_startup_event(level: str, category: str, detail: str) -> None:
    """Record a single startup event.

    Parameters
    ----------
    level:    "info" | "warn" | "error" | "critical"
    category: Short label, e.g. "python", "db_init", "import_error"
    detail:   Human-readable description (may contain newlines for tracebacks)
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry: Dict[str, Any] = {
        "ts": ts,
        "level": level.lower(),
        "category": category,
        "detail": str(detail),
    }
    with _LOCK:
        _events.append(entry)
        if len(_events) > _MAX_EVENTS:
            _events.pop(0)

    # Mirror to startup.log if configured
    _write_to_log(entry)


def configure_startup_log(data_dir: str) -> None:
    """Set the path for the startup.log file under *data_dir*/logs/."""
    global _startup_log_path
    log_dir = os.path.join(data_dir, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        pass
    _startup_log_path = os.path.join(log_dir, "startup.log")


def finalise_startup(success: bool = True) -> None:
    """Mark startup as complete.  Call after Flask app.run() is ready."""
    global _startup_success, _startup_finished_at
    with _LOCK:
        _startup_success = success
        _startup_finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    level = "info" if success else "critical"
    record_startup_event(level, "startup_complete",
                         "App started successfully." if success
                         else "Startup FAILED — check earlier errors.")


# ---------------------------------------------------------------------------
# Public read API
# ---------------------------------------------------------------------------

def get_startup_events() -> List[Dict[str, Any]]:
    """Return a copy of all recorded startup events."""
    with _LOCK:
        return list(_events)


def get_startup_summary() -> Dict[str, Any]:
    """Return a summary dict suitable for JSON serialisation."""
    with _LOCK:
        events_copy = list(_events)
        success = _startup_success
        finished_at = _startup_finished_at

    errors = [e for e in events_copy if e["level"] in ("error", "critical")]
    warnings = [e for e in events_copy if e["level"] == "warn"]

    status: str
    if success is None:
        status = "in_progress"
    elif success:
        status = "ok" if not errors else "ok_with_errors"
    else:
        status = "failed"

    return {
        "status": status,
        "finished_at": finished_at,
        "event_count": len(events_copy),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "events": events_copy,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Convenience: capture the standard startup environment automatically
# ---------------------------------------------------------------------------

def record_environment() -> None:
    """Record Python version, OS, and key environment variables (safe subset)."""
    record_startup_event("info", "python",
                         f"Python {sys.version} on {platform.system()} {platform.release()}")
    record_startup_event("info", "executable", sys.executable)
    record_startup_event("info", "cwd", os.getcwd())
    record_startup_event("info", "platform", platform.platform())

    # Safe env vars only — no secrets
    _SAFE_ENV_KEYS = {
        "RETROIPTV_DATA_DIR", "FLASK_ENV", "FLASK_DEBUG", "FLASK_PORT",
        "PROGRAMDATA", "HOME", "USER", "USERNAME", "PATH",
        "DOCKER_CONTAINER", "HOSTNAME",
    }
    for key in sorted(_SAFE_ENV_KEYS):
        val = os.environ.get(key)
        if val is not None:
            record_startup_event("info", f"env.{key}", val)


def record_import_error(module_name: str, exc: Exception) -> None:
    """Record a failed module import with the exception message."""
    import traceback
    tb = traceback.format_exc()
    record_startup_event(
        "error",
        "import_error",
        f"Failed to import '{module_name}': {type(exc).__name__}: {exc}\n{tb}",
    )


def record_db_init(db_name: str, path: str, success: bool,
                   error: Optional[str] = None) -> None:
    """Record a DB initialisation result."""
    if success:
        record_startup_event("info", "db_init", f"{db_name}: OK ({path})")
    else:
        record_startup_event("error", "db_init",
                             f"{db_name}: FAILED ({path}): {error}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_to_log(entry: Dict[str, Any]) -> None:
    """Append a single event line to startup.log (best-effort, never raises)."""
    if not _startup_log_path:
        return
    try:
        line = f"{entry['ts']}  {entry['level'].upper():<8}  [{entry['category']}]  {entry['detail'][:512]}\n"
        with open(_startup_log_path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:  # noqa: BLE001
        pass
