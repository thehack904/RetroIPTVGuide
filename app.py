# app.py — merged version (features from both sources)
APP_VERSION = "v4.2.0"
APP_RELEASE_DATE = "2025-10-25"

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
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import socket
import ipaddress
import logging
import subprocess
from datetime import datetime, timezone, timedelta

# Optional helper module for vlc (try import; fall back to subprocess-based helpers)
try:
    import vlc_control
except Exception:
    vlc_control = None
    logging.exception("vlc_control import failed (this is optional): %s", sys.exc_info()[0])

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
LOG_PATH = "/home/iptv/iptv-server/logs/activity.log"

def log_event(user, action):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(f"{user} | {action} | {ts}\n")

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
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

# ------------------- Init DBs -------------------
def init_db():
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
        conn.commit()

def add_user(username, password):
    password_hash = generate_password_hash(password)
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)', (username, password_hash))
        conn.commit()

def get_user(username):
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, password FROM users WHERE username=?', (username,))
        row = c.fetchone()
    if row:
        return User(row[0], row[1], row[2])
    return None

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, password FROM users WHERE id=?', (user_id,))
        row = c.fetchone()
    if row:
        return User(row[0], row[1], row[2])
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
        c.execute("DELETE FROM tuners WHERE name=?", (name,))
        conn.commit()

def rename_tuner(old_name, new_name):
    """Rename a tuner in DB."""
    with sqlite3.connect(TUNER_DB, timeout=10) as conn:
        c = conn.cursor()
        c.execute("UPDATE tuners SET name=? WHERE name=?", (new_name, old_name))
        conn.commit()

# ------------------- Global cache -------------------
cached_channels = []
cached_epg = {}

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

    # handle when user pastes same .m3u for XML
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

# ------------------- Helper: safe redirect -------------------
def is_safe_url(target):
    try:
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))
        return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
    except Exception:
        return False

# ------------------- Remote / Playback Helpers -------------------
PLAY_SCRIPT = "/usr/local/bin/vlc-play.sh"
STOP_SCRIPT = "/usr/local/bin/vlc-stop.sh"
VLC_LOG = "/var/log/vlc-play.log"

def run_play_script(url, instance="main"):
    """Run the configured helper script via sudo if vlc_control isn't available."""
    if vlc_control:
        try:
            return vlc_control.start(url, instance)
        except Exception:
            logging.exception("vlc_control.start failed")
            # fallthrough to subprocess
    try:
        subprocess.run(["sudo", PLAY_SCRIPT, url, instance], check=True, timeout=30)
        return True
    except Exception:
        logging.exception("Failed to run play script")
        return False

def run_stop_script(instance="main"):
    if vlc_control:
        try:
            return vlc_control.stop(instance)
        except Exception:
            logging.exception("vlc_control.stop failed")
    try:
        subprocess.run(["sudo", STOP_SCRIPT, instance], check=True, timeout=20)
        return True
    except Exception:
        logging.exception("Failed to run stop script")
        return False

def tail_file(path, lines=200):
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 1024
            data = b''
            while size > 0 and lines > 0:
                size -= block
                if size < 0:
                    block += size
                    size = 0
                f.seek(size)
                chunk = f.read(block)
                data = chunk + data
                lines -= chunk.count(b'\n')
            return data.decode(errors='ignore').splitlines()[-200:]
    except Exception:
        return []

# ------------------- Routes -------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form
        user = get_user(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            log_event(username, "Logged in")
            tuners = get_tuners()
            current_tuner = get_current_tuner()
            m3u_url = tuners[current_tuner]["m3u"]
            xml_url = tuners[current_tuner]["xml"]
            global cached_channels, cached_epg
            cached_channels = parse_m3u(m3u_url)
            cached_epg = parse_epg(xml_url)
            cached_epg = apply_epg_fallback(cached_channels, cached_epg)
            # safe redirect handling for optional 'next' param
            next_url = request.args.get('next') or request.form.get('next')
            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for('guide'))
        else:
            log_event(username if username else "unknown", "Failed login attempt")
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_event(current_user.username, "Logged out")
    logout_user()
    return redirect(url_for('login'))

