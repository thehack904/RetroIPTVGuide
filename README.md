# 📺 RetroIPTVGuide v4.8.0

<p align="center">
  <a href="https://github.com/thehack904/RetroIPTVGuide">
    <img src="https://img.shields.io/badge/version-v4.8.0-blue?style=for-the-badge" alt="Version">
  </a>
  <a href="https://github.com/thehack904/RetroIPTVGuide/pkgs/container/retroiptvguide">
    <img src="https://img.shields.io/badge/GHCR-ghcr.io/thehack904/retroiptvguide-green?style=for-the-badge&logo=docker" alt="GHCR">
  </a>
  <a href="https://github.com/thehack904/RetroIPTVGuide/actions/workflows/docker-publish.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/thehack904/RetroIPTVGuide/docker-publish.yml?style=for-the-badge&logo=github" alt="Build Status">
  </a>
  <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">
    <img src="https://img.shields.io/badge/license-CC--BY--NC--SA%204.0-lightgrey?style=for-the-badge" alt="License">
  </a>
</p>

---

Welcome to **RetroIPTVGuide**, a lightweight self-hosted IPTV + EPG web interface inspired by classic cable TV guides — built for modern home labs, retro media setups, and Android/Fire/Google TV screens.

RetroIPTVGuide is an IPTV Web Interface inspired by 90s/2000s cable TV guides.  

