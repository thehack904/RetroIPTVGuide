# Installation Guide

**Version:** v3.1.0  
**Last Updated:** 2025-10-09  

## Requirements
- Python 3.10+ (Linux) / Python 3.12+ (Windows)
- **Linux (Debian/Ubuntu with systemd)**, **Windows 10/11**, or **Raspberry Pi 3 / 4 / 5 (Headless OS)**
- Administrative privileges:
  - **Linux/WSL/Raspberry Pi:** run install/uninstall with `sudo`
  - **Windows:** run from an Administrator **PowerShell** session

---

## Installation

Clone the repository and run the installer. Choose the command based on your OS.

### Linux / WSL

#### Option 1: One-liner (quick setup)
```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git && cd RetroIPTVGuide && sudo chmod +x install.sh && sudo ./install.sh
```
or

#### Option 2: Multi-line (step-by-step)
```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git
cd RetroIPTVGuide
sudo chmod +x install.sh
sudo ./install.sh
```

**What the installer does (Linux/WSL):**
- Detects Linux/WSL environment  
- Ensures script is run with sudo  
- Creates a system user `iptv`  
- Installs into `/home/iptv/iptv-server`  
- Ensures `python3-venv` is installed  
- Creates Python virtual environment and installs dependencies  
- Creates and enables the `iptv-server` systemd service  
- Starts the service  
- Logs the install to `install_YYYY-MM-DD_HH-MM-SS.log`

---

### Windows 10 / 11

Run this one-liner from an **Administrator PowerShell** prompt:

```powershell
Invoke-WebRequest https://github.com/thehack904/RetroIPTVGuide/archive/refs/heads/main.zip -OutFile RetroIPTVGuide.zip ; tar -xf RetroIPTVGuide.zip ; cd RetroIPTVGuide-main ; .\install.bat
```

**What the installer does (Windows):**
- Bootstraps Chocolatey (if missing)  
- Installs dependencies: `python`, `git`, `nssm`  
- Registers Windows App Paths for `python` / `python3`  
- Adds Python to Git Bash (`~/.bashrc`)  
- Clones RetroIPTVGuide and runs `install.sh` under Git Bash to set up venv + requirements  
- Creates an NSSM service to run `venv\Scripts\python.exe app.py`  
- Opens Windows Firewall port 5000  
- Starts the RetroIPTVGuide service  
- Logs the install to `install_YYYY-MM-DD_HH-MM-SS.log`

---

### Raspberry Pi 3 / 4 / 5 (Headless Edition)

#### Interactive install
```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/refs/heads/dev/retroiptv_rpi.sh | sudo bash -s install
```

#### Unattended / non-interactive
```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/refs/heads/dev/retroiptv_rpi.sh | sudo bash -s install --yes --agree
```

**What the installer does (Raspberry Pi):**
- Detects Pi model (3 / 4 / 5)  
- Installs required packages (`python3-venv`, `ffmpeg`, `git`, etc.) using `apt-get`  
- Creates user `iptv` and installs into `/home/iptv/iptv-server`  
- Configures GPU memory automatically (128 MB on Pi 3 / 256 MB on Pi 4/5)  
- Sets up Python virtual environment and dependencies  
- Creates systemd service `retroiptvguide`  
- Performs post-install HTTP check (localhost:5000) with up-to-15 s polling  
- Logs all activity to `/var/log/retroiptvguide/install-TIMESTAMP.log`  
- Optionally reboots to apply GPU memory changes  

**Requirements**
- Raspberry Pi OS (Bookworm or later)  
- Minimum 8 GB SD card and 1 GB RAM (512 MB swap recommended)  
- SSH or console access with sudo  

---

## Access

Once installed, open your browser:

```
http://<server-ip>:5000
```

Default login: **admin / strongpassword123**
⚠️ This is a **BETA** build for internal network use only.

---

## 🔄 Updating

### Linux / WSL

#### Quick update (one-liner)
```bash
sudo -u iptv bash -H -c "cd /home/iptv/iptv-server && git fetch --all && git reset --hard origin/main" && sudo systemctl daemon-reload && sudo systemctl restart iptv-server.service
```

### Raspberry Pi
```bash
sudo -u iptv bash -H -c "cd /home/iptv/iptv-server && git fetch --all && git reset --hard origin/main" && sudo systemctl daemon-reload && sudo systemctl restart retroiptvguide.service
```

### Windows 10 / 11
```powershell
git fetch --all ; git reset --hard origin/main ; Restart-Service RetroIPTVGuide
```
or

#### Step-by-step
```powershell
git fetch --all
git reset --hard origin/main
Restart-Service RetroIPTVGuide
```

This will:
- Fetch the latest code from GitHub  
- Reset your repo to the latest `windows` branch  
- Restart the RetroIPTVGuide service (installed via NSSM)  

---

## Uninstallation

### Linux / WSL
```bash
sudo -u iptv bash -H -c "cd /home/iptv/iptv-server" && sudo bash /home/iptv/iptv-server/uninstall.sh
```

### Raspberry Pi
```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/refs/heads/main/retroiptv_rpi.sh | sudo bash -s uninstall --yes
```

### Windows
From an Administrator PowerShell prompt:
```powershell
.\uninstall_windows.ps1
```

**Each uninstaller stops its service, removes environment files, and cleans logs.**
⚠️ To completely remove the project, manually delete the project folder after uninstalling.
---

## License
Licensed under CC BY-NC-SA 4.0. See `LICENSE` for details.

---

⚠️ **Initial BETA Notice**  
This project is currently in **BETA** and should **not** be exposed directly to the Internet or used in production without additional hardening.
