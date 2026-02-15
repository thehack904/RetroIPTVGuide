# app.py — merged version (features from both sources)
APP_VERSION = "v4.5.0"
APP_RELEASE_DATE = "2026-02-15"

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import re
import sys
import platform
import os
import datetime
import requests
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import socket
import ipaddress
import logging
import subprocess
from datetime import datetime, timezone, timedelta
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
        conn.commit()
        
        # Add last_login column if it doesn't exist (for existing databases)
        try:
            c.execute('ALTER TABLE users ADD COLUMN last_login TEXT')
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
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
        c.execute("SELECT name, xml, m3u FROM tuners")
        return {row[0]: {"xml": row[1], "m3u": row[2]} for row in c.fetchall()}

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
    """Insert a new tuner into DB."""
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
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


# ------------------- Template context helpers -------------------
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

# ------------------- Global cache -------------------
cached_channels = []
cached_epg = {}
cache_timestamp = None  # When cache was last populated
cache_ttl_minutes = 15  # Default cache duration

# Track currently playing marker (server-side)
CURRENTLY_PLAYING = None

# ------------------- Cache Helper Functions -------------------
def get_cache_ttl():
    """Get cache TTL from settings (in minutes)."""
    try:
        ttl = get_setting("epg_cache_ttl", "15")
        return int(ttl)
    except (ValueError, TypeError):
        return 15

def is_cache_valid():
    """Check if current cache is still valid based on TTL."""
    global cache_timestamp
    
    if cache_timestamp is None:
        return False
    
    if not cached_channels or not cached_epg:
        return False
    
    ttl_minutes = get_cache_ttl()
    now = datetime.now(timezone.utc)
    
    try:
        cache_age_minutes = (now - cache_timestamp).total_seconds() / 60.0
        return cache_age_minutes < ttl_minutes
    except (AttributeError, TypeError):
        return False

def update_cache(channels, epg):
    """Update the global cache with new data and timestamp."""
    global cached_channels, cached_epg, cache_timestamp
    
    cached_channels = channels
    cached_epg = epg
    cache_timestamp = datetime.now(timezone.utc)
    
    logging.info(f"Cache updated at {cache_timestamp.isoformat()}, TTL: {get_cache_ttl()} minutes")

def invalidate_cache():
    """Force cache invalidation."""
    global cache_timestamp
    cache_timestamp = None
    logging.info("Cache invalidated manually")

# ------------------- M3U Parsing -------------------
def parse_m3u(m3u_url):
    channels = []
    try:
        r = requests.get(m3u_url, timeout=10)
        r.raise_for_status()
        lines = r.text.splitlines()
    except:
        return channels
    
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

            # reload cached guide after login
            tuners = get_tuners()
            current_tuner = get_current_tuner()
            m3u_url = tuners[current_tuner]["m3u"] if current_tuner and current_tuner in tuners else None
            xml_url = tuners[current_tuner]["xml"] if current_tuner and current_tuner in tuners else None
            if m3u_url:
                new_channels = parse_m3u(m3u_url)
                new_epg = parse_epg(xml_url) if xml_url else {}
                apply_epg_fallback(new_channels, new_epg)
                update_cache(new_channels, new_epg)

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

    # ---- Normal admin logic below ----
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT username, last_login FROM users WHERE username != "admin"')
        users = [{'username': row[0], 'last_login': row[1]} for row in c.fetchall()]

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

        return redirect(url_for('manage_users'))

    return render_template('manage_users.html', users=users, current_tuner=get_current_tuner())


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

    # Refresh cached guide data
    m3u_url = tuners[name].get("m3u")
    xml_url = tuners[name].get("xml")

    new_channels = parse_m3u(m3u_url) if m3u_url else []
    new_epg = parse_epg(xml_url) if xml_url else {}
    apply_epg_fallback(new_channels, new_epg)
    update_cache(new_channels, new_epg)

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

            # ✅ Refresh cached guide data immediately
            tuners = get_tuners()
            m3u_url = tuners[new_tuner]["m3u"]
            xml_url = tuners[new_tuner]["xml"]
            new_channels = parse_m3u(m3u_url)
            new_epg = parse_epg(xml_url)
            # ✅ Apply "No Guide Data Available" fallback
            apply_epg_fallback(new_channels, new_epg)
            # Use new cache update function
            update_cache(new_channels, new_epg)

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
            name = request.form["tuner_name"].strip()
            xml_url = request.form["xml_url"].strip()
            m3u_url = request.form["m3u_url"].strip()

            if not name:
                flash("Tuner name cannot be empty.", "warning")
            elif name in get_tuners():
                flash(f"Tuner {name} already exists.", "warning")
            else:
                add_tuner(name, xml_url, m3u_url)
                log_event(current_user.username, f"Added tuner {name}")
                flash(f"Tuner {name} added successfully.")

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

        elif action == "update_cache_settings":
            ttl = request.form.get("epg_cache_ttl", "15")
            try:
                ttl_int = int(ttl)
                if ttl_int not in [5, 10, 15, 30, 60]:
                    flash("Invalid cache duration", "warning")
                else:
                    set_setting("epg_cache_ttl", str(ttl_int))
                    flash(f"Cache duration set to {ttl_int} minutes", "success")
                    log_event(current_user.username, f"Updated cache TTL: {ttl_int} minutes")
            except Exception as e:
                logging.exception("Failed to update cache TTL")
                flash("Failed to save cache settings", "warning")

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

    # Pass cache info to template
    epg_cache_ttl = get_setting("epg_cache_ttl", "15")
    
    cache_age_str = None
    if cache_timestamp:
        cache_age_minutes = (datetime.now(timezone.utc) - cache_timestamp).total_seconds() / 60.0
        if cache_age_minutes < 60:
            cache_age_str = f"{cache_age_minutes:.1f} minutes"
        else:
            cache_age_str = f"{cache_age_minutes / 60:.1f} hours"

    return render_template(
        "change_tuner.html",
        tuners=tuners.keys(),
        current_tuner=current_tuner,
        current_urls=tuners[current_tuner],
        TUNERS=tuners,
        auto_refresh_enabled=auto_refresh_enabled,
        auto_refresh_interval_hours=auto_refresh_interval_hours,
        last_auto_refresh=last_auto_refresh,
        epg_cache_ttl=epg_cache_ttl,
        cache_age=cache_age_str
    )

