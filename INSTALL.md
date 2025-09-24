# Installation Guide

## Requirements
- Python 3.10+
- Systemd-based Linux OS

## Installation
Clone the repository and run the installer:

```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git && cd RetroIPTVGuide && sudo chmod +x install.sh && sudo ./install.sh
```

The installer will:
- Create a system user `iptv` (if not present)
- Install into `/home/iptv/iptv-server`
- Set up Python virtual environment + dependencies
- Configure systemd service

## Access
Once installed, access the guide in your browser:

```
http://<server-ip>:5000
```

Default login: **admin / strongpassword123**

## Updating
```bash
git pull origin main
sudo systemctl restart iptv-server.service
```

## License
Licensed under CC BY-NC-SA 4.0. See LICENSE for details.

---

⚠️ **Initial BETA Notice**  
This project is currently in **BETA**.  
It should **not** be exposed directly to the Internet or used in production without additional hardening.
