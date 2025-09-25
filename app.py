APP_VERSION = "v2.0.0"

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import re
import os
import datetime
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse   # added
import socket                       # added
import ipaddress                    # added
from datetime import datetime, timezone, timedelta

# ------------------- Config -------------------
app = Flask(__name__)
app.secret_key = os.urandom(24)  # replace with a fixed key in production

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

# ------------------- Routes -------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            log_event(username, "Logged in")
            tuners = get_tuners()
            current_tuner = get_current_tuner()
            m3u_url = tuners[current_tuner]["m3u"]
            xml_url = tuners[current_tuner]["xml"]
            global cached_channels, cached_epg
            cached_channels = parse_m3u(m3u_url)
            cached_epg = parse_epg(xml_url)
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

        elif action == "update_urls":
            tuner = request.form["tuner"]
            xml_url = request.form["xml_url"]
            m3u_url = request.form["m3u_url"]

            # ✅ Validation before saving
            if xml_url:
              validate_tuner_url(xml_url, label=f"{tuner} XML")
            if m3u_url:
              validate_tuner_url(m3u_url, label=f"{tuner} M3U")

            update_tuner_urls(tuner, xml_url, m3u_url)
            log_event(current_user.username, f"Updated URLs for tuner {tuner}")
            flash(f"Updated tuner {tuner} URLs")

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
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r") as f:
            for line in f:
                parts = line.strip().split(" | ")
                if len(parts) == 3:
                    user, action, timestamp = parts
                    entries.append((user, action, timestamp))
                else:
                    entries.append(("system", line.strip(), ""))
    return render_template("logs.html", entries=entries, current_tuner=get_current_tuner())

# ------------------- Constants -------------------
SCALE = 5
HOURS_SPAN = 6
SLOT_MINUTES = 30

# ------------------- Main -------------------
if __name__ == '__main__':
    init_db()
    add_user('admin', 'strongpassword123')
    init_tuners_db()
    # preload guide cache
    tuners = get_tuners()
    current_tuner = get_current_tuner()
    cached_channels = parse_m3u(tuners[current_tuner]["m3u"])
    cached_epg = parse_epg(tuners[current_tuner]["xml"])
    app.run(host='0.0.0.0', port=5000, debug=False)

