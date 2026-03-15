"""Sanitized system / runtime information for the Diagnostics subsystem.

Rules
-----
* No secrets are ever exposed.
* Environment variables are filtered through an allowlist.
* Only safe, non-sensitive fields are included.
"""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime
from typing import Any, Dict, List

# Environment variable keys that are safe to display
_SAFE_ENV_KEYS: List[str] = [
    "RETROIPTV_DATA_DIR",
    "RETROIPTV_PORT",
    "RETROIPTV_DEBUG",
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "HOSTNAME",
    "TZ",
    "LANG",
    "LC_ALL",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "DOCKER_RUNNING",  # custom flag set in Dockerfile
]


def _detect_install_mode() -> str:
    """Heuristic: docker / systemd / windows-service / manual."""
    # Docker: /.dockerenv file present or DOCKER_RUNNING env var
    if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_RUNNING"):
        return "docker"
    # Windows service: no terminal attached, running as Windows service
    if sys.platform == "win32":
        try:
            import ctypes  # type: ignore[import]  # noqa: PLC0415
            return "windows-service" if ctypes.windll.kernel32.GetConsoleWindow() == 0 else "windows-manual"
        except Exception:
            return "windows"
    # systemd: INVOCATION_ID is set when run as a systemd unit
    if os.environ.get("INVOCATION_ID"):
        return "systemd"
    return "bare-metal"


def get_system_info(
    app_version: str,
    app_start_time: datetime,
    data_dir: str,
    release_date: str = "",
    install_path: str = "",
    db_path: str = "",
    log_path: str = "",
) -> Dict[str, Any]:
    """Return a sanitised snapshot of system and runtime information.

    Parameters
    ----------
    app_version:
        Application version string (e.g. ``"v4.8.0"``).
    app_start_time:
        ``datetime`` when the application process started.
    data_dir:
        Resolved DATA_DIR path.
    release_date:
        Human-readable release date string (e.g. ``"2026-03-05"``).
    install_path:
        Working directory / install root (``os.getcwd()``).
    db_path:
        Path to the main SQLite database file.
    log_path:
        Directory where application logs are written.
    """
    uptime_delta = datetime.now() - app_start_time
    days = uptime_delta.days
    hours, rem = divmod(uptime_delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

    # Safe subset of environment variables
    safe_env: Dict[str, str] = {}
    for key in _SAFE_ENV_KEYS:
        value = os.environ.get(key)
        if value is not None:
            safe_env[key] = value

    return {
        "app_version": app_version,
        "release_date": release_date,
        "python_version": sys.version.split()[0],
        "python_full": sys.version,
        "os_info": platform.platform(),
        "os_name": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "uptime": uptime_str,
        "install_path": install_path,
        "data_dir": data_dir,
        "db_path": db_path,
        "log_path": log_path,
        "install_mode": _detect_install_mode(),
        "safe_env": safe_env,
    }
