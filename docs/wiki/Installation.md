# Installation

This page covers all supported installation methods for RetroIPTVGuide.

---

## Docker (Recommended)

Docker is the recommended and best-supported deployment method.

### Pull and Run

```bash
docker pull ghcr.io/thehack904/retroiptvguide:latest
docker run -d -p 5000:5000 ghcr.io/thehack904/retroiptvguide:latest
```

Open `http://<server-ip>:5000`.

### Docker Compose

A ready-to-use `docker-compose.yml` is included in the `docker/` directory.

```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git
cd RetroIPTVGuide/docker
cp .env.example .env
# Edit .env to set your timezone and secret key
docker compose up -d
```

For full Docker Compose documentation see [`docker/README_DOCKER.md`](../../docker/README_DOCKER.md).

### Updating (Docker)

```bash
docker compose pull && docker compose up -d
```

### Uninstalling (Docker)

```bash
docker compose down -v
```

---

## Linux

### Install

```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_linux.sh \
  | sudo bash -s install --agree --yes
```

Default install location: `/home/iptv/iptv-server`

### Update

```bash
sudo /home/iptv/iptv-server/retroiptv_linux.sh update --yes
```

### Uninstall

```bash
sudo /home/iptv/iptv-server/retroiptv_linux.sh uninstall --yes
```

---

## Raspberry Pi

Supported hardware: Raspberry Pi 3, 4, and 5.

### Install

```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_rpi.sh \
  | sudo bash -s install --agree --yes
```

### Update

```bash
sudo /home/iptv/iptv-server/retroiptv_rpi.sh update --yes
```

### Uninstall

```bash
sudo /home/iptv/iptv-server/retroiptv_rpi.sh uninstall --yes
```

---

## Windows

> ⚠️ **Deprecation Notice:** The Windows installer will be discontinued in **v5.0**.
> Docker is the recommended deployment method going forward. See [Docker](#docker-recommended) above.

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
Invoke-WebRequest https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_windows.bat `
  -OutFile retroiptv_windows.bat
.\retroiptv_windows.bat install
```

---

## Default Login

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `strongpassword123` |

You are required to change the password immediately after the first login.

---

## Admin Password Recovery

If the admin password is lost it can be reset from the command line.

```bash
python3 /home/iptv/iptv-server/scripts/reset_admin_password.py \
  --db /home/iptv/iptv-server/config/users.db
```

Run as the user that owns the database file to avoid permission errors:

```bash
sudo -u iptv python3 /home/iptv/iptv-server/scripts/reset_admin_password.py \
  --db /home/iptv/iptv-server/config/users.db
```

On success the admin password is reset and the account is flagged to require a
password change on next login.

For full recovery steps see [INSTALL.md](../../INSTALL.md).

---

## System Requirements

| Component | Minimum |
|-----------|---------|
| Python | 3.10+ |
| RAM | 512 MB |
| Disk | 500 MB (plus EPG cache) |
| Network | Local LAN access to IPTV source |

Stream playback requires **HLS segmented streams** from your IPTV backend. RetroIPTVGuide
does not transcode streams.

---

## Next Steps

- [Configuration](Configuration.md) — add tuners and configure settings  
- [Virtual Channels](Virtual-Channels.md) — enable built-in virtual channels  
- [Troubleshooting](Troubleshooting.md) — if something isn't working
