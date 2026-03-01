# app.py — merged version (features from both sources)
APP_VERSION = "v4.7.1"
APP_RELEASE_DATE = "2026-02-28"

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
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
import subprocess
from datetime import datetime, timezone, timedelta, date
import threading

# New import: vlc control helper (optional - keep existing integration compatibility)
try:
    import vlc_control
except Exception as e:
    vlc_control = None
    # Log the import failure so we can see why it failed when the app starts
    logging.exception("Failed to import vlc_control: %s", e)

APP_START_TIME = datetime.now()

# ------------------- Config -------------------
app = Flask(__name__)
app.secret_key = os.urandom(24)  # replace with a fixed key in production
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)


DATABASE = 'users.db'
TUNER_DB = 'tuners.db'

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# ------------------- Activity Log -------------------
LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "activity.log")

def log_event(user, action):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(f"{user} | {action} | {ts}\n")
    except (PermissionError, OSError) as e:
        # Log to stderr if file logging fails
        print(f"Warning: Could not write to log file: {e}", file=sys.stderr)

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
        flash(f"⚠️ Validation error for {label}: {str(e)}", "warning")

# ------------------- User Model -------------------
class User(UserMixin):
    def __init__(self, id, username, password_hash, last_login=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.last_login = last_login

# ------------------- Init DBs -------------------
def init_db():
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, last_login TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_preferences
                     (username TEXT PRIMARY KEY, prefs TEXT)''')
        conn.commit()

        # Add last_login column if it doesn't exist (for existing databases)
        try:
            c.execute('ALTER TABLE users ADD COLUMN last_login TEXT')
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # Add assigned_tuner column if it doesn't exist (for existing databases)
        try:
            c.execute('ALTER TABLE users ADD COLUMN assigned_tuner TEXT')
            conn.commit()
        except sqlite3.OperationalError:
            pass

def add_user(username, password):
    password_hash = generate_password_hash(password)
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)', (username, password_hash))
        conn.commit()

def get_user(username):
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, password, last_login FROM users WHERE username=?', (username,))
        row = c.fetchone()
    if row:
        return User(row[0], row[1], row[2], row[3])
    return None

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, password, last_login FROM users WHERE id=?', (user_id,))
        row = c.fetchone()
    if row:
        return User(row[0], row[1], row[2], row[3])
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
        for _ch_id in ('virtual.news', 'virtual.weather', 'virtual.status'):
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
                "Plex": {
                    "m3u": "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/us_plex.m3u",
                    "xml": "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/us_plex.m3u"
                },
                "Tubi": {
                    "m3u": "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/us_tubi.m3u",
                    "xml": "https://raw.githubusercontent.com/iptv-org/iptv/refs/heads/master/streams/us_tubi.m3u"
                }
            }
            for name, urls in defaults.items():
                c.execute("INSERT INTO tuners (name, xml, m3u) VALUES (?, ?, ?)",
                          (name, urls["xml"], urls["m3u"]))
            # set default active tuner
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('current_tuner', 'Tuner 1')")
        conn.commit()

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
    
    # Validate M3U URL
    if not m3u_url or not m3u_url.strip():
        raise ValueError("M3U URL is required")
    if not m3u_url.startswith(('http://', 'https://')):
        raise ValueError("M3U URL must start with http:// or https://")
    
    # Validate XML URL if provided
    if xml_url and xml_url.strip():
        if not xml_url.startswith(('http://', 'https://')):
            raise ValueError("XML URL must start with http:// or https://")
    
    # Optional: Check URL reachability with SSRF protection
    try:
        # Parse the URL to validate the hostname
        parsed_url = urlparse(m3u_url)
        hostname = parsed_url.hostname
        
        if not hostname:
            raise ValueError("M3U URL must have a valid hostname")
        
        # Block localhost to prevent SSRF attacks on local services
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
        except socket.gaierror:
            # If hostname can't be resolved, skip reachability check
            pass
        
        # Make the request with security restrictions
        try:
            r = requests.head(m3u_url, timeout=5, allow_redirects=True)
            r.raise_for_status()
        except requests.exceptions.ConnectionError:
            # DNS resolution failure or unreachable host — skip reachability check
            pass
        except requests.RequestException as e:
            raise ValueError(f"M3U URL unreachable: {str(e)}")
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
            url = lines[i+1].strip() if i+1 < len(lines) else ''

            if url.endswith('.ts'):
                url = url.replace('.ts', '.m3u8')

            channels.append({'name': name, 'logo': logo, 'url': url, 'tvg_id': tvg_id})
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

        if cid not in programs:
            programs[cid] = []
        programs[cid].append({'title': title, 'desc': desc, 'start': start, 'stop': stop})
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
        'overlay_refresh_seconds': 300,
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
]

def get_virtual_channel_settings():
    """Return a dict mapping each virtual channel tvg_id to its enabled state (bool).
    Defaults to True (enabled) when no setting has been persisted yet."""
    defaults = {ch['tvg_id']: True for ch in VIRTUAL_CHANNELS}
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

def get_news_feed_url():
    """Return the configured RSS/Atom news feed URL, or empty string if not set."""
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key='news.rss_url'")
            row = c.fetchone()
            return row[0] if row else ''
    except Exception:
        logging.exception("get_news_feed_url failed")
        return ''

def save_news_feed_url(url):
    """Persist the RSS/Atom news feed URL. Validates scheme is http/https."""
    url = str(url).strip()
    if url:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ValueError(f"Invalid feed URL: {url!r}. Must be an http or https URL with a valid hostname.")
    try:
        with sqlite3.connect(TUNER_DB, timeout=10) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('news.rss_url', ?)", (url,))
            conn.commit()
    except Exception:
        logging.exception("save_news_feed_url failed")
        raise

_WEATHER_CONFIG_KEYS = ('lat', 'lon', 'location_name', 'units')

def get_weather_config():
    """Return weather configuration: lat, lon (strings), location_name, units ('F'/'C')."""
    result = {'lat': '', 'lon': '', 'location_name': '', 'units': 'F'}
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
    """Persist weather configuration. Validates lat/lon as floats when non-empty."""
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

# WMO weather code → (label, icon_key)
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
            'ticker': ticker,
            'forecast': compat_forecast,
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
        'ticker': [],
        'forecast': [],
    }

_RSS_NS = {'atom': 'http://www.w3.org/2005/Atom', 'media': 'http://search.yahoo.com/mrss/'}

def fetch_rss_headlines(feed_url, max_items=20):
    """Fetch a RSS 2.0 or Atom feed and return a list of headline dicts.

    Each item: {'title': str, 'source': str, 'url': str, 'ts': ISO8601 str}
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
            if title:
                items.append({'title': title, 'source': channel_title, 'url': link, 'ts': ts})
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
            if title:
                items.append({'title': title, 'source': channel_title, 'url': link, 'ts': ts})

    return items

def get_virtual_channels():
    """Return the list of virtual channel definitions (deep copy to prevent mutation)."""
    import copy
    return copy.deepcopy(VIRTUAL_CHANNELS)

def get_virtual_epg(grid_start, hours_span=6):
    """Generate synthetic EPG entries for virtual channels spanning the grid window."""
    epg = {}
    grid_end = grid_start + timedelta(hours=hours_span)
    programs_by_tvg_id = {
        'virtual.news': 'News Now',
        'virtual.weather': 'Local Weather',
        'virtual.status': 'System Status',
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
        next_url = request.args.get('next') or request.form.get('next') or url_for('guide')
        if next_url and not is_safe_url(next_url):
            return abort(400)
        return redirect(next_url)

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

            # Determine next redirect target (prefer POSTed next, then query param)
            next_url = request.form.get('next') or request.args.get('next') or url_for('guide')
            if next_url and not is_safe_url(next_url):
                return abort(400)
            return redirect(next_url)
        else:
            log_event(username if username else "unknown", "Failed login attempt")
            error = 'Invalid username or password'
            next_url = request.form.get('next') or request.args.get('next') or ''
            return render_template('login.html', error=error, next=next_url), 401

    # GET: render login form; preserve ?next=... into the form
    next_url = request.args.get('next') or ''
    return render_template('login.html', next=next_url)

@app.route('/_debug/vlcinfo', methods=['GET'])
def _debug_vlcinfo():
    """
    Debug helper: returns last launch args and running vlc/cvlc processes.
    This is safe to keep but can be removed once debugging is done.
    """
    info = {}
    try:
        info['last_launch'] = vlc_control.last_launch_info() if vlc_control else None
    except Exception as e:
        info['last_launch_error'] = str(e)
    try:
        # list vlc/cvlc processes (ps output)
        out = subprocess.check_output(['ps','-o','pid,cmd','-C','cvlc','-C','vlc'], stderr=subprocess.DEVNULL).decode(errors='ignore')
        info['processes'] = out.strip()
    except Exception as e:
        info['processes_error'] = str(e)
    return jsonify(info)

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
    if request.method == 'POST':
        old = request.form['old_password']
        new = request.form['new_password']
        user = get_user(current_user.username)
        if user and check_password_hash(user.password_hash, old):
            with sqlite3.connect(DATABASE, timeout=10) as conn:
                c = conn.cursor()
                c.execute('UPDATE users SET password=? WHERE id=?',
                          (generate_password_hash(new), current_user.id))
                conn.commit()
            log_event(current_user.username, "Changed password")
            flash("Password updated successfully.")
            return redirect(url_for('guide'))
        else:
            log_event(current_user.username, "Failed password change attempt (invalid old password)")
            flash("Old password incorrect.")
    return render_template("change_password.html", current_tuner=get_current_tuner())

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
@login_required  # optional
def about():
    python_version = sys.version.split()[0]
    os_info = platform.platform()
    install_path = os.getcwd()
    db_path = os.path.join(install_path, "app.db")
    log_path = "/var/log/iptv" if os.name != "nt" else os.path.join(install_path, "logs")

    # calculate uptime
    uptime_delta = datetime.now() - APP_START_TIME
    days, seconds = uptime_delta.days, uptime_delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

    info = {
        "version": APP_VERSION,
        "release_date": APP_RELEASE_DATE,
        "python_version": python_version,
        "os_info": os_info,
        "install_path": install_path,
        "db_path": db_path,
        "log_path": log_path,
        "uptime": uptime_str
    }
    return render_template("about.html", info=info)



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
        return redirect(request.referrer or url_for('change_tuner'))

    # Update current tuner
    set_current_tuner(name)

    # Refresh cached guide data (use load_tuner_data so combined tuners work).
    global cached_channels, cached_epg
    cached_channels, cached_epg = load_tuner_data(name)
    cached_epg = apply_epg_fallback(cached_channels, cached_epg)

    log_event(current_user.username, f"Quick switched active tuner to {name}")
    flash(f"Active tuner switched to {name}", "success")

    # Try to redirect back to where the user came from, falling back to guide
    dest = request.referrer or url_for('guide')
    try:
        if not is_safe_url(dest):
            dest = url_for('guide')
    except Exception:
        dest = url_for('guide')
    return redirect(dest)


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

        elif action == "update_virtual_channels":
            new_settings = {}
            for ch in VIRTUAL_CHANNELS:
                tvg_id = ch['tvg_id']
                # A hidden input always submits "0"; the checkbox overrides it with "1" when checked
                new_settings[tvg_id] = request.form.get(f"vc_{tvg_id}", "0") == "1"
            try:
                save_virtual_channel_settings(new_settings)
                log_event(current_user.username, "Updated virtual channel settings")
                flash("Virtual channel settings saved.", "success")
            except Exception:
                flash("Failed to save virtual channel settings.", "warning")

        elif action == "update_overlay_appearance":
            appearance = {
                'text_color': request.form.get('overlay_text_color', '').strip(),
                'bg_color': request.form.get('overlay_bg_color', '').strip(),
                'test_text': request.form.get('overlay_test_text', '').strip(),
            }
            try:
                save_overlay_appearance(appearance)
                log_event(current_user.username, "Updated overlay appearance settings")
                flash("Overlay appearance settings saved.", "success")
            except ValueError as exc:
                flash(f"Invalid color value: {exc}", "warning")
            except Exception:
                flash("Failed to save overlay appearance settings.", "warning")

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
                if tvg_id == 'virtual.weather':
                    # Text color, background color, and test banner are not used by the
                    # weather channel; always clear them so stale values don't linger.
                    appearance = {'text_color': '', 'bg_color': '', 'test_text': ''}
                try:
                    save_channel_overlay_appearance(tvg_id, appearance)
                    if tvg_id == 'virtual.news':
                        rss_url = request.form.get('ch_news_rss_url', '').strip()
                        save_news_feed_url(rss_url)
                    if tvg_id == 'virtual.weather':
                        weather_cfg = {
                            'lat':           request.form.get('ch_weather_lat', '').strip(),
                            'lon':           request.form.get('ch_weather_lon', '').strip(),
                            'location_name': request.form.get('ch_weather_location', '').strip(),
                            'units':         request.form.get('ch_weather_units', 'F').strip(),
                        }
                        save_weather_config(weather_cfg)
                    log_event(current_user.username, f"Updated overlay appearance for {tvg_id}")
                    flash("Channel overlay settings saved.", "success")
                except ValueError as exc:
                    flash(str(exc), "warning")
                except Exception:
                    flash("Failed to save channel overlay settings.", "warning")

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

    vc_settings = get_virtual_channel_settings()
    overlay_appearance = get_overlay_appearance()
    channel_appearances = get_all_channel_appearances()

    return render_template(
        "change_tuner.html",
        tuners=tuners.keys(),
        current_tuner=current_tuner,
        current_urls=tuners[current_tuner],
        TUNERS=tuners,
        auto_refresh_enabled=auto_refresh_enabled,
        auto_refresh_interval_hours=auto_refresh_interval_hours,
        last_auto_refresh=last_auto_refresh,
        VIRTUAL_CHANNELS=VIRTUAL_CHANNELS,
        vc_settings=vc_settings,
        overlay_appearance=overlay_appearance,
        channel_appearances=channel_appearances,
        news_feed_url=get_news_feed_url(),
        weather_config=get_weather_config(),
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

# ------------------- New playback/control API endpoints (VLC/mpv wrapper usage) -------------------
# NOTE: these new endpoints complement your existing vlc_control-backed endpoints.
# remote.html will call these endpoints to invoke the root-owned helper scripts via sudo.

PLAY_SCRIPT = "/usr/local/bin/vlc-play.sh"
STOP_SCRIPT = "/usr/local/bin/vlc-stop.sh"
LOG_FILE = "/var/log/vlc-play.log"
INSTANCE_ID = "default"  # single-instance default; adapt if you support multiple instances

def is_valid_stream_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    # Optional: restrict to allowed hosts/networks; adjust to your security needs.
    return True

@app.route('/api/start_stream', methods=['POST'])
@login_required
def api_start_stream():
    """
    Start playback using the helper script.
    Expects JSON: { "url": "<stream url>", "id": "<optional instance id>", "hide_cursor": true }
    Returns JSON including the instance id to let clients call stop with the same id.
    Ensures CURRENTLY_PLAYING is set to a canonical tvg_id (if resolvable) or fallback token so /api/status
    can tell clients what is currently playing.
    """
    global CURRENTLY_PLAYING
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    instance = (data.get("id") or INSTANCE_ID).strip() or INSTANCE_ID
    hide_cursor = bool(data.get("hide_cursor", False))

    if not url:
        return jsonify({"ok": False, "error": "missing url"}), 400
    if not is_valid_stream_url(url):
        return jsonify({"ok": False, "error": "invalid url"}), 400

    cmd = ["sudo", PLAY_SCRIPT, url, instance]
    if hide_cursor:
        cmd.append("hide")

    try:
        subprocess.check_call(cmd, timeout=30)
    except subprocess.CalledProcessError as e:
        logging.exception("start_stream failed: %s", e)
        return jsonify({"ok": False, "error": f"start failed: {e}"}), 500
    except subprocess.TimeoutExpired:
        logging.exception("start_stream timed out")
        return jsonify({"ok": False, "error": "start timed out"}), 500

    # Try to resolve the URL -> tvg_id using cached_channels for accurate status reporting
    try:
        resolved_tvg = None
        resolved_url = None
        # First try exact url match, then substring match
        for ch in cached_channels:
            ch_url = ch.get('url') or ''
            ch_tvg = ch.get('tvg_id') or ''
            if ch_url and ch_url == url:
                resolved_tvg = ch_tvg
                resolved_url = ch_url
                break
        if not resolved_tvg:
            for ch in cached_channels:
                ch_url = ch.get('url') or ''
                ch_tvg = ch.get('tvg_id') or ''
                if ch_url and ch_url in url:
                    resolved_tvg = ch_tvg
                    resolved_url = ch_url
                    break

        if resolved_tvg:
            CURRENTLY_PLAYING = resolved_tvg
        else:
            # If client provided a meaningful instance id (not default) use it; otherwise store the URL
            if instance and instance != INSTANCE_ID:
                CURRENTLY_PLAYING = instance
            else:
                CURRENTLY_PLAYING = url

    except Exception:
        # On any error just fall back to storing the URL so status has something
        CURRENTLY_PLAYING = url

    log_event(current_user.username, f"Requested start_stream {url} (id={instance}, hide_cursor={hide_cursor})")
    return jsonify({"ok": True, "message": "started", "id": instance})

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
        return jsonify({"error": str(e)}), 500


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

@app.route('/api/stop_stream', methods=['POST'])
@login_required
def api_stop_stream():
    """
    Stop playback using the helper stop script and clear CURRENTLY_PLAYING so /api/status reports nothing playing.
    Expects JSON: { "id": "<optional instance id>" }
    """
    global CURRENTLY_PLAYING
    try:
        logging.info("api_stop_stream called by user=%s remote_addr=%s headers=%s body=%s",
                     getattr(current_user, 'username', 'anonymous'),
                     request.remote_addr,
                     {k: v for k, v in request.headers.items()},
                     request.get_data(as_text=True))

        data = request.get_json(force=True, silent=True) or {}
        instance = (data.get("id") or INSTANCE_ID).strip() or INSTANCE_ID

        cmd = ["sudo", STOP_SCRIPT, instance]
        try:
            subprocess.check_call(cmd, timeout=15)
        except subprocess.CalledProcessError as e:
            logging.exception("stop_stream helper failed: %s", e)
            return jsonify({"ok": False, "error": f"stop failed: {e}", "trace": str(e)}), 500
        except subprocess.TimeoutExpired as e:
            logging.exception("stop_stream helper timed out: %s", e)
            return jsonify({"ok": False, "error": "stop timed out", "trace": str(e)}), 500

        # Clear server-side playback marker after stop completes
        try:
            CURRENTLY_PLAYING = None
        except Exception:
            CURRENTLY_PLAYING = None

        log_event(current_user.username, f"Requested stop_stream (id={instance})")
        return jsonify({"ok": True, "message": "stopped", "id": instance})

    except Exception as e:
        logging.exception("Unexpected error in api_stop_stream: %s", e)
        return jsonify({"ok": False, "error": "unexpected server error", "trace": str(e)}), 500

@app.route('/api/tail_logs', methods=['GET'])
@login_required
def api_tail_logs():
    """
    Return the last N lines of the helper log so remote.html can display them.
    """
    N = 200
    if not os.path.exists(LOG_FILE):
        return jsonify({"ok": False, "error": "log missing", "lines": []}), 200
    try:
        out = subprocess.check_output(["tail", "-n", str(N), LOG_FILE], stderr=subprocess.STDOUT, timeout=5)
        text = out.decode("utf-8", errors="replace")
        lines = text.splitlines()
        return jsonify({"ok": True, "lines": lines})
    except Exception as e:
        logging.exception("tail_logs failed: %s", e)
        return jsonify({"ok": False, "error": str(e), "lines": []}), 500

# ------------------- Existing vlc_control-backed endpoints kept below -------------------
# (Your previous /api/play, /api/stop, /api/next, etc. are preserved.)
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
    """Return headlines from the configured RSS/Atom feed, or empty list if none set."""
    feed_url = get_news_feed_url()
    headlines = fetch_rss_headlines(feed_url) if feed_url else []
    return jsonify({
        "updated": datetime.now(timezone.utc).isoformat(),
        "headlines": headlines,
    })

@app.route('/weather')
@login_required
def weather_page():
    """Retro TV weather overlay page."""
    log_event(current_user.username, "Loaded weather page")
    return render_template('weather.html')

@app.route('/api/weather', methods=['GET'])
@login_required
def api_weather():
    """Weather overlay data endpoint. Returns current conditions, today's forecast,
    extended outlook, and breaking news ticker. Calls open-meteo when configured."""
    cfg = get_weather_config()
    return jsonify(_build_weather_payload(cfg))

@app.route('/api/virtual/status', methods=['GET'])
@login_required
def api_virtual_status():
    """Stub endpoint for virtual system status channel overlay data."""
    uptime_seconds = int((datetime.now() - APP_START_TIME).total_seconds())
    hours, rem = divmod(uptime_seconds, 3600)
    minutes = rem // 60
    return jsonify({
        "updated": datetime.now(timezone.utc).isoformat(),
        "items": [
            {"label": "RetroIPTVGuide", "value": "Running", "state": "good"},
            {"label": "Uptime", "value": f"{hours}h {minutes}m", "state": "good"},
        ],
    })

@app.route('/api/overlay/settings', methods=['GET'])
@login_required
def api_overlay_settings():
    """Return overlay appearance settings. Use ?channel=tvg_id for per-channel settings."""
    channel = request.args.get('channel', '').strip()
    valid_ids = {ch['tvg_id'] for ch in VIRTUAL_CHANNELS}
    if channel and channel in valid_ids:
        return jsonify(get_channel_overlay_appearance(channel))
    return jsonify(get_overlay_appearance())

@app.route('/api/play', methods=['POST'])
@login_required
def api_play():
    """
    Start playback. Accepts JSON or form data with:
      - url: direct stream URL
      - tvg_id: channel id (will be resolved using cached_channels)
      - playlist_index: integer index into the current tuner M3U (0-based)
      - volume: optional 0-512 default volume for this session
    """
    global CURRENTLY_PLAYING
    if vlc_control is None:
        return jsonify({'error': 'vlc_control helper not available on server'}), 500

    data = request.get_json(silent=True) or request.form or {}
    url = data.get('url')
    tvg_id = data.get('tvg_id')
    playlist_index = data.get('playlist_index')
    try:
        # Playlist mode: launch current tuner's M3U and start at specified index
        if playlist_index is not None and playlist_index != "":
            try:
                playlist_index = int(playlist_index)
            except:
                return jsonify({'error': 'playlist_index must be an integer'}), 400
            tuners = get_tuners()
            current = get_current_tuner()
            if not current or current not in tuners:
                return jsonify({'error': 'No active tuner configured'}), 400
            playlist_path = tuners[current]['m3u']
            vlc_control.stop_player()
            vlc_control.start_player(playlist_path, volume=vlc_control.VLC_VOLUME_DEFAULT, playlist_mode=True, playlist_start=playlist_index)
            CURRENTLY_PLAYING = f"playlist:{playlist_path}@{playlist_index}"
            log_event(current_user.username, f"Started playlist {playlist_path} index {playlist_index}")
            return jsonify({'status': 'playing', 'mode': 'playlist', 'playlist': playlist_path, 'index': playlist_index})

        # Resolve tvg_id -> url if needed
        if tvg_id and not url:
            target = None
            for ch in cached_channels:
                if ch.get('tvg_id') == tvg_id:
                    target = ch.get('url')
                    break
            if not target:
                return jsonify({'error': f'Unknown tvg_id: {tvg_id}'}), 404
            url = target

        if not url:
            return jsonify({'error': 'Missing url/tvg_id/playlist_index'}), 400

        volume = data.get('volume', getattr(vlc_control, 'VLC_VOLUME_DEFAULT', 320))
        try:
            vol_int = int(volume)
        except:
            vol_int = getattr(vlc_control, 'VLC_VOLUME_DEFAULT', 320)

        vlc_control.stop_player()
        vlc_control.start_player(url, volume=vol_int, playlist_mode=False)
        CURRENTLY_PLAYING = url
        log_event(current_user.username, f"Started playback of {url}")
        return jsonify({'status': 'playing', 'url': url, 'volume': vol_int})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop', methods=['POST'])
@login_required
def api_stop():
    global CURRENTLY_PLAYING
    if vlc_control is None:
        return jsonify({'error': 'vlc_control helper not available on server'}), 500
    try:
        vlc_control.stop_player()
        CURRENTLY_PLAYING = None
        log_event(current_user.username, "Stopped playback")
        return jsonify({'status': 'stopped'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/next', methods=['POST'])
@login_required
def api_next():
    if vlc_control is None:
        return jsonify({'error': 'vlc_control helper not available on server'}), 500
    try:
        resp = vlc_control.next_track()
        log_event(current_user.username, "Sent VLC next")
        return jsonify({'status': 'ok', 'resp': resp})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prev', methods=['POST'])
@login_required
def api_prev():
    if vlc_control is None:
        return jsonify({'error': 'vlc_control helper not available on server'}), 500
    try:
        resp = vlc_control.prev_track()
        log_event(current_user.username, "Sent VLC prev")
        return jsonify({'status': 'ok', 'resp': resp})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
@login_required
def api_status():
    """
    Returns simple server-side status and VLC RC raw status.
    Added: current_tvg_id and current_channel_url when resolvable so clients
    can immediately identify the playing channel without probing.
    """
    if vlc_control is None:
        return jsonify({'error': 'vlc_control helper not available on server'}), 500
    try:
        raw = vlc_control.get_status()
        lower = raw.lower() if isinstance(raw, str) else ""
        state = "unknown"
        if "state: playing" in lower or "state: play" in lower:
            state = "playing"
        elif "state: paused" in lower:
            state = "paused"
        elif "state: stopped" in lower:
            state = "stopped"

        # Attempt to resolve the currently playing tvg_id and channel url.
        current_tvg_id = None
        current_channel_url = None

        # CURRENTLY_PLAYING may be a URL, an instance id, or other token.
        # Try to match it against cached_channels first by url, then tvg_id.
        try:
            if CURRENTLY_PLAYING:
                candidate = str(CURRENTLY_PLAYING)
                for ch in cached_channels:
                    if not ch:
                        continue
                    ch_url = ch.get('url') or ''
                    ch_tvg = ch.get('tvg_id') or ''
                    # exact URL match
                    if ch_url and ch_url == candidate:
                        current_tvg_id = ch_tvg
                        current_channel_url = ch_url
                        break
                    # URL substring (helper may include args)
                    if ch_url and candidate and ch_url in candidate:
                        current_tvg_id = ch_tvg
                        current_channel_url = ch_url
                        break
                    # tvg_id equality
                    if ch_tvg and ch_tvg == candidate:
                        current_tvg_id = ch_tvg
                        current_channel_url = ch_url
                        break
        except Exception:
            current_tvg_id = None
            current_channel_url = None

        # Fallback: attempt to match a globally stored lastInstanceId to channel tvg_id
        try:
            last_inst = globals().get('lastInstanceId', None)
            if not current_tvg_id and last_inst:
                for ch in cached_channels:
                    if ch.get('tvg_id') == last_inst:
                        current_tvg_id = last_inst
                        current_channel_url = ch.get('url')
                        break
        except Exception:
            pass

        return jsonify({
            'now_playing': CURRENTLY_PLAYING,
            'current_tvg_id': current_tvg_id,
            'current_channel_url': current_channel_url,
            'vlc_state': state,
            'raw_status': raw
        })
    except Exception as e:
        logging.exception("api_status error: %s", e)
        return jsonify({'error': str(e)}), 500

# ------------------- ADDED ROUTE: current_program -------------------
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
        return jsonify({"ok": False, "error": str(e)}), 500
# ------------------- END ADDED ROUTE -------------------

@app.route('/api/volume/<int:value>', methods=['POST'])
@login_required
def api_set_volume(value):
    if vlc_control is None:
        return jsonify({'error': 'vlc_control helper not available on server'}), 500
    try:
        v = max(0, min(512, int(value)))
        resp = vlc_control.set_volume(v)
        log_event(current_user.username, f"Set volume {v}")
        return jsonify({'status': 'ok', 'volume': v, 'resp': resp})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/volume_up', methods=['POST'])
@login_required
def api_volume_up():
    if vlc_control is None:
        return jsonify({'error': 'vlc_control helper not available on server'}), 500
    try:
        resp = vlc_control.vol_up(32)
        log_event(current_user.username, "Volume up")
        return jsonify({'status': 'ok', 'resp': resp})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/volume_down', methods=['POST'])
@login_required
def api_volume_down():
    if vlc_control is None:
        return jsonify({'error': 'vlc_control helper not available on server'}), 500
    try:
        resp = vlc_control.vol_down(32)
        log_event(current_user.username, "Volume down")
        return jsonify({'status': 'ok', 'resp': resp})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logs', methods=['GET'], endpoint='view_logs')
@login_required
def view_logs():
    if current_user.username != 'admin':
        log_event(current_user.username, "Unauthorized access attempt to /logs")
        return redirect(url_for('guide'))

    log_event(current_user.username, "Accessed logs page")
    entries = []
    log_size = 0

    if os.path.exists(LOG_PATH):
        log_size = os.path.getsize(LOG_PATH)
        with open(LOG_PATH, "r") as f:
            for line in f:
                parts = line.strip().split(" | ")
                if len(parts) == 3:
                    user, action, timestamp = parts
                    log_type = "security" if any(
                        x in action.lower() for x in
                        ["unauthorized", "revoked", "failed", "denied"]
                    ) else "activity"
                    entries.append((user, action, timestamp, log_type))
                else:
                    entries.append(("system", line.strip(), "", "activity"))
    else:
        entries = [("system", "No log file found.", "", "activity")]

    return render_template(
        "logs.html",
        entries=entries,
        current_tuner=get_current_tuner(),
        log_size=log_size
    )



@app.route('/clear_logs', methods=['POST'])
@login_required
def clear_logs():
    if current_user.username != 'admin':
        flash("Unauthorized access.")
        return redirect(url_for('view_logs'))

    open(LOG_PATH, "w").close()  # clear the file
    log_event("admin", "Cleared log file")
    flash("🧹 Logs cleared successfully.")
    return redirect(url_for('view_logs'))


# ------------------- Constants -------------------
SCALE = 5
HOURS_SPAN = 6
SLOT_MINUTES = 30

# ------------------- Main -------------------
def ensure_default_tuner():
    conn = sqlite3.connect('tuners.db')
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
        return jsonify({"error": str(e)}), 500


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

# (rest of the file unchanged)
# ------------------- Health endpoint and the remainder of the script -------------------

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
    init_db()
    add_user('admin', 'strongpassword123')
    init_tuners_db()

    # make sure there’s at least one tuner in the DB
    ensure_default_tuner()

    # preload guide cache
    tuners = get_tuners()
    current_tuner = get_current_tuner()
    if not current_tuner and tuners:  # fallback if no active tuner set
        current_tuner = list(tuners.keys())[0]
    # Use load_tuner_data so combined tuners are handled correctly at startup.
    cached_channels, cached_epg = load_tuner_data(current_tuner)

    # No background scheduler — auto-refresh is triggered lazily on page/API hits.
    app.run(host='0.0.0.0', port=5000, debug=False)