It is designed to work with [ErsatzTV](https://ersatztv.org/) [(GitRepo)](https://github.com/ErsatzTV/ErsatzTV/tree/main) but supports any `.m3u`, `.m3u8`, and `.xml` IPTV source.  

## 🚀 Features

📺 **Self-hosted IPTV Electronic Program Guide (EPG)**  
Turn any IPTV playlist into a full TV-style channel guide.

🛰 **Virtual Channels System**  
Create channels such as **News, Weather, Traffic (simulated), and System Status** that appear directly inside your guide alongside live IPTV channels.

- **News** uses your own configurable RSS feeds  
- **Weather** provides location-based forecasts using ZIP code or latitude/longitude  
- **Traffic** provides simulated retro-style traffic reports  

📡 **Multi-Source IPTV Support**  
Load multiple **M3U / M3U8 playlists** with **XMLTV EPG data**.

🔀 **Combined Tuners**  
Merge multiple IPTV providers or playlists into one unified channel lineup.

🧭 **Integrated Channel Guide**  
Retro-style guide with smooth **auto-scroll navigation** and TV-style browsing.

📱 **TV-Optimized Web Interface**  
Designed to work well on **Android TV, Fire TV, browsers, and tablets**.

🎛 **Display Scaling Modes**  
Adjust the interface for different screen sizes: **Large / Medium / Small**.

🎨 **Customizable Retro Themes**  
Multiple themes inspired by classic TV guides and retro UI styles.

👥 **User Management System**  
Admin interface for managing users and guide preferences.

🐳 **Simple Deployment Options**

Run almost anywhere:

- Docker
- Linux
- Windows
- Raspberry Pi

🔐 **Local-First by Default**  
Runs entirely on your server with **no cloud services or external dependencies**.

⚙ **Lightweight Backend**  
Built with Flask for easy self-hosting and minimal system requirements.


## 📦 Image Information

| Registry | Image | Architectures | Updated |
|-----------|--------|----------------|----------|
| **GitHub Container Registry** | `ghcr.io/thehack904/retroiptvguide:latest` | amd64 / arm64 | Automatically via CI/CD |

----
⚠️ **Note:** This is still a BETA release. It is not recommended for direct Internet/public-facing deployments.

- [Installation / Uninstall Guide](INSTALL.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [License](LICENSE)

---


## 🛠 Installation

### 🐳 Docker
```bash
docker pull ghcr.io/thehack904/retroiptvguide:latest
docker run -d -p 5000:5000 ghcr.io/thehack904/retroiptvguide:latest
```

### 🧩 TrueNAS SCALE App
- Repository: `ghcr.io/thehack904/retroiptvguide`
- Tag: `latest`
- Exposes port `5000`.

### 🧩 Unraid (Docker) — **BETA / Manual Install Only**
See docker/unraid/ for RetroIPTVGuide.xml / README-unraid.md for installation instructions

### 🐧 Linux 
```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_linux.sh | sudo bash -s install --agree --yes
```

### 🍓 Raspberry Pi
```bash
curl -sSL https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_rpi.sh | sudo bash -s install --agree --yes
```

### 🪟 Windows (PowerShell)
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
Invoke-WebRequest https://raw.githubusercontent.com/thehack904/RetroIPTVGuide/main/retroiptv_windows.bat -OutFile retroiptv_windows.bat
.\retroiptv_windows.bat install
```

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

### 🔄 Updating

### 🐧 Linux 
```bash
sudo /home/iptv/iptv-server/retroiptv_linux.sh update --yes
```

### 🍓 Raspberry Pi 
```bash
sudo /home/iptv/iptv-server/retroiptv_rpi.sh update --yes
```

### 🪟 Windows
**Alignment with Linux/Pi currently on track for v4.0.1 release**
```powershell
git fetch --all ; git reset --hard origin/main ; Restart-Service RetroIPTVGuide
```

---

## 📘 Uninstall

### 🐧 Linux
Run the updater from your installed RetroIPTVGuide folder.
```bash
sudo /home/iptv/iptv-server/retroiptv_linux.sh uninstall --yes
```

### 🍓 Raspberry Pi
```bash
sudo /home/iptv/iptv-server/retroiptv_rpi.sh uninstall --yes
```

### 🪟 Windows
1. Double click or Right Click on retroiptv_windows.bat and select Run As Administrator
2. Select Uninstall

---

## 📸 Screenshots
### 📺 Guide Page - Weather
![Guide Screenshot](docs/screenshots/Virtual_Channel-Guide_w_Weather.png)

### 📺 Guide Page - Traffic
![Guide Screenshot](docs/screenshots/Virtual_Channel-Guide_w_Traffic.png)

### 📺 Virtual Channel - News
![Guide Screenshot](docs/screenshots/Virtual_Channel-News.png)

### 📺 Virtual Channel - Traffic (Simulated)
![Guide Screenshot](docs/screenshots/Virtual_Channel-Traffic-Simulated.png)

### 📺 Auto Scroll
![Auto Scroll](docs/screenshots/auto-scroll.gif)

### 📺 Mobile
![Mobile](docs/screenshots/IMG_0001.jpg)

### 📺 Mobile
![Mobile](docs/screenshots/IMG_0002.jpg)

### 📺 Video Pop Out
![Guide Pop Out](docs/screenshots/guide_with_video_breakout.png)

### 💻 Desktop Pop Out
![Desktop Pop Out](docs/screenshots/video_breakout_desktop.png)

### 📰 TV Guide Magazine Theme
![TV Guide Theme](docs/screenshots/TV_Guide_Theme.png)

### 💾 AOL / CompuServe Theme
![AOL Theme](docs/screenshots/AOL_Compuserve_Theme.png)

---

## 🤝 Contributing

Contributions are welcome! Here’s how you can help:

1. **Report Issues** – Found a bug or want to suggest a feature? Open an [issue](../../issues).  
2. **Submit Pull Requests** – Fork, modify, test, and submit PRs for new features or fixes.  
3. **Improve Documentation** – Add screenshots, examples, or clearer explanations.

All contributions will be reviewed before merging into the main branch.

---

## 🧭 Project Info
- **Homepage:** [GitHub – RetroIPTVGuide](https://github.com/thehack904/RetroIPTVGuide)
- **License:** CC BY-NC-SA 4.0
- **Maintainer:** @thehack904

See [ROADMAP.md](ROADMAP.md) for full details.

---

## 💡 Tip
Combine this with **ErsatzTV** for full media channel playout and a seamless retro-TV experience!
