# RetroIPTVGuide

<p align="center">
  <a href="https://github.com/thehack904/RetroIPTVGuide">
    <img src="https://img.shields.io/badge/version-v3.2.0-blue?style=for-the-badge" alt="Version">
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

## 📦 Image Information

| Registry | Image | Architectures | Updated |
|-----------|--------|----------------|----------|
| **GitHub Container Registry** | `ghcr.io/thehack904/retroiptvguide:latest` | amd64 / arm64 | Automatically via CI/CD |

---

RetroIPTVGuide is an IPTV Web Interface inspired by 90s/2000s cable TV guides.  
It is designed to work with [ErsatzTV](https://ersatztv.org/) [(GitRepo)](https://github.com/ErsatzTV/ErsatzTV/tree/main) but supports any `.m3u`, `.m3u8`, and `.xml` IPTV source.  
Now includes **Docker and TrueNAS SCALE deployment support** for easy installation and persistence.

⚠️ **Note:** This is still a BETA release. It is not recommended for direct Internet/public-facing deployments.

- [Installation / Uninstall Guide](INSTALL.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [License](LICENSE)

---
## 🚀 Containerized Deployment (v3.2.0)

### 🐳 Docker
```bash
docker pull ghcr.io/thehack904/retroiptvguide:latest
docker run -d -p 5000:5000 ghcr.io/thehack904/retroiptvguide:latest
```
Access the web interface at:  
`http://<server-ip>:5000`

### 🧩 TrueNAS SCALE App
- Upload the provided `retroiptvguide-3.2.0.zip` chart.
- Repository: `ghcr.io/thehack904/retroiptvguide`
- Tag: `latest`
- Exposes port `5000`.

---

## ✨ Features (v3.2.0)

- Official **Docker / TrueNAS** support with persistent volumes.
- Automatic build/publish to **GHCR** via GitHub Actions.
- Same RetroIPTVGuide web interface and EPG features from v3.1.x.
- Backward compatible with Linux, Windows, and Raspberry Pi installs.

---

### 🔑 User Authentication
- Login/logout system with hashed passwords.
- Admin and regular user accounts.
- Password change functionality.
- Admin-only user management (add/delete users).

### 📡 Tuner Management
- Multiple tuner support stored in `tuners.db`.
- Switch between active tuners via the web UI.
- Update `.m3u`, `.m3u8`, and `.xml` tuner URLs (persisted in DB).
- Active tuner refreshes instantly when changed — **no logout required**.
- Detection for invalid XML inputs (e.g., `.m3u` pasted into `.xml` field).

### 📺 Guide & Playback
- Program guide rendered from XMLTV data.
- **Automatic fallback:** Channels missing XMLTV data display *“No Guide Data Available”*.
- Channel list parsed from M3U playlist.
- Video playback using HTML5 + HLS.js.
- Playback events logged with user + channel + timestamp.
- Scalable time grid and responsive EPG layout.

### 📑 Logging
- `activity.log` records authentication events, tuner changes, playback, and admin actions.
- Admin-only **Logs page** with real-time log viewing.
- Log file size display with color coding.
- Admin-only “Clear Logs” button to truncate logs.

### 🎨 UI Enhancements
- Unified header across all pages: Guide, Logs, Add User, Delete User, Change Password, Change Tuner, and Login.
- Active tuner display + live clock in header.
- “No Guide Data Available” placeholders styled in gray/italic with dashed border.
- **Themes submenu** with multiple options:
  - Light  
  - Dark  
  - AOL/CompuServe  
  - TV Guide Magazine  
- Theme persistence stored in browser localStorage, applied instantly across all pages.
- **About Page under Settings** — shows version, Python, OS, uptime, and paths.
- **Login Page Redesign (v3.0.1)**:
  - Floating centered login box with 3D shadow.
  - RetroIPTVGuide logo positioned upper-right.

### ⚙️ System
- Automatic initialization of `users.db` and `tuners.db` on first run.
- SQLite databases use WAL mode for better concurrency.
- Preloads tuner/channel/guide data from DB on startup.
- **Cross-platform installers:**  
  - Linux / WSL (`install.sh`)  
  - Windows (`install_windows.ps1`)  
  - Raspberry Pi (`retroiptv_rpi.sh`)  
- **Uninstaller scripts for all platforms**
- **Automated version bump tool (`bump_version.py`)** — now updates both `install.sh` and `retroiptv_rpi.sh`.

---

## 🧩 Version History

| Version | Date | Key Features |
|----------|------|---------------|
| **v3.2.0** | 2025-10-11 | Containerized Deployment / TrueNAS Scale App installer |
| **v3.1.0** | 2025-10-09 | Raspberry Pi installer, verified GPU setup, improved HTTP service check |
| **v3.0.1** | 2025-10-07 | EPG fallback system, tuner refresh fix, login redesign |
| **v3.0.0** | 2025-10-03 | Windows installer/uninstaller, cross-platform setup, unified UI |
| **v2.3.x** | 2025-09 | Unified theming, About page, installer logging, tuner rename/delete |
| **v2.0.0** | 2025-09 | Persistent tuners.db, user logs, unified headers |
| **v1.x.x** | 2025-08 | Initial IPTV Flask prototype |

---

## 🌐 Browser Compatibility
RetroIPTVGuide is compatible with all modern browsers:

- Firefox  
- Chrome  
- Safari  
- Edge  

---

## 💻 Tested Devices & Operating Systems
- **Ubuntu 24.04 (desktop/server)**
- **TrueNAS SCALE (Docker)**
- **Windows 10 / 11**
- **Raspberry Pi 3B+ / 4 / 5 (Raspberry Pi OS Bookworm)**
- **macOS Monterey / Ventura**
- **iOS (mobile/tablet)**
- **Android (Samsung / Pixel)**

---

## 🛠️ Installation Platforms
- Debian-based Linux (Ubuntu, Pop!\_OS, Mint)
- Windows 10/11 (via PowerShell + NSSM)
- Raspberry Pi 3 / 4 / 5 (Headless OS, `retroiptv_rpi.sh`)
- Docker (Generic Linux / macOS / Windows)

---

## 📸 Screenshots

### 📺 Guide Page
![Guide Screenshot](docs/screenshots/guide.png)

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

## 🧭 Roadmap (Next Planned Features)
- [ ] `.m3u8` single-channel tuner support  
- [ ] Log filtering and pagination  
- [ ] Guide search/filter  
- [ ] Favorites and notifications  
- [ ] Responsive mobile layout  
- [ ] Auto-refresh EPG schedule  

See [ROADMAP.md](ROADMAP.md) for full details.

---

## 🧰 Maintainer Notes
- **Repo:** [RetroIPTVGuide](https://github.com/thehack904/RetroIPTVGuide)
- **Maintainer:** J.H.  
- **License:** [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/)  
- **Version:** v3.2.0  
- **Release Date:** 2025-10-11  

---

© 2025 RetroIPTVGuide Project — *Licensed under CC BY-NC-SA 4.0. Inspired by the golden era of cable TV.*
