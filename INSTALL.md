# Installation Guide

**Version:** v4.0.0  
**Last Updated:** 2025-10-19  

---

## 🧰 Requirements
- Python 3.10+ (Linux) / Python 3.12+ (Windows)
- **Linux (Debian/Ubuntu with systemd)**, **Windows 10/11**, or **Raspberry Pi 3 / 4 / 5 (Headless OS) / Docker**
- Administrative privileges:
  - **Linux/WSL/Raspberry Pi:** run install/uninstall with `sudo`
  - **Windows:** run from an Administrator **PowerShell** session

---

## 🛠 Installation

### 🧱 Docker (Generic Linux / macOS / Windows)

## 🐳 Quick Docker Run

The fastest way to launch **RetroIPTVGuide v3.2.0**:

```bash
docker pull ghcr.io/thehack904/retroiptvguide:latest
docker run -d   --name retroiptvguide   -p 5000:5000   -e TZ=America/Chicago   -e SECRET_KEY=$(openssl rand -hex 32)   -v $(pwd)/config:/app/config   -v $(pwd)/logs:/app/logs   -v $(pwd)/data:/app/data   ghcr.io/thehack904/retroiptvguide:latest
```

#### Using Docker Compose

```bash
git clone https://github.com/thehack904/RetroIPTVGuide.git
cd RetroIPTVGuide/docker
cp .env.example .env
docker compose up -d
```

### 🐧 Linux
#### Automated
```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_linux.sh | sudo bash -s install --agree --yes
```

#### Manual
```bash
wget https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_linux.sh
sudo bash ./retroiptv_linux.sh install
```

---

### 🍓 Raspberry Pi
#### Automated
```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_rpi.sh | sudo bash -s install --agree --yes
```

#### Manual
```bash
wget https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_rpi.sh
sudo bash ./retroiptv_rpi.sh install
```

---

### 🪟 Windows (PowerShell)
#### Automated
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
Invoke-WebRequest https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_windows.ps1 -OutFile retroiptv_windows.ps1
.\retroiptv_windows.ps1 install
```

#### Manual
1. Download `retroiptv_windows.ps1` from the GitHub repository.  
2. Open **PowerShell as Administrator**.  
3. Navigate to the folder containing the script.  
4. Run:
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force
   .\retroiptv_windows.ps1 install
   ```

---

## 🌐 Access
After installation:
```
🌐 RetroIPTVGuide Web Interface: http://<server-ip>:5000
🔑 Default Login: admin / strongpassword123
```

> ⚠️ **Beta Notice:**  
> This version is feature-complete and stable, but still displays a *Beta* disclaimer during installation for liability protection.  
> Do not expose your instance directly to the public Internet.

---

## 🔄 Updating

### 🐧 Linux
```bash
sudo retroiptv_linux.sh update
```

### 🍓 Raspberry Pi
```bash
sudo retroiptv_rpi.sh update
```

### 🪟 Windows
**Alignment with Linux/Pi currently on track for v4.0.1 release**
```powershell
git fetch --all ; git reset --hard origin/main ; Restart-Service RetroIPTVGuide
```

#### Docker
```bash
docker compose pull && docker compose up -d
```

---

## 📘 Uninstall

### 🐧 Linux
```bash
sudo retroiptv_linux.sh uninstall
```

### 🍓 Raspberry Pi
```bash
sudo retroiptv_rpi.sh uninstall
```

### 🪟 Windows
1. Double-click or right-click on `retroiptv_windows.bat` and select **Run as Administrator**  
2. Select **Uninstall**

#### Docker
```bash
docker compose down -v
```

**Each uninstaller stops its service, removes environment files, and cleans logs.**
⚠️ To completely remove the project, manually delete the project folder after uninstalling.
---

## ⚙️ Notes
- All installers log activity with timestamps (stored in the same directory or `/var/log/retroiptvguide/`).  
- Uninstallers remove services and dependencies cleanly but preserve user data unless explicitly deleted.  
- These scripts are intended for **local or internal networks only**.

---

## License
Licensed under **CC BY-NC-SA 4.0**. See `LICENSE` for details.
