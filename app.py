# app.py — merged version (features from both sources)
APP_VERSION = "v4.9.4"
APP_RELEASE_DATE = "2026-04-25"

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import re
import sys
import platform
import os
import json as _json
import datetime
import requests
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import socket
import ipaddress
import logging
from datetime import datetime, timezone, timedelta, date
import threading


# Pillow is used to stitch OSM map tiles into the static basemap PNGs for the
# traffic demo.  It is optional — without it the browser falls back to Leaflet.
try:
    from PIL import Image as _PilImage
    import io as _io
    import math as _math
    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False
    logging.info("Pillow not installed — traffic demo will use Leaflet basemaps")

APP_START_TIME = datetime.now()

# ------------------- Canonical Data Directory -------------------
# Priority: 1) RETROIPTV_DATA_DIR env var  2) OS default  3) ./config fallback
def _resolve_data_dir() -> str:
    env_val = os.environ.get("RETROIPTV_DATA_DIR", "").strip()
    if env_val:
        return env_val
    if sys.platform == "win32":
        prog_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return os.path.join(prog_data, "RetroIPTVGuide")
    # Linux / macOS: try the system path only when we can actually write to it
    system_path = "/var/lib/retroiptvguide"
    try:
        os.makedirs(system_path, exist_ok=True)
        # Verify writability with a probe
        probe = os.path.join(system_path, ".write_probe")
        with open(probe, "w") as _fh:
            _fh.write("ok")
        os.unlink(probe)
        return system_path
    except (PermissionError, OSError):
        pass
    # Fallback: portable ./config directory next to app.py
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

DATA_DIR = _resolve_data_dir()

# Ensure required subdirectories exist
for _subdir in ("logs", "db", "xmltv", "support"):
    _subdir_path = os.path.join(DATA_DIR, _subdir)
    try:
        os.makedirs(_subdir_path, exist_ok=True)
    except (PermissionError, OSError) as _mkdir_err:
        print(
            f"[RetroIPTVGuide] WARNING: could not create directory {_subdir_path!r}: {_mkdir_err}",
            file=sys.stderr,
        )

# ------------------- Logging Setup -------------------
from utils.logging_setup import configure_logging as _configure_logging
_configure_logging(DATA_DIR)

# ------------------- Startup Diagnostics -------------------
# Initialised right after logging so startup errors are captured
# even if later imports fail or the DB can't be opened.
from utils.startup_diag import (
    configure_startup_log as _configure_startup_log,
    record_environment as _record_environment,
    record_startup_event as _record_startup_event,
    record_import_error as _record_import_error,
    record_db_init as _record_db_init,
)
_configure_startup_log(DATA_DIR)
_record_environment()
_record_startup_event("info", "data_dir", DATA_DIR)
_record_startup_event("info", "app_version", APP_VERSION)

# ------------------- Config -------------------
app = Flask(__name__)
app.secret_key = os.urandom(24)  # replace with a fixed key in production
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)


DATABASE = os.path.join(DATA_DIR, 'users.db')
TUNER_DB = os.path.join(DATA_DIR, 'tuners.db')
ROADS_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'roads_cache')
ROADS_BUNDLED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'data', 'roads')
AUDIO_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'audio')
_ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'ogg', 'wav', 'aac', 'm4a', 'flac'}
LOGO_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'logos', 'virtual')
ICON_PACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'logos', 'virtual', 'icon_pack')
_ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# ------------------- Diagnostics Blueprint -------------------
from utils.log_reading import configure_allowed_logs as _configure_allowed_logs
_configure_allowed_logs(DATA_DIR)

from blueprints.admin_diagnostics import admin_diagnostics_bp

# Inject runtime config into the app so the blueprint can access it
app.config["DIAG_DATA_DIR"] = DATA_DIR
app.config["DIAG_APP_VERSION"] = APP_VERSION
app.config["DIAG_APP_START_TIME"] = APP_START_TIME
# DATABASE and TUNER_DB may be overridden in tests; blueprint reads them lazily
# via a lambda so they pick up any monkeypatch changes made after import.
app.config["DIAG_DATABASE"] = DATABASE
app.config["DIAG_TUNER_DB"] = TUNER_DB

app.register_blueprint(admin_diagnostics_bp)

# ------------------- Public startup-status endpoint -------------------
@app.route('/startup-status')
def startup_status_public():
    """Public (no login required) endpoint for pre-login diagnostics.

    Returns minimal JSON describing whether the app started successfully and
    any critical errors that occurred during startup.  Deliberately limited —
    no log content, no paths, no secrets.  Useful when the admin panel itself
    cannot be reached.
    """
    from utils.startup_diag import get_startup_summary
    summary = get_startup_summary()
    # Return only fields safe for unauthenticated callers
    return jsonify({
        "app": "RetroIPTVGuide",
        "version": APP_VERSION,
        "status": summary["status"],
        "finished_at": summary["finished_at"],
        "error_count": summary["error_count"],
        "warning_count": summary["warning_count"],
        # Surface error categories (no detail text) so the caller knows where to look
        "error_categories": list({e["category"] for e in summary["errors"]}),
    })

# ------------------- Activity Log -------------------
# LOG_PATH is kept for legacy reference and to derive the logs directory path.
LOG_PATH = os.path.join(DATA_DIR, "logs", "activity.log")

def log_event(user, action):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DATABASE, timeout=10) as conn:
            conn.execute(
                "INSERT INTO activity_logs (username, action, timestamp) VALUES (?, ?, ?)",
                (user, action, ts),
            )
            conn.commit()
    except sqlite3.OperationalError:
        # Table may not exist on older installs where init_db() hasn't run yet — auto-heal.
        init_db()
        log_event(user, action)
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Could not write activity log to DB: {e}", file=sys.stderr)

# ------------------- URL Validation -------------------
def validate_tuner_url(url, label="Tuner"):
    """Warn if tuner URL uses DNS that can't be resolved or invalid IP ranges."""
    try:
        host = urlparse(url).hostname
        if not host:
            flash(f"⚠️ {label} URL seems invalid: {url}", "warning")
            return

        # If it's an IP, validate private vs public
        try:
            ip_obj = ipaddress.ip_address(host)
            if ip_obj.is_private:
                flash(f"ℹ️ {label} is using a private IP ({host})", "info")
            else:
                flash(f"ℹ️ {label} is using a public IP ({host}). Ensure it’s reachable.", "info")
        except ValueError:
            # Not an IP → must be a hostname
            try:
                resolved_ip = socket.gethostbyname(host)
                ip_obj = ipaddress.ip_address(resolved_ip)
                if ip_obj.is_private:
                    flash(f"ℹ️ {label} hostname '{host}' resolved to local IP {resolved_ip}.", "info")
                else:
                    flash(f"ℹ️ {label} hostname '{host}' resolved to public IP {resolved_ip}.", "info")
            except socket.gaierror:
                flash(f"⚠️ {label} hostname '{host}' could not be resolved. Consider using IP instead.", "warning")

    except Exception as e:
        logging.exception("validate_tuner_url error for %s: %s", label, e)
        flash(f"⚠️ Validation error for {label}. Please check the value and try again.", "warning")


def _safe_next_url(raw: str) -> str:
    """Return *raw* if it is a safe, same-site relative URL; otherwise return ''.

    Guards against open-redirect attacks (CWE-601) by ensuring the redirect
    target has no scheme or host component — i.e. it is a relative path on
    the same origin.  Backslashes are normalised to forward slashes first
    because some browsers treat them as path separators.

    Also rejects any string that starts with '//' (before or after normalisation)
    to prevent protocol-relative redirect bypasses.  For example:
      - '////evil.com' → urlparse gives path='//evil.com' (empty netloc) but the
        normalised string still starts with '//', so it is rejected.
      - '///evil.com'  → starts with '//' in the raw string, rejected.
      - '//evil.com'   → urlparse gives netloc='evil.com', also rejected.
    """
    raw = (raw or '').strip().replace('\\', '/')
    # Reject anything whose text or parsed netloc/scheme would redirect off-site.
    if raw.startswith('//'):
        return ''
    parsed = urlparse(raw)
    if not parsed.scheme and not parsed.netloc:
        return raw
    return ''


# ------------------- User Model -------------------
class User(UserMixin):
    def __init__(self, id, username, password_hash, last_login=None, must_change_password=0):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.last_login = last_login
        self.must_change_password = bool(must_change_password)

# ------------------- Init DBs -------------------
def _migrate_activity_log(conn):
    """Import entries from the legacy activity.log flat file into the activity_logs table.

    The rename from ``activity.log`` → ``activity.log.migrated`` is performed
    **first** (before any reads), so the operation is effectively atomic in
    multi-worker deployments: only the worker that wins the rename proceeds
    to import; all others see that the source file is gone and skip.

    Returns the number of rows imported (0 if nothing to migrate).
    """
    if not os.path.isfile(LOG_PATH):
        return 0
    migrated_path = LOG_PATH + ".migrated"

    # Fast-path: already migrated on a previous run.
    if os.path.isfile(migrated_path):
        return 0

    # Atomically claim the file.  On POSIX, os.rename is atomic; if the file
    # was already renamed by another worker, OSError is raised and we bail out.
    # We check for the sentinel above as a fast-path to avoid a redundant rename
    # attempt on every subsequent startup.
    try:
        os.rename(LOG_PATH, migrated_path)
    except OSError:
        # Another process already renamed it, or a permission error occurred.
        return 0

    rows = []
    skipped = 0
    try:
        with open(migrated_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.strip().split(" | ")
                if len(parts) == 3:
                    rows.append((parts[0], parts[1], parts[2]))
                elif line.strip():
                    skipped += 1
    except OSError:
        return 0

    if skipped:
        print(
            f"Warning: _migrate_activity_log: skipped {skipped} malformed line(s) from {LOG_PATH}",
            file=sys.stderr,
        )
    if rows:
        conn.executemany(
            "INSERT INTO activity_logs (username, action, timestamp) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
    return len(rows)


def _apply_users_schema_migrations(conn: sqlite3.Connection) -> None:
    """Apply incremental column migrations to the ``users`` table.

    Each statement is wrapped in its own try/except so that a column that
    already exists (``OperationalError``) is silently skipped.  New columns
    must be appended to the bottom of this function — never removed — so that
    any older database is always brought forward to the latest schema.
    """
    _migrations = [
        # v1 → v2: persisted last-login timestamp
        'ALTER TABLE users ADD COLUMN last_login TEXT',
        # v2 → v3: per-user tuner assignment
        'ALTER TABLE users ADD COLUMN assigned_tuner TEXT',
        # v3 → v4: force password change on first login
        'ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0',
    ]
    for stmt in _migrations:
        try:
            conn.execute(stmt)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already present — safe to skip


def init_db():
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, last_login TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_preferences
                     (username TEXT PRIMARY KEY, prefs TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS activity_logs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      username TEXT NOT NULL,
                      action TEXT NOT NULL,
                      timestamp TEXT NOT NULL)''')
        conn.commit()

        _apply_users_schema_migrations(conn)

        # Migrate entries from the legacy activity.log flat file (one-time migration).
        migrated_count = _migrate_activity_log(conn)
        if migrated_count > 0:
            try:
                from utils.startup_diag import record_startup_event as _rse
                _rse(
                    "info",
                    "activity_log_migration",
                    f"Imported {migrated_count} entr{'y' if migrated_count == 1 else 'ies'} "
                    f"from legacy activity.log into SQLite activity_logs table.",
                )
            except Exception:  # noqa: BLE001
                pass

def add_user(username, password, must_change_password=0):
    password_hash = generate_password_hash(password)
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (username, password, must_change_password) VALUES (?, ?, ?)', (username, password_hash, must_change_password))
        conn.commit()

def get_user(username):
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, password, last_login, must_change_password FROM users WHERE username=?', (username,))
        row = c.fetchone()
    if row:
        return User(row[0], row[1], row[2], row[3], row[4])
    return None

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, password, last_login, must_change_password FROM users WHERE id=?', (user_id,))
        row = c.fetchone()
    if row:
        return User(row[0], row[1], row[2], row[3], row[4])
    return None

# ------------------- Tuner DB -------------------
def init_tuners_db():
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS tuners
                     (name TEXT PRIMARY KEY, xml TEXT, m3u TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings
                     (key TEXT PRIMARY KEY, value TEXT)''')
        conn.commit()

        # Add tuner_type column if it doesn't exist (for existing databases)
        try:
            c.execute("ALTER TABLE tuners ADD COLUMN tuner_type TEXT DEFAULT 'standard'")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # Add sources column if it doesn't exist (for combined tuners)
        try:
            c.execute("ALTER TABLE tuners ADD COLUMN sources TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # Remove the test banner feature entirely: delete the global overlay.test_text key
        # and the per-channel test_text keys for all virtual channels.  This clears any
        # stale "This is test Text!" values that were stored during early development.
        c.execute("DELETE FROM settings WHERE key='overlay.test_text'")
        for _ch_id in ('virtual.news', 'virtual.weather', 'virtual.status', 'virtual.traffic', 'virtual.updates', 'virtual.sports', 'virtual.nasa'):
            c.execute("DELETE FROM settings WHERE key=?",
                      (f"overlay.{_ch_id}.test_text",))
        conn.commit()

        # bootstrap if empty
        c.execute("SELECT COUNT(*) FROM tuners")
        if c.fetchone()[0] == 0:
            defaults = {
                "Tuner 1": {
                    "m3u": "http://iptv.lan:8409/iptv/channels.m3u",
                    "xml": "http://iptv.lan:8409/iptv/xmltv.xml"
                },
                "Tuner 2": {
                    "m3u": "http://iptv2.lan:8500/iptv/channels.m3u",
                    "xml": "http://iptv2.lan:8500/iptv/xmltv.xml"
                },
            }
            for name, urls in defaults.items():
                c.execute("INSERT INTO tuners (name, xml, m3u) VALUES (?, ?, ?)",
                          (name, urls["xml"], urls["m3u"]))
            # set default active tuner
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('current_tuner', 'Tuner 1')")
        conn.commit()

        # Ensure traffic demo cities table exists and is seeded
        _init_traffic_demo_db(conn)

def get_tuners():
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        try:
            c.execute("SELECT name, xml, m3u, tuner_type, sources FROM tuners")
            rows = c.fetchall()
            result = {}
            for row in rows:
                name, xml, m3u, tuner_type, sources_json = row
                entry = {"xml": xml, "m3u": m3u, "tuner_type": tuner_type or "standard"}
                if sources_json:
                    try:
                        entry["sources"] = _json.loads(sources_json)
                    except Exception:
                        entry["sources"] = []
                else:
                    entry["sources"] = []
                result[name] = entry
            return result
        except sqlite3.OperationalError:
            # Fallback for old schema without tuner_type/sources columns
            c.execute("SELECT name, xml, m3u FROM tuners")
            return {row[0]: {"xml": row[1], "m3u": row[2], "tuner_type": "standard", "sources": []}
                    for row in c.fetchall()}

def get_current_tuner():
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key='current_tuner'")
        row = c.fetchone()
        return row[0] if row else None

def set_current_tuner(name):
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET value=? WHERE key='current_tuner'", (name,))
        conn.commit()

def update_tuner_urls(name, xml_url, m3u_url):
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        c.execute("UPDATE tuners SET xml=?, m3u=? WHERE name=?", (xml_url, m3u_url, name))
        conn.commit()

def add_tuner(name, xml_url, m3u_url):
    """Insert a new tuner into DB with validation."""
    # Check for duplicate name
    tuners = get_tuners()
    if name in tuners:
        raise ValueError(f"Tuner '{name}' already exists")
    
    # Validate XML URL (optional – single .m3u8 stream tuners may omit it)
    if xml_url and xml_url.strip():
        if not xml_url.startswith(('http://', 'https://')):
            raise ValueError("XML URL must start with http:// or https://")

    # Validate M3U URL
    if not m3u_url or not m3u_url.strip():
        raise ValueError("M3U URL cannot be empty")
    if not m3u_url.startswith(('http://', 'https://')):
        raise ValueError("M3U URL must start with http:// or https://")
    
    # Validate the URL hostname and block internal/private addresses to prevent SSRF
    try:
        parsed_url = urlparse(m3u_url)
        hostname = parsed_url.hostname
        
        if not hostname:
            raise ValueError("M3U URL must have a valid hostname")
        
        try:
            # Resolve hostname to IP address
            ip_addr = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip_addr)
            
            # Block localhost (127.0.0.0/8) to prevent SSRF
            if ip_obj.is_loopback:
                raise ValueError("M3U URL cannot point to localhost (127.0.0.0/8)")
            # Block link-local addresses (169.254.0.0/16) which could be cloud metadata
            if ip_obj.is_link_local:
                raise ValueError("M3U URL cannot point to link-local addresses (169.254.0.0/16)")
            # Block reserved, unspecified, or multicast addresses
            if ip_obj.is_reserved or ip_obj.is_unspecified or ip_obj.is_multicast:
                raise ValueError("M3U URL cannot point to a reserved or multicast address")
        except socket.gaierror:
            # If hostname can't be resolved, skip IP check
            pass
    except ValueError:
        # Re-raise ValueError from our validation
        raise
    except Exception as e:
        raise ValueError(f"M3U URL validation failed: {str(e)}")
    
    # Insert into database
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO tuners (name, xml, m3u, tuner_type) VALUES (?, ?, ?, 'standard')",
                (name, xml_url, m3u_url)
            )
        except sqlite3.OperationalError:
            # Fallback for old schema without tuner_type column
            c.execute(
                "INSERT INTO tuners (name, xml, m3u) VALUES (?, ?, ?)",
                (name, xml_url, m3u_url)
            )
        conn.commit()

def delete_tuner(name):
    """Delete a tuner from DB (except current one)."""
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM tuners WHERE name=?', (name,))
        conn.commit()

def rename_tuner(old_name, new_name):
    """Rename a tuner in DB."""
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        c.execute("UPDATE tuners SET name=? WHERE name=?", (new_name, old_name))
        conn.commit()


def add_combined_tuner(name, sources):
    """Create a combined tuner that merges channels and EPG from multiple source tuners."""
    if not sources:
        raise ValueError("Combined tuner requires at least one source tuner")
    tuners = get_tuners()
    if name in tuners:
        raise ValueError(f"Tuner '{name}' already exists")
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO tuners (name, xml, m3u, tuner_type, sources) VALUES (?, ?, ?, ?, ?)",
            (name, None, None, "combined", _json.dumps(sources))
        )
        conn.commit()


def load_tuner_data(tuner_name):
    """Load channels and EPG for a tuner, supporting combined tuners.

    Returns:
        (channels, epg) — lists/dicts as returned by parse_m3u / parse_epg.
    """
    tuners = get_tuners()
    tuner = tuners.get(tuner_name)
    if not tuner:
        return [], {}

    if tuner.get("tuner_type") == "combined":
        merged_channels = []
        merged_epg = {}
        for source_name in tuner.get("sources", []):
            source = tuners.get(source_name)
            if not source:
                continue  # skip missing source tuners
            src_channels = parse_m3u(source["m3u"]) if source.get("m3u") else []
            src_epg = parse_epg(source["xml"]) if source.get("xml") else {}
            merged_channels.extend(src_channels)
            merged_epg.update(src_epg)
        return merged_channels, merged_epg
    else:
        channels = parse_m3u(tuner["m3u"]) if tuner.get("m3u") else []
        epg = parse_epg(tuner["xml"]) if tuner.get("xml") else {}
        return channels, epg
@app.template_filter('format_datetime')
def format_datetime_filter(iso_string):
    """Format ISO datetime string to human-readable format."""
    if not iso_string:
        return 'Never'
    try:
        dt = datetime.fromisoformat(iso_string)
        # Convert to local time (or keep UTC, depending on preference)
        # For now, we'll display in UTC with a cleaner format
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return iso_string

@app.context_processor
def inject_tuner_context():
    """Inject tuner info into all templates (for header fly-outs)."""
    try:
        tuners = get_tuners()
        tuner_names = list(tuners.keys())
    except Exception:
        tuner_names = []
    return {
        "current_tuner": get_current_tuner(),
        "tuner_names": tuner_names
    }

# ------------------- User Preferences -------------------

_DEFAULT_PREFS = {
    "auto_load_channel": None,
    "hidden_channels": [],
    "sizzle_reels_enabled": False,
    "default_theme": None,
}


def get_user_prefs(username):
    """Return the stored preferences for *username*, merged with defaults."""
    try:
        with sqlite3.connect(DATABASE, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT prefs FROM user_preferences WHERE username=?", (username,))
            row = c.fetchone()
        if row and row[0]:
            stored = _json.loads(row[0])
            prefs = dict(_DEFAULT_PREFS)
            prefs.update({k: v for k, v in stored.items() if k in _DEFAULT_PREFS})
            return prefs
        return dict(_DEFAULT_PREFS)
    except Exception:
        return dict(_DEFAULT_PREFS)


def save_user_prefs(username, prefs):
    """Upsert preferences for *username* into the database.

    Only known preference keys (those in _DEFAULT_PREFS) are stored.
    Missing keys are filled from the existing stored value so callers can
    do partial updates.
    """
    try:
        existing = get_user_prefs(username)
        merged = dict(existing)
        merged.update({k: v for k, v in prefs.items() if k in _DEFAULT_PREFS})
        with sqlite3.connect(DATABASE, timeout=10) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO user_preferences (username, prefs) VALUES (?, ?)",
                (username, _json.dumps(merged))
            )
            conn.commit()
    except sqlite3.OperationalError:
        # Table may not exist yet on very old installs — auto-heal
        init_db()
        save_user_prefs(username, prefs)


cached_channels = []
cached_epg = {}

# Track currently playing marker (server-side)
CURRENTLY_PLAYING = None

# ------------------- M3U Parsing -------------------
def parse_m3u(m3u_url):
    channels = []
    try:
        r = requests.get(m3u_url, timeout=10)
        r.raise_for_status()
        lines = r.text.splitlines()
    except:
        return channels
    
    # Filter out empty lines and comments (except #EXTINF)
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    
    # Check if this is a single-channel playlist (no #EXTINF tags)
    has_extinf = any(line.startswith('#EXTINF:') for line in non_empty_lines)
    
    if not has_extinf:
        # Look for a single stream URL
        stream_urls = [line for line in non_empty_lines 
                      if line.startswith(('http://', 'https://')) 
                      and not line.startswith('#')]
        
        if len(stream_urls) == 1:
            url = stream_urls[0]
            # Extract a channel name from the URL or use default
            try:
                parsed = urlparse(url)
                name = parsed.path.split('/')[-1].replace('.m3u8', '').replace('_', ' ').title()
                if not name:
                    name = 'Live Stream'
            except Exception:
                name = 'Live Stream'
            
            channels.append({
                'name': name,
                'logo': '',
                'url': url,
                'tvg_id': 'stream_1'
            })
            return channels
    
    # Existing multi-channel parsing logic
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF:'):
            info = line.strip()
            name_match = re.search(r',(.+)$', info)
            name = name_match.group(1) if name_match else f'Channel {i}'
            logo_match = re.search(r'tvg-logo="([^"]+)"', info)
            logo = logo_match.group(1) if logo_match else ''
            tvg_id_match = re.search(r'tvg-id="([^"]+)"', info)
            tvg_id = tvg_id_match.group(1) if tvg_id_match else name
            group_match = re.search(r'group-title="([^"]*)"', info, re.IGNORECASE)
            group = group_match.group(1).strip() if group_match else ''
            url = lines[i+1].strip() if i+1 < len(lines) else ''

            if url.endswith('.ts'):
                url = url.replace('.ts', '.m3u8')

            channels.append({'name': name, 'logo': logo, 'url': url, 'tvg_id': tvg_id, 'group': group})
    return channels

