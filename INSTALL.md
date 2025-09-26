# Installation Guide

## Requirements
- Python 3.10+
- Linux (Debian/Ubuntu with systemd) **or** Windows (Git Bash with Python 3.12+)
- Administrative privileges:
  - **Linux/WSL:** run install/uninstall with `sudo`
  - **Windows (Git Bash):** run from an Administrator shell

---

## Installation

Clone the repository and run the installer (choose one, no need to do both below)

### Option 1: One-liner (quick setup)
```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git && cd RetroIPTVGuide && sudo chmod +x install.sh && sudo ./install.sh
```
or

### Option 2: Multi-line (step-by-step)
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

### Linux/WSL

#### Option 1: One-liner (quick update)
```bash
sudo -u iptv bash -H -c "cd /home/iptv/iptv-server && git fetch --all && git reset --hard origin/main" && sudo systemctl restart iptv-server.service
```
or

#### Option 2: Step-by-step
```bash
sudo -u iptv bash -H
cd /home/iptv/iptv-server
git fetch --all
git reset --hard origin/main
exit
sudo systemctl restart iptv-server.service
```

---

### Windows (Git Bash)

Run these from the folder where you cloned the repo:

#### Option 1: One-liner
```bash
git fetch --all && git reset --hard origin/main && ./venv/Scripts/python app.py
```

or

#### Option 2: Step-by-step
```bash
git fetch --all
git reset --hard origin/main
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