@app.route('/refresh_guide_now', methods=['POST'])
@login_required
def refresh_guide_now():
    """Manually refresh the guide data, invalidating cache."""
    if current_user.username != 'admin':
        log_event(current_user.username, "Unauthorized access attempt to /refresh_guide_now")
        flash("Unauthorized access", "warning")
        return redirect(request.referrer or url_for('guide'))
    
    log_event(current_user.username, "Manual guide refresh triggered")
    
    # Invalidate cache first
    invalidate_cache()
    
    tuner_name = get_current_tuner()
    if not tuner_name:
        flash("No tuner selected", "warning")
        return redirect(request.referrer or url_for('guide'))
    
    try:
        success = refresh_current_tuner(tuner_name)
        if success:
            flash("Guide refreshed successfully!", "success")
        else:
            flash("Guide refresh failed. Check logs for details.", "error")
    except Exception as e:
        logging.exception("Manual refresh failed")
        flash(f"Guide refresh error: {str(e)}", "error")
    
    return redirect(request.referrer or url_for('guide'))

@app.route('/guide')
@login_required
def guide():
    log_event(current_user.username, "Loaded guide page")
    # Check and run auto-refresh if due (minimal preset-based approach)
    try:
        refresh_if_due()
    except Exception:
        logging.exception("refresh_if_due from guide() failed")

    # Check if cache is valid
    if not is_cache_valid():
        logging.info("Cache expired or invalid, reloading EPG data")
        tuner = get_current_tuner()
        if tuner:
            tuners = get_tuners()
            urls = tuners.get(tuner, {})
            xml_url = urls.get("xml", "")
            m3u_url = urls.get("m3u", "")
            
            if m3u_url:
                new_channels = parse_m3u(m3u_url)
                new_epg = parse_epg(xml_url) if xml_url else {}
                apply_epg_fallback(new_channels, new_epg)
                update_cache(new_channels, new_epg)
    else:
        cache_age_minutes = (datetime.now(timezone.utc) - cache_timestamp).total_seconds() / 60.0
        logging.info(f"Using cached EPG data (age: {cache_age_minutes:.1f} minutes)")

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


    return render_template(
        'guide.html',
        channels=cached_channels,
        epg=cached_epg,
        now=now,
        grid_start=grid_start,
        hours_header=hours_header,
        SCALE=SCALE,
        total_width=total_width,
        now_offset=now_offset,
        current_tuner=get_current_tuner()
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

        m3u_url = info.get('m3u')
        xml_url = info.get('xml')

        new_channels = parse_m3u(m3u_url) if m3u_url else []
        new_epg = parse_epg(xml_url) if xml_url else {}
        apply_epg_fallback(new_channels, new_epg)

        # Use new cache update function
        update_cache(new_channels, new_epg)

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

    m3u_url = t.get("m3u", "")
    xml_url = t.get("xml", "")

    # Reachability checks
    m3u_ok = check_url_reachable(m3u_url) if m3u_url else False
    xml_ok = check_url_reachable(xml_url) if xml_url else False

    # Freshness check (keep your current function)
    # If you don't compute age yet, return None so "Unknown" shows
    xml_fresh, xml_age_hours = check_xmltv_freshness(xml_url)


    return jsonify({
        "tuner": curr,
        "m3u_reachable": m3u_ok,
        "xml_reachable": xml_ok,
        "xmltv_fresh": xml_fresh,

        # ADD THESE:
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
    cached_channels = parse_m3u(tuners[current_tuner]["m3u"])
    cached_epg = parse_epg(tuners[current_tuner]["xml"])

    # No background scheduler — auto-refresh is triggered lazily on page/API hits.
    app.run(host='0.0.0.0', port=5000, debug=False)
