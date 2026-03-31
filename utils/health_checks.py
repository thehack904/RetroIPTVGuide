"""Health-check utilities for the Diagnostics subsystem.

Each check returns a dict with:
  ``status``      – "PASS" | "WARN" | "FAIL"
  ``detail``      – human-readable description (no secrets)
  ``remediation`` – suggested fix (empty string when PASS/WARN is fine)

Additional deep-checks (check_tuner_connectivity, check_file_system,
check_cache_state) return richer structured data for per-tuner
troubleshooting (see bug #203, #70).
"""

from __future__ import annotations

import logging
import os
import shutil
import socket
import sqlite3
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Basic checks
# ---------------------------------------------------------------------------

def check_db(db_path: str) -> Dict[str, Any]:
    """Verify that the main users database is reachable and readable."""
    abs_path = os.path.abspath(db_path)
    exists = os.path.exists(abs_path)
    size_bytes = os.path.getsize(abs_path) if exists else 0
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            conn.execute("SELECT 1")
        return {
            "status": "PASS",
            "detail": f"Connection OK. Path: {abs_path}  Size: {size_bytes} bytes.",
            "path": abs_path,
            "size_bytes": size_bytes,
            "exists": exists,
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Database connection failed for %s: %s", abs_path, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": f"Connection failed. Check application logs for details. Path: {abs_path}",
            "path": abs_path,
            "size_bytes": size_bytes,
            "exists": exists,
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
                "detail": f"Missing tables: {', '.join(sorted(missing))}. Found: {', '.join(sorted(found)) or 'none'}",
                "tables_found": sorted(found),
                "tables_missing": sorted(missing),
                "remediation": (
                    "Restart the application to trigger automatic schema initialisation."
                ),
            }
        return {
            "status": "PASS",
            "detail": f"All required tables present. Tables: {', '.join(sorted(found))}",
            "tables_found": sorted(found),
            "tables_missing": [],
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Schema check failed for %s: %s", db_path, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "Schema check failed. Check application logs for details.",
            "tables_found": [],
            "tables_missing": sorted(required),
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
                "count": 0,
                "remediation": "Add at least one tuner in Settings → Tuner Management.",
            }
        return {
            "status": "PASS",
            "detail": f"{count} tuner(s) configured.",
            "count": count,
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Tuner database error for %s: %s", tuner_db_path, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "Tuner database error. Check application logs for details.",
            "count": 0,
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
                "detail": f"Tuner(s) missing XMLTV URL: {', '.join(missing)}",
                "remediation": "Set an XMLTV URL in Settings → Tuner Management.",
            }
        return {
            "status": "PASS",
            "detail": "All tuners have XMLTV URLs configured.",
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("XMLTV check failed for %s: %s", tuner_db_path, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "XMLTV check failed. Check application logs for details.",
            "remediation": "Check tuner database integrity.",
        }


def check_disk_space(data_dir: str, warn_threshold_mb: int = 500) -> Dict[str, Any]:
    """Check that DATA_DIR has sufficient free disk space."""
    try:
        usage = shutil.disk_usage(data_dir)
        free_mb = usage.free // (1024 * 1024)
        total_mb = usage.total // (1024 * 1024)
        used_mb = (usage.used) // (1024 * 1024)
        if free_mb < 50:
            return {
                "status": "FAIL",
                "detail": f"Critical: only {free_mb} MB free of {total_mb} MB total ({used_mb} MB used).",
                "free_mb": free_mb,
                "total_mb": total_mb,
                "remediation": "Free disk space immediately. Rotate or delete old log files.",
            }
        if free_mb < warn_threshold_mb:
            return {
                "status": "WARN",
                "detail": f"Low: {free_mb} MB free of {total_mb} MB total ({used_mb} MB used).",
                "free_mb": free_mb,
                "total_mb": total_mb,
                "remediation": f"Consider freeing disk space. Warning threshold is {warn_threshold_mb} MB.",
            }
        return {
            "status": "PASS",
            "detail": f"{free_mb} MB free of {total_mb} MB total ({used_mb} MB used).",
            "free_mb": free_mb,
            "total_mb": total_mb,
            "remediation": "",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not check disk space for %s: %s", data_dir, exc, exc_info=True)
        return {
            "status": "WARN",
            "detail": "Could not check disk space. Check application logs for details.",
            "free_mb": None,
            "total_mb": None,
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
        logger.error("Cannot write to DATA_DIR %s: %s", data_dir, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "Cannot write to data directory. Check application logs for details.",
            "remediation": (
                f"Grant the application process write access to {data_dir}. "
                "Check directory ownership and permissions."
            ),
        }


# ---------------------------------------------------------------------------
# Deep diagnostics (for real-world troubleshooting, e.g. bug #203, #70)
# ---------------------------------------------------------------------------

def _probe_url(url: str, timeout: int = 8) -> Dict[str, Any]:
    """Perform a HEAD (fallback GET) request and return rich result dict.

    Returns a dict with keys:
      reachable, status_code, error, content_type, response_time_ms,
      resolved_ip, hostname
    """
    import requests as _requests  # noqa: PLC0415 – keep import local

    result: Dict[str, Any] = {
        "url": url,
        "reachable": False,
        "status_code": None,
        "error": None,
        "content_type": None,
        "response_time_ms": None,
        "resolved_ip": None,
        "hostname": None,
    }

    if not url:
        result["error"] = "URL is empty."
        return result

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        result["hostname"] = hostname

        # DNS resolution (before HTTP, so we get a clear error if DNS fails)
        if hostname:
            try:
                resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
                result["resolved_ip"] = resolved[0][4][0] if resolved else None
            except socket.gaierror as dns_err:
                logger.debug("DNS resolution failed for %s: %s", hostname, dns_err)
                result["error"] = f"DNS resolution failed for '{hostname}'"
                return result

        t0 = time.monotonic()
        try:
            resp = _requests.head(url, timeout=timeout, allow_redirects=True)
            elapsed = int((time.monotonic() - t0) * 1000)
            result["status_code"] = resp.status_code
            result["response_time_ms"] = elapsed
            result["content_type"] = resp.headers.get("Content-Type", "")
            if resp.status_code < 400:
                result["reachable"] = True
            else:
                result["error"] = f"HTTP {resp.status_code}"
        except _requests.exceptions.Timeout:
            elapsed = int((time.monotonic() - t0) * 1000)
            result["response_time_ms"] = elapsed
            result["error"] = f"Connection timed out after {timeout}s (server at {result.get('resolved_ip') or hostname or 'unknown'} did not respond)"
        except _requests.exceptions.ConnectionError as conn_err:
            logger.debug("Connection error probing %s: %s", url, conn_err)
            result["error"] = "Connection error. Check application logs for details."
        except Exception as exc:  # noqa: BLE001
            logger.debug("Unexpected error probing %s: %s", url, exc, exc_info=True)
            result["error"] = "Unexpected probe error. Check application logs for details."

    except Exception as exc:  # noqa: BLE001
        logger.debug("URL probe failed for %s: %s", url, exc, exc_info=True)
        result["error"] = "URL probe failed. Check application logs for details."

    return result


def check_tuner_connectivity(tuner_db_path: str) -> List[Dict[str, Any]]:
    """Deep per-tuner connectivity check.

    For each configured tuner, probes M3U and XML/XMLTV URLs and returns:
    - URL probe result (status code, error, DNS, response time)
    - Whether the URL scheme looks like M3U vs XMLTV
    - Channel count from DB cache (if available via app module)

    Returns a list of per-tuner result dicts.
    """
    tuners_result: List[Dict[str, Any]] = []
    try:
        with sqlite3.connect(tuner_db_path, timeout=5) as conn:
            try:
                cur = conn.execute(
                    "SELECT name, xml, m3u, tuner_type, sources FROM tuners"
                )
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                cur = conn.execute("SELECT name, xml, m3u FROM tuners")
                rows = [(r[0], r[1], r[2], "standard", None) for r in cur.fetchall()]

            # Get active tuner
            try:
                cur2 = conn.execute("SELECT value FROM settings WHERE key='current_tuner'")
                active_row = cur2.fetchone()
                active_tuner = active_row[0] if active_row else None
            except Exception:
                active_tuner = None

            # Get last auto-refresh status per tuner
            last_refresh: Dict[str, str] = {}
            try:
                cur3 = conn.execute(
                    "SELECT key, value FROM settings WHERE key LIKE 'last_auto_refresh:%'"
                )
                for key, value in cur3.fetchall():
                    tname = key.split(":", 1)[1]
                    last_refresh[tname] = value
            except Exception:
                pass

    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot read tuner database %s: %s", tuner_db_path, exc, exc_info=True)
        return [{"error": "Cannot read tuner database. Check application logs for details."}]

    for name, xml_url, m3u_url, tuner_type, sources_json in rows:
        entry: Dict[str, Any] = {
            "name": name,
            "tuner_type": tuner_type or "standard",
            "is_active": (name == active_tuner),
            "m3u_url": m3u_url or "",
            "xml_url": xml_url or "",
            "m3u_probe": None,
            "xml_probe": None,
            "sources": [],
            "last_refresh": last_refresh.get(name, "never"),
            "overall_status": "PASS",
        }

        if tuner_type == "combined":
            # Combined tuners have no direct URLs; list their source names
            if sources_json:
                try:
                    import json as _json  # noqa: PLC0415
                    entry["sources"] = _json.loads(sources_json)
                except Exception:
                    pass
            entry["overall_status"] = "INFO"
        else:
            # Probe M3U URL
            if m3u_url:
                entry["m3u_probe"] = _probe_url(m3u_url)
                if not entry["m3u_probe"]["reachable"]:
                    entry["overall_status"] = "FAIL"
            else:
                entry["m3u_probe"] = {"error": "No M3U URL configured.", "reachable": False}
                entry["overall_status"] = "WARN"

            # Probe XML/XMLTV URL (only if different from M3U URL)
            if xml_url and xml_url != m3u_url:
                entry["xml_probe"] = _probe_url(xml_url)
                if not entry["xml_probe"]["reachable"] and entry["overall_status"] == "PASS":
                    entry["overall_status"] = "WARN"
            elif xml_url == m3u_url and xml_url:
                entry["xml_probe"] = {"reachable": entry["m3u_probe"]["reachable"],
                                       "note": "Same URL as M3U."}
            else:
                entry["xml_probe"] = {"error": "No XMLTV URL configured.", "reachable": False}

        tuners_result.append(entry)

    return tuners_result


def check_file_system(db_path: str, tuner_db_path: str, data_dir: str) -> Dict[str, Any]:
    """Return file-system details critical for Docker/path troubleshooting (bug #70).

    Reports:
    - Absolute paths and existence for each key file
    - File sizes
    - Symlink targets (critical for Docker volume setups)
    - Owner/permissions (octal)
    - DATA_DIR subdirectory listing
    """

    def _file_info(path: str) -> Dict[str, Any]:
        abs_p = os.path.abspath(path)
        info: Dict[str, Any] = {
            "path": abs_p,
            "exists": os.path.exists(abs_p),
            "is_symlink": os.path.islink(abs_p),
            "symlink_target": None,
            "size_bytes": None,
            "permissions": None,
        }
        if info["is_symlink"]:
            try:
                info["symlink_target"] = os.path.realpath(abs_p)
            except Exception:
                pass
        if info["exists"]:
            try:
                st = os.stat(abs_p)
                info["size_bytes"] = st.st_size
                info["permissions"] = oct(st.st_mode)
            except Exception:
                pass
        return info

    def _dir_listing(path: str, max_entries: int = 30) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        try:
            for name in sorted(os.listdir(path))[:max_entries]:
                full = os.path.join(path, name)
                is_link = os.path.islink(full)
                try:
                    size = os.path.getsize(full) if os.path.isfile(full) else None
                except Exception:
                    size = None
                entries.append({
                    "name": name,
                    "is_symlink": is_link,
                    "symlink_target": os.path.realpath(full) if is_link else None,
                    "size_bytes": size,
                    "is_dir": os.path.isdir(full),
                })
        except Exception as exc:
            logger.debug("Directory listing failed for %s: %s", path, exc)
            entries.append({"error": "Directory listing failed. Check application logs for details."})
        return entries

    return {
        "users_db": _file_info(db_path),
        "tuners_db": _file_info(tuner_db_path),
        "data_dir": {
            "path": os.path.abspath(data_dir),
            "exists": os.path.isdir(data_dir),
            "listing": _dir_listing(data_dir),
        },
        "logs_dir": {
            "path": os.path.abspath(os.path.join(data_dir, "logs")),
            "exists": os.path.isdir(os.path.join(data_dir, "logs")),
            "listing": _dir_listing(os.path.join(data_dir, "logs")),
        },
        "app_working_dir": {
            "path": os.path.abspath(os.getcwd()),
            "listing": _dir_listing(os.getcwd(), max_entries=40),
        },
    }


def check_cache_state(tuner_db_path: str) -> Dict[str, Any]:
    """Return runtime cache / EPG state useful for stream-play troubleshooting (bug #203).

    Reads the live in-memory globals from the app module so the data is
    always current (not a stale DB snapshot).
    """
    try:
        import app as app_module  # noqa: PLC0415

        channels = getattr(app_module, "cached_channels", [])
        epg = getattr(app_module, "cached_epg", {})
        active_tuner = getattr(app_module, "get_current_tuner", lambda: None)()
        currently_playing = getattr(app_module, "CURRENTLY_PLAYING", None)

        # Sample of first 5 channels (name + stream URL, no secrets)
        sample_channels = [
            {
                "name": ch.get("name", ""),
                "tvg_id": ch.get("tvg_id", ""),
                "url": ch.get("url", ""),
                "logo": ch.get("logo", ""),
            }
            for ch in channels[:5]
        ]

        # Auto-refresh status
        refresh_enabled = False
        refresh_interval = None
        last_refresh_info: Dict[str, str] = {}
        try:
            with sqlite3.connect(tuner_db_path, timeout=5) as conn:
                cur = conn.execute(
                    "SELECT key, value FROM settings WHERE key IN ('auto_refresh_enabled', 'auto_refresh_interval_hours') "
                    "OR key LIKE 'last_auto_refresh:%'"
                )
                for key, value in cur.fetchall():
                    if key == "auto_refresh_enabled":
                        refresh_enabled = value in ("1", "true", "True")
                    elif key == "auto_refresh_interval_hours":
                        refresh_interval = value
                    elif key.startswith("last_auto_refresh:"):
                        tname = key.split(":", 1)[1]
                        last_refresh_info[tname] = value
        except Exception:
            pass

        epg_channel_count = len(epg)
        epg_entry_count = sum(len(v) for v in epg.values())

        # All configured tuner names (for UI selects)
        all_tuners: List[str] = []
        try:
            with sqlite3.connect(tuner_db_path, timeout=5) as conn:
                cur = conn.execute("SELECT name FROM tuners ORDER BY name")
                all_tuners = [row[0] for row in cur.fetchall()]
        except Exception:
            pass

        return {
            "active_tuner": active_tuner,
            "channel_count": len(channels),
            "epg_channel_count": epg_channel_count,
            "epg_entry_count": epg_entry_count,
            "currently_playing": currently_playing,
            "sample_channels": sample_channels,
            "auto_refresh_enabled": refresh_enabled,
            "auto_refresh_interval_hours": refresh_interval,
            "last_refresh_per_tuner": last_refresh_info,
            "all_tuners": all_tuners,
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("Could not read cache state: %s", exc, exc_info=True)
        return {
            "error": "Could not read cache state. Check application logs for details.",
            "active_tuner": None,
            "channel_count": 0,
            "epg_channel_count": 0,
            "epg_entry_count": 0,
            "currently_playing": None,
            "sample_channels": [],
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
        "file_system": check_file_system(db_path, tuner_db_path, data_dir),
        "cache_state": check_cache_state(tuner_db_path),
    }