# ------------------- XMLTV EPG Parsing -------------------
def parse_epg(xml_url):
    programs = {}
    
    # ✅ Handle when user pastes same .m3u for XML
    if xml_url.lower().endswith(('.m3u', '.m3u8')):
        return programs  # empty, fallback will fill it later
        
    try:
        r = requests.get(xml_url, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except:
        return programs

    for channel in root.findall('channel'):
        cid = channel.attrib.get('id')
        programs[cid] = []

    for prog in root.findall('programme'):
        cid = prog.attrib.get('channel')
        start_str = prog.attrib.get('start')
        stop_str = prog.attrib.get('stop')

        start = None
        stop = None
        try:
            start = datetime.strptime(start_str[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        except:
            pass
        if stop_str:
            try:
                stop = datetime.strptime(stop_str[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            except:
                stop = None

        title = prog.find('title').text if prog.find('title') is not None else ''
        desc = prog.find('desc').text if prog.find('desc') is not None else ''
        icon_el = prog.find('icon')
        icon = icon_el.attrib.get('src', '') if icon_el is not None else ''

        if cid not in programs:
            programs[cid] = []
        programs[cid].append({'title': title, 'desc': desc, 'start': start, 'stop': stop, 'icon': icon})
    return programs

# ------------------- EPG Fallback Helper -------------------
def apply_epg_fallback(channels, epg):
    """Ensure each channel has at least one program entry, even if missing in XML."""
    for ch in channels:
        tvg_id = ch.get('tvg_id')
        if not tvg_id:
            continue
        if tvg_id not in epg or not epg[tvg_id]:
            epg[tvg_id] = [{
                'title': 'No Guide Data Available',
                'desc': '',
                'start': None,
                'stop': None
            }]
    return epg


# ------------------- Virtual Channels -------------------
VIRTUAL_CHANNELS = [
    {
        'name': 'News Now',
        'logo': '/static/logos/virtual/news.svg',
        'url': '',
        'tvg_id': 'virtual.news',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '/static/loops/news.mp4',
        'overlay_type': 'news',
        'overlay_refresh_seconds': 60,
    },
    {
        'name': 'Weather Now',
        'logo': '/static/logos/virtual/weather.svg',
        'url': '',
        'tvg_id': 'virtual.weather',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '/static/loops/weather.mp4',
        'overlay_type': 'weather',
        'overlay_refresh_seconds': 30,
    },
    {
        'name': 'System Status',
        'logo': '/static/logos/virtual/status.svg',
        'url': '',
        'tvg_id': 'virtual.status',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '/static/loops/status.mp4',
        'overlay_type': 'status',
        'overlay_refresh_seconds': 30,
    },
    {
        'name': 'Traffic Now',
        'logo': '/static/logos/virtual/traffic.svg',
        'url': '',
        'tvg_id': 'virtual.traffic',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '/static/loops/traffic.mp4',
        'overlay_type': 'traffic',
        'overlay_refresh_seconds': 120,
    },
    {
        'name': 'Updates & Announcements',
        'logo': '/static/logos/virtual/updates.svg',
        'url': '',
        'tvg_id': 'virtual.updates',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '/static/loops/updates.mp4',
        'overlay_type': 'updates',
        'overlay_refresh_seconds': 1800,
    },
    {
        'name': 'Sports Scores',
        'logo': '/static/logos/virtual/sports.svg',
        'url': '',
        'tvg_id': 'virtual.sports',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '/static/loops/sports.mp4',
        'overlay_type': 'sports',
        'overlay_refresh_seconds': 60,
    },
    {
        'name': 'Space Channel',
        'logo': '/static/logos/virtual/nasa.svg',
        'url': '',
        'tvg_id': 'virtual.nasa',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '/static/loops/nasa.mp4',
        'overlay_type': 'nasa',
        'overlay_refresh_seconds': 900,
    },
    {
        'name': 'Channel Mix',
        'logo': '/static/logos/virtual/channel_mix.svg',
        'url': '',
        'tvg_id': 'virtual.channel_mix',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '',
        'overlay_type': 'channel_mix',
        'overlay_refresh_seconds': 30,
    },
    {
        'name': 'On This Day',
        'logo': '/static/logos/virtual/on_this_day.svg',
        'url': '',
        'tvg_id': 'virtual.on_this_day',
        'is_virtual': True,
        'playback_mode': 'local_loop',
        'loop_asset': '/static/loops/on_this_day.mp4',
        'overlay_type': 'on_this_day',
        'overlay_refresh_seconds': 30,
    },
]

def get_virtual_channel_settings():
    """Return a dict mapping each virtual channel tvg_id to its enabled state (bool).
    Defaults to False (disabled) when no setting has been persisted yet."""
    defaults = {ch['tvg_id']: False for ch in VIRTUAL_CHANNELS}
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for tvg_id in defaults:
                key = f"virtual_channel.{tvg_id}.enabled"
                c.execute("SELECT value FROM settings WHERE key=?", (key,))
                row = c.fetchone()
                if row is not None:
                    defaults[tvg_id] = row[0] == "1"
    except Exception:
        logging.exception("get_virtual_channel_settings failed, using defaults")
    return defaults

def save_virtual_channel_settings(settings_dict):
    """Persist virtual channel enabled states.  settings_dict maps tvg_id -> bool."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for tvg_id, enabled in settings_dict.items():
                key = f"virtual_channel.{tvg_id}.enabled"
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          (key, "1" if enabled else "0"))
            conn.commit()
    except Exception:
        logging.exception("save_virtual_channel_settings failed")
        raise

_OVERLAY_APPEARANCE_KEYS = ('text_color', 'bg_color', 'test_text')
_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

def get_overlay_appearance():
    """Return overlay appearance settings: text_color, bg_color (hex or ''), test_text (str)."""
    result = {'text_color': '', 'bg_color': '', 'test_text': ''}
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for key in _OVERLAY_APPEARANCE_KEYS:
                c.execute("SELECT value FROM settings WHERE key=?", (f"overlay.{key}",))
                row = c.fetchone()
                if row is not None:
                    result[key] = row[0]
    except Exception:
        logging.exception("get_overlay_appearance failed, using defaults")
    return result

def save_overlay_appearance(appearance_dict):
    """Persist overlay appearance settings.  Validates hex colors; strips test_text."""
    cleaned = {}
    for key in _OVERLAY_APPEARANCE_KEYS:
        val = str(appearance_dict.get(key, '')).strip()
        if key in ('text_color', 'bg_color'):
            if val and not _HEX_COLOR_RE.match(val):
                raise ValueError(f"Invalid color value for {key}: {val!r}")
        cleaned[key] = val
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for key, value in cleaned.items():
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          (f"overlay.{key}", value))
            conn.commit()
    except ValueError:
        raise
    except Exception:
        logging.exception("save_overlay_appearance failed")
        raise

def get_channel_overlay_appearance(tvg_id):
    """Return overlay appearance settings for a specific virtual channel.
    Keys stored as overlay.{tvg_id}.text_color etc. in the settings table."""
    result = {'text_color': '', 'bg_color': '', 'test_text': ''}
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for key in _OVERLAY_APPEARANCE_KEYS:
                c.execute("SELECT value FROM settings WHERE key=?", (f"overlay.{tvg_id}.{key}",))
                row = c.fetchone()
                if row is not None:
                    result[key] = row[0]
    except Exception:
        logging.exception("get_channel_overlay_appearance failed, using defaults")
    return result

def save_channel_overlay_appearance(tvg_id, appearance_dict):
    """Persist per-channel overlay appearance settings."""
    cleaned = {}
    for key in _OVERLAY_APPEARANCE_KEYS:
        val = str(appearance_dict.get(key, '')).strip()
        if key in ('text_color', 'bg_color'):
            if val and not _HEX_COLOR_RE.match(val):
                raise ValueError(f"Invalid color value for {key}: {val!r}")
        cleaned[key] = val
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for key, value in cleaned.items():
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          (f"overlay.{tvg_id}.{key}", value))
            conn.commit()
    except ValueError:
        raise
    except Exception:
        logging.exception("save_channel_overlay_appearance failed")
        raise

def get_all_channel_appearances():
    """Return dict of tvg_id -> appearance for all virtual channels."""
    return {ch['tvg_id']: get_channel_overlay_appearance(ch['tvg_id']) for ch in VIRTUAL_CHANNELS}

def get_news_feed_urls():
    """Return list of configured RSS/Atom news feed URLs (up to 6, non-empty strings).

    Reads numbered keys ``news.rss_url_1`` … ``news.rss_url_6``.  Falls back to
    the legacy ``news.rss_url`` key when no numbered keys are set.
    """
    urls = []
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for i in range(1, 7):
                c.execute("SELECT value FROM settings WHERE key=?", (f'news.rss_url_{i}',))
                row = c.fetchone()
                if row and row[0]:
                    urls.append(row[0])
            # Backward compat: if no numbered keys present, check the legacy single key
            if not urls:
                c.execute("SELECT value FROM settings WHERE key='news.rss_url'")
                row = c.fetchone()
                if row and row[0]:
                    urls.append(row[0])
    except Exception:
        logging.exception("get_news_feed_urls failed")
    return urls


def save_news_feed_urls(urls):
    """Persist up to 6 RSS/Atom feed URLs.

    ``urls`` is an iterable of URL strings (may be empty or contain blanks which
    are silently skipped after stripping).  Raises ``ValueError`` for any URL
    with an invalid scheme.
    """
    validated = []
    for raw in list(urls)[:6]:
        url = str(raw).strip()
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                raise ValueError(f"Invalid feed URL: {url!r}. Must be an http or https URL with a valid hostname.")
            validated.append(url)
        else:
            validated.append('')
    # Pad to exactly 6 entries so old slots are explicitly cleared
    while len(validated) < 6:
        validated.append('')
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for i, url in enumerate(validated, 1):
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          (f'news.rss_url_{i}', url))
            conn.commit()
    except Exception:
        logging.exception("save_news_feed_urls failed")
        raise


def get_news_feed_url():
    """Return the first configured RSS/Atom news feed URL, or empty string.

    Kept for backward compatibility; delegates to :func:`get_news_feed_urls`.
    """
    urls = get_news_feed_urls()
    return urls[0] if urls else ''


def save_news_feed_url(url):
    """Persist a single RSS/Atom news feed URL (legacy helper).

    Stores the URL as slot 1, clearing all other slots.  Kept for backward
    compatibility; prefer :func:`save_news_feed_urls` for new code.
    """
    save_news_feed_urls([url])


# ── Sports channel: available leagues ────────────────────────────────────────
SPORTS_LEAGUES = [
    {'id': 'nfl',   'name': 'NFL Football',       'sport': 'football',   'league_slug': 'nfl',                     'emoji': '🏈'},
    {'id': 'nba',   'name': 'NBA Basketball',     'sport': 'basketball', 'league_slug': 'nba',                     'emoji': '🏀'},
    {'id': 'mlb',   'name': 'MLB Baseball',       'sport': 'baseball',   'league_slug': 'mlb',                     'emoji': '⚾'},
    {'id': 'nhl',   'name': 'NHL Hockey',         'sport': 'hockey',     'league_slug': 'nhl',                     'emoji': '🏒'},
    {'id': 'mls',   'name': 'MLS Soccer',         'sport': 'soccer',     'league_slug': 'usa.1',                   'emoji': '⚽'},
    {'id': 'ncaaf', 'name': 'College Football',   'sport': 'football',   'league_slug': 'college-football',        'emoji': '🏈'},
    {'id': 'ncaab', 'name': 'College Basketball', 'sport': 'basketball', 'league_slug': 'mens-college-basketball', 'emoji': '🏀'},
]

_SPORTS_LEAGUE_BY_ID = {lg['id']: lg for lg in SPORTS_LEAGUES}


def get_sports_mode():
    """Return the sports channel display mode: 'scores' (default) or 'rss'."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='sports.mode'")
            row = c.fetchone()
            if row and row[0] in ('rss', 'scores'):
                return row[0]
    except Exception:
        logging.exception("get_sports_mode failed")
    return 'scores'


def save_sports_mode(mode):
    """Persist sports channel display mode ('rss' or 'scores')."""
    if mode not in ('rss', 'scores'):
        raise ValueError(f"Invalid sports mode: {mode!r}")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('sports.mode', ?)", (mode,))
            conn.commit()
    except Exception:
        logging.exception("save_sports_mode failed")
        raise


def get_sports_feed_urls():
    """Return list of configured RSS/Atom sports feed URLs (up to 6, non-empty strings).

    Reads numbered keys ``sports.rss_url_1`` … ``sports.rss_url_6``.
    """
    urls = []
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for i in range(1, 7):
                c.execute("SELECT value FROM settings WHERE key=?", (f'sports.rss_url_{i}',))
                row = c.fetchone()
                if row and row[0]:
                    urls.append(row[0])
    except Exception:
        logging.exception("get_sports_feed_urls failed")
    return urls


def save_sports_feed_urls(urls):
    """Persist up to 6 RSS/Atom sports feed URLs.

    ``urls`` is an iterable of URL strings (may be empty or contain blanks which
    are silently skipped after stripping).  Raises ``ValueError`` for any URL
    with an invalid scheme.
    """
    validated = []
    for raw in list(urls)[:6]:
        url = str(raw).strip()
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                raise ValueError(f"Invalid feed URL: {url!r}. Must be an http or https URL with a valid hostname.")
            validated.append(url)
        else:
            validated.append('')
    while len(validated) < 6:
        validated.append('')
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for i, url in enumerate(validated, 1):
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          (f'sports.rss_url_{i}', url))
            conn.commit()
    except Exception:
        logging.exception("save_sports_feed_urls failed")
        raise


def get_sports_external_data_enabled():
    """Return whether external sports data fetching is enabled.

    Defaults to ``False`` (disabled) so no external requests are made until the
    user explicitly opts in and configures a source.
    """
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='sports.external_data_enabled'")
            row = c.fetchone()
            if row is not None:
                return row[0] == '1'
    except Exception:
        logging.exception("get_sports_external_data_enabled failed")
    return False


def save_sports_external_data_enabled(enabled):
    """Persist whether external sports data fetching is enabled."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES "
                      "('sports.external_data_enabled', ?)", ('1' if enabled else '0',))
            conn.commit()
    except Exception:
        logging.exception("save_sports_external_data_enabled failed")
        raise


def get_sports_scores_base_url():
    """Return the user-configured base URL for the scores JSON endpoint.

    Returns an empty string when not configured.  No default value is shipped;
    users must supply their own compatible endpoint.
    """
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='sports.scores_base_url'")
            row = c.fetchone()
            if row and row[0]:
                return row[0].rstrip('/')
    except Exception:
        logging.exception("get_sports_scores_base_url failed")
    return ''


def save_sports_scores_base_url(url):
    """Persist the user-configured scores API base URL.

    ``url`` must be an empty string or a valid http/https URL.
    Raises ``ValueError`` for invalid schemes.
    """
    url = str(url).strip().rstrip('/')
    if url:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError(f"Invalid scores base URL: {url!r}. Must be an http or https URL.")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES "
                      "('sports.scores_base_url', ?)", (url,))
            conn.commit()
    except Exception:
        logging.exception("save_sports_scores_base_url failed")
        raise


def get_sports_config():
    """Return sports channel configuration dict:
        {
            'mode':                 'scores' | 'rss',
            'leagues':              {league_id: bool, ...},
            'external_data_enabled': bool,
            'scores_base_url':      str,
        }
    Defaults: mode='scores', no leagues pre-enabled, external data disabled.
    """
    mode = get_sports_mode()
    external_data_enabled = get_sports_external_data_enabled()
    scores_base_url = get_sports_scores_base_url()
    league_defaults = {lg['id']: False for lg in SPORTS_LEAGUES}
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for lg_id in league_defaults:
                c.execute("SELECT value FROM settings WHERE key=?", (f'sports.league.{lg_id}',))
                row = c.fetchone()
                if row is not None:
                    league_defaults[lg_id] = row[0] == '1'
    except Exception:
        logging.exception("get_sports_config failed")
    return {
        'mode': mode,
        'leagues': league_defaults,
        'external_data_enabled': external_data_enabled,
        'scores_base_url': scores_base_url,
    }


def save_sports_config(cfg):
    """Persist sports league enabled states.  cfg maps league_id -> bool."""
    valid_ids = {lg['id'] for lg in SPORTS_LEAGUES}
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for lg_id, enabled in cfg.items():
                if lg_id not in valid_ids:
                    continue
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          (f'sports.league.{lg_id}', '1' if enabled else '0'))
            conn.commit()
    except Exception:
        logging.exception("save_sports_config failed")
        raise


def fetch_scores(sport, league_slug, base_url):
    """Fetch today's scoreboard from a user-configured JSON scores endpoint.

    ``base_url`` is the root of the scores API.  The full request URL is built as::

        {base_url}/{sport}/{league_slug}/scoreboard

    Returns a list of game dicts:
        {home_team, home_abbr, home_score,
         away_team, away_abbr, away_score,
         status_text, status_state, clock}

    ``status_state`` is one of: 'pre' (scheduled), 'in' (live), 'post' (final).
    Returns an empty list on any error or when ``base_url`` is empty.
    """
    if not base_url:
        return []
    url = f'{base_url.rstrip("/")}/{sport}/{league_slug}/scoreboard'
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logging.exception("fetch_scores failed for %s/%s", sport, league_slug)
        return []

    games = []
    for event in data.get('events', []):
        competitions = event.get('competitions', [])
        if not competitions:
            continue
        comp = competitions[0]
        status = event.get('status', {})
        status_type = status.get('type', {})
        raw_state = status_type.get('state', 'pre')   # 'pre' | 'in' | 'post'
        clock_str  = status.get('displayClock', '')
        period_str = status_type.get('description', '')

        home = {'team': '', 'abbr': '', 'score': ''}
        away = {'team': '', 'abbr': '', 'score': ''}
        for comp_team in comp.get('competitors', []):
            side = 'home' if comp_team.get('homeAway') == 'home' else 'away'
            team_info = comp_team.get('team', {})
            target = home if side == 'home' else away
            target['team']  = team_info.get('displayName', team_info.get('name', ''))
            target['abbr']  = team_info.get('abbreviation', '')
            target['score'] = comp_team.get('score', '')

        if raw_state == 'pre':
            # For pre-game, show the scheduled start time in Eastern Time
            start_date_str = event.get('date', '')
            try:
                start_utc = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                try:
                    from zoneinfo import ZoneInfo
                    et_zone = ZoneInfo('America/New_York')
                    start_local = start_utc.astimezone(et_zone)
                    tz_label = 'EDT' if start_local.utcoffset().seconds // 3600 == 20 else 'EST'
                except Exception:
                    # zoneinfo unavailable — fall back to fixed UTC-5 offset
                    start_local = start_utc - timedelta(hours=5)
                    tz_label = 'ET'
                clock_str = start_local.strftime('%-I:%M %p ') + tz_label
            except Exception:
                clock_str = ''
            status_text = clock_str or 'Scheduled'
        elif raw_state == 'in':
            status_text = period_str or clock_str or 'Live'
        else:
            status_text = 'Final'

        games.append({
            'home_team':   home['team'],
            'home_abbr':   home['abbr'],
            'home_score':  home['score'],
            'away_team':   away['team'],
            'away_abbr':   away['abbr'],
            'away_score':  away['score'],
            'status_text': status_text,
            'status_state': raw_state,
            'clock':       clock_str,
        })
    return games


# ── NASA Imagery channel helpers ──────────────────────────────────────────────

# Module-level APOD image cache.
# Structure: { cache_key: (List[Dict], float) }
#   cache_key  = "{interval}:{image_count}:{api_key}"
#   List[Dict] = raw APOD image objects from the NASA API
#   float      = unix timestamp when the cache was populated
_NASA_APOD_CACHE: dict = {}


def get_nasa_interval():
    """Return the NASA image-display interval in minutes: '15' or '30'. Default '15'."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='nasa.interval'")
            row = c.fetchone()
            if row and row[0] in ('15', '30'):
                return row[0]
    except Exception:
        logging.exception("get_nasa_interval failed")
    return '15'


def save_nasa_interval(interval):
    """Persist NASA image-display interval ('15' or '30' minutes)."""
    if interval not in ('15', '30'):
        raise ValueError(f"Invalid NASA interval: {interval!r}")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('nasa.interval', ?)",
                (interval,)
            )
            conn.commit()
    except Exception:
        logging.exception("save_nasa_interval failed")


def get_nasa_api_key():
    """Return the configured NASA API key, or 'DEMO_KEY' as default."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='nasa.api_key'")
            row = c.fetchone()
            if row and row[0]:
                return row[0].strip()
    except Exception:
        logging.exception("get_nasa_api_key failed")
    return 'DEMO_KEY'


def save_nasa_api_key(api_key):
    """Persist NASA API key (empty string resets to DEMO_KEY)."""
    api_key = (api_key or '').strip()
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('nasa.api_key', ?)",
                (api_key,)
            )
            conn.commit()
    except Exception:
        logging.exception("save_nasa_api_key failed")


def get_nasa_image_count():
    """Return the number of APOD images to cycle (1–15). Default 5 for 15-min, 10 for 30-min.

    The stored value is a plain integer string.  The per-image display time is
    automatically calculated as ``cycle_minutes * 60 / image_count`` seconds,
    so the full cycle always fills the selected cycle duration:
        15-min / 5 images  → 180 s (3 min) per image
        15-min / 15 images →  60 s (1 min) per image
        30-min / 10 images → 180 s (3 min) per image
        30-min / 15 images → 120 s (2 min) per image
    """
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='nasa.image_count'")
            row = c.fetchone()
            if row:
                val = int(row[0])
                if 1 <= val <= 15:
                    return val
    except Exception:
        logging.exception("get_nasa_image_count failed")
    # Sensible defaults: 5 for 15-min mode, 10 for 30-min mode.  Since the
    # interval is read separately, return a single global default here; the
    # caller picks the right contextual default if needed.
    return None   # None → caller uses interval-specific default


def save_nasa_image_count(count):
    """Persist NASA image count (1–15, or None to reset to the interval default)."""
    if count is not None:
        count = int(count)
        if not (1 <= count <= 15):
            raise ValueError(f"Invalid NASA image count: {count!r}")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            if count is None:
                conn.execute("DELETE FROM settings WHERE key='nasa.image_count'")
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES ('nasa.image_count', ?)",
                    (str(count),)
                )
            conn.commit()
    except Exception:
        logging.exception("save_nasa_image_count failed")


def get_nasa_config():
    """Return NASA channel configuration dict.

    ``image_count`` is the resolved count (interval-specific default applied when
    no override has been stored).
    ``seconds_per_image`` is derived automatically from cycle_minutes / image_count.
    """
    interval = get_nasa_interval()
    cycle_minutes = int(interval)
    raw_count = get_nasa_image_count()
    # Apply interval-specific defaults (5 for 15-min, 10 for 30-min)
    if raw_count is None:
        image_count = 5 if cycle_minutes == 15 else 10
    else:
        image_count = raw_count
    seconds_per_image = (cycle_minutes * 60) // image_count
    return {
        'interval':          interval,
        'image_count':       image_count,
        'seconds_per_image': seconds_per_image,
        'api_key':           get_nasa_api_key(),
    }


def _fetch_nasa_apod_images(count, api_key='DEMO_KEY'):
    """Fetch *count* random APOD images from the NASA API.

    Returns a list of image dicts (``media_type == 'image'`` only).
    Returns an empty list on any error so the overlay degrades gracefully.
    """
    url = (
        f'https://api.nasa.gov/planetary/apod'
        f'?api_key={api_key}&count={count}&thumbs=true'
    )
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            images = [
                d for d in (data if isinstance(data, list) else [data])
                if d.get('media_type') == 'image'
            ]
            return images
        logging.warning("NASA APOD API returned %s", resp.status_code)
    except Exception:
        logging.exception("_fetch_nasa_apod_images failed")
    return []


# ── On This Day channel helpers ───────────────────────────────────────────────

# Sources that the On This Day channel can pull from.
# Each entry describes a Wikipedia REST API sub-endpoint.
ON_THIS_DAY_SOURCES = [
    {
        'id':            'wikipedia_events',
        'label':         'Wikipedia \u2014 Historical Events',
        'category':      'event',
        'api_type':      'events',
        'wiki_section':  'Events',
    },
    {
        'id':            'wikipedia_births',
        'label':         'Wikipedia \u2014 Notable Births',
        'category':      'birth',
        'api_type':      'births',
        'wiki_section':  'Births',
    },
    {
        'id':            'wikipedia_deaths',
        'label':         'Wikipedia \u2014 Notable Deaths',
        'category':      'death',
        'api_type':      'deaths',
        'wiki_section':  'Deaths',
    },
]

# Module-level cache for Wikipedia On This Day events.
# Structure: { (api_type, month, day): (List[Dict], float) }
#   List[Dict] = normalised event dicts
#   float      = unix timestamp when the cache was populated
_ON_THIS_DAY_CACHE: dict = {}

# How long to keep the cache before re-fetching (6 hours)
_ON_THIS_DAY_CACHE_TTL = 6 * 3600

# Seconds each event is displayed (wall-clock aligned)
_ON_THIS_DAY_SECONDS_PER_EVENT = 30


def get_on_this_day_source_enabled(source_id):
    """Return True if the given On This Day source is enabled (default: True)."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key=?",
                      (f'on_this_day.source.{source_id}.enabled',))
            row = c.fetchone()
            if row is None:
                return True
            return row[0] != '0'
    except Exception:
        logging.exception("get_on_this_day_source_enabled failed")
        return True


def save_on_this_day_source_enabled(source_id, enabled):
    """Persist the enabled state for an On This Day source."""
    valid_ids = {s['id'] for s in ON_THIS_DAY_SOURCES}
    if source_id not in valid_ids:
        raise ValueError(f"Unknown On This Day source: {source_id!r}")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (f'on_this_day.source.{source_id}.enabled', '1' if enabled else '0'),
            )
            conn.commit()
    except Exception:
        logging.exception("save_on_this_day_source_enabled failed")
        raise


def get_on_this_day_custom_events(source_id):
    """Return the list of custom events for the given source (empty list by default).

    Each event is a dict: {'year': str, 'text': str, 'category': str}.
    """
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key=?",
                      (f'on_this_day.custom.{source_id}',))
            row = c.fetchone()
            if row is None:
                return []
            return _json.loads(row[0]) or []
    except Exception:
        logging.exception("get_on_this_day_custom_events failed")
        return []


def save_on_this_day_custom_events(source_id, events):
    """Persist custom events for the given source.

    ``events`` must be a list of dicts with at least 'year' and 'text' keys.
    """
    valid_ids = {s['id'] for s in ON_THIS_DAY_SOURCES}
    if source_id not in valid_ids:
        raise ValueError(f"Unknown On This Day source: {source_id!r}")
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (f'on_this_day.custom.{source_id}', _json.dumps(events)),
            )
            conn.commit()
    except Exception:
        logging.exception("save_on_this_day_custom_events failed")
        raise


def get_on_this_day_config():
    """Return a config dict describing all On This Day sources and their state.

    Returns a dict with:
      sources           – list of source dicts (id, label, category, enabled,
                          custom_events, wiki_url)
      seconds_per_event – how long each event is displayed
    """
    now = datetime.now(timezone.utc)
    enriched = []
    for src in ON_THIS_DAY_SOURCES:
        enriched.append({
            **src,
            'enabled':       get_on_this_day_source_enabled(src['id']),
            'custom_events': get_on_this_day_custom_events(src['id']),
            'wiki_url': (
                f"https://en.wikipedia.org/api/rest_v1/feed/onthisday"
                f"/{src['api_type']}/{now.month:02d}/{now.day:02d}"
            ),
        })
    return {
        'sources':           enriched,
        'seconds_per_event': _ON_THIS_DAY_SECONDS_PER_EVENT,
    }