def revoke_user_sessions(username):
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

    tv_patterns = ['silk', 'aft', 'android tv', 'googletv', 'mibox', 'bravia', 'shield', 'tcl', 'hisense', 'puffin', 'tv bro']
    is_tv = any(p in ua for p in tv_patterns)

    if current_user.username != 'admin' or is_tv:
        log_event(current_user.username, f"Unauthorized attempt to access /manage_users from UA: {ua}")
        flash("Unauthorized access.")
        return redirect(url_for('guide'))

    with sqlite3.connect(DATABASE, timeout=10) as conn:
        c = conn.cursor()
        c.execute('SELECT username FROM users WHERE username != "admin"')
        users = [row[0] for row in c.fetchall()]

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
@login_required
def about():
    python_version = sys.version.split()[0]
    os_info = platform.platform()
    install_path = os.getcwd()
    db_path = os.path.join(install_path, "app.db")
    log_path = "/var/log/iptv" if os.name != "nt" else os.path.join(install_path, "logs")

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

            global cached_channels, cached_epg
            tuners = get_tuners()
            m3u_url = tuners[new_tuner]["m3u"]
            xml_url = tuners[new_tuner]["xml"]
            cached_channels = parse_m3u(m3u_url)
            cached_epg = parse_epg(xml_url)
            cached_epg = apply_epg_fallback(cached_channels, cached_epg)

        elif action == "update_urls":
            tuner = request.form["tuner"]
            xml_url = request.form["xml_url"]
            m3u_url = request.form["m3u_url"]

            update_tuner_urls(tuner, xml_url, m3u_url)
            log_event(current_user.username, f"Updated URLs for tuner {tuner}")
            flash(f"Updated URLs for tuner {tuner}")

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
            old_name = request.form["tuner"]
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

    tuners = get_tuners()
    current_tuner = get_current_tuner()
    return render_template(
        "change_tuner.html",
        tuners=tuners.keys(),
        current_tuner=current_tuner,
        current_urls=tuners[current_tuner],
        TUNERS=tuners
    )

@app.route('/guide')
@login_required
def guide():
    log_event(current_user.username, "Loaded guide page")
    now = datetime.now(timezone.utc)
    grid_start = now.replace(minute=(0 if now.minute < 30 else 30), second=0, microsecond=0)
    slots = int((HOURS_SPAN * 60) / SLOT_MINUTES)
    hours_header = [grid_start + timedelta(minutes=SLOT_MINUTES * i) for i in range(slots)]
    total_width = slots * SLOT_MINUTES * SCALE
    minutes_from_start = (now - grid_start).total_seconds() / 60.0
    now_offset = int(minutes_from_start * SCALE)

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

    open(LOG_PATH, "w").close()
    log_event("admin", "Cleared log file")
    flash("🧹 Logs cleared successfully.")
    return redirect(url_for('view_logs'))

# ------------------- Constants -------------------
SCALE = 5
HOURS_SPAN = 6
SLOT_MINUTES = 30

# ------------------- API: guide snapshot -------------------
@app.route('/api/guide_snapshot', methods=['GET'])
def api_guide_snapshot():
    """
    Returns a compact JSON payload representing the current guide window
    and channels. Useful for lightweight clients.
    Query params:
      - tuner (optional)
      - minutes (window size in minutes; default 120)
    """
    try:
        tuner_name = request.args.get('tuner') or get_current_tuner()
        minutes_window = int(request.args.get('minutes') or 120)
        slots = max(1, (minutes_window // 30))
        now = datetime.utcnow()
        start = now - timedelta(minutes=(now.minute % 30), seconds=now.second, microseconds=now.microsecond)
        end = start + timedelta(minutes=minutes_window)

        tuner_info = get_tuners().get(tuner_name, {})
        channels_out = []
        timeline = []

        # build timeline slots
        slot_start = start
        while slot_start < end:
            timeline.append(slot_start.isoformat())
            slot_start += timedelta(minutes=30)

        for ch in cached_channels:
            visible_programs = []
            try:
                tvg = ch.get('tvg_id')
                progs = cached_epg.get(tvg, [])
                for p in progs:
                    pstart = p.get('start')
                    pstop = p.get('stop')
                    if not pstart or not pstop:
                        continue
                    if pstop <= start or pstart >= end:
                        continue
                    clipped_start = max(pstart, start)
                    clipped_stop = min(pstop, end)
                    duration = int((clipped_stop - clipped_start).total_seconds() / 60)
                    visible_programs.append({
                        "title": p.get('title'),
                        "desc": p.get('desc'),
                        "start_iso": clipped_start.isoformat(),
                        "stop_iso": clipped_stop.isoformat(),
                        "duration": duration
                    })
            except Exception:
                pass

            if not visible_programs:
                visible_programs = [{
                    "title": "No Data",
                    "desc": "",
                    "start_iso": start.isoformat(),
                    "stop_iso": (start + timedelta(minutes=30)).isoformat(),
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
                "version": APP_VERSION
            },
            "timeline": timeline,
            "window": {
                "start_iso": start.isoformat(),
                "end_iso": end.isoformat(),
                "minutes": minutes_window
            },
            "channels": channels_out
        }
        return jsonify(payload)
    except Exception as e:
        logging.exception("api_guide_snapshot failed: %s", e)
        return jsonify({"error": str(e)}), 500

@app.route('/api/theme_snapshot', methods=['GET'])
def api_theme_snapshot():
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

# ------------------- QR Visibility Control -------------------
crt_qr_visible = True
qr_hide_time = None
QR_AUTO_RESHOW_MINUTES = 15  # inactivity window

@app.route('/api/qr_status', methods=['GET'])
def api_qr_status():
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
    global crt_qr_visible, qr_hide_time
    crt_qr_visible = False
    qr_hide_time = datetime.utcnow()
    logging.info("QR overlay hidden; inactivity timer started")
    return jsonify({"status": "hidden"})

@app.route('/api/qr_show', methods=['POST'])
def api_qr_show():
    global crt_qr_visible, qr_hide_time
    crt_qr_visible = True
    qr_hide_time = None
    logging.info("QR overlay manually shown via /api/qr_show")
    return jsonify({"status": "visible"})

# ------------------- Playback control endpoints -------------------
@app.route('/api/start_stream', methods=['POST'])
@login_required
def api_start_stream():
    """
    Starts playback using the helper script or vlc_control.
    Expects JSON: { "url": "<stream url>", "instance": "main" }
    """
    data = request.get_json() or {}
    url = data.get('url') or request.form.get('url')
    instance = data.get('instance') or request.form.get('instance') or "main"
    if not url:
        return jsonify({"ok": False, "error": "missing url"}), 400
    ok = run_play_script(url, instance=instance)
    if ok:
        log_event(current_user.username, f"Started stream {url} (instance={instance})")
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "failed to start"}), 500

