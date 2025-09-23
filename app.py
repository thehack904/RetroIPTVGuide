from flask import Flask, render_template, jsonify, redirect, url_for
from flask_login import LoginManager, login_required
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

def init_db():
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT)")
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return redirect(url_for('guide'))

@app.route('/guide')
@login_required
def guide():
    return render_template('guide.html')

@app.route('/api/state')
def api_state():
    return jsonify({"status": "ok"})

@app.route('/api/epg')
def api_epg():
    return jsonify({"slots": [], "grid": []})

if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=5000)