def _fetch_on_this_day_from_wikipedia(api_type, month, day):
    """Fetch On This Day events from the Wikipedia REST API (with 6-hour cache).

    Returns a list of normalised event dicts:
      {'year': str, 'text': str, 'category': str}

    Returns an empty list on any error so the overlay degrades gracefully.
    """
    cache_key = (api_type, month, day)
    cached = _ON_THIS_DAY_CACHE.get(cache_key)
    now_ts = time.time()
    if cached:
        events, cached_at = cached
        if now_ts - cached_at < _ON_THIS_DAY_CACHE_TTL:
            return events

    url = (
        f"https://en.wikipedia.org/api/rest_v1/feed/onthisday"
        f"/{api_type}/{month:02d}/{day:02d}"
    )
    try:
        resp = requests.get(url, timeout=15, headers={
            'User-Agent': 'RetroIPTVGuide/1.0 (https://github.com/thehack904/RetroIPTVGuide)',
            'Accept': 'application/json',
        })
        if resp.status_code == 200:
            data = resp.json()
            raw_list = data.get(api_type, [])
            category_map = {'events': 'event', 'births': 'birth', 'deaths': 'death'}
            category = category_map.get(api_type, api_type)
            events = []
            for item in raw_list:
                year = str(item.get('year', ''))
                text = item.get('text', '').strip()
                if year and text:
                    events.append({'year': year, 'text': text, 'category': category})
            _ON_THIS_DAY_CACHE[cache_key] = (events, now_ts)
            return events
        logging.warning("Wikipedia On This Day API returned %s for %s", resp.status_code, url)
    except Exception:
        logging.exception("_fetch_on_this_day_from_wikipedia failed for %s", url)
    return []


def get_current_feed_state(feed_count):
    """Return ``(feed_index, ms_until_next_feed, elapsed_in_slot_ms)`` driven entirely by wall-clock time.

    The 30-minute block is divided equally across feeds.  All clients receive
    the same ``feed_index`` at any given moment, so the cycling happens in the
    background regardless of whether anyone is tuned to the channel.

    ``ms_until_next_feed`` is how many milliseconds remain in the current slot,
    letting clients schedule their next reload precisely at the transition point.

    ``elapsed_in_slot_ms`` is how many milliseconds have elapsed since the slot
    started, so callers can compute the exact slot-start wall-clock time.
    """
    if feed_count <= 0:
        return 0, 5 * 60 * 1000, 0
    feed_duration_s = (30 * 60) / feed_count
    now = time.time()
    time_slot = int(now / feed_duration_s)
    feed_index = time_slot % feed_count
    elapsed_in_slot_s = now % feed_duration_s
    elapsed_in_slot_ms = int(elapsed_in_slot_s * 1000)
    remaining_ms = int((feed_duration_s - elapsed_in_slot_s) * 1000)
    # Clamp to at least 1 s so clients never schedule a zero-delay reload
    _MIN_MS = 1000
    ms_until_next = max(_MIN_MS, remaining_ms)
    return feed_index, ms_until_next, elapsed_in_slot_ms



_WEATHER_CONFIG_KEYS = ('lat', 'lon', 'location_name', 'units', 'seconds_per_segment')
_WEATHER_SECONDS_PER_SEGMENT_DEFAULT = 300  # 5 minutes
_WEATHER_SEGMENT_LABELS = ('current', 'forecast', 'radar', 'alerts')

def get_weather_config():
    """Return weather configuration: lat, lon (strings), location_name, units ('F'/'C'),
    seconds_per_segment (int, default 300)."""
    result = {'lat': '', 'lon': '', 'location_name': '', 'units': 'F',
              'seconds_per_segment': str(_WEATHER_SECONDS_PER_SEGMENT_DEFAULT)}
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for key in _WEATHER_CONFIG_KEYS:
                c.execute("SELECT value FROM settings WHERE key=?", (f"weather.{key}",))
                row = c.fetchone()
                if row is not None:
                    result[key] = row[0]
    except Exception:
        logging.exception("get_weather_config failed, using defaults")
    return result

def save_weather_config(config_dict):
    """Persist weather configuration. Validates lat/lon as floats when non-empty and
    seconds_per_segment as an integer in [30, 600]."""
    cleaned = {}
    for key in _WEATHER_CONFIG_KEYS:
        val = str(config_dict.get(key, '')).strip()
        if key in ('lat', 'lon') and val:
            try:
                float(val)
            except ValueError:
                raise ValueError(f"Invalid value for {key}: {val!r}. Must be a number.")
        if key == 'units' and val not in ('F', 'C', ''):
            raise ValueError(f"Invalid units: {val!r}. Must be 'F' or 'C'.")
        if key == 'seconds_per_segment' and val:
            try:
                sps = int(val)
            except ValueError:
                raise ValueError(f"Invalid seconds_per_segment: {val!r}. Must be an integer.")
            if not (30 <= sps <= 600):
                raise ValueError(
                    f"seconds_per_segment must be between 30 and 600, got {sps}.")
        cleaned[key] = val
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for key, value in cleaned.items():
                c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          (f"weather.{key}", value))
            conn.commit()
    except ValueError:
        raise
    except Exception:
        logging.exception("save_weather_config failed")
        raise

# ─── Traffic Demo Mode ────────────────────────────────────────────────────────

# US cities with population > 1,000,000 (2024 Census estimates, city proper)
_TRAFFIC_DEMO_CITIES_SEED = [
    {'name': 'New York City', 'state': 'NY', 'lat': 40.7128, 'lon': -74.0060,  'population': 8258035},
    {'name': 'Los Angeles',   'state': 'CA', 'lat': 34.0522, 'lon': -118.2437, 'population': 3898747},
    {'name': 'Chicago',       'state': 'IL', 'lat': 41.8781, 'lon': -87.6298,  'population': 2696555},
    {'name': 'Houston',       'state': 'TX', 'lat': 29.7604, 'lon': -95.3698,  'population': 2304580},
    {'name': 'Phoenix',       'state': 'AZ', 'lat': 33.4484, 'lon': -112.0740, 'population': 1608139},
    {'name': 'Philadelphia',  'state': 'PA', 'lat': 39.9526, 'lon': -75.1652,  'population': 1550542},
    {'name': 'San Antonio',   'state': 'TX', 'lat': 29.4241, 'lon': -98.4936,  'population': 1434625},
    {'name': 'San Diego',     'state': 'CA', 'lat': 32.7157, 'lon': -117.1611, 'population': 1386932},
    {'name': 'Dallas',        'state': 'TX', 'lat': 32.7767, 'lon': -96.7970,  'population': 1304379},
    {'name': 'San Jose',      'state': 'CA', 'lat': 37.3382, 'lon': -121.8863, 'population': 1013240},
]

_TRAFFIC_DEMO_CACHE_TTL = 120   # seconds — matches overlay_refresh_seconds in VIRTUAL_CHANNELS
_TRAFFIC_DEMO_CACHE: dict = {}  # cache_key -> payload dict

# Per-city highway/arterial names used to generate realistic demo incidents
_CITY_HIGHWAYS: dict = {
    'New York City': ['I-95', 'I-278', 'I-495', 'FDR Drive', 'Belt Pkwy', 'Cross Bronx Expwy'],
    'Los Angeles':   ['I-5', 'I-10', 'I-405', 'US-101', 'SR-110', 'SR-60'],
    'Chicago':       ['I-90', 'I-94', 'I-290', 'I-55', 'I-88', 'Lake Shore Dr'],
    'Houston':       ['I-10', 'I-45', 'I-610', 'US-59', 'US-290', 'Beltway 8'],
    'Phoenix':       ['I-10', 'I-17', 'SR-51', 'SR-101', 'US-60', 'Loop 202'],
    'Philadelphia':  ['I-95', 'I-76', 'I-676', 'US-1', 'PA-309', 'Schuylkill Expwy'],
    'San Antonio':   ['I-10', 'I-35', 'I-37', 'US-281', 'Loop 410', 'Loop 1604'],
    'San Diego':     ['I-5', 'I-8', 'I-15', 'SR-94', 'SR-163', 'SR-125'],
    'Dallas':        ['I-30', 'I-35E', 'I-635', 'US-75', 'SR-114', 'Loop 12'],
    'San Jose':      ['I-280', 'I-880', 'SR-87', 'SR-101', 'US-101', 'SR-85'],
}
_CITY_HIGHWAYS_DEFAULT = ['I-10', 'I-20', 'I-40', 'US-1', 'State Hwy 1', 'Main Blvd']

_INCIDENT_TYPES = [
    ('Accident',            'red',    '⚠'),
    ('Multi-vehicle crash', 'red',    '⚠'),
    ('Stalled vehicle',     'yellow', '🚘'),
    ('Road work',           'yellow', '🚧'),
    ('Debris on road',      'yellow', '⚠'),
    ('Slow traffic',        'green',  '🐢'),
    ('Lane closure',        'yellow', '🚧'),
    ('Emergency response',  'red',    '🚨'),
]
_DIRECTIONS = ['Northbound', 'Southbound', 'Eastbound', 'Westbound']


