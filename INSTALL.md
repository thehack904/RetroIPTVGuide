# Installation Guide

## Requirements
- Python 3.10+ (Linux) / Python 3.12+ (Windows)
- **Linux (Debian/Ubuntu with systemd)** or **Windows 10/11**
- Administrative privileges:
  - **Linux/WSL:** run install/uninstall with `sudo`
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

### Windows 10/11

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

## Access

Once installed, open your browser:

```
http://<server-ip>:5000
```

Default login: **admin / strongpassword123**

---

## 🔄 Updating

### Linux / WSL

#### Quick update (one-liner)
```bash
sudo -u iptv bash -H -c "cd /home/iptv/iptv-server && git fetch --all && git reset --hard origin/main" && sudo systemctl daemon-reload && sudo systemctl restart iptv-server.service
```
or

#### Step-by-step
```bash
sudo -u iptv bash -H
cd /home/iptv/iptv-server
git fetch --all
git reset --hard origin/main
exit
sudo systemctl restart iptv-server.service
```

---

### Windows 10/11

From an **Administrator PowerShell** prompt, go to your RetroIPTVGuide folder and run:

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
sudo chmod +x uninstall.sh
sudo ./uninstall.sh
```

**What the uninstaller does (Linux/WSL):**
- Stops and disables the systemd service
- Removes the systemd unit file
- Deletes the `iptv` system user and related logs
- Removes the Python virtual environment

---

### Windows
From an Administrator PowerShell prompt:
```powershell
.\uninstall_windows.ps1
```

**What the uninstaller does (Windows):**
- Stops and removes the NSSM service
- Removes the Python virtual environment
- Deletes the Windows Firewall rule (port 5000)
- Lists remaining Chocolatey packages
- Prompts whether to uninstall **all Chocolatey packages (including Chocolatey itself)**

⚠️ To completely remove the project, manually delete the project folder after uninstalling.

---

## License
Licensed under CC BY-NC-SA 4.0. See LICENSE for details.

---

⚠️ **Initial BETA Notice**  
This project is currently in **BETA**.  
It should **not** be exposed directly to the Internet or used in production without additional hardening.
