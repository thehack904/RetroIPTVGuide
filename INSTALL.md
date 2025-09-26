# Installation Guide

## Requirements
- Python 3.10+
- Linux (Debian/Ubuntu with systemd) **or** Windows (Git Bash with Python 3.12+)
- Administrative privileges:
  - **Linux/WSL:** run install/uninstall with `sudo`
  - **Windows (Git Bash):** run from an Administrator shell

---

## Installation

Clone the repository and run the installer

One-line:
```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git && cd RetroIPTVGuide && sudo chmod +x install.sh && sudo ./install.sh
```
Multi-line (step-by-step commands):
```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git
cd RetroIPTVGuide
sudo chmod +x install.sh
sudo ./install.sh
```

### What the installer does
- Detects environment (Linux, WSL, or Git Bash on Windows)
- Creates a system user `iptv` and sets up systemd service (Linux/WSL only)
- Installs into `/home/iptv/iptv-server` (Linux/WSL) or local project folder (Windows)
- Creates Python virtual environment + installs dependencies
- Logs the full install process to `install_YYYY-MM-DD_HH-MM-SS.log`

---

## Access

Once installed, access the guide in your browser:

```
http://<server-ip>:5000
```

Default login: **admin / strongpassword123**

---

## Updating

To update from the repository:

```bash
git pull origin main
sudo systemctl restart iptv-server.service   # Linux/WSL only
```

On Windows (Git Bash), just pull and restart with:

```bash
git pull origin main
./venv/Scripts/python app.py
```

---

## Uninstallation

Run the included `uninstall.sh`:

```bash
sudo chmod +x uninstall.sh
sudo ./uninstall.sh
```

### What the uninstaller does
- **Linux/WSL:**
  - Stops and disables the systemd service
  - Removes the systemd unit file
  - Deletes the `iptv` system user and related logs
  - Removes the Python virtual environment
- **Windows (Git Bash):**
  - Stops any running `python app.py` process
  - Removes the Python virtual environment
  - Leaves the project folder in place

⚠️ To completely remove the project, **manually delete the project folder** after running `uninstall.sh`.

---

## License
Licensed under CC BY-NC-SA 4.0. See LICENSE for details.

---

⚠️ **Initial BETA Notice**  
This project is currently in **BETA**.  
It should **not** be exposed directly to the Internet or used in production without additional hardening.
