# 🐳 RetroIPTVGuide Docker Deployment

This folder contains everything you need to deploy **RetroIPTVGuide** via Docker or Docker Compose.

---

## 🚀 Quick Start

### 1️⃣ Clone the repository and navigate into the Docker directory
```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git
cd RetroIPTVGuide/docker
```

### 2️⃣ Create a `.env` file from the example
```bash
cp .env.example .env
```
Edit `.env` to set your timezone and secret key.

### 3️⃣ Launch the container
```bash
docker compose up -d
```

### 4️⃣ Access the web interface
```
http://<your-server-ip>:5000
```

---

## 🔄 Updating

**Pull the latest pre-built image (recommended):**
```bash
docker compose pull && docker compose up -d
```

**Or, rebuild locally from source (e.g. after `git pull`):**
```bash
git pull && docker compose build && docker compose up -d
```

> Python dependencies in `requirements.txt` are automatically installed when the image is built, and the entrypoint also ensures they are up-to-date on every container start.

---

## 🧹 Uninstalling
```bash
docker compose down -v
```
This stops and removes the container, volumes, and network.

---

## 🧱 Directory Layout
```
docker/
├── docker-compose.yml
├── .env.example
├── config/    → Persistent configuration files
├── data/      → SQLite database files
└── logs/      → Application logs
```
Docker automatically creates these directories on first run if they don’t exist.

---

## 🧠 Notes
- The container image supports both **amd64** and **arm64** (e.g. Raspberry Pi).
- Default exposed port: **5000**
- Default image: `ghcr.io/thehack904/retroiptvguide:latest`
- Restart policy: `unless-stopped`
- Logs, configs, and data persist between updates.

---

## 🧩 Example Commands

View logs:
```bash
docker compose logs -f
```

Restart the container:
```bash
docker compose restart
```

Stop the container:
```bash
docker compose down
```

---

## 🧰 Customization

You can override settings directly in the `.env` file:

| Variable | Description | Example |
|-----------|--------------|----------|
| `TZ` | Timezone | `America/New_York` |
| `FLASK_ENV` | Flask environment | `production` |
| `SECRET_KEY` | Random secure key | `openssl rand -hex 32` |
| `DATABASE_FILE` | SQLite DB filename | `retroiptv.db` |
| `LOG_FILE` | Log file name | `retroiptv.log` |

---

## 🧭 Compatibility

✅ Docker Desktop (Windows/macOS)  
✅ Linux (Ubuntu, Debian, Arch, etc.)  
✅ TrueNAS SCALE (Compose Stack or App)  
✅ Raspberry Pi (ARM builds supported)

---

© 2025 RetroIPTVGuide — Licensed under CC BY-NC-SA 4.0