def _generate_demo_incidents(city_name, rng, red_pct):
    """Generate a deterministic list of realistic-looking demo traffic incidents.
    The number and severity of incidents scales with the congestion level."""
    highways = _CITY_HIGHWAYS.get(city_name, _CITY_HIGHWAYS_DEFAULT)
    # Scale incident count: heavy congestion → more incidents
    max_incidents = 3 + (red_pct // 15)   # 3–7 depending on red_pct
    count = rng.randint(max(1, max_incidents - 2), max_incidents)

    incidents = []
    used_roads = set()
    for _ in range(count):
        road = rng.choice(highways)
        direction = rng.choice(_DIRECTIONS)
        inc_type, severity, icon = rng.choice(_INCIDENT_TYPES)
        # Avoid exact duplicate road+direction pairs
        key = (road, direction)
        if key in used_roads and len(used_roads) < len(highways) * 4:
            road = rng.choice([h for h in highways if h != road] or highways)
            key = (road, direction)
        used_roads.add(key)
        incidents.append({
            'title':     inc_type,
            'severity':  severity,
            'icon':      icon,
            'road':      road,
            'direction': direction,
        })
    return incidents


def _init_traffic_demo_db(conn):
    """Create and seed the traffic_demo_cities table (called from init_tuners_db)."""
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS traffic_demo_cities
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  state TEXT NOT NULL,
                  lat REAL NOT NULL,
                  lon REAL NOT NULL,
                  population INTEGER DEFAULT 0,
                  enabled INTEGER DEFAULT 1,
                  weight INTEGER DEFAULT 1,
                  created_at TEXT,
                  updated_at TEXT)''')
    conn.commit()
    c.execute("SELECT COUNT(*) FROM traffic_demo_cities")
    if c.fetchone()[0] == 0:
        now_iso = datetime.now(timezone.utc).isoformat()
        for city in _TRAFFIC_DEMO_CITIES_SEED:
            c.execute(
                "INSERT INTO traffic_demo_cities "
                "(name, state, lat, lon, population, enabled, weight, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)",
                (city['name'], city['state'], city['lat'], city['lon'],
                 city['population'], now_iso, now_iso)
            )
        conn.commit()


def get_traffic_demo_config():
    """Return traffic demo mode configuration from settings table."""
    defaults = {
        'mode':             'admin_rotation',
        'pack_size':        '10',
        'pack':             '[]',
        'rotation_seconds': '120',
    }
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for key in defaults:
                c.execute("SELECT value FROM settings WHERE key=?", (f"traffic_demo.{key}",))
                row = c.fetchone()
                if row is not None:
                    defaults[key] = row[0]
    except Exception:
        logging.exception("get_traffic_demo_config failed, using defaults")
    return defaults


def save_traffic_demo_config(cfg):
    """Persist traffic demo configuration. Raises ValueError on invalid input."""
    allowed_modes = ('admin_rotation', 'random_pack')
    mode = cfg.get('mode', 'admin_rotation')
    if mode not in allowed_modes:
        raise ValueError(f"Invalid mode: {mode!r}. Must be one of {allowed_modes}.")
    try:
        pack_size = int(cfg.get('pack_size', 10))
        if not (1 <= pack_size <= 50):
            raise ValueError("pack_size must be between 1 and 50")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid pack_size: {exc}") from exc
    try:
        rotation_secs = int(cfg.get('rotation_seconds', 120))
        if not (30 <= rotation_secs <= 3600):
            raise ValueError("rotation_seconds must be between 30 and 3600")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid rotation_seconds: {exc}") from exc
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      ('traffic_demo.mode', mode))
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      ('traffic_demo.pack_size', str(pack_size)))
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      ('traffic_demo.rotation_seconds', str(rotation_secs)))
            conn.commit()
    except ValueError:
        raise
    except Exception:
        logging.exception("save_traffic_demo_config failed")
        raise


def get_traffic_demo_cities():
    """Return all rows from traffic_demo_cities ordered by population desc."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id, name, state, lat, lon, population, enabled, weight "
                "FROM traffic_demo_cities ORDER BY population DESC"
            )
            rows = c.fetchall()
        return [
            {'id': r[0], 'name': r[1], 'state': r[2], 'lat': r[3], 'lon': r[4],
             'population': r[5], 'enabled': bool(r[6]), 'weight': int(r[7] or 1)}
            for r in rows
        ]
    except Exception:
        logging.exception("get_traffic_demo_cities failed")
        return []


def save_traffic_demo_city(city_id, enabled, weight=1):
    """Update enabled flag and weight for a single city row."""
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE traffic_demo_cities SET enabled=?, weight=?, updated_at=? WHERE id=?",
                (1 if enabled else 0, max(1, int(weight)), now_iso, int(city_id))
            )
            conn.commit()
    except Exception:
        logging.exception("save_traffic_demo_city failed for id=%s", city_id)
        raise


def set_all_traffic_demo_cities_enabled(enabled):
    """Enable or disable every city in one shot."""
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("UPDATE traffic_demo_cities SET enabled=?, updated_at=?",
                      (1 if enabled else 0, now_iso))
            conn.commit()
    except Exception:
        logging.exception("set_all_traffic_demo_cities_enabled failed")
        raise


def pick_random_traffic_demo_pack(pack_size=10):
    """Randomly select pack_size enabled cities and persist as traffic_demo.pack.
    Returns list of chosen city dicts."""
    import random as _rand
    cities = [c for c in get_traffic_demo_cities() if c['enabled']]
    if not cities:
        cities = get_traffic_demo_cities()
    chosen = _rand.sample(cities, min(pack_size, len(cities)))
    pack_ids = [c['id'] for c in chosen]
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      ('traffic_demo.pack', _json.dumps(pack_ids)))
            conn.commit()
    except Exception:
        logging.exception("pick_random_traffic_demo_pack failed")
    return chosen


def _get_congestion_distribution(hour, is_weekend=False):
    """Return (green_pct, yellow_pct, red_pct) based on local hour and day type.
    Percentages always sum to 100."""
    if is_weekend:
        if 2 <= hour < 5:
            return 90, 8, 2
        elif 9 <= hour < 12:
            return 70, 20, 10
        elif 12 <= hour < 15:
            return 65, 25, 10
        elif 17 <= hour < 20:
            return 60, 28, 12
        else:
            return 82, 13, 5
    else:
        if 2 <= hour < 5:
            return 90, 8, 2
        elif 7 <= hour < 9:
            return 50, 30, 20
        elif 12 <= hour < 14:
            return 65, 25, 10
        elif 16 <= hour < 19:
            return 45, 30, 25
        elif 22 <= hour or hour < 1:
            return 80, 15, 5
        else:
            return 75, 18, 7


def _build_traffic_demo_payload():
    """Build the demo traffic payload with deterministic city rotation and
    simulated congestion segments.  Results are cached per rotation slot so
    all viewers share the same snapshot."""
    import hashlib
    import random as _rnd

    demo_cfg = get_traffic_demo_config()
    mode = demo_cfg.get('mode', 'admin_rotation')
    rotation_seconds = max(30, int(demo_cfg.get('rotation_seconds', 120)))

    now_ts = time.time()
    time_slot = int(now_ts // rotation_seconds)

    all_cities = get_traffic_demo_cities()

    # Determine the pool to rotate through
    if mode == 'random_pack':
        try:
            pack_ids = _json.loads(demo_cfg.get('pack', '[]'))
        except Exception:
            pack_ids = []
        if pack_ids:
            id_set = {c['id'] for c in all_cities}
            pack_ids = [pid for pid in pack_ids if pid in id_set]
            cities_pool = [c for c in all_cities if c['id'] in pack_ids and c['enabled']]
        else:
            cities_pool = [c for c in all_cities if c['enabled']]
    else:  # admin_rotation
        cities_pool = [c for c in all_cities if c['enabled']]

    if not cities_pool:
        return {'no_cities': True}

    # Build a weighted list for round-robin
    weighted = []
    for city in cities_pool:
        w = max(1, city.get('weight', 1))
        weighted.extend([city] * w)

    city = weighted[time_slot % len(weighted)]

    # Cache lookup
    cache_key = f"demo:{city['id']}:{time_slot}"
    cached = _TRAFFIC_DEMO_CACHE.get(cache_key)
    if cached:
        return cached

    # Evict stale entries
    for k in list(_TRAFFIC_DEMO_CACHE):
        if k != cache_key:
            _TRAFFIC_DEMO_CACHE.pop(k, None)

    # Time-of-day congestion distribution
    now_dt = datetime.now(timezone.utc)
    hour = now_dt.hour
    is_weekend = now_dt.weekday() >= 5
    green_pct, yellow_pct, red_pct = _get_congestion_distribution(hour, is_weekend)

    # Congestion level label
    if red_pct >= 20:
        congestion_level = 'Heavy'
    elif red_pct >= 10 or yellow_pct >= 25:
        congestion_level = 'Moderate'
    else:
        congestion_level = 'Light'

    # Generate road segments deterministically using a seeded RNG
    # MD5 is used purely for deterministic seeding (not for security).
    # All viewers at the same time slot see the same road-color snapshot.
    seed_hex = hashlib.md5(f"{city['id']}:{time_slot}".encode()).hexdigest()[:8]
    rng = _rnd.Random(int(seed_hex, 16))

    NUM_SEGMENTS = 24
    colors = ['green'] * green_pct + ['yellow'] * yellow_pct + ['red'] * red_pct
    segments = [{'id': f'seg_{i}', 'color': rng.choice(colors)}
                for i in range(1, NUM_SEGMENTS + 1)]

    # Actual percentages from generated segments
    total = len(segments)
    actual_green  = sum(1 for s in segments if s['color'] == 'green')
    actual_yellow = sum(1 for s in segments if s['color'] == 'yellow')
    actual_red    = sum(1 for s in segments if s['color'] == 'red')

    # Generate deterministic demo incidents (scaled to congestion level)
    incidents = _generate_demo_incidents(city['name'], rng, red_pct)

    payload = {
        'updated': now_dt.isoformat(),
        'city': {
            'id':    city['id'],
            'name':  city['name'],
            'state': city['state'],
            'lat':   city['lat'],
            'lon':   city['lon'],
        },
        'time_slot': time_slot,
        'summary': {
            'congestion_level': congestion_level,
            'green_percent':    round(actual_green  * 100 / total),
            'yellow_percent':   round(actual_yellow * 100 / total),
            'red_percent':      round(actual_red    * 100 / total),
            'incident_count':   len(incidents),
        },
        'incidents': incidents,
        'segments':  segments,
        'demo_mode': True,
    }
    _TRAFFIC_DEMO_CACHE[cache_key] = payload
    return payload


# ─── Road geometry (Overpass API) ────────────────────────────────────────────

# Roads are cached per city (long TTL — road geometry rarely changes).
_ROADS_CACHE: dict = {}   # city_id -> GeoJSON FeatureCollection dict
_ROADS_CACHE_TTL = 86400  # 24 hours — in-memory hot cache
_ROADS_DISK_TTL  = 2_592_000  # 30 days — disk cache; road geometry barely changes
_ROADS_CACHE_TIME: dict = {}  # city_id -> timestamp of last fetch
_OVERPASS_PREWARM_STAGGER_S = 12  # seconds between per-city Overpass requests at startup
_OVERPASS_MAX_RETRIES = 3         # retry attempts on 429 / transient errors
_OVERPASS_RETRY_BACKOFF_S = 10    # initial back-off in seconds (doubles each retry)
_OVERPASS_SEMAPHORE = threading.Semaphore(1)  # at most one live Overpass request at a time


def _roads_cache_path(city_id: int) -> str:
    """Return the absolute path of the on-disk cache file for a given city.

    The path is validated against ROADS_CACHE_DIR to prevent path traversal
    attacks where a malicious city_id could escape the cache directory.
    """
    # Explicitly convert to int so that the filename component is a plain
    # integer with no path-separator or traversal characters.
    city_id_int = int(city_id)
    safe_dir = os.path.normpath(os.path.abspath(ROADS_CACHE_DIR))
    path = os.path.normpath(os.path.join(safe_dir, f"city_{city_id_int}.json"))
    if not path.startswith(safe_dir + os.sep) and path != safe_dir:
        raise ValueError(f"city_id {city_id_int!r} would escape the cache directory")
    return path


def _load_roads_from_disk(city_id: int) -> dict | None:
    """Load GeoJSON from disk cache if the file exists and is not stale.
    Returns the GeoJSON dict on success, None if missing or expired."""
    try:
        path = _roads_cache_path(city_id)
        if not os.path.isfile(path):
            return None
        age = time.time() - os.path.getmtime(path)
        if age > _ROADS_DISK_TTL:
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return _json.load(fh)
    except ValueError:
        return None
    except Exception:
        logging.warning("_load_roads_from_disk: failed to read cache for city_id=%s", city_id,
                        exc_info=True)
        return None


def _save_roads_to_disk(city_id: int, geojson: dict) -> None:
    """Persist GeoJSON to disk so restarts don't need to re-fetch from Overpass."""
    try:
        path = _roads_cache_path(city_id)
    except ValueError:
        logging.warning("_save_roads_to_disk: refusing unsafe path for city_id=%s", city_id)
        return
    try:
        os.makedirs(ROADS_CACHE_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump(geojson, fh)
    except Exception:
        logging.warning("_save_roads_to_disk: failed to write cache for city_id=%s", city_id,
                        exc_info=True)


def _load_bundled_roads(city_name: str) -> dict | None:
    """Load GeoJSON from the bundled static file shipped with the repository.

    These files are pre-downloaded via ``scripts/download_road_data.py`` and
    committed to ``static/data/roads/<cityslug>.geojson`` so the app can serve
    road geometry without any external network connection.

    Returns the GeoJSON dict when a non-empty bundled file is found, otherwise
    returns None so the caller can fall back to the Overpass API.
    """
    slug = _city_slug(city_name)
    path = os.path.join(ROADS_BUNDLED_DIR, f"{slug}.geojson")
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        # Only use the bundled file if it contains actual road features
        if data.get("features"):
            return data
        return None
    except Exception:
        logging.warning("_load_bundled_roads: failed to read bundled file for %s", city_name,
                        exc_info=True)
        return None

# Most-recent Overpass API error recorded at runtime. Populated by
# _fetch_overpass_roads on any HTTP error (including 429 rate-limit and
# 504 gateway timeout) and cleared after a successful fetch. Exposed to
# the Admin Diagnostics external-services check so that rate-limiting
# failures are visible in the health panel even though the /api/status
# probe may return 200 OK.
_OVERPASS_LAST_ERROR: dict = {}  # keys: status_code, lat, lon, ts, message


def _fetch_overpass_roads(lat: float, lon: float, radius_m: int = 80_467) -> dict:
    """Fetch major road geometry from the Overpass API (free, no API key).
    Default radius is 80_467 m (50 miles) to match the zoom-10 map view.
    Only motorway and trunk-class roads are fetched; at this scale primary/
    secondary roads would return thousands of segments across the viewport.
    Returns a GeoJSON FeatureCollection with LineString features for each road way.
    Retries up to _OVERPASS_MAX_RETRIES times on 429 / transient errors,
    honouring the Retry-After response header when present.
    _OVERPASS_SEMAPHORE ensures at most one live Overpass request runs at a time
    across all threads, preventing concurrent requests that trigger rate-limits.
    On any HTTP error (including 429 Too Many Requests and 504 Gateway Timeout)
    records the failure in _OVERPASS_LAST_ERROR for the Admin Diagnostics health
    check.  On permanent failure returns an empty FeatureCollection."""
    global _OVERPASS_LAST_ERROR  # noqa: PLW0603
    query = (
        f"[out:json][timeout:60];"
        f"(way[\"highway\"~\"^(motorway|trunk)$\"]"
        f"(around:{radius_m},{lat},{lon}););"
        f"out body;>;out skel qt;"
    )
    with _OVERPASS_SEMAPHORE:
        backoff = _OVERPASS_RETRY_BACKOFF_S
        for attempt in range(_OVERPASS_MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    "https://overpass-api.de/api/interpreter",
                    data={"data": query},
                    timeout=65,
                    headers={"User-Agent": "RetroIPTVGuide/1.0 (traffic demo overlay)"},
                )
                if resp.status_code == 429 and attempt < _OVERPASS_MAX_RETRIES:
                    wait = int(resp.headers.get("Retry-After", backoff))
                    logging.warning(
                        "_fetch_overpass_roads: 429 rate-limited (attempt %d/%d),"
                        " sleeping %ds before retry",
                        attempt + 1, _OVERPASS_MAX_RETRIES, wait,
                    )
                    time.sleep(wait)
                    backoff *= 2
                    continue
                resp.raise_for_status()
                # Successful fetch — clear any previously recorded error so that the
                # diagnostics check reflects the current (healthy) state.
                _OVERPASS_LAST_ERROR = {}
                return resp.json()
            except requests.exceptions.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if attempt < _OVERPASS_MAX_RETRIES and status_code not in (429,):
                    logging.warning(
                        "_fetch_overpass_roads: HTTP error %s (attempt %d/%d),"
                        " retrying in %ds",
                        status_code, attempt + 1, _OVERPASS_MAX_RETRIES, backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                if status_code == 429:
                    logging.warning(
                        "_fetch_overpass_roads rate-limited (429 Too Many Requests) "
                        "for lat=%s lon=%s — road overlay will be empty until rate limit lifts",
                        lat, lon,
                    )
                else:
                    logging.exception("_fetch_overpass_roads failed for lat=%s lon=%s", lat, lon)
                _OVERPASS_LAST_ERROR = {
                    "status_code": status_code,
                    "lat": lat,
                    "lon": lon,
                    "ts": time.time(),
                    "message": str(exc),
                }
            except Exception:
                if attempt < _OVERPASS_MAX_RETRIES:
                    logging.warning(
                        "_fetch_overpass_roads: transient error (attempt %d/%d),"
                        " retrying in %ds",
                        attempt + 1, _OVERPASS_MAX_RETRIES, backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                logging.exception(
                    "_fetch_overpass_roads failed for lat=%s lon=%s", lat, lon
                )
                _OVERPASS_LAST_ERROR = {
                    "status_code": None,
                    "lat": lat,
                    "lon": lon,
                    "ts": time.time(),
                    "message": "network or timeout error",
                }
        return {"elements": []}


def _overpass_to_geojson(raw: dict) -> dict:
    """Convert Overpass JSON response to a GeoJSON FeatureCollection.
    Only LineString features are produced (one per road way)."""
    nodes: dict = {}
    ways: list  = []
    for el in raw.get("elements", []):
        t = el.get("type")
        if t == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif t == "way":
            ways.append(el)

    features = []
    for way in ways:
        coords = [nodes[nid] for nid in way.get("nodes", []) if nid in nodes]
        if len(coords) < 2:
            continue
        tags = way.get("tags", {})
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "way_id":  way["id"],
                "name":    tags.get("name", ""),
                "highway": tags.get("highway", ""),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def get_traffic_demo_roads(city_id: int) -> dict:
    """Return cached road GeoJSON for a city, fetching from Overpass only when needed.

    Lookup order:
      1. In-memory cache  (hot, 24 h TTL)
      2. Disk cache       (persistent across restarts, 30 day TTL)
      3. Bundled static data (ships with the repo; no network required)
      4. Overpass API     (network call — only when no valid cached copy exists)

    After a successful Overpass fetch the result is saved to disk so that
    subsequent app restarts never need to call the API for already-fetched cities.
    """
    now_ts = time.time()
    cached_at = _ROADS_CACHE_TIME.get(city_id, 0)
    if city_id in _ROADS_CACHE and (now_ts - cached_at) < _ROADS_CACHE_TTL:
        return _ROADS_CACHE[city_id]

    # 2. Try disk cache before making a network call
    disk_geojson = _load_roads_from_disk(city_id)
    if disk_geojson is not None:
        _ROADS_CACHE[city_id] = disk_geojson
        _ROADS_CACHE_TIME[city_id] = now_ts
        return disk_geojson

    # 3. Look up city coordinates from DB (needed for both bundled lookup and Overpass)
    try:
        cities = get_traffic_demo_cities()
        city = next((c for c in cities if c["id"] == city_id), None)
        if city is None:
            return {"type": "FeatureCollection", "features": []}
    except Exception:
        logging.exception("get_traffic_demo_roads: city lookup failed for id=%s", city_id)
        return {"type": "FeatureCollection", "features": []}

    # 3. Try bundled static GeoJSON files (pre-downloaded via scripts/download_road_data.py)
    bundled = _load_bundled_roads(city["name"])
    if bundled is not None:
        logging.info("get_traffic_demo_roads: using bundled data for %s", city["name"])
        _ROADS_CACHE[city_id] = bundled
        _ROADS_CACHE_TIME[city_id] = now_ts
        return bundled

    # 4. Last resort: fetch from Overpass API (requires network access)
    raw = _fetch_overpass_roads(city["lat"], city["lon"])
    geojson = _overpass_to_geojson(raw)
    _ROADS_CACHE[city_id] = geojson
    _ROADS_CACHE_TIME[city_id] = now_ts
    # Persist to disk so future restarts skip the Overpass call
    if geojson["features"]:
        _save_roads_to_disk(city_id, geojson)
    return geojson


def _prewarm_roads_cache() -> None:
    """Background thread: fetch road geometry for every enabled city so the
    Overpass data is cached before any user rotates to that city.

    Local sources (memory cache, disk cache, bundled static files) are checked
    first for every city.  The inter-request stagger delay is only inserted
    immediately before cities that genuinely need a live Overpass call, so
    deployments with pre-downloaded bundled data complete the prewarm instantly
    with zero Overpass requests."""
    try:
        cities = [c for c in get_traffic_demo_cities() if c.get("enabled")]
    except Exception:
        logging.exception("_prewarm_roads_cache: could not load city list")
        return
    last_overpass_at = 0.0
    for city in cities:
        cid = city["id"]
        # Determine upfront whether a live Overpass call will be needed by
        # checking every local source in priority order.
        needs_overpass = (
            cid not in _ROADS_CACHE
            and _load_roads_from_disk(cid) is None
            and _load_bundled_roads(city["name"]) is None
        )
        if needs_overpass:
            # Only stagger when a real Overpass request is coming up.
            elapsed   = time.time() - last_overpass_at
            remaining = _OVERPASS_PREWARM_STAGGER_S - elapsed
            if remaining > 0:
                time.sleep(remaining)
        try:
            get_traffic_demo_roads(cid)
            logging.info("_prewarm_roads_cache: cached roads for %s", city["name"])
        except Exception:
            logging.exception("_prewarm_roads_cache: failed for city id=%s", cid)
        if needs_overpass:
            last_overpass_at = time.time()


# ─── Static basemap PNGs (OSM tile stitching) ─────────────────────────────────

_BASEMAP_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'static', 'maps', 'traffic_demo')
_BASEMAP_ZOOM = 10       # OSM zoom level — matches traffic.html BASEMAP_ZOOM
_BASEMAP_W    = 1280     # output width  — matches traffic.html BASEMAP_W
_BASEMAP_H    = 720      # output height — matches traffic.html BASEMAP_H
_TILE_SIZE    = 256      # standard OSM tile size in pixels
_OSM_TILE_UA  = "RetroIPTVGuide/1.0 (traffic demo basemap; see github.com/thehack904/RetroIPTVGuide)"

# Tile server templates tried in order.  Multiple mirrors improve reliability
# from cloud/datacenter hosts where tile.openstreetmap.org may rate-limit.
_TILE_SERVERS = [
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
    "https://b.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
    "https://c.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
]


def _city_slug(name: str) -> str:
    """Convert a city name to the lowercase alphanumeric slug used for PNG filenames.
    Must match the JavaScript citySlug() function in traffic.html."""
    return ''.join(c for c in name.lower() if c.isalnum())


def _generate_basemap_png(lat: float, lon: float, out_path: str) -> bool:
    """Stitch OSM tiles into a _BASEMAP_W x _BASEMAP_H PNG centred on lat/lon.

    Returns True on success, False if Pillow is unavailable or all tiles fail.
    The file is written atomically (temp file → rename) so a half-written PNG
    is never served to the browser.
    """
    if not _PILLOW_AVAILABLE:
        return False

    zoom = _BASEMAP_ZOOM
    n    = 2 ** zoom

    # Fractional tile coordinates for the centre point
    cx_f = (lon + 180.0) / 360.0 * n
    lat_rad = _math.radians(lat)
    cy_f = (1.0 - _math.asinh(_math.tan(lat_rad)) / _math.pi) / 2.0 * n

    cx_tile = int(cx_f)
    cy_tile = int(cy_f)
    off_x   = (cx_f - cx_tile) * _TILE_SIZE   # pixel offset within centre tile
    off_y   = (cy_f - cy_tile) * _TILE_SIZE

    # Number of extra tiles needed on each side of the centre tile
    half_w = _BASEMAP_W / 2
    half_h = _BASEMAP_H / 2
    tiles_left  = _math.ceil((half_w - (_TILE_SIZE - off_x)) / _TILE_SIZE) + 1
    tiles_right = _math.ceil((half_w - off_x)               / _TILE_SIZE) + 1
    tiles_up    = _math.ceil((half_h - (_TILE_SIZE - off_y)) / _TILE_SIZE) + 1
    tiles_down  = _math.ceil((half_h - off_y)               / _TILE_SIZE) + 1

    x0 = cx_tile - tiles_left
    y0 = cy_tile - tiles_up
    x1 = cx_tile + tiles_right
    y1 = cy_tile + tiles_down
    cols = x1 - x0 + 1
    rows = y1 - y0 + 1

    canvas = _PilImage.new("RGB", (cols * _TILE_SIZE, rows * _TILE_SIZE))
    sess   = requests.Session()
    sess.headers.update({"User-Agent": _OSM_TILE_UA})
    any_ok = False
    server_idx = 0  # round-robin across tile servers to spread load

    for row_i, ty in enumerate(range(y0, y1 + 1)):
        for col_i, tx in enumerate(range(x0, x1 + 1)):
            tx_c = max(0, min(n - 1, tx))
            ty_c = max(0, min(n - 1, ty))
            fetched = False
            for attempt in range(len(_TILE_SERVERS) * 2):
                srv = _TILE_SERVERS[server_idx % len(_TILE_SERVERS)]
                url = srv.format(z=zoom, x=tx_c, y=ty_c)
                try:
                    resp = sess.get(url, timeout=15)
                    resp.raise_for_status()
                    tile = _PilImage.open(_io.BytesIO(resp.content)).convert("RGB")
                    canvas.paste(tile, (col_i * _TILE_SIZE, row_i * _TILE_SIZE))
                    any_ok = True
                    fetched = True
                    time.sleep(0.15)   # respect tile server fair-use policy
                    break
                except Exception as exc:
                    logging.debug("_generate_basemap_png: %s tile %s/%s attempt %s failed: %s",
                                  srv, tx_c, ty_c, attempt + 1, exc)
                    server_idx += 1    # try next server on next attempt
                    if attempt < len(_TILE_SERVERS) * 2 - 1:
                        time.sleep(min(2 ** (attempt % len(_TILE_SERVERS)), 30))
            if not fetched:
                logging.warning("_generate_basemap_png: all servers failed for tile %s/%s", tx_c, ty_c)
            server_idx += 1  # distribute load across servers

    if not any_ok:
        return False

    # Crop to exact output size, centred on the requested coordinates
    centre_x = (cx_tile - x0) * _TILE_SIZE + off_x
    centre_y = (cy_tile - y0) * _TILE_SIZE + off_y
    left   = int(centre_x - half_w)
    top    = int(centre_y - half_h)
    cropped = canvas.crop((left, top, left + _BASEMAP_W, top + _BASEMAP_H))

    # Write atomically
    os.makedirs(_BASEMAP_DIR, exist_ok=True)
    tmp_path = out_path + ".tmp"
    cropped.save(tmp_path, "PNG", optimize=True)
    os.replace(tmp_path, out_path)
    return True


def _generate_placeholder_basemap_png(city_name: str, out_path: str) -> bool:
    """Generate a map-like placeholder PNG using Pillow only (no network access).

    Creates a 1280×720 image with a street-map-inspired colour scheme — a
    light-grey land base, subtle grid lines for roads, and the city name
    centred in the image.  This runs instantly at startup so the traffic
    overlay always has a background, even when external tile servers are
    unreachable.

    Returns True on success, False if Pillow is unavailable.
    """
    if not _PILLOW_AVAILABLE:
        return False

    from PIL import ImageDraw, ImageFont

    w, h = _BASEMAP_W, _BASEMAP_H

    # OSM-inspired colour palette
    BG_LAND    = (242, 239, 233)   # warm off-white (OSM land)
    GRID_MAJOR = (200, 196, 187)   # subtle grey grid (arterial roads)
    GRID_MINOR = (220, 216, 208)   # lighter minor grid
    LABEL_CLR  = (130, 120, 100)   # muted brown-grey for city name

    img  = _PilImage.new("RGB", (w, h), BG_LAND)
    draw = ImageDraw.Draw(img)

    # Minor grid (~city blocks, ~64 px apart)
    for x in range(0, w, 64):
        draw.line([(x, 0), (x, h)], fill=GRID_MINOR, width=1)
    for y in range(0, h, 64):
        draw.line([(0, y), (w, y)], fill=GRID_MINOR, width=1)

    # Major grid (~arterial roads, ~256 px apart)
    for x in range(0, w, 256):
        draw.line([(x, 0), (x, h)], fill=GRID_MAJOR, width=2)
    for y in range(0, h, 256):
        draw.line([(0, y), (w, y)], fill=GRID_MAJOR, width=2)

    # City name label centred on the image
    _font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",   # Debian/Ubuntu
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",             # Fedora/RHEL
        "/System/Library/Fonts/Helvetica.ttc",                     # macOS
        "C:/Windows/Fonts/arial.ttf",                              # Windows
    ]
    font = None
    for _fp in _font_candidates:
        try:
            font = ImageFont.truetype(_fp, 36)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    label = city_name
    bbox  = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) // 2, (h - th) // 2), label, fill=LABEL_CLR, font=font)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp_path = out_path + ".tmp"
    img.save(tmp_path, "PNG", optimize=True)
    os.replace(tmp_path, out_path)
    return True


def _prewarm_basemaps() -> None:
    """Background thread: generate missing basemap PNGs for all seed cities.

    Runs once at startup.  Already-present files are skipped so the roads
    and basemap pre-warm threads don't conflict on subsequent restarts.

    Strategy (in order):
    1. Try to download real OSM tiles via _generate_basemap_png.
    2. If all tile servers fail (e.g. datacenter IP is blocked), fall back to
       _generate_placeholder_basemap_png which uses Pillow only and works
       instantly with no network access.  This guarantees every city gets a
       usable basemap at startup regardless of tile-server availability.
    """
    if not _PILLOW_AVAILABLE:
        logging.info("_prewarm_basemaps: Pillow not available, skipping basemap generation")
        return

    os.makedirs(_BASEMAP_DIR, exist_ok=True)
    for city in _TRAFFIC_DEMO_CITIES_SEED:
        slug     = _city_slug(city['name'])
        out_path = os.path.join(_BASEMAP_DIR, f"{slug}.png")
        if os.path.isfile(out_path):
            logging.debug("_prewarm_basemaps: %s already exists, skipping", slug)
            continue
        logging.info("_prewarm_basemaps: generating basemap for %s …", city['name'])
        try:
            ok = _generate_basemap_png(city['lat'], city['lon'], out_path)
            if ok:
                logging.info("_prewarm_basemaps: saved real OSM basemap for %s", slug)
                time.sleep(1)
                continue
        except Exception:
            logging.exception("_prewarm_basemaps: tile download exception for %s", city['name'])

        # Tile download failed — generate a placeholder so the page always works
        logging.info("_prewarm_basemaps: tile servers unavailable, using placeholder for %s",
                     city['name'])
        try:
            ok = _generate_placeholder_basemap_png(city['name'], out_path)
            if ok:
                logging.info("_prewarm_basemaps: saved placeholder basemap for %s", slug)
            else:
                logging.warning("_prewarm_basemaps: placeholder also failed for %s", city['name'])
        except Exception:
            logging.exception("_prewarm_basemaps: placeholder exception for %s", city['name'])


def get_channel_music_file(tvg_id):
    """Return the selected audio filename (basename only) for a virtual channel, or ''."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key=?",
                      (f"overlay.{tvg_id}.music_file",))
            row = c.fetchone()
            return row[0] if row else ''
    except Exception:
        logging.exception("get_channel_music_file failed")
        return ''

def save_channel_music_file(tvg_id, filename):
    """Persist the selected audio filename for a virtual channel.
    Pass '' to clear. Validates that the filename exists in AUDIO_UPLOAD_DIR."""
    filename = str(filename).strip()
    if filename:
        safe = secure_filename(filename)
        if safe != filename or not safe:
            raise ValueError(f"Invalid audio filename: {filename!r}")
        ext = safe.rsplit('.', 1)[-1].lower() if '.' in safe else ''
        if ext not in _ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError(f"Unsupported audio type: {ext!r}")
        target = os.path.join(AUDIO_UPLOAD_DIR, safe)
        if not os.path.isfile(target):
            raise ValueError(f"Audio file not found: {safe!r}")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      (f"overlay.{tvg_id}.music_file", filename))
            conn.commit()
    except ValueError:
        raise
    except Exception:
        logging.exception("save_channel_music_file failed")
        raise

def list_audio_files():
    """Return a sorted list of uploaded audio filenames in AUDIO_UPLOAD_DIR."""
    try:
        os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)
        return sorted(
            f for f in os.listdir(AUDIO_UPLOAD_DIR)
            if os.path.isfile(os.path.join(AUDIO_UPLOAD_DIR, f))
            and '.' in f
            and f.rsplit('.', 1)[-1].lower() in _ALLOWED_AUDIO_EXTENSIONS
        )
    except Exception:
        logging.exception("list_audio_files failed")
        return []

# Default logo paths for each virtual channel (used to restore after a reset)
_DEFAULT_CHANNEL_LOGOS = {
    'virtual.news':         '/static/logos/virtual/news.svg',
    'virtual.weather':      '/static/logos/virtual/weather.svg',
    'virtual.status':       '/static/logos/virtual/status.svg',
    'virtual.traffic':      '/static/logos/virtual/traffic.svg',
    'virtual.updates':      '/static/logos/virtual/updates.svg',
    'virtual.sports':       '/static/logos/virtual/sports.svg',
    'virtual.nasa':         '/static/logos/virtual/nasa.svg',
    'virtual.channel_mix':  '/static/logos/virtual/channel_mix.svg',
    'virtual.on_this_day':  '/static/logos/virtual/on_this_day.svg',
}

# Icon pack logo paths (stored in static/logos/virtual/icon_pack/)
_ICON_PACK_LOGOS = {
    'virtual.news':         '/static/logos/virtual/icon_pack/news.png',
    'virtual.weather':      '/static/logos/virtual/icon_pack/weather.png',
    'virtual.status':       '/static/logos/virtual/icon_pack/status.png',
    'virtual.traffic':      '/static/logos/virtual/icon_pack/traffic.png',
    'virtual.updates':      '/static/logos/virtual/icon_pack/updates.png',
    'virtual.sports':       '/static/logos/virtual/icon_pack/sports.png',
    'virtual.nasa':         '/static/logos/virtual/icon_pack/nasa.png',
    'virtual.channel_mix':  '/static/logos/virtual/icon_pack/channel_mix.png',
    'virtual.on_this_day':  '/static/logos/virtual/icon_pack/on_this_day.png',
}


def get_use_icon_pack():
    """Return True if the icon pack is enabled for virtual channel logos."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='virtual_channel.use_icon_pack'")
            row = c.fetchone()
            return row[0] == '1' if row else False
    except Exception:
        logging.exception("get_use_icon_pack failed")
        return False


def set_use_icon_pack(enabled):
    """Persist the icon pack preference (True = use icon pack, False = use default SVG logos)."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      ('virtual_channel.use_icon_pack', '1' if enabled else '0'))
            conn.commit()
    except Exception:
        logging.exception("set_use_icon_pack failed")
        raise


def _resolve_channel_logo(tvg_id, default_logo, custom_filename, use_icon_pack):
    """Return the effective logo URL for a channel, applying priority:
    1. User-uploaded custom logo (highest priority)
    2. Icon pack logo (when enabled and file exists on disk)
    3. Default SVG logo (fallback)
    """
    if custom_filename:
        return f'/static/logos/virtual/{custom_filename}'
    if use_icon_pack:
        pack_url = _ICON_PACK_LOGOS.get(tvg_id)
        if pack_url:
            filename = pack_url.rsplit('/', 1)[-1]
            abs_path = os.path.join(ICON_PACK_DIR, filename)
            if os.path.isfile(abs_path):
                return pack_url
    return default_logo


def get_channel_custom_logo(tvg_id):
    """Return the custom logo filename for a virtual channel, or '' if none is set."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key=?", (f"channel.{tvg_id}.logo",))
            row = c.fetchone()
            return row[0] if row else ''
    except Exception:
        logging.exception("get_channel_custom_logo failed")
        return ''

def save_channel_custom_logo(tvg_id, filename):
    """Persist a custom logo filename for a virtual channel.
    Pass '' to clear.  Validates that the file exists in LOGO_UPLOAD_DIR."""
    filename = str(filename).strip()
    if filename:
        safe = secure_filename(filename)
        if safe != filename or not safe:
            raise ValueError(f"Invalid logo filename: {filename!r}")
        ext = safe.rsplit('.', 1)[-1].lower() if '.' in safe else ''
        if ext not in _ALLOWED_LOGO_EXTENSIONS:
            raise ValueError(f"Unsupported logo type: {ext!r}")
        target = os.path.join(LOGO_UPLOAD_DIR, safe)
        real_target = os.path.realpath(target)
        real_dir = os.path.realpath(LOGO_UPLOAD_DIR)
        if os.path.commonpath([real_dir, real_target]) != real_dir:
            raise ValueError(f"Invalid logo filename: {filename!r}")
        if not os.path.isfile(target):
            raise ValueError(f"Logo file not found: {safe!r}")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      (f"channel.{tvg_id}.logo", filename))
            conn.commit()
    except ValueError:
        raise
    except Exception:
        logging.exception("save_channel_custom_logo failed")
        raise


# icon_key maps to SVG/emoji used in the weather template
_WMO_MAP = {
    0:  ('Sunny',           'sunny'),
    1:  ('Mostly Clear',    'sunny'),
    2:  ('Partly Cloudy',   'partly_cloudy'),
    3:  ('Overcast',        'cloudy'),
    45: ('Foggy',           'foggy'),
    48: ('Icy Fog',         'foggy'),
    51: ('Light Drizzle',   'drizzle'),
    53: ('Drizzle',         'drizzle'),
    55: ('Heavy Drizzle',   'drizzle'),
    61: ('Light Rain',      'rain'),
    63: ('Rain',            'rain'),
    65: ('Heavy Rain',      'rain'),
    71: ('Light Snow',      'snow'),
    73: ('Snow',            'snow'),
    75: ('Heavy Snow',      'snow'),
    77: ('Snow Grains',     'snow'),
    80: ('Showers',         'showers'),
    81: ('Showers',         'showers'),
    82: ('Heavy Showers',   'showers'),
    85: ('Snow Showers',    'snow'),
    86: ('Heavy Snow Shwr', 'snow'),
    95: ('T-Storms',        'thunderstorm'),
    96: ('T-Storms',        'thunderstorm'),
    99: ('T-Storms',        'thunderstorm'),
}

def _wmo_label(code):
    return _WMO_MAP.get(code, ('Unknown', 'cloudy'))[0]

def _wmo_icon(code):
    return _WMO_MAP.get(code, ('Unknown', 'cloudy'))[1]

# Daytime icon keys that have a distinct night variant in the weather template
_NIGHT_ICON_MAP = {
    'sunny':         'partly_cloudy_night',
    'partly_cloudy': 'partly_cloudy_night',
    'cloudy':        'cloudy_night',
}

def _to_night_icon(day_icon):
    """Return the night variant of a day icon key, or the original if no variant exists."""
    return _NIGHT_ICON_MAP.get(day_icon, day_icon)

_WIND_DIRS = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW']

def _wind_dir(degrees):
    try:
        return _WIND_DIRS[round(float(degrees) / 22.5) % 16]
    except Exception:
        return ''

_RADAR_URL_CONUS = (
    "https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_raw/ows"
    "?service=WMS&version=1.3.0&request=GetMap&layers=conus_bref_raw"
    "&bbox=-126,24,-66,50&width=800&height=450"
    "&crs=EPSG:4326&format=image/png"
)
_RADAR_LAT_OFFSET = 5.0  # degrees north/south from centre for regional radar view
_RADAR_LON_OFFSET = 8.0  # degrees east/west from centre for regional radar view

def _build_radar_url(lat, lon):
    """Return a NOAA WMS radar PNG URL centred on lat/lon (±_RADAR_LAT_OFFSET° lat,
    ±_RADAR_LON_OFFSET° lon), or the CONUS-wide URL when no coordinates are available."""
    if not lat or not lon:
        return _RADAR_URL_CONUS
    try:
        flat, flon = float(lat), float(lon)
        min_lat = round(flat - _RADAR_LAT_OFFSET, 2)
        max_lat = round(flat + _RADAR_LAT_OFFSET, 2)
        min_lon = round(flon - _RADAR_LON_OFFSET, 2)
        max_lon = round(flon + _RADAR_LON_OFFSET, 2)
        return (
            "https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_raw/ows"
            f"?service=WMS&version=1.3.0&request=GetMap&layers=conus_bref_raw"
            f"&bbox={min_lon},{min_lat},{max_lon},{max_lat}"
            f"&width=800&height=450&crs=EPSG:4326&format=image/png"
        )
    except (TypeError, ValueError):
        return _RADAR_URL_CONUS


def _fetch_open_meteo(lat, lon, units):
    """Fetch current + hourly + daily weather from open-meteo. Returns dict or None on failure."""
    temp_unit = 'fahrenheit' if units != 'C' else 'celsius'
    wind_unit = 'mph' if units != 'C' else 'kmh'
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        "weather_code,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,weather_code"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code,sunrise,sunset"
        f"&temperature_unit={temp_unit}&wind_speed_unit={wind_unit}"
        "&forecast_days=5&timezone=auto"
    )
    try:
        resp = requests.get(url, timeout=10, headers={'User-Agent': 'RetroIPTVGuide/1.0'})
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logging.exception("_fetch_open_meteo failed for lat=%s lon=%s", lat, lon)
        return None

def _build_weather_payload(cfg):
    """Build the full weather API payload from open-meteo data or a stub when unconfigured."""
    now_utc = datetime.now(timezone.utc)
    updated_str = now_utc.isoformat()  # ISO 8601 UTC; browsers convert to local time
    lat = cfg.get('lat', '')
    lon = cfg.get('lon', '')
    location_name = cfg.get('location_name') or 'Local Weather'
    units = cfg.get('units') or 'F'
    deg = '°F' if units != 'C' else '°C'

    raw = None
    if lat and lon:
        raw = _fetch_open_meteo(lat, lon, units)

    if raw:
        cur = raw.get('current', {})
        cur_vars = raw.get('current_units', {})
        hourly = raw.get('hourly', {})
        daily = raw.get('daily', {})

        temp = cur.get('temperature_2m')
        feels = cur.get('apparent_temperature')
        humidity = cur.get('relative_humidity_2m')
        wcode = cur.get('weather_code', 0)
        wind_spd = cur.get('wind_speed_10m')
        wind_deg = cur.get('wind_direction_10m', 0)
        wind_str = f"{_wind_dir(wind_deg)} {round(wind_spd)} {cur_vars.get('wind_speed_10m','mph')}" if wind_spd is not None else ''

        now_info = {
            'temp': round(temp) if temp is not None else None,
            'condition': _wmo_label(wcode),
            'humidity': round(humidity) if humidity is not None else None,
            'wind': wind_str,
            'feels_like': round(feels) if feels is not None else None,
            'icon': _wmo_icon(wcode),
        }

        # Today's forecast: morning=6-11, afternoon=12-17, evening=18-22
        h_times = hourly.get('time', [])
        h_temps = hourly.get('temperature_2m', [])
        h_wcodes = hourly.get('weather_code', [])
        today_str = now_utc.strftime('%Y-%m-%d')

        def _period_avg(start_h, end_h):
            temps, codes = [], []
            for i, t in enumerate(h_times):
                if t.startswith(today_str):
                    try:
                        h = int(t[11:13])
                    except Exception:
                        continue
                    if start_h <= h < end_h:
                        if i < len(h_temps) and h_temps[i] is not None:
                            temps.append(h_temps[i])
                        if i < len(h_wcodes) and h_wcodes[i] is not None:
                            codes.append(h_wcodes[i])
            avg_t = round(sum(temps) / len(temps)) if temps else None
            dominant = max(set(codes), key=codes.count) if codes else 0
            return avg_t, dominant

        m_temp, m_code = _period_avg(6, 12)
        a_temp, a_code = _period_avg(12, 18)
        e_temp, e_code = _period_avg(18, 23)

        today_forecast = [
            {'label': 'MORNING',   'temp': m_temp, 'condition': _wmo_label(m_code), 'icon': _wmo_icon(m_code)},
            {'label': 'AFTERNOON', 'temp': a_temp, 'condition': _wmo_label(a_code), 'icon': _wmo_icon(a_code)},
            {'label': 'EVENING',   'temp': e_temp, 'condition': _wmo_label(e_code), 'icon': _to_night_icon(_wmo_icon(e_code))},
        ]

        # Extended: days 1–4 (skip today = index 0)
        d_times  = daily.get('time', [])
        d_maxes  = daily.get('temperature_2m_max', [])
        d_mins   = daily.get('temperature_2m_min', [])
        d_wcodes = daily.get('weather_code', [])
        extended = []
        for i in range(1, min(5, len(d_times))):
            try:
                dow = date.fromisoformat(d_times[i]).strftime('%a').upper()
            except Exception:
                dow = d_times[i][-5:]
            hi  = round(d_maxes[i])  if i < len(d_maxes)  and d_maxes[i]  is not None else None
            lo  = round(d_mins[i])   if i < len(d_mins)   and d_mins[i]   is not None else None
            wc  = d_wcodes[i]        if i < len(d_wcodes)                              else 0
            extended.append({'dow': dow, 'hi': hi, 'lo': lo,
                              'condition': _wmo_label(wc), 'icon': _wmo_icon(wc)})

        # 5-day forecast: today (index 0) + days 1-4
        five_day = []
        for i in range(min(5, len(d_times))):
            try:
                dow = 'TODAY' if i == 0 else date.fromisoformat(d_times[i]).strftime('%a').upper()
            except Exception:
                dow = 'TODAY' if i == 0 else d_times[i][-5:]
            hi  = round(d_maxes[i])  if i < len(d_maxes)  and d_maxes[i]  is not None else None
            lo  = round(d_mins[i])   if i < len(d_mins)   and d_mins[i]   is not None else None
            wc  = d_wcodes[i]        if i < len(d_wcodes)                              else 0
            five_day.append({'dow': dow, 'hi': hi, 'lo': lo,
                             'condition': _wmo_label(wc), 'icon': _wmo_icon(wc)})

        ticker = []
        if wcode in (95, 96, 99):
            ticker.append('Severe Thunderstorms Possible')
        if wcode in (71, 73, 75, 77, 85, 86):
            ticker.append('Winter Weather Advisory in Effect')

        # backward-compat forecast list
        compat_forecast = [{'label': d['dow'], 'hi': d['hi'], 'lo': d['lo'],
                            'condition': d['condition']} for d in extended]

        return {
            'updated': updated_str,
            'location': location_name,
            'now': now_info,
            'today': today_forecast,
            'extended': extended,
            'five_day': five_day,
            'ticker': ticker,
            'forecast': compat_forecast,
            'radar_url': _build_radar_url(lat, lon),
        }

    # Stub / demo data when no coordinates configured
    return {
        'updated': updated_str,
        'location': location_name,
        'now': {'temp': None, 'condition': 'Not Configured', 'humidity': None,
                'wind': '', 'feels_like': None, 'icon': 'cloudy'},
        'today': [
            {'label': 'MORNING',   'temp': None, 'condition': '--', 'icon': 'cloudy'},
            {'label': 'AFTERNOON', 'temp': None, 'condition': '--', 'icon': 'cloudy'},
            {'label': 'EVENING',   'temp': None, 'condition': '--', 'icon': 'cloudy_night'},
        ],
        'extended': [],
        'five_day': [],
        'ticker': [],
        'forecast': [],
        'radar_url': _build_radar_url('', ''),
    }

_RSS_NS = {'atom': 'http://www.w3.org/2005/Atom', 'media': 'http://search.yahoo.com/mrss/'}

def _strip_html_tags(text):
    """Remove HTML tags from a string, returning plain text."""
    return re.sub(r'<[^>]+>', '', text or '').strip()

def _extract_rss_image(element):
    """Extract the best image URL from an RSS <item> or Atom <entry> element.

    Checks (in priority order):
      1. <media:content medium="image"> or type starting with "image/"
      2. <media:thumbnail>
      3. <enclosure type="image/...">
      4. First <img src="..."> found inside <description> or <content>
    Returns empty string when no image is found.
    """
    _MEDIA_NS = 'http://search.yahoo.com/mrss/'

    # 1. media:content
    for mc in element.findall(f'{{{_MEDIA_NS}}}content'):
        medium = mc.get('medium', '')
        ctype  = mc.get('type', '')
        url    = mc.get('url', '').strip()
        if url and (medium == 'image' or ctype.startswith('image/')):
            return url
    # also accept any media:content with an image url if medium/type not set
    for mc in element.findall(f'{{{_MEDIA_NS}}}content'):
        url = mc.get('url', '').strip()
        if url and re.search(r'\.(jpe?g|png|gif|webp)(\?|$)', url, re.IGNORECASE):
            return url

    # 2. media:thumbnail
    mt = element.find(f'{{{_MEDIA_NS}}}thumbnail')
    if mt is not None:
        url = mt.get('url', '').strip()
        if url:
            return url

    # 3. enclosure
    enc = element.find('enclosure')
    if enc is not None:
        ctype = enc.get('type', '')
        url   = enc.get('url', '').strip()
        if url and ctype.startswith('image/'):
            return url

    # 4. First <img src> in description / content / summary
    for tag_name in ('description', 'content', 'summary',
                     '{http://www.w3.org/2005/Atom}summary',
                     '{http://www.w3.org/2005/Atom}content'):
        el = element.find(tag_name)
        if el is not None:
            text = el.text or ''
            m = re.search(r'<img\s[^>]*src=["\']([^"\']+)["\']', text, re.IGNORECASE)
            if m:
                return m.group(1).strip()

    return ''


def fetch_rss_headlines(feed_url, max_items=20):
    """Fetch a RSS 2.0 or Atom feed and return a list of headline dicts.

    Each item: {'title': str, 'source': str, 'url': str, 'ts': ISO8601 str, 'image': str, 'summary': str}
    Returns empty list on any error (non-throwing).
    """
    try:
        resp = requests.get(feed_url, timeout=8, headers={'User-Agent': 'RetroIPTVGuide/1.0'})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception:
        logging.exception("fetch_rss_headlines: failed to fetch or parse %r", feed_url)
        return []

    items = []
    tag = root.tag.lower()

    # Strip namespace for tag detection
    local = root.tag.split('}')[-1].lower() if '}' in root.tag else tag

    if local == 'feed':
        # Atom feed
        channel_title = ''
        t = root.find('{http://www.w3.org/2005/Atom}title')
        if t is not None:
            channel_title = (t.text or '').strip()
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry')[:max_items]:
            title_el = entry.find('{http://www.w3.org/2005/Atom}title')
            title = (title_el.text or '').strip() if title_el is not None else ''
            link_el = entry.find('{http://www.w3.org/2005/Atom}link')
            link = (link_el.get('href', '') if link_el is not None else '').strip()
            ts_el = entry.find('{http://www.w3.org/2005/Atom}updated') or entry.find('{http://www.w3.org/2005/Atom}published')
            ts = (ts_el.text or '').strip() if ts_el is not None else ''
            summary_el = entry.find('{http://www.w3.org/2005/Atom}summary') or entry.find('{http://www.w3.org/2005/Atom}content')
            summary = _strip_html_tags((summary_el.text or '') if summary_el is not None else '')
            image = _extract_rss_image(entry)
            if title:
                items.append({'title': title, 'source': channel_title, 'url': link, 'ts': ts, 'image': image, 'summary': summary})
    else:
        # RSS 2.0 / RSS 1.0
        channel = root.find('channel') or root
        channel_title = ''
        ct = channel.find('title')
        if ct is not None:
            channel_title = (ct.text or '').strip()
        for item in channel.findall('item')[:max_items]:
            title_el = item.find('title')
            title = (title_el.text or '').strip() if title_el is not None else ''
            link_el = item.find('link')
            link = (link_el.text or '').strip() if link_el is not None else ''
            pub_el = item.find('pubDate')
            ts = (pub_el.text or '').strip() if pub_el is not None else ''
            desc_el = item.find('description')
            summary = _strip_html_tags((desc_el.text or '') if desc_el is not None else '')
            image = _extract_rss_image(item)
            if title:
                items.append({'title': title, 'source': channel_title, 'url': link, 'ts': ts, 'image': image, 'summary': summary})

    return items

def get_virtual_channel_order():
    """Return the saved tvg_id order list, or None if not set."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='virtual_channel.order'")
            row = c.fetchone()
            if row:
                return _json.loads(row[0])
    except Exception:
        logging.exception("get_virtual_channel_order failed")
    return None

# ------------------- Channel Mix -------------------

_CHANNEL_MIX_VALID_IDS = frozenset(
    ch['tvg_id'] for ch in VIRTUAL_CHANNELS if ch['tvg_id'] != 'virtual.channel_mix'
)

def get_channel_mix_config():
    """Return the Channel Mix configuration.

    Returns a dict with:
      - 'name': display name (str, defaults to 'Channel Mix')
      - 'channels': list of dicts with 'tvg_id' and 'duration_minutes' (int)
    """
    result = {'name': 'Channel Mix', 'channels': []}
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='channel_mix.name'")
            row = c.fetchone()
            if row and row[0]:
                result['name'] = row[0]
            c.execute("SELECT value FROM settings WHERE key='channel_mix.channels'")
            row = c.fetchone()
            if row and row[0]:
                channels = _json.loads(row[0])
                valid = []
                for entry in channels:
                    if entry.get('tvg_id') in _CHANNEL_MIX_VALID_IDS:
                        minutes = int(entry.get('duration_minutes', 120))
                        minutes = max(1, min(minutes, 1440))
                        valid.append({'tvg_id': entry['tvg_id'], 'duration_minutes': minutes})
                result['channels'] = valid
    except Exception:
        logging.exception("get_channel_mix_config failed, using defaults")
    return result

def save_channel_mix_config(config):
    """Persist Channel Mix configuration.

    config must be a dict with optional 'name' (str) and 'channels' list.
    Each channel entry must have 'tvg_id' (one of the non-mix virtual channels)
    and 'duration_minutes' (int, 1–1440).
    """
    name = str(config.get('name', '')).strip()
    if not name:
        name = 'Channel Mix'
    if len(name) > 120:
        raise ValueError("Channel Mix name must be 120 characters or fewer")
    channels = config.get('channels', [])
    validated = []
    for entry in channels:
        tvg_id = str(entry.get('tvg_id', '')).strip()
        if tvg_id not in _CHANNEL_MIX_VALID_IDS:
            raise ValueError(f"Invalid channel ID for Channel Mix: {tvg_id!r}")
        minutes = int(entry.get('duration_minutes', 120))
        if minutes < 1 or minutes > 1440:
            raise ValueError(f"duration_minutes must be 1–1440, got {minutes}")
        validated.append({'tvg_id': tvg_id, 'duration_minutes': minutes})
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('channel_mix.name', ?)", (name,))
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('channel_mix.channels', ?)",
                      (_json.dumps(validated),))
            conn.commit()
    except ValueError:
        raise
    except Exception:
        logging.exception("save_channel_mix_config failed")
        raise

def _get_active_channel_mix_slot(channels):
    """Return (active_tvg_id, seconds_remaining) for the channel mix based on wall-clock time.

    Uses Unix timestamp modulo the total cycle duration so all viewers are
    always in sync regardless of when they tuned in.  Returns (None, 0) when
    no channels are configured.
    """
    if not channels:
        return None, 0
    total_seconds = sum(ch['duration_minutes'] * 60 for ch in channels)
    if total_seconds == 0:
        return None, 0
    offset = int(time.time()) % total_seconds
    elapsed = 0
    for ch in channels:
        slot_seconds = ch['duration_minutes'] * 60
        if offset < elapsed + slot_seconds:
            return ch['tvg_id'], elapsed + slot_seconds - offset
        elapsed += slot_seconds
    # Fallback (should not happen, but defend against floating-point edge cases)
    return channels[0]['tvg_id'], channels[0]['duration_minutes'] * 60



def save_virtual_channel_order(order):
    """Persist virtual channel order.  order is a list of tvg_id strings.
    Channel Mix is always moved to the end before saving so it remains last
    regardless of what the caller supplies."""
    # Enforce Channel Mix last: remove it from wherever it sits, then re-append
    without_mix = [tid for tid in order if tid != 'virtual.channel_mix']
    if 'virtual.channel_mix' in order:
        without_mix.append('virtual.channel_mix')
    order = without_mix
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('virtual_channel.order', ?)",
                      (_json.dumps(order),))
            conn.commit()
    except Exception:
        logging.exception("save_virtual_channel_order failed")
        raise

def get_virtual_channels():
    """Return the list of virtual channel definitions in the user-defined order.
    Logo priority: custom upload > icon pack (when enabled) > default SVG.
    Channel Mix is always pinned as the last channel regardless of saved order or
    future additions to VIRTUAL_CHANNELS."""
    import copy
    channels = copy.deepcopy(VIRTUAL_CHANNELS)
    use_icon_pack = get_use_icon_pack()
    # Apply effective logos
    for ch in channels:
        custom = get_channel_custom_logo(ch['tvg_id'])
        ch['logo'] = _resolve_channel_logo(ch['tvg_id'], ch['logo'], custom, use_icon_pack)
    order = get_virtual_channel_order()
    if order:
        id_to_ch = {ch['tvg_id']: ch for ch in channels}
        # Build ordered list excluding Channel Mix (pinned last)
        ordered = [id_to_ch[tvg_id] for tvg_id in order
                   if tvg_id in id_to_ch and tvg_id != 'virtual.channel_mix']
        # Append any channels not present in the saved order (e.g. newly added),
        # still excluding Channel Mix
        seen = set(order) | {'virtual.channel_mix'}
        ordered += [ch for ch in channels if ch['tvg_id'] not in seen]
        # Always append Channel Mix last
        if 'virtual.channel_mix' in id_to_ch:
            ordered.append(id_to_ch['virtual.channel_mix'])
        return ordered
    # Default VIRTUAL_CHANNELS order: ensure Channel Mix is still last
    non_mix, mix = [], []
    for ch in channels:
        (mix if ch['tvg_id'] == 'virtual.channel_mix' else non_mix).append(ch)
    return non_mix + mix

def get_virtual_epg(grid_start, hours_span=6):
    """Generate synthetic EPG entries for virtual channels spanning the grid window."""
    epg = {}
    grid_end = grid_start + timedelta(hours=hours_span)
    programs_by_tvg_id = {
        'virtual.news':        'News Now',
        'virtual.weather':     'Local Weather',
        'virtual.status':      'System Status',
        'virtual.traffic':     'Traffic Now',
        'virtual.updates':     'Updates & Announcements',
        'virtual.sports':      'Sports Scores',
        'virtual.nasa':        'Space Channel',
        'virtual.channel_mix': 'Channel Mix',
        'virtual.on_this_day': 'On This Day',
    }
    for tvg_id, title in programs_by_tvg_id.items():
        slots = []
        slot_start = grid_start
        while slot_start < grid_end:
            slot_stop = slot_start + timedelta(hours=1)
            slots.append({'title': title, 'desc': '', 'start': slot_start, 'stop': slot_stop})
            slot_start = slot_stop
        epg[tvg_id] = slots
    return epg

# ------------------- Safe redirect helper -------------------
def is_safe_url(target):
    """
    Return True if the target is a safe local URL (same host). Prevent open redirect.
    """
    try:
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))
        return (test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc)
    except Exception:
        return False

# ------------------- Routes -------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    """
    Login view updated to preserve a safe 'next' redirect. If a user supplies ?next=/remote
    (e.g. from the QR), after successful login they will be redirected there automatically.
    """
    # If already authenticated, redirect to next or guide
    if getattr(current_user, "is_authenticated", False):
        safe_next = _safe_next_url(request.args.get('next') or request.form.get('next') or '')
        return redirect(safe_next or url_for('guide'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on' or request.form.get('remember') == 'true' or 'remember' in request.form
        user = get_user(username)
        if user and check_password_hash(user.password_hash, password):
            # Update last_login timestamp
            with sqlite3.connect(DATABASE, timeout=10) as conn:
                c = conn.cursor()
                c.execute('UPDATE users SET last_login=? WHERE username=?',
                          (datetime.now(timezone.utc).isoformat(), username))
                conn.commit()
            
            login_user(user, remember=remember)
            log_event(username, "Logged in")

            # Force password change if required (e.g. first login)
            if user.must_change_password:
                return redirect(url_for('change_password'))

            # Determine next redirect target (prefer POSTed next, then query param)
            safe_next = _safe_next_url(request.form.get('next') or request.args.get('next') or '')
            return redirect(safe_next or url_for('guide'))
        else:
            log_event(username if username else "unknown", "Failed login attempt")
            error = 'Invalid username or password'
            next_url = request.form.get('next') or request.args.get('next') or ''
            return render_template('login.html', error=error, next=next_url), 401

    # GET: render login form; preserve ?next=... into the form
    next_url = request.args.get('next') or ''
    return render_template('login.html', next=next_url)


@app.route('/_debug/current', methods=['GET'])
@login_required
def _debug_current():
    """
    Debug helper: returns the server-side CURRENTLY_PLAYING value so you can verify what the server thinks is playing.
    """
    return jsonify({
        "CURRENTLY_PLAYING": CURRENTLY_PLAYING,
        "cached_channels_sample": [{
            "tvg_id": ch.get('tvg_id'),
            "url": ch.get('url'),
            "name": ch.get('name')
        } for ch in cached_channels[:10]]
    })

@app.route('/logout')
@login_required
def logout():
    log_event(current_user.username, "Logged out")
    logout_user()
    return redirect(url_for('login'))

def revoke_user_sessions(username):
    # Placeholder: later this can use a session-tracking table or Redis
    # For now, it clears any "remember" cookie or stored flag
    session_key = f"user_session_{username}"
    if session_key in session:
        session.pop(session_key, None)
    log_event("admin", f"Revoked sessions for {username}")

@app.route('/change_password', methods=['GET','POST'])
@login_required
def change_password():
    forced = current_user.must_change_password
    if request.method == 'POST':
        old = request.form['old_password']
        new = request.form['new_password']
        user = get_user(current_user.username)
        if user and check_password_hash(user.password_hash, old):
            with sqlite3.connect(DATABASE, timeout=10) as conn:
                c = conn.cursor()
                c.execute('UPDATE users SET password=?, must_change_password=0 WHERE id=?',
                          (generate_password_hash(new), current_user.id))
                conn.commit()
            log_event(current_user.username, "Changed password")
            flash("Password updated successfully.")
            return redirect(url_for('guide'))
        else:
            log_event(current_user.username, "Failed password change attempt (invalid old password)")
            flash("Old password incorrect.")
    return render_template("change_password.html", current_tuner=get_current_tuner(), forced=forced)

@app.route('/add_user', methods=['GET','POST'])
@login_required
def add_user_route():
    if current_user.username != 'admin':
        log_event(current_user.username, "Unauthorized access attempt to /add_user")
        return redirect(url_for('guide'))

    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']
        try:
            with sqlite3.connect(DATABASE, timeout=10) as conn:
                c = conn.cursor()
                c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                          (new_username, generate_password_hash(new_password)))
                conn.commit()
            log_event(current_user.username, f"Added user {new_username}")
            flash(f"User {new_username} added successfully.")
            return redirect(url_for('guide'))
        except sqlite3.IntegrityError:
            log_event(current_user.username, f"Failed to add user {new_username} (duplicate)")
            flash("Username already exists.")
    return render_template("add_user.html", current_tuner=get_current_tuner())

@app.route('/delete_user', methods=['GET','POST'])
@login_required
def delete_user():
    if current_user.username != 'admin':
        log_event(current_user.username, "Unauthorized access attempt to /delete_user")
        return redirect(url_for('guide'))

    if request.method == 'POST':
        del_username = request.form['username']
        if del_username == 'admin':
            log_event(current_user.username, "Attempted to delete admin user (blocked)")
            flash("You cannot delete the admin account.")
            return redirect(url_for('delete_user'))

        with sqlite3.connect(DATABASE, timeout=10) as conn:
            c = conn.cursor()
            c.execute('DELETE FROM users WHERE username=?', (del_username,))
            conn.commit()
        log_event(current_user.username, f"Deleted user {del_username}")
        flash(f"User {del_username} deleted (if they existed).")
        return redirect(url_for('guide'))

    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT username FROM users WHERE username != "admin"')
        users = [row[0] for row in c.fetchall()]
    return render_template("delete_user.html", current_tuner=get_current_tuner(), users=users)

@app.route('/manage_users', methods=['GET', 'POST'])
@login_required
def manage_users():
    ua = request.headers.get('User-Agent', '').lower()

    # Detect Android / Fire / Google TV browsers
    tv_patterns = ['silk', 'aft', 'android tv', 'googletv', 'mibox', 'bravia', 'shield', 'tcl', 'hisense', 'puffin', 'tv bro']
    is_tv = any(p in ua for p in tv_patterns)

    # Restrict access
    if current_user.username != 'admin' or is_tv:
        # Log unauthorized or TV-based attempt
        log_event(current_user.username, f"Unauthorized attempt to access /manage_users from UA: {ua}")
        flash("Unauthorized access.")
        return redirect(url_for('guide'))

    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')

        if action == 'add':
            if not username or not password:
                flash("Please provide both username and password.")
            else:
                try:
                    with sqlite3.connect(DATABASE, timeout=10) as conn:
                        c = conn.cursor()
                        c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                                  (username, generate_password_hash(password)))
                        conn.commit()
                    log_event(current_user.username, f"Added user {username}")
                    flash(f"✅ User '{username}' added successfully.")
                except sqlite3.IntegrityError:
                    flash("⚠️ Username already exists.")

        elif action == 'delete':
            if username == 'admin':
                flash("❌ Cannot delete the admin account.")
            else:
                with sqlite3.connect(DATABASE, timeout=10) as conn:
                    c = conn.cursor()
                    c.execute('DELETE FROM users WHERE username=?', (username,))
                    conn.commit()
                log_event(current_user.username, f"Deleted user {username}")
                flash(f"🗑 Deleted user '{username}'.")

        elif action == 'signout':
            revoke_user_sessions(username)
            log_event(current_user.username, f"Revoked sessions for {username}")
            flash(f"🚪 Signed out all active logins for '{username}'.")

        elif action == 'set_user_prefs':
            ch_id = request.form.get('auto_load_channel_id', '').strip()
            ch_name = request.form.get('auto_load_channel_name', '').strip() or ch_id
            auto_load = {"id": ch_id, "name": ch_name} if ch_id else None
            raw_theme = request.form.get('default_theme', '').strip() or None
            save_user_prefs(username, {
                "auto_load_channel": auto_load,
                "default_theme": raw_theme,
            })
            log_event(current_user.username, f"Updated prefs for {username}")
            flash(f"✅ Preferences saved for '{username}'.")

        elif action == 'assign_tuner':
            new_tuner = request.form.get('tuner_name', '').strip() or None
            # Fetch current assigned tuner before updating
            with sqlite3.connect(DATABASE, timeout=10) as conn:
                c = conn.cursor()
                c.execute('SELECT assigned_tuner FROM users WHERE username=?', (username,))
                row = c.fetchone()
                old_tuner = row[0] if row else None
                c.execute('UPDATE users SET assigned_tuner=? WHERE username=?', (new_tuner, username))
                conn.commit()
            # Clear auto-load channel when tuner assignment changes
            if new_tuner != old_tuner:
                prefs = get_user_prefs(username)
                prefs["auto_load_channel"] = None
                save_user_prefs(username, prefs)
            log_event(current_user.username, f"Assigned tuner {new_tuner!r} to {username}")
            flash(f"✅ Tuner assigned for '{username}'.")

        return redirect(url_for('manage_users'))

    # ---- Build user list with prefs and channel_list ----
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT username, last_login, assigned_tuner FROM users WHERE username != "admin"')
        rows = c.fetchall()

    curr_tuner = get_current_tuner()
    # Cache load_tuner_data results so we don't re-fetch the same tuner's M3U for
    # every user that shares it.
    tuner_channel_cache = {}
    users = []
    for row in rows:
        uname, last_login, assigned_tuner = row[0], row[1], row[2]
        prefs = get_user_prefs(uname)
        tuner_name = assigned_tuner or curr_tuner
        if tuner_name == curr_tuner:
            # Use the in-memory cache for the active tuner (already fetched).
            ch_list = cached_channels
        else:
            # For any other tuner (including combined tuners) load its channels.
            # Results are memoized within this request to avoid redundant fetches
            # when multiple users share the same non-active tuner.
            if tuner_name not in tuner_channel_cache:
                try:
                    fetched, _ = load_tuner_data(tuner_name)
                except Exception:
                    fetched = []
                tuner_channel_cache[tuner_name] = fetched
            ch_list = tuner_channel_cache[tuner_name]
        # Convert to simple {id, name} dicts for template
        channel_list = [{"id": ch.get("tvg_id", ""), "name": ch.get("name", "")} for ch in ch_list]
        users.append({
            "username": uname,
            "last_login": last_login,
            "assigned_tuner": assigned_tuner,
            "prefs": prefs,
            "channel_list": channel_list,
        })

    resp = make_response(render_template('manage_users.html', users=users, current_tuner=get_current_tuner()))
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route("/about")
@login_required
def about():
    return render_template("about.html", version=APP_VERSION, release_date=APP_RELEASE_DATE, sys_platform=sys.platform)



@app.route('/set_tuner/<name>')
@login_required
def set_tuner(name):
    """Quick-switch the active tuner from the header fly-out.
    Admin-only, mirrors the behaviour of the 'switch_tuner' action in /change_tuner.
    """
    if current_user.username != 'admin':
        log_event(current_user.username, f"Unauthorized quick tuner switch attempt to {name}")
        flash("Unauthorized access.", "warning")
        return redirect(url_for('guide'))

    tuners = get_tuners()
    if name not in tuners:
        flash(f"Tuner '{name}' does not exist.", "warning")
        return redirect(url_for('change_tuner'))

    # Update current tuner
    set_current_tuner(name)

    # Refresh cached guide data (use load_tuner_data so combined tuners work).
    global cached_channels, cached_epg
    cached_channels, cached_epg = load_tuner_data(name)
    cached_epg = apply_epg_fallback(cached_channels, cached_epg)

    log_event(current_user.username, f"Quick switched active tuner to {name}")
    flash(f"Active tuner switched to {name}", "success")

    # Try to redirect back to where the user came from, falling back to guide.
    # Only same-origin paths are followed to prevent open redirect (CWE-601).
    # Extract just the path+query from the Referer, verify same-origin, then
    # pass through _safe_next_url as a final guard against protocol-relative paths.
    dest = url_for('guide')
    _raw_ref = request.referrer or ''
    if _raw_ref:
        try:
            _ref_parsed = urlparse(_raw_ref)
            _host_parsed = urlparse(request.host_url)
            if (
                _ref_parsed.scheme in ('http', 'https')
                and _ref_parsed.netloc == _host_parsed.netloc
            ):
                # Same origin: extract relative path+query then sanitize.
                _rel = _ref_parsed.path or '/'
                if not _rel.startswith('/'):
                    _rel = '/' + _rel
                if _ref_parsed.query:
                    _rel += '?' + _ref_parsed.query
                dest = _safe_next_url(_rel) or url_for('guide')
        except Exception:  # noqa: BLE001
            pass
    return redirect(dest)


@app.route('/virtual_channels', methods=['GET', 'POST'])
@login_required
def virtual_channels():
    if current_user.username != 'admin':
        log_event(current_user.username, "Unauthorized access attempt to /virtual_channels")
        return redirect(url_for('guide'))

    if request.method == 'POST':
        action = request.form.get("action")

        if action == "update_virtual_channels":
            new_settings = {}
            for ch in VIRTUAL_CHANNELS:
                tvg_id = ch['tvg_id']
                new_settings[tvg_id] = request.form.get(f"vc_{tvg_id}", "0") == "1"
            try:
                save_virtual_channel_settings(new_settings)
                log_event(current_user.username, "Updated virtual channel settings")
                flash("Virtual channel settings saved.", "success")
            except Exception:
                flash("Failed to save virtual channel settings.", "warning")

        elif action == "update_virtual_channel_order":
            valid_ids = {ch['tvg_id'] for ch in VIRTUAL_CHANNELS}
            raw_order = request.form.getlist('channel_order[]')
            order = [tid for tid in raw_order if tid in valid_ids]
            if set(order) == valid_ids:
                try:
                    save_virtual_channel_order(order)
                    return ('', 204)
                except Exception:
                    return ('Failed to save channel order', 500)
            return ('Invalid channel order', 400)

        elif action == "update_channel_overlay_appearance":
            tvg_id = request.form.get('tvg_id', '').strip()
            valid_ids = {ch['tvg_id'] for ch in VIRTUAL_CHANNELS}
            if tvg_id not in valid_ids:
                flash("Unknown virtual channel.", "warning")
            else:
                appearance = {
                    'text_color': request.form.get('ch_text_color', '').strip(),
                    'bg_color': request.form.get('ch_bg_color', '').strip(),
                    'test_text': request.form.get('ch_test_text', '').strip(),
                }
                if tvg_id in ('virtual.weather', 'virtual.news', 'virtual.traffic', 'virtual.sports', 'virtual.nasa', 'virtual.on_this_day'):
                    appearance = {'text_color': '', 'bg_color': '', 'test_text': ''}
                try:
                    save_channel_overlay_appearance(tvg_id, appearance)
                    if tvg_id == 'virtual.news':
                        rss_urls = [request.form.get(f'ch_news_rss_url_{i}', '').strip()
                                    for i in range(1, 7)]
                        save_news_feed_urls(rss_urls)
                    if tvg_id == 'virtual.weather':
                        weather_cfg = {
                            'lat':                  request.form.get('ch_weather_lat', '').strip(),
                            'lon':                  request.form.get('ch_weather_lon', '').strip(),
                            'location_name':        request.form.get('ch_weather_location', '').strip(),
                            'units':                request.form.get('ch_weather_units', 'F').strip(),
                            'seconds_per_segment':  request.form.get('ch_weather_seconds_per_segment',
                                                                     str(_WEATHER_SECONDS_PER_SEGMENT_DEFAULT)).strip(),
                        }
                        save_weather_config(weather_cfg)
                    if tvg_id == 'virtual.traffic':
                        demo_cfg = {
                            'mode':             request.form.get('ch_traffic_demo_mode', 'admin_rotation').strip(),
                            'pack_size':        request.form.get('ch_traffic_pack_size', '10').strip(),
                            'rotation_seconds': request.form.get('ch_traffic_rotation_seconds', '120').strip(),
                        }
                        save_traffic_demo_config(demo_cfg)
                    if tvg_id == 'virtual.updates':
                        updates_cfg = {
                            'show_beta': request.form.get('ch_updates_show_beta') == '1',
                        }
                        save_updates_config(updates_cfg)
                    if tvg_id == 'virtual.sports':
                        sports_mode = request.form.get('ch_sports_mode', 'scores').strip()
                        if sports_mode not in ('rss', 'scores'):
                            sports_mode = 'scores'
                        save_sports_mode(sports_mode)
                        sports_external = request.form.get('ch_sports_external_data_enabled') == '1'
                        save_sports_external_data_enabled(sports_external)
                        scores_base_url = request.form.get('ch_sports_scores_base_url', '').strip()
                        save_sports_scores_base_url(scores_base_url)
                        rss_urls = [request.form.get(f'ch_sports_rss_url_{i}', '').strip()
                                    for i in range(1, 7)]
                        save_sports_feed_urls(rss_urls)
                        sports_cfg = {lg['id']: request.form.get(f'ch_sports_league_{lg["id"]}') == '1'
                                      for lg in SPORTS_LEAGUES}
                        save_sports_config(sports_cfg)
                    if tvg_id == 'virtual.nasa':
                        nasa_interval = request.form.get('ch_nasa_interval', '15').strip()
                        if nasa_interval not in ('15', '30'):
                            nasa_interval = '15'
                        save_nasa_interval(nasa_interval)
                        nasa_count_raw = request.form.get('ch_nasa_image_count', '').strip()
                        if nasa_count_raw:
                            save_nasa_image_count(int(nasa_count_raw))
                        else:
                            save_nasa_image_count(None)
                    if tvg_id == 'virtual.channel_mix':
                        mix_name = request.form.get('ch_mix_name', '').strip()
                        mix_channels = []
                        for src_ch in VIRTUAL_CHANNELS:
                            src_id = src_ch['tvg_id']
                            if src_id not in _CHANNEL_MIX_VALID_IDS:
                                continue
                            if request.form.get(f'cm_ch_{src_id}') == '1':
                                dur_raw = request.form.get(f'cm_dur_{src_id}', '120').strip()
                                try:
                                    minutes = max(1, min(int(dur_raw), 1440))
                                except (ValueError, TypeError):
                                    minutes = 120
                                mix_channels.append({'tvg_id': src_id, 'duration_minutes': minutes})
                        try:
                            save_channel_mix_config({'name': mix_name, 'channels': mix_channels})
                        except ValueError as exc:
                            flash(str(exc), "warning")
                    if tvg_id == 'virtual.on_this_day':
                        for src in ON_THIS_DAY_SOURCES:
                            sid = src['id']
                            enabled = request.form.get(f'ch_otd_source_{sid}') == '1'
                            save_on_this_day_source_enabled(sid, enabled)
                            # Parse custom events (one per line: "YEAR: text")
                            raw_custom = request.form.get(f'ch_otd_custom_{sid}', '').strip()
                            custom_events = []
                            for line in raw_custom.splitlines():
                                line = line.strip()
                                if not line:
                                    continue
                                if ':' in line:
                                    year_part, _, text_part = line.partition(':')
                                    year_part = year_part.strip()
                                    text_part = text_part.strip()
                                    if year_part and text_part:
                                        custom_events.append({
                                            'year':     year_part,
                                            'text':     text_part,
                                            'category': src['category'],
                                        })
                                else:
                                    custom_events.append({
                                        'year':     '',
                                        'text':     line,
                                        'category': src['category'],
                                    })
                            save_on_this_day_custom_events(sid, custom_events)
                    music_file = request.form.get('ch_music_file', '').strip()
                    save_channel_music_file(tvg_id, music_file)
                    log_event(current_user.username, f"Updated overlay appearance for {tvg_id}")
                    flash("Channel overlay settings saved.", "success")
                except ValueError as exc:
                    flash(str(exc), "warning")
                except Exception:
                    flash("Failed to save channel overlay settings.", "warning")

    vc_settings = get_virtual_channel_settings()
    overlay_appearance = get_overlay_appearance()
    channel_appearances = get_all_channel_appearances()
    audio_files = list_audio_files()
    channel_music_files = {ch['tvg_id']: get_channel_music_file(ch['tvg_id'])
                           for ch in VIRTUAL_CHANNELS}

    return render_template(
        "virtual_channels.html",
        VIRTUAL_CHANNELS=get_virtual_channels(),
        vc_settings=vc_settings,
        overlay_appearance=overlay_appearance,
        channel_appearances=channel_appearances,
        news_feed_urls=get_news_feed_urls(),
        weather_config=get_weather_config(),
        traffic_demo_config=get_traffic_demo_config(),
        traffic_demo_cities=get_traffic_demo_cities(),
        updates_config=get_updates_config(),
        sports_config=get_sports_config(),
        sports_feed_urls=get_sports_feed_urls(),
        SPORTS_LEAGUES=SPORTS_LEAGUES,
        nasa_config=get_nasa_config(),
        channel_mix_config=get_channel_mix_config(),
        on_this_day_config=get_on_this_day_config(),
        audio_files=audio_files,
        channel_music_files=channel_music_files,
        use_icon_pack=get_use_icon_pack(),
        icon_pack_logos=_ICON_PACK_LOGOS,
    )


@app.route('/change_tuner', methods=['GET', 'POST'])
@login_required
def change_tuner():
    if current_user.username != 'admin':
        log_event(current_user.username, "Unauthorized access attempt to /change_tuner")
        return redirect(url_for('guide'))

    if request.method == 'POST':
        action = request.form.get("action")

        if action == "switch_tuner":
            new_tuner = request.form["tuner"]
            set_current_tuner(new_tuner)
            log_event(current_user.username, f"Switched active tuner to {new_tuner}")
            flash(f"Active tuner switched to {new_tuner}")

            # ✅ Refresh cached guide data immediately (use load_tuner_data so combined tuners work)
            global cached_channels, cached_epg
            cached_channels, cached_epg = load_tuner_data(new_tuner)
            # ✅ Apply “No Guide Data Available” fallback
            cached_epg = apply_epg_fallback(cached_channels, cached_epg)

        elif action == "update_urls":
            tuner = request.form["tuner"]
            xml_url = request.form["xml_url"]
            m3u_url = request.form["m3u_url"]

            # update DB
            update_tuner_urls(tuner, xml_url, m3u_url)
            log_event(current_user.username, f"Updated URLs for tuner {tuner}")
            flash(f"Updated URLs for tuner {tuner}")

            # ✅ Validate inputs
            if xml_url:
                validate_tuner_url(xml_url, label=f"{tuner} XML")
            if m3u_url:
                validate_tuner_url(m3u_url, label=f"{tuner} M3U")

        elif action == "delete_tuner":
            tuner = request.form["tuner"]
            current_tuner = get_current_tuner()
            if tuner == current_tuner:
                flash("You cannot delete the currently active tuner.", "warning")
            else:
                delete_tuner(tuner)
                log_event(current_user.username, f"Deleted tuner {tuner}")
                flash(f"Tuner {tuner} deleted.")

        elif action == "rename_tuner":
            old_name = request.form["tuner"]   # matches HTML <select name="tuner">
            new_name = request.form["new_name"].strip()
            if not new_name:
                flash("New name cannot be empty.", "warning")
            else:
                rename_tuner(old_name, new_name)
                log_event(current_user.username, f"Renamed tuner {old_name} → {new_name}")
                flash(f"Tuner {old_name} renamed to {new_name}")

        elif action == "add_tuner":
            name = request.form.get("tuner_name", "").strip()
            tuner_mode = request.form.get("tuner_mode", "standard")

            if not name:
                flash("Tuner name cannot be empty.", "warning")
            elif tuner_mode == "combined":
                sources = request.form.getlist("source_tuners")
                try:
                    add_combined_tuner(name, sources)
                    log_event(current_user.username, f"Added combined tuner {name}")
                    flash(f"Combined tuner {name} added successfully.")
                except ValueError as e:
                    flash(str(e), "warning")
                    log_event(current_user.username, f"Failed to add combined tuner {name}: {str(e)}")
            else:
                if tuner_mode == "single_stream":
                    xml_url = ""
                    m3u_url = request.form.get("m3u8_stream_url", "").strip()
                else:
                    xml_url = request.form.get("xml_url", "").strip()
                    m3u_url = request.form.get("m3u_url", "").strip()
                try:
                    add_tuner(name, xml_url, m3u_url)
                    log_event(current_user.username, f"Added tuner {name}")
                    flash(f"Tuner {name} added successfully.")
                except ValueError as e:
                    flash(str(e), "warning")
                    log_event(current_user.username, f"Failed to add tuner {name}: {str(e)}")

        elif action == "update_auto_refresh":
            # Expect form fields: auto_refresh_enabled ('0' or '1') and auto_refresh_interval_hours (2/4/6/12/24)
            enabled = request.form.get("auto_refresh_enabled", "0")
            interval = request.form.get("auto_refresh_interval_hours", "")
            if enabled not in ("0", "1"):
                enabled = "0"
            if interval:
                try:
                    intval = int(interval)
                except:
                    intval = None
            else:
                intval = None

            # only allow preset intervals
            AUTO_REFRESH_PRESETS = [2, 4, 6, 12, 24]
            if intval and intval not in AUTO_REFRESH_PRESETS:
                flash(f"Invalid interval. Allowed: {AUTO_REFRESH_PRESETS}", "warning")
            else:
                # persist using existing settings table
                try:
                    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
                        c = conn.cursor()
                        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("auto_refresh_enabled", "1" if enabled == "1" else "0"))
                        if intval:
                            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("auto_refresh_interval_hours", str(intval)))
                        else:
                            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("auto_refresh_interval_hours", ""))
                        conn.commit()
                except Exception:
                    logging.exception("Failed to persist auto-refresh settings")
                    flash("Failed to save auto-refresh settings.", "warning")
                else:
                    log_event(current_user.username, f"Updated auto-refresh: enabled={enabled} interval={interval}")
                    flash("Auto-refresh settings updated.", "success")


    tuners = get_tuners()
    current_tuner = get_current_tuner()

    # read auto-refresh status for template display
    def _get_setting_inline(key, default=None):
        try:
            with sqlite3.connect(TUNER_DB, timeout=10) as conn:
                c = conn.cursor()
                c.execute("SELECT value FROM settings WHERE key=?", (key,))
                row = c.fetchone()
            return row[0] if row else default
        except Exception:
            return default

    auto_refresh_enabled = _get_setting_inline("auto_refresh_enabled", "0")
    auto_refresh_interval_hours = _get_setting_inline("auto_refresh_interval_hours", "")
    last_auto_refresh = None
    if current_tuner:
        last_auto_refresh = _get_setting_inline(f"last_auto_refresh:{current_tuner}", None)

    # Build per-tuner sync info for the Configured Tuners table
    tuner_sync_info = {}
    for tname in tuners:
        raw = _get_setting_inline(f"last_auto_refresh:{tname}", None)
        if raw:
            parts = raw.split('|', 2)  # format: "status|datetime[|detail]"
            sync_status = parts[0] if parts else ''
            sync_dt = parts[1] if len(parts) > 1 else ''
        else:
            sync_status = ''
            sync_dt = ''
        tuner_sync_info[tname] = {'status': sync_status, 'last_sync': sync_dt}

    return render_template(
        "change_tuner.html",
        tuners=tuners.keys(),
        current_tuner=current_tuner,
        current_urls=tuners[current_tuner],
        TUNERS=tuners,
        auto_refresh_enabled=auto_refresh_enabled,
        auto_refresh_interval_hours=auto_refresh_interval_hours,
        last_auto_refresh=last_auto_refresh,
        tuner_sync_info=tuner_sync_info,
    )



@app.route('/guide')
@login_required
def guide():
    log_event(current_user.username, "Loaded guide page")
    # Check and run auto-refresh if due (minimal preset-based approach)
    try:
        refresh_if_due()
    except Exception:
        logging.exception("refresh_if_due from guide() failed")

    now = datetime.now(timezone.utc)
    grid_start = now.replace(minute=(0 if now.minute < 30 else 30), second=0, microsecond=0)
    slots = int((HOURS_SPAN * 60) / SLOT_MINUTES)
    hours_header = [grid_start + timedelta(minutes=SLOT_MINUTES * i) for i in range(slots)]
    total_width = slots * SLOT_MINUTES * SCALE
    minutes_from_start = (now - grid_start).total_seconds() / 60.0
    now_offset = int(minutes_from_start * SCALE)
    
    # --- DEBUG: Show alignment between M3U and EPG ---
    #print("\n=== DEBUG: Cached Channels and EPG Keys ===")
    #print("First 5 channel IDs from M3U:")
    #for ch in cached_channels[:5]:
    #    print("  ", ch.get('tvg_id'))

    #print("\nFirst 5 EPG keys:")
    #for key in list(cached_epg.keys())[:5]:
    #    print("  ", key)
    #print("==========================================\n")


    user_prefs = get_user_prefs(current_user.username)
    user_default_theme = user_prefs.get("default_theme") or None

    virtual_ch = get_virtual_channels()
    vc_settings = get_virtual_channel_settings()
    virtual_ch = [ch for ch in virtual_ch if vc_settings.get(ch['tvg_id'], True)]
    virtual_epg = get_virtual_epg(grid_start, HOURS_SPAN)
    all_channels = virtual_ch + cached_channels
    all_epg = {**virtual_epg, **cached_epg}

    return render_template(
        'guide.html',
        channels=all_channels,
        epg=all_epg,
        now=now,
        grid_start=grid_start,
        hours_header=hours_header,
        SCALE=SCALE,
        total_width=total_width,
        now_offset=now_offset,
        current_tuner=get_current_tuner(),
        user_prefs=user_prefs,
        user_default_theme=user_default_theme,
        overlay_appearance=get_overlay_appearance(),
        channel_appearances=get_all_channel_appearances(),
        channel_music_files={
                ch['tvg_id']: (f'/static/audio/{f}' if (f := get_channel_music_file(ch['tvg_id'])) else '')
                for ch in virtual_ch
            },
    )

@app.route('/play_channel', methods=['POST'])
@login_required
def play_channel():
    channel_name = request.form.get("channel_name")
    if channel_name:
        log_event(current_user.username, f"Started playback of channel {channel_name}")
    return ("", 204)


@app.route('/remote')
def remote():
    """
    Mobile remote page (phone / tablet). Intentionally public so a phone can load the page
    via QR. Note: the API endpoints (e.g. /api/play, /api/channels) are still protected
    by @login_required in the current build. If you want the remote to be usable without
    login, we can add token-based pairing or relax authentication on specific API endpoints.
    """
    return render_template('remote.html')


@app.route('/crt')
def crt():
    """
    CRT-friendly local page for the Pi display. Shows a simple, large-font guide and
    a QR that points to /remote. This page is public by default so the Pi can display it
    without logging in to the web UI.
    """
    return render_template('crt.html')


@app.route('/api/auto_refresh/status', methods=['GET'])
@login_required
def api_auto_refresh_status():
    """
    Return auto-refresh status for the current tuner:
      { tuner, enabled (bool), interval_hours (int|null), last_run (string|null) }
    """
    try:
        tuner = get_current_tuner()
        enabled = get_setting("auto_refresh_enabled", "0")
        interval = get_setting("auto_refresh_interval_hours", "")
        last = get_setting(f"last_auto_refresh:{tuner}", None) if tuner else None

        return jsonify({
            "tuner": tuner,
            "enabled": bool(str(enabled) in ("1", "true", "True")),
            "interval_hours": int(interval) if interval not in (None, "") else None,
            "last_run": last
        })
    except Exception as e:
        logging.exception("api_auto_refresh_status failed: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/user_prefs', methods=['GET'])
@login_required
def api_user_prefs_get():
    """Return the current user's saved preferences."""
    return jsonify(get_user_prefs(current_user.username))


@app.route('/api/user_prefs', methods=['POST'])
@login_required
def api_user_prefs_post():
    """Update one or more preference keys for the current user.

    Accepts JSON with a subset of preference keys; missing keys are preserved.
    Returns { status: "ok", prefs: <updated prefs> }.
    """
    try:
        data = request.get_json(force=True, silent=False)
        if data is None:
            return jsonify({"error": "invalid JSON"}), 400
    except Exception:
        return jsonify({"error": "invalid JSON"}), 400

    # Sanitise auto_load_channel: must have a non-empty 'id' key or be None
    if "auto_load_channel" in data:
        alc = data["auto_load_channel"]
        if not (isinstance(alc, dict) and alc.get("id")):
            data["auto_load_channel"] = None

    save_user_prefs(current_user.username, data)
    return jsonify({"status": "ok", "prefs": get_user_prefs(current_user.username)})

@app.route('/api/channels', methods=['GET'])
@login_required
def api_channels():
    """
    Return JSON list of cached channels for remote UIs.
    """
    out = []
    for ch in cached_channels:
        out.append({
            'tvg_id': ch.get('tvg_id'),
            'name': ch.get('name'),
            'logo': ch.get('logo'),
            'url': ch.get('url'),
            'number': ch.get('tvg_chno') if ch.get('tvg_chno') else ch.get('number'),
            'playlist_index': ch.get('playlist_index') if ch.get('playlist_index') is not None else None,
            'group': ch.get('group'),
            'source': ch.get('source')
        })
    return jsonify({'channels': out, 'timestamp': datetime.now(timezone.utc).isoformat()})

@app.route('/api/news', methods=['GET'])
@login_required
def api_news():
    """Return headlines from the configured RSS/Atom feeds.

    The server computes ``feed_index`` from wall-clock time so all clients see
    the same feed and cycling continues even when nobody is tuned in.
    ``ms_until_next_feed`` tells the client exactly when to fetch the next feed.

    * 6 feeds → 5 min each  (6 × 5 min = 30 min block)
    * 3 feeds → 10 min each (3 × 10 min = 30 min block)
    * 1 feed  → 30 min
    * 0 feeds → 5 min fallback (no feed configured)
    """
    feeds = get_news_feed_urls()
    feed_count = len(feeds)
    refresh_ms = int((30 * 60 * 1000) / feed_count) if feed_count else 5 * 60 * 1000
    feed_index, ms_until_next_feed, elapsed_in_slot_ms = get_current_feed_state(feed_count)
    # Compute the wall-clock time when the current feed slot started so that
    # all viewers see the same "Updated" time regardless of when they tune in.
    slot_start = datetime.now(timezone.utc) - timedelta(milliseconds=elapsed_in_slot_ms)
    if feeds:
        headlines = fetch_rss_headlines(feeds[feed_index])
    else:
        headlines = []
    return jsonify({
        "updated": slot_start.isoformat(),
        "headlines": headlines,
        "feed_count": feed_count,
        "feed_index": feed_index,
        "refresh_ms": refresh_ms,
        "ms_until_next_feed": ms_until_next_feed,
    })

@app.route('/news')
@login_required
def news_page():
    """Retro TV news overlay page."""
    log_event(current_user.username, "Loaded news page")
    return render_template('news.html')

@app.route('/news.html')
@login_required
def news_page_compat():
    """Redirect legacy .html URL to canonical /news route."""
    return redirect(url_for('news_page'), 301)

@app.route('/weather')
@login_required
def weather_page():
    """Retro TV weather overlay page."""
    log_event(current_user.username, "Loaded weather page")
    return render_template('weather.html')

@app.route('/traffic')
@login_required
def traffic_page():
    """Retro TV traffic overlay page."""
    log_event(current_user.username, "Loaded traffic page")
    return render_template('traffic.html')

@app.route('/status')
@login_required
def status_page():
    """Retro TV system status overlay page."""
    log_event(current_user.username, "Loaded status page")
    return render_template('status.html')

@app.route('/sports')
@login_required
def sports_page():
    """Retro TV sports scores overlay page."""
    log_event(current_user.username, "Loaded sports page")
    return render_template('sports.html')

@app.route('/api/sports', methods=['GET'])
@login_required
def api_sports():
    """Sports overlay data endpoint.

    Returns a not-configured response when external sports data is disabled.

    When external data is enabled, branches on the configured mode:
    * ``'rss'``    — returns RSS/Atom headlines from up to 6 user-supplied feeds,
                     cycling wall-clock aligned the same way as /api/news.
    * ``'scores'`` — returns today's game scores from the user-configured scores
                     endpoint, cycling through enabled leagues every 60 s
                     (wall-clock aligned).

    Both modes include ``mode``, ``ms_until_next``, and ``updated`` in the response.
    """
    sports_cfg = get_sports_config()
    mode = sports_cfg.get('mode', 'scores')
    music_filename = get_channel_music_file('virtual.sports')
    music_file = f'/static/audio/{music_filename}' if music_filename else ''
    _now_ts = datetime.now(timezone.utc).timestamp()

    if not sports_cfg.get('external_data_enabled', False):
        return jsonify({
            'mode':          mode,
            'updated':       datetime.now(timezone.utc).isoformat(),
            'not_configured': True,
            'league':        None,
            'games':         [],
            'headlines':     [],
            'ms_until_next': 60 * 1000,
            'music_file':    music_file,
        })

    if mode == 'rss':
        feeds = get_sports_feed_urls()
        feed_count = len(feeds)
        refresh_ms = int((30 * 60 * 1000) / feed_count) if feed_count else 5 * 60 * 1000
        feed_index, ms_until_next_feed, elapsed_in_slot_ms = get_current_feed_state(feed_count)
        slot_start = datetime.now(timezone.utc) - timedelta(milliseconds=elapsed_in_slot_ms)
        headlines = fetch_rss_headlines(feeds[feed_index]) if feeds else []
        return jsonify({
            'mode':              'rss',
            'updated':           slot_start.isoformat(),
            'headlines':         headlines,
            'feed_count':        feed_count,
            'feed_index':        feed_index,
            'refresh_ms':        refresh_ms,
            'ms_until_next':     ms_until_next_feed,
            'music_file':        music_file,
        })

    # scores mode — cycle through enabled leagues every 60 s
    _cycle_seconds = 60
    enabled_league_ids = [lg_id for lg_id, on in sports_cfg.get('leagues', {}).items() if on]
    # Preserve SPORTS_LEAGUES ordering
    enabled_leagues = [lg for lg in SPORTS_LEAGUES if lg['id'] in set(enabled_league_ids)]
    league_count = len(enabled_leagues)
    if league_count == 0:
        return jsonify({
            'mode':          'scores',
            'updated':       datetime.now(timezone.utc).isoformat(),
            'league':        None,
            'games':         [],
            'ms_until_next': _cycle_seconds * 1000,
            'music_file':    music_file,
        })

    slot_seconds = _cycle_seconds
    block_seconds = slot_seconds * league_count
    elapsed_in_block = _now_ts % block_seconds
    league_index = int(elapsed_in_block // slot_seconds)
    ms_until_next = int((slot_seconds - (elapsed_in_block % slot_seconds)) * 1000)
    slot_start_ts = _now_ts - (elapsed_in_block % slot_seconds)
    slot_start = datetime.fromtimestamp(slot_start_ts, tz=timezone.utc)

    current_league = enabled_leagues[league_index % league_count]
    scores_base_url = sports_cfg.get('scores_base_url', '')
    games = fetch_scores(current_league['sport'], current_league['league_slug'], scores_base_url)
    return jsonify({
        'mode':          'scores',
        'updated':       slot_start.isoformat(),
        'league':        current_league,
        'league_index':  league_index,
        'league_count':  league_count,
        'games':         games,
        'ms_until_next': ms_until_next,
        'music_file':    music_file,
    })


@app.route('/nasa')
@login_required
def nasa_page():
    """Retro TV NASA imagery overlay page."""
    log_event(current_user.username, "Loaded nasa page")
    return render_template('nasa.html')


@app.route('/api/nasa', methods=['GET'])
@login_required
def api_nasa():
    """NASA Imagery overlay data endpoint.

    Fetches APOD images from the NASA API and rotates through them on a
    wall-clock-aligned schedule so all viewers see the same image at any
    given moment.

    Cycle logic
    -----------
    * cycle_seconds  = interval_minutes × 60  (900 or 1800)
    * slot_seconds   = cycle_seconds ÷ image_count  (always an integer)
    * image_index    = floor((now_ts % cycle_seconds) ÷ slot_seconds)
    * ms_until_next  = remaining ms in the current slot

    Examples:
        15-min /  5 images → 180 s (3 min) per image
        15-min / 15 images →  60 s (1 min) per image
        30-min / 10 images → 180 s (3 min) per image
        30-min / 15 images → 120 s (2 min) per image

    Images are cached for one full cycle so we make at most one NASA API
    call per cycle regardless of how many clients are tuned to the channel.
    """
    nasa_cfg = get_nasa_config()
    interval = nasa_cfg['interval']
    image_count = nasa_cfg['image_count']
    seconds_per_image = nasa_cfg['seconds_per_image']
    api_key = nasa_cfg['api_key']
    music_filename = get_channel_music_file('virtual.nasa')
    music_file = f'/static/audio/{music_filename}' if music_filename else ''

    cycle_seconds = int(interval) * 60  # 900 or 1800

    _now_ts = datetime.now(timezone.utc).timestamp()

    # Cache key encodes every setting that affects which images we show, so a
    # change in the admin panel takes effect on the very next cycle boundary.
    cache_key = f'{interval}:{image_count}:{api_key}'
    cached = _NASA_APOD_CACHE.get(cache_key)
    images: list = []
    if cached:
        imgs, cached_at = cached
        # Keep the cache alive for one full cycle so we don't re-fetch mid-cycle.
        if _now_ts - cached_at < cycle_seconds:
            images = imgs
    if not images:
        fetched = _fetch_nasa_apod_images(image_count, api_key)
        if fetched:
            images = fetched
            _NASA_APOD_CACHE[cache_key] = (images, _now_ts)

    elapsed_in_cycle = _now_ts % cycle_seconds
    image_index = int(elapsed_in_cycle / seconds_per_image)
    # Guard against floating-point overshoot at cycle boundaries
    image_index = min(image_index, image_count - 1)
    ms_until_next = int((seconds_per_image - (elapsed_in_cycle % seconds_per_image)) * 1000)
    slot_start_ts = _now_ts - (elapsed_in_cycle % seconds_per_image)
    slot_start = datetime.fromtimestamp(slot_start_ts, tz=timezone.utc)

    current_image = images[image_index % len(images)] if images else None

    return jsonify({
        'interval':          interval,
        'image_count':       image_count,
        'seconds_per_image': seconds_per_image,
        'image':             current_image,
        'image_index':       image_index,
        'total_images':      len(images),
        'ms_until_next':     ms_until_next,
        'updated':           slot_start.isoformat(),
        'music_file':        music_file,
    })


@app.route('/on_this_day')
@login_required
def on_this_day_page():
    """Retro TV On This Day overlay page."""
    log_event(current_user.username, "Loaded on_this_day page")
    return render_template('on_this_day.html')


@app.route('/api/on_this_day', methods=['GET'])
@login_required
def api_on_this_day():
    """On This Day overlay data endpoint.

    Collects historical events, births, and deaths from the Wikipedia REST API
    (or user-supplied custom entries when a source is disabled) and rotates
    through them on a wall-clock-aligned schedule so all viewers see the same
    event at the same moment.

    Cycle logic
    -----------
    * seconds_per_event = _ON_THIS_DAY_SECONDS_PER_EVENT  (30 s)
    * event_index       = floor((now_ts % (event_count × 30)) ÷ 30)
    * ms_until_next     = remaining ms in the current 30-second slot

    Events are cached for _ON_THIS_DAY_CACHE_TTL (6 hours) per Wikipedia
    source/month/day so we make at most one Wikipedia API call per 6-hour
    window regardless of how many clients are tuned to the channel.
    """
    now = datetime.now(timezone.utc)
    month = now.month
    day   = now.day
    now_ts = now.timestamp()

    month_name = now.strftime('%B')
    date_label = f"{month_name} {now.day}"

    music_filename = get_channel_music_file('virtual.on_this_day')
    music_file = f'/static/audio/{music_filename}' if music_filename else ''

    # Gather events from all enabled sources (or custom events for disabled ones)
    all_events: list = []
    source_info = {}
    for src in ON_THIS_DAY_SOURCES:
        sid = src['id']
        enabled = get_on_this_day_source_enabled(sid)
        wiki_url = (
            f"https://en.wikipedia.org/api/rest_v1/feed/onthisday"
            f"/{src['api_type']}/{month:02d}/{day:02d}"
        )
        source_info[sid] = {
            'enabled':       enabled,
            'label':         src['label'],
            'category':      src['category'],
            'wiki_url':      wiki_url,
            'wiki_page_url': (
                f"https://en.wikipedia.org/wiki/{month_name}_{day}"
                f"#{src['wiki_section']}"
            ),
        }
        if enabled:
            fetched = _fetch_on_this_day_from_wikipedia(src['api_type'], month, day)
            all_events.extend(fetched)
        else:
            custom = get_on_this_day_custom_events(sid)
            all_events.extend(custom)

    event_count = len(all_events)
    if event_count == 0:
        return jsonify({
            'month':             month,
            'day':               day,
            'date_label':        date_label,
            'events':            [],
            'event':             None,
            'event_index':       0,
            'event_count':       0,
            'seconds_per_event': _ON_THIS_DAY_SECONDS_PER_EVENT,
            'ms_until_next':     _ON_THIS_DAY_SECONDS_PER_EVENT * 1000,
            'sources':           source_info,
            'music_file':        music_file,
        })

    cycle_seconds = event_count * _ON_THIS_DAY_SECONDS_PER_EVENT
    elapsed_in_cycle = now_ts % cycle_seconds
    event_index = int(elapsed_in_cycle / _ON_THIS_DAY_SECONDS_PER_EVENT)
    event_index = min(event_index, event_count - 1)
    ms_until_next = int(
        (_ON_THIS_DAY_SECONDS_PER_EVENT - (elapsed_in_cycle % _ON_THIS_DAY_SECONDS_PER_EVENT))
        * 1000
    )

    current_event = all_events[event_index]

    return jsonify({
        'month':             month,
        'day':               day,
        'date_label':        date_label,
        'events':            all_events,
        'event':             current_event,
        'event_index':       event_index,
        'event_count':       event_count,
        'seconds_per_event': _ON_THIS_DAY_SECONDS_PER_EVENT,
        'ms_until_next':     ms_until_next,
        'sources':           source_info,
        'music_file':        music_file,
    })


@app.route('/api/weather', methods=['GET'])
@login_required
def api_weather():
    """Weather overlay data endpoint. Returns current conditions, today's forecast,
    extended outlook, 5-day forecast, radar URL, and breaking news ticker.
    Calls open-meteo when configured.

    The channel cycles through 4 segments wall-clock aligned:
      0 – Current Conditions
      1 – 5-Day Forecast
      2 – Regional Radar
      3 – Severe Weather Alerts

    Each segment lasts ``seconds_per_segment`` seconds (admin-configurable, default 300 s).
    """
    cfg = get_weather_config()
    payload = _build_weather_payload(cfg)
    music_filename = get_channel_music_file('virtual.weather')
    payload['music_file'] = f'/static/audio/{music_filename}' if music_filename else ''

    # Configurable segment duration (validated to [30, 600] on save; clamp defensively)
    try:
        seconds_per_segment = max(30, min(600, int(cfg.get('seconds_per_segment') or
                                                    _WEATHER_SECONDS_PER_SEGMENT_DEFAULT)))
    except (TypeError, ValueError):
        seconds_per_segment = _WEATHER_SECONDS_PER_SEGMENT_DEFAULT

    # Wall-clock aligned 4-segment cycle
    _cycle_seconds = 4 * seconds_per_segment
    _now_ts = datetime.now(timezone.utc).timestamp()
    _cycle_pos = _now_ts % _cycle_seconds
    segment = int(_cycle_pos / seconds_per_segment)
    ms_until_next = int((seconds_per_segment - (_cycle_pos % seconds_per_segment)) * 1000)

    payload['segment'] = segment
    payload['segment_label'] = _WEATHER_SEGMENT_LABELS[segment]
    payload['seconds_per_segment'] = seconds_per_segment
    payload['ms_until_next'] = ms_until_next
    return jsonify(payload)

@app.route('/api/traffic', methods=['GET'])
@login_required
def api_traffic():
    """Traffic overlay data endpoint — Demo Mode.
    Returns simulated congestion data for a rotating U.S. city.
    No external API or configuration required."""
    payload = dict(_build_traffic_demo_payload())
    music_filename = get_channel_music_file('virtual.traffic')
    payload['music_file'] = f'/static/audio/{music_filename}' if music_filename else ''
    _now_ts = time.time()
    rotation_seconds = max(30, int(get_traffic_demo_config().get('rotation_seconds', 120)))
    payload['ms_until_next'] = int(
        (rotation_seconds - (_now_ts % rotation_seconds)) * 1000
    )
    return jsonify(payload)


@app.route('/api/traffic/demo', methods=['GET'])
@login_required
def api_traffic_demo():
    """Alias for /api/traffic — always returns demo mode payload."""
    return api_traffic()


@app.route('/api/traffic/demo/cities', methods=['GET'])
@login_required
def api_traffic_demo_cities():
    """Return all cities from traffic_demo_cities table."""
    return jsonify({'cities': get_traffic_demo_cities()})


@app.route('/api/traffic/demo/cities/<int:city_id>', methods=['POST'])
@login_required
def api_traffic_demo_city_update(city_id):
    """Update enabled/weight for a single city (admin action)."""
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', True))
    weight  = max(1, int(data.get('weight', 1)))
    try:
        save_traffic_demo_city(city_id, enabled, weight)
        return jsonify({'ok': True})
    except Exception as exc:
        logging.exception("api_traffic_demo_city_update failed for city_id=%s: %s", city_id, exc)
        return jsonify({'ok': False, 'error': 'Internal server error'}), 500


@app.route('/api/traffic/demo/enable_all', methods=['POST'])
@login_required
def api_traffic_demo_enable_all():
    """Enable all cities."""
    set_all_traffic_demo_cities_enabled(True)
    return jsonify({'ok': True})


@app.route('/api/traffic/demo/disable_all', methods=['POST'])
@login_required
def api_traffic_demo_disable_all():
    """Disable all cities."""
    set_all_traffic_demo_cities_enabled(False)
    return jsonify({'ok': True})


@app.route('/api/traffic/demo/pick_random', methods=['POST'])
@login_required
def api_traffic_demo_pick_random():
    """Randomly pick N cities and store as the rotation pack."""
    data = request.get_json(silent=True) or {}
    demo_cfg = get_traffic_demo_config()
    n = int(data.get('pack_size', demo_cfg.get('pack_size', 10)))
    chosen = pick_random_traffic_demo_pack(n)
    return jsonify({'ok': True, 'cities': chosen})


@app.route('/api/traffic/demo/roads/<int:city_id>', methods=['GET'])
@login_required
def api_traffic_demo_roads(city_id):
    """Return GeoJSON road geometry for a city fetched from the free Overpass API.
    Results are cached server-side per city (24h TTL).
    No API key required — Overpass is a free public service."""
    geojson = get_traffic_demo_roads(city_id)
    return jsonify(geojson)

@app.route('/api/virtual/status', methods=['GET'])
@login_required
def api_virtual_status():
    """Return system status data for the virtual status channel overlay."""
    _LOAD_WARN_THRESHOLD  = 2.0
    _DISK_WARN_THRESHOLD  = 70
    _DISK_ERROR_THRESHOLD = 85

    uptime_seconds = int((datetime.now() - APP_START_TIME).total_seconds())
    hours, rem = divmod(uptime_seconds, 3600)
    minutes = rem // 60

    # System load (Unix only; graceful fallback on Windows)
    try:
        load1, load5, load15 = os.getloadavg()
        load_str = f"{load1:.2f}  {load5:.2f}  {load15:.2f}"
        load_state = "warn" if load1 > _LOAD_WARN_THRESHOLD else "good"
    except (AttributeError, OSError):
        load_str = "N/A"
        load_state = "good"

    # Disk free on root (Unix) or current drive (Windows)
    try:
        st = os.statvfs('/')
        disk_free_gb = (st.f_bavail * st.f_frsize) / (1024 ** 3)
        disk_total_gb = (st.f_blocks * st.f_frsize) / (1024 ** 3)
        disk_used_pct = int(100 * (1 - st.f_bavail / st.f_blocks)) if st.f_blocks else 0
        disk_str = f"{disk_free_gb:.1f} GB free of {disk_total_gb:.1f} GB"
        if disk_used_pct > _DISK_ERROR_THRESHOLD:
            disk_state = "error"
        elif disk_used_pct > _DISK_WARN_THRESHOLD:
            disk_state = "warn"
        else:
            disk_state = "good"
    except (AttributeError, OSError):
        disk_str = "N/A"
        disk_state = "good"
        disk_used_pct = 0

    # Channel count
    try:
        channel_count = len(cached_channels)
    except Exception:
        channel_count = 0

    items = [
        {"label": "App Status",     "value": "Running",                     "state": "good"},
        {"label": "Version",        "value": APP_VERSION,                    "state": "good"},
        {"label": "Uptime",         "value": f"{hours}h {minutes}m",        "state": "good"},
        {"label": "Platform",       "value": platform.system() + " " + platform.release(), "state": "good"},
        {"label": "Python",         "value": sys.version.split()[0],        "state": "good"},
        {"label": "Load Avg",       "value": load_str,                      "state": load_state},
        {"label": "Disk",           "value": disk_str,                      "state": disk_state},
        {"label": "Channels",       "value": str(channel_count),            "state": "good"},
    ]

    return jsonify({
        "updated": datetime.now(timezone.utc).isoformat(),
        "app_version": APP_VERSION,
        "uptime": f"{hours}h {minutes}m",
        "uptime_seconds": uptime_seconds,
        "overall_state": "good",
        "items": items,
        "disk_used_pct": disk_used_pct,
        "ticker": [item["label"] + ": " + item["value"] for item in items],
        "ms_until_next": 30000,
    })

# ─── Updates / Announcements virtual channel ──────────────────────────────────

_GITHUB_REPO = "thehack904/RetroIPTVGuide"
_GITHUB_RELEASES_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases"
_UPDATES_CACHE_TTL = 1800   # 30 minutes
_updates_cache: dict = {"data": None, "fetched_at": 0.0}
_updates_cache_lock = threading.Lock()


def _fetch_github_releases() -> list:
    """Fetch releases from the GitHub API, returning a list of dicts.
    Returns an empty list on any error so the channel degrades gracefully."""
    try:
        resp = requests.get(
            _GITHUB_RELEASES_URL,
            timeout=8,
            headers={
                "User-Agent": "RetroIPTVGuide/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        releases = resp.json()
        if not isinstance(releases, list):
            return []
        result = []
        for rel in releases[:10]:
            result.append({
                "tag":        str(rel.get("tag_name", "")),
                "name":       str(rel.get("name", "") or rel.get("tag_name", "")),
                "body":       str(rel.get("body", "") or ""),
                "prerelease": bool(rel.get("prerelease", False)),
                "draft":      bool(rel.get("draft", False)),
                "published":  str(rel.get("published_at", "") or ""),
                "url":        str(rel.get("html_url", "")),
            })
        return result
    except Exception:
        logging.warning("Failed to fetch GitHub releases for updates channel", exc_info=True)
        return []


def _get_cached_releases() -> list:
    """Return cached GitHub releases, refreshing when the TTL has expired."""
    with _updates_cache_lock:
        now = time.time()
        if _updates_cache["data"] is None or (now - _updates_cache["fetched_at"]) > _UPDATES_CACHE_TTL:
            releases = _fetch_github_releases()
            _updates_cache["data"] = releases
            _updates_cache["fetched_at"] = now
        return _updates_cache["data"]


def get_updates_config() -> dict:
    """Return updates channel configuration.

    Keys
    ----
    show_beta : bool  — whether pre-release / beta GitHub releases are shown
                        on the Updates & Announcements channel (default False).
    """
    defaults = {"show_beta": "0"}
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            for key in defaults:
                c.execute("SELECT value FROM settings WHERE key=?", (f"updates.{key}",))
                row = c.fetchone()
                if row is not None:
                    defaults[key] = row[0]
    except Exception:
        logging.exception("get_updates_config failed, using defaults")
    return {"show_beta": defaults["show_beta"] == "1"}


def save_updates_config(cfg: dict) -> None:
    """Persist updates channel configuration."""
    show_beta = bool(cfg.get("show_beta", False))
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("updates.show_beta", "1" if show_beta else "0"),
            )
            conn.commit()
    except Exception:
        logging.exception("save_updates_config failed")
        raise


@app.route('/api/virtual/updates', methods=['GET'])
@login_required
def api_virtual_updates():
    """Return version update and release-notes data for the Updates & Announcements virtual channel.

    Pulls from the GitHub releases API (cached 30 min).  Falls back to showing
    the current APP_VERSION when the API is unreachable.
    Pre-releases are included only when the show_beta setting is enabled."""
    cfg = get_updates_config()
    show_beta = cfg["show_beta"]
    all_releases = _get_cached_releases()

    # Filter out pre-releases when show_beta is disabled
    releases = [r for r in all_releases if not r["draft"] and (show_beta or not r["prerelease"])]

    # Latest non-draft, non-filtered release is the one featured prominently.
    latest = releases[0] if releases else None

    # Build ticker from (filtered) release tag names + dates
    ticker_parts = []
    for r in releases:
        date_str = ''
        if r.get("published"):
            try:
                pub = datetime.fromisoformat(r["published"].replace('Z', '+00:00'))
                date_str = ' \u2014 ' + pub.strftime('%b %d, %Y')
            except Exception:
                pass
        if r["prerelease"]:
            label = "\u26A0\uFE0F Pre-release: " + r["tag"] + date_str
        else:
            label = "Release " + r["tag"] + date_str
        ticker_parts.append(label)
    if not ticker_parts:
        ticker_parts = [f"Current version: {APP_VERSION}"]

    now_ts = time.time()
    fetched_at = _updates_cache.get("fetched_at", 0.0)
    elapsed = now_ts - fetched_at if fetched_at > 0 else _UPDATES_CACHE_TTL
    ms_until_next = max(0, int((_UPDATES_CACHE_TTL - elapsed) * 1000))

    return jsonify({
        "updated":      datetime.now(timezone.utc).isoformat(),
        "app_version":  APP_VERSION,
        "latest":       latest,
        "releases":     releases,
        "ticker":       ticker_parts,
        "repo":         _GITHUB_REPO,
        "show_beta":    show_beta,
        "ms_until_next": ms_until_next,
    })


@app.route('/api/channel_mix', methods=['GET'])
@login_required
def api_channel_mix():
    """Return the current active channel in the Channel Mix based on wall-clock time.

    The active channel is determined by cycling through the configured channels
    in order, each playing for its configured duration.  All viewers always see
    the same active channel at the same moment (wall-clock-aligned scheduling).

    Response JSON:
      name               – display name of the mix (str)
      active_type        – overlay_type of the currently-active channel, or null
      active_name        – display name of the currently-active channel, or null
      active_tvg_id      – tvg_id of the currently-active channel, or null
      seconds_remaining  – seconds until the next channel switch (int)
      total_cycle_seconds – total cycle length in seconds (int)
      channels           – list of configured channel dicts (tvg_id, name,
                           overlay_type, duration_minutes)
    """
    cfg = get_channel_mix_config()
    mix_channels = cfg['channels']

    # Build a lookup of tvg_id → channel metadata from VIRTUAL_CHANNELS
    ch_meta = {ch['tvg_id']: ch for ch in VIRTUAL_CHANNELS}

    enriched = []
    for entry in mix_channels:
        meta = ch_meta.get(entry['tvg_id'], {})
        enriched.append({
            'tvg_id':           entry['tvg_id'],
            'name':             meta.get('name', entry['tvg_id']),
            'overlay_type':     meta.get('overlay_type', ''),
            'duration_minutes': entry['duration_minutes'],
        })

    active_tvg_id, seconds_remaining = _get_active_channel_mix_slot(mix_channels)
    active_meta = ch_meta.get(active_tvg_id, {}) if active_tvg_id else {}
    total_cycle_seconds = sum(ch['duration_minutes'] * 60 for ch in mix_channels)

    return jsonify({
        'name':               cfg['name'],
        'active_type':        active_meta.get('overlay_type') if active_tvg_id else None,
        'active_name':        active_meta.get('name') if active_tvg_id else None,
        'active_tvg_id':      active_tvg_id,
        'seconds_remaining':  seconds_remaining,
        'total_cycle_seconds': total_cycle_seconds,
        'channels':           enriched,
    })


@app.route('/updates')
@login_required
def updates_page():
    """Retro TV updates & announcements overlay page."""
    log_event(current_user.username, "Loaded updates page")
    return render_template('updates.html')


# ─── Audio upload / management routes ────────────────────────────────────────

@app.route('/api/audio/files', methods=['GET'])
@login_required
def api_audio_files():
    """Return a JSON list of uploaded audio filenames."""
    return jsonify({'files': list_audio_files()})

@app.route('/api/audio/upload', methods=['POST'])
@login_required
def api_audio_upload():
    """Upload an audio file to the audio directory."""
    if 'audio_file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400
    f = request.files['audio_file']
    if not f or not f.filename:
        return jsonify({'error': 'No file selected.'}), 400
    original_name = f.filename
    safe_name = secure_filename(original_name)
    if not safe_name:
        return jsonify({'error': 'Invalid filename.'}), 400
    ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        return jsonify({'error': f'Unsupported file type. Allowed: {", ".join(sorted(_ALLOWED_AUDIO_EXTENSIONS))}'}), 400
    os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(AUDIO_UPLOAD_DIR, safe_name)
    # Verify destination stays inside AUDIO_UPLOAD_DIR (prevent path traversal)
    real_dest = os.path.realpath(dest)
    real_dir = os.path.realpath(AUDIO_UPLOAD_DIR)
    if os.path.commonpath([real_dir, real_dest]) != real_dir:
        return jsonify({'error': 'Invalid filename.'}), 400
    f.save(dest)
    log_event(current_user.username, f"Uploaded audio file: {safe_name}")
    return jsonify({'ok': True, 'filename': safe_name}), 201

@app.route('/api/audio/delete/<filename>', methods=['POST'])
@login_required
def api_audio_delete(filename):
    """Delete an uploaded audio file."""
    safe_name = secure_filename(filename)
    if not safe_name:
        return jsonify({'error': 'Invalid filename.'}), 400
    ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        return jsonify({'error': 'Invalid filename.'}), 400
    target = os.path.join(AUDIO_UPLOAD_DIR, safe_name)
    # Verify it stays inside AUDIO_UPLOAD_DIR (prevent path traversal)
    if os.path.abspath(target) != os.path.join(os.path.abspath(AUDIO_UPLOAD_DIR), safe_name):
        return jsonify({'error': 'Invalid filename.'}), 400
    if not os.path.isfile(target):
        return jsonify({'error': 'File not found.'}), 404
    os.remove(target)
    log_event(current_user.username, f"Deleted audio file: {safe_name}")
    return jsonify({'ok': True})


# ─── Logo upload / management routes ─────────────────────────────────────────

@app.route('/api/logo/upload', methods=['POST'])
@login_required
def api_logo_upload():
    """Upload a custom channel logo image for a virtual channel."""
    if current_user.username != 'admin':
        return jsonify({'error': 'Admin access required.'}), 403
    tvg_id = request.form.get('tvg_id', '').strip()
    valid_ids = {ch['tvg_id'] for ch in VIRTUAL_CHANNELS}
    if tvg_id not in valid_ids:
        return jsonify({'error': 'Unknown virtual channel.'}), 400
    if 'logo_file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400
    f = request.files['logo_file']
    if not f or not f.filename:
        return jsonify({'error': 'No file selected.'}), 400
    original_name = f.filename
    safe_name = secure_filename(original_name)
    if not safe_name:
        return jsonify({'error': 'Invalid filename.'}), 400
    ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
    if ext not in _ALLOWED_LOGO_EXTENSIONS:
        return jsonify({'error': f'Unsupported file type. Allowed: {", ".join(sorted(_ALLOWED_LOGO_EXTENSIONS))}'}), 400
    # Prefix filename with tvg_id slug to avoid name collisions between channels.
    # Use re.sub to allow only alphanumeric characters and underscores, then
    # apply secure_filename to eliminate any remaining special characters and
    # break the taint chain from user-controlled tvg_id to the filesystem path.
    slug = re.sub(r'[^a-zA-Z0-9_]', '_', tvg_id)
    dest_name = secure_filename(f'{slug}_logo.{ext}')
    if not dest_name:
        return jsonify({'error': 'Invalid filename.'}), 400
    os.makedirs(LOGO_UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(LOGO_UPLOAD_DIR, dest_name)
    # Verify destination stays inside LOGO_UPLOAD_DIR (prevent path traversal)
    real_dest = os.path.realpath(dest)
    real_dir = os.path.realpath(LOGO_UPLOAD_DIR)
    if os.path.commonpath([real_dir, real_dest]) != real_dir:
        return jsonify({'error': 'Invalid filename.'}), 400
    f.save(real_dest)
    try:
        save_channel_custom_logo(tvg_id, dest_name)
    except ValueError as exc:
        logging.warning("api_logo_upload: invalid logo for %s: %s", tvg_id, exc)
        return jsonify({'error': 'Invalid logo file.'}), 400
    log_event(current_user.username, f"Uploaded logo for {tvg_id}: {dest_name}")
    return jsonify({'ok': True, 'filename': dest_name, 'url': f'/static/logos/virtual/{dest_name}'}), 201


@app.route('/api/logo/reset/<tvg_id>', methods=['POST'])
@login_required
def api_logo_reset(tvg_id):
    """Reset a virtual channel's logo to the built-in default (or icon pack if enabled)."""
    if current_user.username != 'admin':
        return jsonify({'error': 'Admin access required.'}), 403
    valid_ids = {ch['tvg_id'] for ch in VIRTUAL_CHANNELS}
    if tvg_id not in valid_ids:
        return jsonify({'error': 'Unknown virtual channel.'}), 400
    try:
        save_channel_custom_logo(tvg_id, '')
    except Exception:
        return jsonify({'error': 'Failed to reset logo.'}), 500
    log_event(current_user.username, f"Reset logo for {tvg_id} to default")
    effective_url = _resolve_channel_logo(
        tvg_id,
        _DEFAULT_CHANNEL_LOGOS.get(tvg_id, ''),
        '',
        get_use_icon_pack(),
    )
    return jsonify({'ok': True, 'url': effective_url})


@app.route('/api/virtual/icon_pack', methods=['GET', 'POST'])
@login_required
def api_virtual_icon_pack():
    """GET: return current icon pack state. POST: toggle or set the icon pack preference."""
    if request.method == 'GET':
        return jsonify({'enabled': get_use_icon_pack()})
    # POST
    if current_user.username != 'admin':
        return jsonify({'error': 'Admin access required.'}), 403
    data = request.get_json(silent=True) or {}
    if 'enabled' not in data:
        return jsonify({'error': 'Missing "enabled" field.'}), 400
    enabled = bool(data['enabled'])
    try:
        set_use_icon_pack(enabled)
    except Exception:
        return jsonify({'error': 'Failed to save icon pack setting.'}), 500
    log_event(current_user.username, f"Icon pack {'enabled' if enabled else 'disabled'}")
    # Build effective logo map so the browser can refresh previews immediately
    logos = {}
    for ch in VIRTUAL_CHANNELS:
        custom = get_channel_custom_logo(ch['tvg_id'])
        logos[ch['tvg_id']] = _resolve_channel_logo(
            ch['tvg_id'], ch['logo'], custom, enabled
        )
    return jsonify({'ok': True, 'enabled': enabled, 'logos': logos})


@app.route('/api/overlay/settings', methods=['GET'])
@login_required
def api_overlay_settings():
    """Return overlay appearance settings. Use ?channel=tvg_id for per-channel settings."""
    channel = request.args.get('channel', '').strip()
    valid_ids = {ch['tvg_id'] for ch in VIRTUAL_CHANNELS}
    if channel and channel in valid_ids:
        return jsonify(get_channel_overlay_appearance(channel))
    return jsonify(get_overlay_appearance())

@app.route('/api/current_program', methods=['GET'])
@login_required
def api_current_program():
    """
    Return the currently playing program info for a given channel id.
    Query params:
      - tvg_id (preferred) OR id (fallback) — the channel identifier used in cached_channels
    Response:
      { ok: True, channel: "<name>", tvg_id: "<id>", program: { title, desc, start_iso, stop_iso } }
      or { ok: False, error: "..." }
    """
    tvg_id = request.args.get('tvg_id') or request.args.get('id') or ''
    if not tvg_id:
        return jsonify({"ok": False, "error": "missing tvg_id or id"}), 400

    try:
        now = datetime.now(timezone.utc)
        # find channel name
        channel_name = None
        for ch in cached_channels:
            if ch.get('tvg_id') == tvg_id or str(ch.get('number')) == str(tvg_id):
                channel_name = ch.get('name')
                break

        # get epg entries for tvg_id
        programs = cached_epg.get(tvg_id) or []
        current_prog = None
        for prog in programs:
            start = prog.get('start')
            stop = prog.get('stop')
            # some programs may be missing start/stop (fallback entries)
            if start and stop:
                # ensure timezone-aware comparison — cached_epg should use UTC timezone if parsed as such
                if start <= now <= stop:
                    current_prog = prog
                    break

        # if not found, maybe the first fallback entry or nearest upcoming/current
        if not current_prog and programs:
            # prefer any entry with a real title
            for prog in programs:
                if prog.get('title') and prog.get('title') != 'No Guide Data Available':
                    current_prog = prog
                    break
            if not current_prog:
                current_prog = programs[0]

        if current_prog:
            return jsonify({
                "ok": True,
                "channel": channel_name,
                "tvg_id": tvg_id,
                "program": {
                    "title": current_prog.get('title') or '',
                    "desc": current_prog.get('desc') or '',
                    "start_iso": (current_prog.get('start').isoformat() if current_prog.get('start') else None),
                    "stop_iso": (current_prog.get('stop').isoformat() if current_prog.get('stop') else None)
                }
            })
        else:
            return jsonify({
                "ok": True,
                "channel": channel_name,
                "tvg_id": tvg_id,
                "program": {
                    "title": "No Guide Data Available",
                    "desc": "",
                    "start_iso": None,
                    "stop_iso": None
                }
            })
    except Exception as e:
        logging.exception("api_current_program error: %s", e)
        return jsonify({"ok": False, "error": "Internal server error"}), 500

@app.route('/logs', methods=['GET'], endpoint='view_logs')
@login_required
def view_logs():
    if current_user.username != 'admin':
        log_event(current_user.username, "Unauthorized access attempt to /logs")
        return redirect(url_for('guide'))

    log_event(current_user.username, "Accessed logs page")
    entries = []
    entry_count = 0

    try:
        with sqlite3.connect(DATABASE, timeout=10) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT username, action, timestamp FROM activity_logs ORDER BY id ASC"
            )
            for row in c.fetchall():
                user, action, timestamp = row
                log_type = "security" if any(
                    x in action.lower() for x in
                    ["unauthorized", "revoked", "failed", "denied"]
                ) else "activity"
                entries.append((user, action, timestamp, log_type))
        entry_count = len(entries)
    except Exception as e:  # noqa: BLE001
        logging.exception("view_logs: failed to read activity_logs: %s", e)
        entries = [("system", "Error reading log database.", "", "activity")]

    return render_template(
        "logs.html",
        entries=entries,
        current_tuner=get_current_tuner(),
        entry_count=entry_count
    )



@app.route('/clear_logs', methods=['POST'])
@login_required
def clear_logs():
    if current_user.username != 'admin':
        flash("Unauthorized access.")
        return redirect(url_for('guide'))

    try:
        with sqlite3.connect(DATABASE, timeout=10) as conn:
            conn.execute("DELETE FROM activity_logs")
            conn.commit()
    except Exception as e:  # noqa: BLE001
        logging.exception("clear_logs: failed to clear activity_logs: %s", e)
        flash("⚠️ Failed to clear logs.")
        return redirect(url_for('admin_diagnostics.diagnostics_index', tab='activity'))
    log_event("admin", "Cleared activity logs")
    flash("🧹 Logs cleared successfully.")
    return redirect(url_for('admin_diagnostics.diagnostics_index', tab='activity'))


# ------------------- Constants -------------------
SCALE = 5
HOURS_SPAN = 6
SLOT_MINUTES = 30

# ------------------- Main -------------------
def ensure_default_tuner():
    conn = sqlite3.connect(TUNER_DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM tuners")
    count = c.fetchone()[0]
    if count == 0:
        # Insert a safe default
        c.execute(
            "INSERT INTO tuners (name, xml, m3u) VALUES (?, ?, ?)",
            ("Tuner 1", "http://example.com/guide.xml", "http://example.com/playlist.m3u")
        )
        conn.commit()
    conn.close()

# ------------------- Public Unified Guide + Theme APIs -------------------
from flask import Response

@app.route('/api/guide_snapshot', methods=['GET'])
def api_guide_snapshot():
    """
    Public unified guide data for framebuffer/RetroIPTV OS clients.
    Supports ?hours=N (0.5–8) to control window size.
    """
    try:
        # Run auto-refresh if due so CRT clients get fresh data when they poll
        try:
            refresh_if_due()
        except Exception:
            logging.exception("refresh_if_due from api_guide_snapshot failed")

        now = datetime.now(timezone.utc)

        # Read optional hours parameter
        hours_param = request.args.get("hours", type=float)
        if hours_param is None:
            hours = 2.0
        else:
            hours = max(0.5, min(hours_param, 8.0))  # clamp 0.5–8h

        start = now.replace(
            minute=(0 if now.minute < 30 else 30),
            second=0,
            microsecond=0
        )
        end = start + timedelta(hours=hours)

        # 30-minute timeline labels across the window
        slot_count = int((hours * 60) / 30) + 1
        slots = [start + timedelta(minutes=30 * i) for i in range(slot_count)]
        timeline = [s.strftime("%I:%M %p").lstrip("0") for s in slots]

        tuner_name = get_current_tuner()
        tuners = get_tuners()
        tuner_info = tuners.get(tuner_name, {})

        channels_out = []
        for ch in cached_channels[:50]:  # perf cap
            tvg_id = ch.get('tvg_id')
            progs = cached_epg.get(tvg_id, [])
            visible_programs = []

            for p in progs:
                st, sp = p.get('start'), p.get('stop')
                if not st or not sp:
                    continue

                # include any program overlapping [start, end)
                if st < end and sp > start:
                    clipped_start = max(st, start)
                    clipped_stop = min(sp, end)
                    dur_min = max(
                        1,
                        int((clipped_stop - clipped_start).total_seconds() // 60)
                    )

                    visible_programs.append({
                        "title": p.get('title') or "No Data",
                        "desc":  p.get('desc')  or "",
                        "start": st.isoformat(),
                        "stop":  sp.isoformat(),
                        "clipped_start": clipped_start.isoformat(),
                        "clipped_stop":  clipped_stop.isoformat(),
                        "duration": dur_min
                    })

            if not visible_programs:
                visible_programs = [{
                    "title": "No Data",
                    "desc":  "",
                    "start": None,
                    "stop":  None,
                    "clipped_start": start.isoformat(),
                    "clipped_stop": (start + timedelta(minutes=30)).isoformat(),
                    "duration": 30
                }]

            channels_out.append({
                "number": ch.get('number') or ch.get('tvg_chno'),
                "name": ch.get('name'),
                "logo": ch.get('logo'),
                "programs": visible_programs
            })

        payload = {
            "meta": {
                "generated": datetime.utcnow().isoformat() + "Z",
                "tuner": tuner_name,
                "tuner_xml": tuner_info.get('xml'),
                "tuner_m3u": tuner_info.get('m3u'),
                "theme": "default_crt_blue",
                "version": APP_VERSION,
            },
            "timeline": timeline,
            "window": {
                "start_iso": start.isoformat(),
                "end_iso": end.isoformat(),
                "minutes": int(hours * 60),
            },
            "channels": channels_out
        }
        return jsonify(payload)
    except Exception as e:
        logging.exception("api_guide_snapshot failed: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/theme_snapshot', methods=['GET'])
def api_theme_snapshot():
    """
    Public theme info for lightweight CRT / Android clients.
    Future: this can later read user-specific or tuner-specific themes.
    """
    theme = {
        "name": "DirecTV CRT Blue",
        "font": "DejaVu Sans Bold",
        "variant": "dark_blue",
        "palette": {
            "background": "#000820",
            "channel_column": "#253b6e",
            "program_block": "#3b5ba0",
            "grid_line": "#6070a0",
            "highlight": "#ffff00",
            "header": "#001844",
            "text": "#ffffff"
        },
        "crt_effects": {
            "scanlines": True,
            "bloom": True,
            "vignette": True
        },
        "generated": datetime.utcnow().isoformat() + "Z"
    }
    return jsonify(theme)

# ------------------- QR Visibility Control (with auto-restore) -------------------

from datetime import datetime, timedelta

crt_qr_visible = True
qr_hide_time = None
QR_AUTO_RESHOW_MINUTES = 15  # inactivity window

@app.route('/api/qr_status', methods=['GET'])
def api_qr_status():
    """
    Returns current QR visibility. If QR was hidden longer than the
    inactivity window, auto-re-enable it.
    """
    global crt_qr_visible, qr_hide_time
    if not crt_qr_visible and qr_hide_time:
        elapsed = datetime.utcnow() - qr_hide_time
        if elapsed > timedelta(minutes=QR_AUTO_RESHOW_MINUTES):
            crt_qr_visible = True
            qr_hide_time = None
            logging.info(f"QR overlay auto-restored after {elapsed}")
    return jsonify({"visible": crt_qr_visible})

@app.route('/api/qr_hide', methods=['POST'])
def api_qr_hide():
    """
    Called when a user reaches /remote (after login).
    Hides the QR and starts the inactivity timer.
    """
    global crt_qr_visible, qr_hide_time
    crt_qr_visible = False
    qr_hide_time = datetime.utcnow()
    logging.info("QR overlay hidden; inactivity timer started")
    return jsonify({"status": "hidden"})

@app.route('/api/qr_show', methods=['POST'])
def api_qr_show():
    """
    Manual override: instantly re-enable QR (resets timer).
    """
    global crt_qr_visible, qr_hide_time
    crt_qr_visible = True
    qr_hide_time = None
    logging.info("QR overlay manually shown via /api/qr_show")
    return jsonify({"status": "visible"})


def check_url_reachable(url, timeout=5):
    try:
        r = requests.head(url, timeout=timeout)
        return r.status_code < 400
    except:
        return False

def check_xmltv_freshness(xml_url, max_age_hours=6):
    try:
        r = requests.get(xml_url, timeout=10)
        r.raise_for_status()

        root = ET.fromstring(r.content)

        now = datetime.now(timezone.utc)
        past_starts = []

        for prog in root.findall(".//programme"):
            start = prog.get("start")
            if not start:
                continue

            # example format: "20251115051031 +0000"
            parts = start.split()
            ts = parts[0]  # 20251115051031
            if len(ts) >= 14:
                try:
                    dt = datetime.strptime(ts[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                    if dt <= now:
                        past_starts.append(dt)
                except:
                    pass

        if not past_starts:
            # If no past events, assume fresh
            return (True, 0.0)

        latest_past = max(past_starts)
        age_hours = (now - latest_past).total_seconds() / 3600.0

        return (age_hours <= max_age_hours, age_hours)

    except Exception as e:
        print("XMLTV freshness error:", e)
        return (False, None)

# ------------------- Minimal Auto-refresh (preset-based, no scheduler) -------------------
AUTO_REFRESH_PRESETS = [2, 4, 6, 12, 24]  # allowed hours
_auto_refresh_locks = {}  # in-memory locks (OK for single-process)

def get_setting(key, default=None):
    """Read key from tuners.settings table (existing settings table)."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = c.fetchone()
        return row[0] if row else default
    except Exception:
        return default

def set_setting(key, value):
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
    except Exception:
        logging.exception("set_setting failed for %s", key)

def _acquire_lock(name):
    lock = _auto_refresh_locks.setdefault(name, threading.Lock())
    return lock.acquire(blocking=False)

def _release_lock(name):
    lock = _auto_refresh_locks.get(name)
    try:
        if lock and lock.locked():
            lock.release()
    except RuntimeError:
        # already released or not owned
        pass

def refresh_current_tuner(tuner_name=None):
    """Perform the same refresh logic you already run on login/tuner switch.
       Returns True on success, False on failure/skip.
    """
    try:
        if not tuner_name:
            tuner_name = get_current_tuner()
        if not tuner_name:
            logging.info("refresh_current_tuner: no current tuner set")
            return False

        if not _acquire_lock(tuner_name):
            logging.info("refresh_current_tuner: lock busy for %s", tuner_name)
            return False

        logging.info("refresh_current_tuner: refreshing tuner %s", tuner_name)
        tuners = get_tuners()
        info = tuners.get(tuner_name)
        if not info:
            logging.warning("refresh_current_tuner: tuner %s not found", tuner_name)
            return False

        # Use load_tuner_data so combined tuners (which have no direct m3u/xml)
        # are handled correctly by merging their source tuners' feeds.
        new_channels, new_epg = load_tuner_data(tuner_name)
        new_epg = apply_epg_fallback(new_channels, new_epg)

        # atomic swap
        global cached_channels, cached_epg
        cached_channels = new_channels
        cached_epg = new_epg

        now_iso = datetime.now(timezone.utc).isoformat()
        set_setting(f"last_auto_refresh:{tuner_name}", f"success|{now_iso}")

        logging.info("refresh_current_tuner: finished %s", tuner_name)
        return True

    except Exception as e:
        logging.exception("refresh_current_tuner error for %s: %s", tuner_name, e)
        now_iso = datetime.now(timezone.utc).isoformat()
        set_setting(f"last_auto_refresh:{tuner_name}", f"failed|{now_iso}|{str(e)[:200]}")
        return False
    finally:
        try:
            _release_lock(tuner_name)
        except Exception:
            pass

def refresh_if_due(tuner_name=None):
    """Check settings and last-run timestamp; refresh if interval elapsed."""
    try:
        # global enabling (simple): stored as 'auto_refresh_enabled' = "1" or "0"
        enabled = get_setting("auto_refresh_enabled", "0")
        if str(enabled) not in ("1", "true", "True"):
            return False

        interval_value = get_setting("auto_refresh_interval_hours", None)
        try:
            interval_hours = int(interval_value) if interval_value is not None and interval_value != "" else None
        except:
            interval_hours = None

        # Only allow preset intervals for simplicity/safety
        if interval_hours not in AUTO_REFRESH_PRESETS:
            logging.debug("refresh_if_due: interval %s not in presets %s", interval_hours, AUTO_REFRESH_PRESETS)
            return False

        if not tuner_name:
            tuner_name = get_current_tuner()
        if not tuner_name:
            return False

        last_raw = get_setting(f"last_auto_refresh:{tuner_name}", None)
        if last_raw:
            # stored as "success|{ISO}" or "failed|{ISO}|msg"
            try:
                last_iso = last_raw.split("|")[1]
                last_dt = datetime.fromisoformat(last_iso)
            except Exception:
                last_dt = None
        else:
            last_dt = None

        now = datetime.now(timezone.utc)
        if last_dt is None:
            due = True
        else:
            elapsed_hours = (now - last_dt).total_seconds() / 3600.0
            due = (elapsed_hours >= interval_hours)

        if due:
            logging.info("refresh_if_due: due for tuner %s (interval=%s)", tuner_name, interval_hours)
            return refresh_current_tuner(tuner_name)
        return False

    except Exception:
        logging.exception("refresh_if_due unexpected error")
        return False

# ------------------- QR Visibility Control (with auto-restore) -------------------

@app.route('/api/health')
@login_required
def api_health():
    tuners = get_tuners()
    curr = get_current_tuner()
    t = tuners.get(curr, {})

    # Combined tuners have no direct m3u/xml URLs
    if t.get("tuner_type") == "combined":
        return jsonify({
            "tuner": curr,
            "tuner_type": "combined",
            "m3u_reachable": None,
            "xml_reachable": None,
            "xmltv_fresh": None,
            "tuner_m3u": None,
            "tuner_xml": None,
            "xmltv_age_hours": None,
        })

    m3u_url = t.get("m3u", "")
    xml_url = t.get("xml", "")

    # Reachability checks
    m3u_ok = check_url_reachable(m3u_url) if m3u_url else False
    xml_ok = check_url_reachable(xml_url) if xml_url else False

    # Freshness check
    xml_fresh, xml_age_hours = check_xmltv_freshness(xml_url)

    return jsonify({
        "tuner": curr,
        "tuner_type": t.get("tuner_type", "standard"),
        "m3u_reachable": m3u_ok,
        "xml_reachable": xml_ok,
        "xmltv_fresh": xml_fresh,
        "tuner_m3u": m3u_url,
        "tuner_xml": xml_url,
        "xmltv_age_hours": xml_age_hours
    })


if __name__ == '__main__':
    from utils.startup_diag import finalise_startup as _finalise_startup
    try:
        init_db()
        _record_db_init("users.db", DATABASE, success=True)
    except Exception as _dberr:
        _record_db_init("users.db", DATABASE, success=False, error=str(_dberr))
        raise

    add_user('admin', 'strongpassword123', must_change_password=1)

    try:
        init_tuners_db()
        _record_db_init("tuners.db", TUNER_DB, success=True)
    except Exception as _dberr:
        _record_db_init("tuners.db", TUNER_DB, success=False, error=str(_dberr))
        raise

    # make sure there’s at least one tuner in the DB
    ensure_default_tuner()

    # preload guide cache
    tuners = get_tuners()
    current_tuner = get_current_tuner()
    if not current_tuner and tuners:  # fallback if no active tuner set
        current_tuner = list(tuners.keys())[0]
    # Use load_tuner_data so combined tuners are handled correctly at startup.
    cached_channels, cached_epg = load_tuner_data(current_tuner)

    _record_startup_event("info", "cache_load",
                          f"Loaded {len(cached_channels)} channel(s) from tuner '{current_tuner}'")

    # Pre-warm the Overpass road-geometry cache for all enabled traffic cities
    # so the overlay is ready before any city rotation happens.
    threading.Thread(target=_prewarm_roads_cache, daemon=True, name="roads-prewarm").start()

    # Generate missing static basemap PNGs (OSM tile mosaics) for all seed
    # cities so the traffic demo never serves 404s for the basemap images.
    threading.Thread(target=_prewarm_basemaps, daemon=True, name="basemaps-prewarm").start()

    # Mark startup complete before handing off to Flask
    _finalise_startup(success=True)

    # No background scheduler — auto-refresh is triggered lazily on page/API hits.
    app.run(host='0.0.0.0', port=5000, debug=False)