@app.route('/api/stop_stream', methods=['POST'])
@login_required
def api_stop_stream():
    data = request.get_json() or {}
    instance = data.get('instance') or request.form.get('instance') or "main"
    ok = run_stop_script(instance=instance)
    if ok:
        log_event(current_user.username, f"Stopped stream (instance={instance})")
        return jsonify({"ok": True})
    else:
        return jsonify({"ok": False, "error": "failed to stop"}), 500

@app.route('/api/tail_logs', methods=['GET'])
@login_required
def api_tail_logs():
    max_lines = int(request.args.get('lines') or 200)
    lines = tail_file(VLC_LOG, lines=max_lines)
    return jsonify({"lines": lines})

@app.route('/api/status', methods=['GET'])
@login_required
def api_status():
    """
    Returns playback/log status. This is a best-effort summary (may parse vlc_control if available).
    """
    try:
        state = "stopped"
        raw = ""
        if vlc_control:
            try:
                raw = vlc_control.query()
                state = raw.get('state', 'unknown')
            except Exception:
                logging.exception("vlc_control.query failed")
        # fallback: read tail log
        tail = tail_file(VLC_LOG, lines=20)
        return jsonify({
            'now_playing': None,
            'current_tvg_id': None,
            'current_channel_url': None,
            'vlc_state': state,
            'raw_status': raw,
            'tail_log': tail
        })
    except Exception as e:
        logging.exception("api_status error: %s", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/current_program', methods=['GET'])
@login_required
def api_current_program():
    tvg_id = request.args.get('tvg_id') or request.args.get('id') or ''
    if not tvg_id:
        return jsonify({"ok": False, "error": "missing tvg_id or id"}), 400
    try:
        progs = cached_epg.get(tvg_id, [])
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        current = None
        for p in progs:
            start = p.get('start')
            stop = p.get('stop')
            if start and stop and start <= now < stop:
                current = p
                break
        if not current and progs:
            current = progs[0]
        return jsonify({"ok": True, "channel": tvg_id, "program": current})
    except Exception as e:
        logging.exception("api_current_program error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

# ------------------- Main -------------------
def ensure_default_tuner():
    conn = sqlite3.connect('tuners.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM tuners")
    count = c.fetchone()[0]
    if count == 0:
        c.execute(
            "INSERT INTO tuners (name, xml, m3u) VALUES (?, ?, ?)",
            ("Tuner 1", "http://example.com/guide.xml", "http://example.com/playlist.m3u")
        )
        conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    add_user('admin', 'strongpassword123')
    init_tuners_db()
    ensure_default_tuner()

    tuners = get_tuners()
    current_tuner = get_current_tuner()
    if not current_tuner and tuners:
        current_tuner = list(tuners.keys())[0]
    cached_channels = parse_m3u(tuners[current_tuner]["m3u"])
    cached_epg = parse_epg(tuners[current_tuner]["xml"])
    cached_epg = apply_epg_fallback(cached_channels, cached_epg)

    app.run(host='0.0.0.0', port=5000, debug=False)

