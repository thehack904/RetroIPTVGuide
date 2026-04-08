"""Application-level configuration diagnostics for the RetroIPTVGuide Admin UI.

Five check functions that expose the information most useful for diagnosing
real-world user issues:

check_user_accounts()      – user list with last-logins and assigned tuners
check_virtual_channels()   – per-channel enabled state + configuration gaps
check_external_services()  – live reachability probes for weather API and news feeds
check_system_resources()   – load, memory, open files, installed Python packages
run_config_checks()        – aggregate runner (includes dependency + security checks)
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
import time
import socket
from typing import Any, Dict, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User Accounts
# ---------------------------------------------------------------------------

def check_user_accounts(db_path: str) -> Dict[str, Any]:
    """Return non-sensitive user account summary.

    Reports:
    - Total user count
    - Per-user: username, last_login timestamp, assigned_tuner
    - Any account with no last_login (never logged in)
    - Any account with an assigned tuner that no longer exists in tuners.db
    """
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            cur = conn.execute(
                "SELECT username, last_login, assigned_tuner FROM users ORDER BY username"
            )
            rows = cur.fetchall()

        users = []
        never_logged_in = []
        for username, last_login, assigned_tuner in rows:
            users.append({
                "username": username,
                "last_login": last_login or "never",
                "assigned_tuner": assigned_tuner or "none (uses active tuner)",
            })
            if not last_login:
                never_logged_in.append(username)

        return {
            "status": "PASS" if users else "WARN",
            "detail": f"{len(users)} user account(s) found.",
            "users": users,
            "never_logged_in": never_logged_in,
            "remediation": "" if users else "No user accounts exist. Run the application to initialise the default admin account.",
        }
    except sqlite3.OperationalError as exc:
        logger.error("Could not read users table in %s: %s", db_path, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "Could not read users table. Check application logs for details.",
            "users": [],
            "never_logged_in": [],
            "remediation": "Check that the users database has been initialised.",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("User account check failed for %s: %s", db_path, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "User account check failed. Check application logs for details.",
            "users": [],
            "never_logged_in": [],
            "remediation": "Check database integrity.",
        }


# ---------------------------------------------------------------------------
# Virtual Channel Configuration
# ---------------------------------------------------------------------------

def check_virtual_channels(tuner_db_path: str) -> Dict[str, Any]:
    """Return per-virtual-channel enabled state and configuration completeness.

    Checks:
    - Which virtual channels are enabled / disabled
    - Whether the weather channel has lat/lon/location configured
    - Whether the news channel has at least one RSS feed URL configured
    - Whether the traffic channel has demo mode or a configured city
    - Sports channel mode and RSS feed configuration (if in RSS mode)
    - NASA channel interval, image count, and API key status
    - Channel Mix name and configured sub-channels
    - On This Day enabled sources count
    - Updates channel show_beta setting
    """
    # Read all relevant settings in one pass
    settings: Dict[str, str] = {}
    try:
        with sqlite3.connect(tuner_db_path, timeout=5) as conn:
            cur = conn.execute("SELECT key, value FROM settings")
            for key, value in cur.fetchall():
                settings[key] = value
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot read virtual channel settings from %s: %s", tuner_db_path, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "Cannot read virtual channel settings. Check application logs for details.",
            "channels": [],
            "remediation": "Check tuners.db integrity.",
        }

    VIRTUAL_IDS = [
        ("virtual.news",        "News Now"),
        ("virtual.weather",     "Weather Now"),
        ("virtual.status",      "System Status"),
        ("virtual.traffic",     "Traffic Now"),
        ("virtual.updates",     "Updates & Announcements"),
        ("virtual.sports",      "Sports Now"),
        ("virtual.nasa",        "NASA Imagery"),
        ("virtual.channel_mix", "Channel Mix"),
        ("virtual.on_this_day", "On This Day"),
    ]

    channels = []
    warnings = []

    for tvg_id, name in VIRTUAL_IDS:
        enabled_val = settings.get(f"virtual_channel.{tvg_id}.enabled", "1")
        enabled = (enabled_val == "1")

        entry: Dict[str, Any] = {
            "tvg_id": tvg_id,
            "name": name,
            "enabled": enabled,
            "config_ok": True,
            "config_issues": [],
        }

        # Per-channel configuration checks
        if tvg_id == "virtual.weather":
            lat = settings.get("weather.lat", "").strip()
            lon = settings.get("weather.lon", "").strip()
            location = settings.get("weather.location_name", "").strip()
            units = settings.get("weather.units", "F").strip()
            entry["weather_config"] = {
                "lat": lat or "(not set)",
                "lon": lon or "(not set)",
                "location_name": location or "(not set)",
                "units": units or "F",
            }
            if not lat or not lon:
                entry["config_ok"] = False
                entry["config_issues"].append("Latitude and/or longitude not configured — weather data will not load.")
                if enabled:
                    warnings.append(f"{name}: missing lat/lon configuration")
            if not location:
                entry["config_issues"].append("Location name not set — will display as 'Local Weather'.")

        elif tvg_id == "virtual.news":
            feed_urls = []
            for i in range(1, 7):
                val = settings.get(f"news.rss_url_{i}", "").strip()
                if val:
                    feed_urls.append(val)
            # Legacy key fallback
            if not feed_urls:
                legacy = settings.get("news.rss_url", "").strip()
                if legacy:
                    feed_urls.append(legacy)
            entry["news_config"] = {"feed_urls": feed_urls}
            if not feed_urls:
                entry["config_ok"] = False
                entry["config_issues"].append("No RSS/Atom feed URLs configured — news channel will show no headlines.")
                if enabled:
                    warnings.append(f"{name}: no RSS feed URLs configured")
            else:
                entry["config_issues"].append(f"{len(feed_urls)} RSS feed(s) configured.")

        elif tvg_id == "virtual.traffic":
            demo_mode = settings.get("traffic_demo.mode", "demo").strip()
            entry["traffic_config"] = {"mode": demo_mode}

        elif tvg_id == "virtual.updates":
            show_beta = settings.get("updates.show_beta", "1") == "1"
            entry["updates_config"] = {"show_beta": show_beta}

        elif tvg_id == "virtual.sports":
            mode = settings.get("sports.mode", "scores").strip() or "scores"
            feed_urls = []
            for i in range(1, 7):
                val = settings.get(f"sports.rss_url_{i}", "").strip()
                if val:
                    feed_urls.append(val)
            entry["sports_config"] = {"mode": mode, "rss_feed_count": len(feed_urls)}
            if mode == "rss" and not feed_urls:
                entry["config_ok"] = False
                entry["config_issues"].append("Sports channel is in RSS mode but no RSS feed URLs are configured.")
                if enabled:
                    warnings.append(f"{name}: RSS mode selected but no feed URLs configured")
            elif mode == "rss":
                entry["config_issues"].append(f"RSS mode: {len(feed_urls)} feed(s) configured.")
            else:
                entry["config_issues"].append("Scores mode: uses ESPN live scoreboard API.")

        elif tvg_id == "virtual.nasa":
            interval = settings.get("nasa.interval", "15").strip() or "15"
            if interval not in ("15", "30"):
                interval = "15"
            raw_count = settings.get("nasa.image_count", "").strip()
            try:
                image_count = int(raw_count) if raw_count else None
            except (ValueError, TypeError):
                image_count = None
            if image_count is None:
                image_count = 5 if interval == "15" else 10
            api_key_raw = settings.get("nasa.api_key", "").strip()
            using_demo_key = not api_key_raw
            entry["nasa_config"] = {
                "interval_minutes": interval,
                "image_count": image_count,
                "using_demo_key": using_demo_key,
            }
            if using_demo_key:
                entry["config_issues"].append("Using DEMO_KEY — rate-limited to 30 requests/hour. Add a NASA API key for higher limits.")

        elif tvg_id == "virtual.channel_mix":
            import json as _json  # noqa: PLC0415
            mix_name = settings.get("channel_mix.name", "").strip() or "Channel Mix"
            raw_channels = settings.get("channel_mix.channels", "").strip()
            mix_channel_count = 0
            if raw_channels:
                try:
                    parsed = _json.loads(raw_channels)
                    mix_channel_count = len([c for c in parsed if isinstance(c, dict) and c.get("tvg_id")])
                except Exception:  # noqa: BLE001
                    pass
            entry["channel_mix_config"] = {
                "name": mix_name,
                "channel_count": mix_channel_count,
            }
            if mix_channel_count == 0:
                entry["config_issues"].append("No sub-channels configured — mix will show a placeholder.")

        elif tvg_id == "virtual.on_this_day":
            ON_THIS_DAY_SOURCE_IDS = [
                "wikipedia_events",
                "wikipedia_births",
                "wikipedia_deaths",
            ]
            enabled_sources = []
            for sid in ON_THIS_DAY_SOURCE_IDS:
                val = settings.get(f"on_this_day.source.{sid}.enabled", "1")
                if val == "1":
                    enabled_sources.append(sid)
            entry["on_this_day_config"] = {
                "enabled_source_count": len(enabled_sources),
                "total_source_count": len(ON_THIS_DAY_SOURCE_IDS),
            }
            if not enabled_sources:
                entry["config_ok"] = False
                entry["config_issues"].append("No Wikipedia sources enabled — channel will only show custom entries.")
                if enabled:
                    warnings.append(f"{name}: no Wikipedia sources enabled")
            else:
                entry["config_issues"].append(f"{len(enabled_sources)}/{len(ON_THIS_DAY_SOURCE_IDS)} Wikipedia source(s) enabled.")

        channels.append(entry)

    status = "WARN" if warnings else "PASS"
    detail = (
        f"{sum(1 for c in channels if c['enabled'])}/{len(channels)} virtual channel(s) enabled."
        + (f" Issues: {'; '.join(warnings)}" if warnings else "")
    )

    return {
        "status": status,
        "detail": detail,
        "channels": channels,
        "remediation": "Configure the flagged channels under Admin → Virtual Channels." if warnings else "",
    }


# ---------------------------------------------------------------------------
# External Services
# ---------------------------------------------------------------------------

def check_external_services(tuner_db_path: str) -> Dict[str, Any]:
    """Probe external service URLs configured in the application.

    Tests:
    - Open-Meteo weather API (if lat/lon configured)
    - Each configured news RSS feed
    - Overpass API status (if the traffic virtual channel is enabled)
    - ESPN Scoreboard API (if sports channel is enabled in scores mode)
    - Sports RSS feeds (if sports channel is enabled in RSS mode)
    - NASA APOD API (if NASA channel is enabled)
    - Wikipedia On This Day API (if On This Day channel is enabled)

    The Overpass API probe has two layers:
    1. A live connectivity check against ``/api/status`` (lightweight, no
       query payload) to detect DNS failures, 5xx errors, and gateway timeouts.
    2. A runtime-error check against ``app._OVERPASS_LAST_ERROR``, which is
       populated by ``_fetch_overpass_roads`` whenever an HTTP error (including
       429 Too Many Requests and 504 Gateway Timeout) occurs on the actual
       ``/api/interpreter`` endpoint.  ``/api/status`` may return 200 OK even
       while ``/api/interpreter`` is rate-limiting, so this second layer is
       needed to surface 429 errors in the health panel.

    Returns per-service results with HTTP status, response time, error messages.
    """
    import requests as _req  # noqa: PLC0415

    # Read settings
    settings: Dict[str, str] = {}
    try:
        with sqlite3.connect(tuner_db_path, timeout=5) as conn:
            cur = conn.execute("SELECT key, value FROM settings")
            for key, value in cur.fetchall():
                settings[key] = value
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot read settings from %s: %s", tuner_db_path, exc, exc_info=True)
        return {
            "status": "FAIL",
            "detail": "Cannot read settings. Check application logs for details.",
            "services": [],
            "remediation": "Check tuners.db integrity.",
        }

    services: List[Dict[str, Any]] = []

    # --- Weather API ---
    lat = settings.get("weather.lat", "").strip()
    lon = settings.get("weather.lon", "").strip()
    if lat and lon:
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current=temperature_2m&forecast_days=1"
        )
        svc = _probe_service("weather_api", "Open-Meteo Weather API", weather_url)
        services.append(svc)
    else:
        services.append({
            "id": "weather_api",
            "name": "Open-Meteo Weather API",
            "url": "(not configured — no lat/lon set)",
            "reachable": None,
            "status_code": None,
            "response_time_ms": None,
            "error": None,
            "note": "Configure Weather channel lat/lon to enable this check.",
        })

    # --- News RSS feeds ---
    feed_urls: List[str] = []
    for i in range(1, 7):
        val = settings.get(f"news.rss_url_{i}", "").strip()
        if val:
            feed_urls.append(val)
    if not feed_urls:
        legacy = settings.get("news.rss_url", "").strip()
        if legacy:
            feed_urls.append(legacy)

    if feed_urls:
        for idx, url in enumerate(feed_urls, start=1):
            svc = _probe_service(f"news_feed_{idx}", f"News RSS Feed {idx}", url)
            services.append(svc)
    else:
        services.append({
            "id": "news_feed",
            "name": "News RSS Feed",
            "url": "(not configured)",
            "reachable": None,
            "status_code": None,
            "response_time_ms": None,
            "error": None,
            "note": "Configure a news RSS feed URL to enable this check.",
        })

    # --- Overpass API (used by the Traffic virtual channel road overlay) ---
    # Only probe when the traffic channel is enabled; the check uses the
    # /api/status endpoint (plain-text, no query payload) so it is cheap and
    # does not consume Overpass fair-use quota.
    traffic_enabled = settings.get("virtual_channel.virtual.traffic.enabled", "1") == "1"
    if traffic_enabled:
        svc = _probe_service(
            "overpass_api",
            "Overpass API (traffic road overlay)",
            "https://overpass-api.de/api/status",
            timeout=10,
        )
        svc["note"] = (
            "Used by the Traffic virtual channel to fetch road geometry. "
            "A failure here explains empty or missing road overlays."
        )

        # Layer 2: check for runtime errors recorded by _fetch_overpass_roads.
        # /api/status can return 200 OK while /api/interpreter is rate-limiting
        # (429 Too Many Requests), so we also surface any error that was
        # recorded since the last successful road-geometry fetch.
        try:
            import app as _app_module  # noqa: PLC0415
            last_err: dict = getattr(_app_module, "_OVERPASS_LAST_ERROR", {})
        except Exception:  # noqa: BLE001
            last_err = {}

        if last_err:
            status_code = last_err.get("status_code")
            message = last_err.get("message", "unknown error")
            lat_err = last_err.get("lat")
            lon_err = last_err.get("lon")
            # Override the probe result: the server may be reachable via
            # /api/status but the actual road-query endpoint is failing.
            svc["reachable"] = False
            svc["status_code"] = status_code
            svc["error"] = (
                f"Runtime error on /api/interpreter "
                f"(lat={lat_err}, lon={lon_err}): {message}"
            )
            if status_code == 429:
                svc["note"] = (
                    "Overpass API is rate-limiting road-geometry requests "
                    "(429 Too Many Requests). Reduce the number of enabled "
                    "traffic cities or increase the pre-warm stagger interval."
                )
            elif status_code == 504:
                svc["note"] = (
                    "Overpass API gateway timed out (504). The server is "
                    "temporarily overloaded; road overlays will be empty until "
                    "the next successful fetch."
                )

        services.append(svc)
    else:
        services.append({
            "id": "overpass_api",
            "name": "Overpass API (traffic road overlay)",
            "url": "https://overpass-api.de/api/status",
            "reachable": None,
            "status_code": None,
            "response_time_ms": None,
            "error": None,
            "note": "Traffic virtual channel is disabled — Overpass API not probed.",
        })

    # --- Sports channel external services ---
    sports_enabled = settings.get("virtual_channel.virtual.sports.enabled", "1") == "1"
    sports_mode = settings.get("sports.mode", "scores").strip() or "scores"
    if sports_enabled:
        if sports_mode == "scores":
            # Probe the ESPN Scoreboard API (a stable, public endpoint)
            svc = _probe_service(
                "espn_api",
                "ESPN Scoreboard API (sports scores)",
                "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
                timeout=10,
            )
            svc["note"] = (
                "Used by the Sports channel in Scores mode to fetch live game data. "
                "A failure here explains missing scores or empty sports overlays."
            )
            services.append(svc)
        else:
            # RSS mode — probe configured sports feed URLs
            sports_feed_urls: List[str] = []
            for i in range(1, 7):
                val = settings.get(f"sports.rss_url_{i}", "").strip()
                if val:
                    sports_feed_urls.append(val)
            if sports_feed_urls:
                for idx, url in enumerate(sports_feed_urls, start=1):
                    svc = _probe_service(f"sports_feed_{idx}", f"Sports RSS Feed {idx}", url)
                    services.append(svc)
            else:
                services.append({
                    "id": "sports_feed",
                    "name": "Sports RSS Feed",
                    "url": "(not configured)",
                    "reachable": None,
                    "status_code": None,
                    "response_time_ms": None,
                    "error": None,
                    "note": "Sports channel is in RSS mode but no feed URLs are configured.",
                })
    else:
        services.append({
            "id": "espn_api",
            "name": "ESPN Scoreboard API (sports scores)",
            "url": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
            "reachable": None,
            "status_code": None,
            "response_time_ms": None,
            "error": None,
            "note": "Sports virtual channel is disabled — ESPN API not probed.",
        })

    # --- NASA APOD API ---
    nasa_enabled = settings.get("virtual_channel.virtual.nasa.enabled", "1") == "1"
    if nasa_enabled:
        nasa_api_key = settings.get("nasa.api_key", "").strip() or "DEMO_KEY"
        nasa_probe_url = f"https://api.nasa.gov/planetary/apod?api_key={nasa_api_key}&count=1"
        svc = _probe_service("nasa_apod_api", "NASA APOD API", nasa_probe_url, timeout=10)
        # Sanitize displayed URL to avoid leaking the API key in diagnostic output
        svc["url"] = "https://api.nasa.gov/planetary/apod"
        svc["note"] = (
            "Used by the NASA Imagery channel to fetch Astronomy Picture of the Day images. "
            "A failure here explains empty or placeholder NASA imagery."
        )
        services.append(svc)
    else:
        services.append({
            "id": "nasa_apod_api",
            "name": "NASA APOD API",
            "url": "https://api.nasa.gov/planetary/apod",
            "reachable": None,
            "status_code": None,
            "response_time_ms": None,
            "error": None,
            "note": "NASA Imagery virtual channel is disabled — NASA APOD API not probed.",
        })

    # --- Wikipedia On This Day API ---
    on_this_day_enabled = settings.get("virtual_channel.virtual.on_this_day.enabled", "1") == "1"
    if on_this_day_enabled:
        import datetime as _dt  # noqa: PLC0415
        _now = _dt.datetime.now(_dt.timezone.utc)
        wiki_url = (
            f"https://en.wikipedia.org/api/rest_v1/feed/onthisday"
            f"/events/{_now.month:02d}/{_now.day:02d}"
        )
        svc = _probe_service("wikipedia_on_this_day", "Wikipedia On This Day API", wiki_url, timeout=10)
        svc["note"] = (
            "Used by the On This Day channel to fetch historical events from Wikipedia. "
            "A failure here explains missing historical events in the overlay."
        )
        services.append(svc)
    else:
        services.append({
            "id": "wikipedia_on_this_day",
            "name": "Wikipedia On This Day API",
            "url": "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events",
            "reachable": None,
            "status_code": None,
            "response_time_ms": None,
            "error": None,
            "note": "On This Day virtual channel is disabled — Wikipedia API not probed.",
        })

    failing = [s["name"] for s in services if s.get("reachable") is False]
    unconfigured = [s["name"] for s in services if s.get("reachable") is None]
    status = "FAIL" if failing else ("WARN" if unconfigured else "PASS")
    detail = f"{len(services)} external service(s) checked."
    if failing:
        detail += f" Unreachable: {', '.join(failing)}."

    return {
        "status": status,
        "detail": detail,
        "services": services,
        "remediation": (
            "Check network connectivity from the server to the failing services."
            if failing else ""
        ),
    }


def _probe_service(svc_id: str, name: str, url: str, timeout: int = 8) -> Dict[str, Any]:
    """Probe a single external URL and return a result dict."""
    import requests as _req  # noqa: PLC0415

    result: Dict[str, Any] = {
        "id": svc_id,
        "name": name,
        "url": url,
        "reachable": False,
        "status_code": None,
        "response_time_ms": None,
        "error": None,
        "resolved_ip": None,
    }

    # Strip query string and fragment for logging to avoid exposing API keys or tokens
    # that may appear as query parameters (e.g. ?api_key=…).
    parsed = urlparse(url)
    _log_url = parsed._replace(query="", fragment="").geturl()
    hostname = parsed.hostname

    try:
        if hostname:
            try:
                result["resolved_ip"] = socket.getaddrinfo(hostname, None)[0][4][0]
            except socket.gaierror as dns_err:
                # hostname is the bare domain name (e.g. api.nasa.gov) — no query parameters
                logger.debug("DNS resolution failed for '%s': %s", hostname, dns_err)
                result["error"] = "DNS resolution failed. Check application logs for details."
                return result

        t0 = time.monotonic()
        try:
            resp = _req.head(url, timeout=timeout, allow_redirects=True,
                             headers={"User-Agent": "RetroIPTVGuide-Diagnostics/1.0"})
            elapsed = int((time.monotonic() - t0) * 1000)
            result["status_code"] = resp.status_code
            result["response_time_ms"] = elapsed
            if resp.status_code < 400:
                result["reachable"] = True
            else:
                result["error"] = f"HTTP {resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            result["response_time_ms"] = int((time.monotonic() - t0) * 1000)
            logger.debug("Service probe failed for %s: %s", _log_url, exc, exc_info=True)
            result["error"] = "Service probe failed. Check application logs for details."

    except Exception as exc:  # noqa: BLE001
        logger.debug("URL probe setup failed for %s: %s", _log_url, exc, exc_info=True)
        result["error"] = "URL probe setup failed. Check application logs for details."

    return result


# ---------------------------------------------------------------------------
# System Resources
# ---------------------------------------------------------------------------

def check_system_resources() -> Dict[str, Any]:
    """Return system resource and runtime environment information.

    Collects (without requiring psutil):
    - CPU load average (1/5/15 min)
    - Memory: resident set size of current process
    - Open file descriptor count (Linux /proc)
    - Python interpreter and active packages vs requirements.txt
    - Thread count for the current process
    """
    import threading  # noqa: PLC0415

    result: Dict[str, Any] = {
        "load_avg": None,
        "memory_rss_mb": None,
        "open_fds": None,
        "thread_count": threading.active_count(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "packages": [],
        "requirements_check": [],
    }

    # Load average
    try:
        load1, load5, load15 = os.getloadavg()
        result["load_avg"] = {"1min": round(load1, 2), "5min": round(load5, 2), "15min": round(load15, 2)}
    except (AttributeError, OSError):
        result["load_avg"] = {"note": "Not available on this platform (Windows)."}

    # Memory (resident set size)
    try:
        with open(f"/proc/{os.getpid()}/status", "r") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    result["memory_rss_mb"] = round(kb / 1024, 1)
                    break
    except (OSError, ValueError):
        # Fallback: resource module
        try:
            import resource  # noqa: PLC0415
            usage = resource.getrusage(resource.RUSAGE_SELF)
            # ru_maxrss units differ by platform:
            #   Linux  → kilobytes (divide by 1024 to get MB)
            #   macOS  → bytes    (divide by 1024*1024 to get MB)
            divisor = 1024 if sys.platform == "linux" else (1024 * 1024)
            result["memory_rss_mb"] = round(usage.ru_maxrss / divisor, 1)
        except Exception:  # noqa: BLE001
            result["memory_rss_mb"] = None

    # Open file descriptors
    try:
        fds = os.listdir(f"/proc/{os.getpid()}/fd")
        result["open_fds"] = len(fds)
    except (OSError, PermissionError):
        result["open_fds"] = None

    # Installed packages (via importlib.metadata / pkg_resources)
    installed: Dict[str, str] = {}
    try:
        from importlib.metadata import version  # noqa: PLC0415
        # Collect a representative set of packages we care about
        INTERESTING = ["flask", "flask-login", "requests", "werkzeug", "jinja2",
                       "click", "itsdangerous", "certifi", "charset-normalizer"]
        for pkg in INTERESTING:
            try:
                installed[pkg] = version(pkg)
            except Exception:  # noqa: BLE001
                pass
    except ImportError:
        pass

    result["packages"] = [{"name": k, "version": v} for k, v in sorted(installed.items())]

    # Check requirements.txt
    req_checks = []
    req_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.txt")
    if os.path.isfile(req_path):
        try:
            import re as _re  # noqa: PLC0415
            # Regex strips all common version specifiers: ==, >=, <=, ~=, !=, >, <
            # Also strips extras like package[extra] and environment markers (;...)
            _pkg_name_re = _re.compile(r'^([A-Za-z0-9_.\-]+)', _re.ASCII)
            with open(req_path, "r") as fh:
                lines = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
            from importlib.metadata import version as _ver  # noqa: PLC0415
            for req_line in lines:
                m = _pkg_name_re.match(req_line)
                pkg_name = m.group(1).lower() if m else req_line.lower()
                try:
                    ver = _ver(pkg_name)
                    req_checks.append({"package": pkg_name, "required": req_line, "installed": ver, "ok": True})
                except Exception:  # noqa: BLE001
                    req_checks.append({"package": pkg_name, "required": req_line, "installed": "NOT FOUND", "ok": False})
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not read requirements.txt: %s", exc, exc_info=True)
            req_checks.append({"error": "Could not read requirements.txt. Check application logs for details."})
    else:
        req_checks.append({"note": "requirements.txt not found relative to app root."})

    result["requirements_check"] = req_checks

    missing = [r["package"] for r in req_checks if isinstance(r, dict) and not r.get("ok", True)]
    status = "FAIL" if missing else "PASS"
    detail = (
        f"Thread count: {result['thread_count']}. "
        f"Memory RSS: {result['memory_rss_mb']} MB. "
        + (f"Missing packages: {', '.join(missing)}." if missing else "All requirements satisfied.")
    )

    return {
        "status": status,
        "detail": detail,
        "remediation": f"Run: pip install {' '.join(missing)}" if missing else "",
        **result,
    }


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------

def run_config_checks(db_path: str, tuner_db_path: str) -> Dict[str, Any]:
    """Run all application-config diagnostics and return a combined dict."""
    from utils.dependency_check import check_external_binaries, check_python_packages
    from utils.conflict_detector import detect_channel_conflicts
    from utils.security_diag import run_security_checks

    # Gather Flask runtime context for the security check
    try:
        import app as _app_module  # noqa: PLC0415
        secret_key: str = _app_module.app.config.get("SECRET_KEY", "") or ""
        debug_mode: bool = bool(_app_module.app.config.get("DEBUG", False))
        bind_host: str = _app_module.app.config.get("SERVER_BIND_HOST", "0.0.0.0")
    except Exception:  # noqa: BLE001
        secret_key = ""
        debug_mode = False
        bind_host = "0.0.0.0"

    return {
        "user_accounts": check_user_accounts(db_path),
        "virtual_channels": check_virtual_channels(tuner_db_path),
        "external_services": check_external_services(tuner_db_path),
        "system_resources": check_system_resources(),
        "external_binaries": check_external_binaries(),
        "python_packages": check_python_packages(),
        "channel_conflicts": detect_channel_conflicts(),
        "security": run_security_checks(
            db_path=db_path,
            secret_key=secret_key,
            debug_mode=debug_mode,
            bind_host=bind_host,
        ),
    }
