# Installation Instructions

## Prerequisites
- Ubuntu 22.04+ or Debian-based Linux
- Python 3.10+
- Systemd

## Steps

```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git
cd RetroIPTVGuide
chmod +x install.sh
./install.sh
```

This will:
- Create a dedicated `iptv` system user
- Install the project under `/home/iptv/iptv-server`
- Setup a Python virtual environment and dependencies
- Install and start a systemd service

## Access
Once installed, access the IPTV web interface at:

```
http://<your-server-ip>:5000
```

### Default login
- **Username:** admin  
- **Password:** admin  

⚠️ Change this immediately after first login.

---

## Updating
```bash
git pull origin main
sudo systemctl restart iptv-server.service
```

## License
Licensed under CC BY-NC-SA 4.0. See LICENSE for details.

---

🚨 **BETA WARNING**  
This is an initial BETA release. Do not expose it directly to the public Internet without additional security hardening.
