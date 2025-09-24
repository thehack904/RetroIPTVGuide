APP_VERSION = "v2.0.0"

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import re
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ------------------- Config -------------------
app = Flask(__name__)
app.secret_key = os.urandom(24)  # replace with a fixed key in production

login_manager = LoginManager()
@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, username, password FROM users WHERE id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2])
    return None
login_manager.login_view = 'login'
login_manager.init_app(app)

DATABASE = 'users.db'

# IPTV tuners
TUNERS = {
    "Tuner 1": {
        "M3U": "http://iptv.lan:8409/iptv/channels.m3u",
        "EPG": "http://iptv.lan:8409/iptv/xmltv.xml"
    },
    "Tuner 2": {
        "M3U": "http://iptv2.lan:8500/iptv/channels.m3u",
        "EPG": "http://iptv2.lan:8500/iptv/xmltv.xml"
    }
}
CURRENT_TUNER = "Tuner 1"
M3U_URL = TUNERS[CURRENT_TUNER]["M3U"]
EPG_URL = TUNERS[CURRENT_TUNER]["EPG"]

# Guide layout
SCALE = 5         # px/min
HOURS_SPAN = 6    # show next 6 hours
SLOT_MINUTES = 30 # 30-min blocks

# ------------------- Global cache -------------------
cached_channels = []
cached_epg = {}

# ------------------- User Management -------------------
class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
    conn.commit()
    conn.close()

def add_user(username, password):
    password_hash = generate_password_hash(password)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)', (username, password_hash))
    conn.commit()
    conn.close()

def get_user(username):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, username, password FROM users WHERE username=?', (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2])
    return None

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, username, password FROM users WHERE id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2])
    return None

# ------------------- M3U Parsing -------------------
def parse_m3u():
    channels = []
    try:
        r = requests.get(M3U_URL, timeout=10)
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
def parse_epg():
    programs = {}
    try:
        r = requests.get(EPG_URL, timeout=15)
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
            global cached_channels, cached_epg
            cached_channels = parse_m3u()
            cached_epg = parse_epg()
            return redirect(url_for('guide'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
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
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('UPDATE users SET password=? WHERE id=?',
                      (generate_password_hash(new), current_user.id))
            conn.commit()
            conn.close()
            flash("Password updated successfully.")
            return redirect(url_for('guide'))
        else:
            flash("Old password incorrect.")
    return render_template('change_password.html')

@app.route('/add_user', methods=['GET','POST'])
@login_required
def add_user_route():
    if current_user.username != 'admin':
        return redirect(url_for('guide'))

    if request.method == 'POST':
        new_username = request.form['username']
        new_password = request.form['password']
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                      (new_username, generate_password_hash(new_password)))
            conn.commit()
            conn.close()
            flash(f"User {new_username} added successfully.")
            return redirect(url_for('guide'))
        except sqlite3.IntegrityError:
            flash("Username already exists.")
    return render_template('add_user.html')

@app.route('/delete_user', methods=['GET','POST'])
@login_required
def delete_user():
    if current_user.username != 'admin':
        return redirect(url_for('guide'))

    if request.method == 'POST':
        del_username = request.form['username']
        if del_username == 'admin':
            flash("You cannot delete the admin account.")
            return redirect(url_for('delete_user'))

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM users WHERE username=?', (del_username,))
        conn.commit()
        conn.close()
        flash(f"User {del_username} deleted (if they existed).")
        return redirect(url_for('guide'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # exclude admin from dropdown
    c.execute('SELECT username FROM users WHERE username != "admin"')
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return render_template('delete_user.html', users=users)

@app.route('/change_tuner', methods=['GET','POST'])
@login_required
def change_tuner():
    global M3U_URL, EPG_URL, CURRENT_TUNER, cached_channels, cached_epg
    if current_user.username != 'admin':
        return redirect(url_for('guide'))

    if request.method == 'POST':
        selected = request.form.get('tuner')
        if selected in TUNERS:
            CURRENT_TUNER = selected
            if 'm3u' in request.form and 'epg' in request.form:
                TUNERS[selected]["M3U"] = request.form['m3u'].strip()
                TUNERS[selected]["EPG"] = request.form['epg'].strip()
                flash(f"Tuner {selected} updated.")
            else:
                flash(f"Tuner switched to {selected}")

            M3U_URL = TUNERS[CURRENT_TUNER]["M3U"]
            EPG_URL = TUNERS[CURRENT_TUNER]["EPG"]

            cached_channels = parse_m3u()
            cached_epg = parse_epg()
            return redirect(url_for('guide'))

    return render_template('change_tuner.html',
                           tuners=TUNERS.keys(),
                           current=CURRENT_TUNER,
                           current_urls=TUNERS[CURRENT_TUNER])

@app.route('/guide')
@login_required
def guide():
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
        current_tuner=CURRENT_TUNER
    )

# ------------------- Main -------------------
if __name__ == '__main__':
    init_db()
    add_user('admin', 'strongpassword123')  # default admin account
    cached_channels = parse_m3u()
    cached_epg = parse_epg()
    app.run(host='0.0.0.0', port=5000, debug=False)

