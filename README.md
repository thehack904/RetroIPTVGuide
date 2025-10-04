# RetroIPTVGuide

![Version](https://img.shields.io/badge/version-v3.0.0-blue)

RetroIPTVGuide is an IPTV Web Interface inspired by 90s/2000s cable TV guides.  
It is designed to work with [ErsatzTV](https://ersatztv.org/) [(GitRepo)](https://github.com/ErsatzTV/ErsatzTV/tree/main) but should support any `.m3u` and `.xml` IPTV source.  

⚠️ **Note:** This is still a BETA release. It is not recommended for direct Internet/public-facing deployments.

- [Installation / Uninstall Guide](INSTALL.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [License](LICENSE)

## ✨ Features (v3.0.0)
- 🔑 **User Authentication**
  - Login/logout system with hashed passwords.
  - Admin and regular user accounts.
  - Password change functionality.
  - Admin-only user management (add/delete users).
- 📡 **Tuner Management**
  - Multiple tuner support stored in `tuners.db`.
  - Switch between active tuners via the web UI.
  - Update `.m3u` and `.xml` tuner URLs (persisted in DB).
- 📺 **Guide & Playback**
  - Program guide rendered from XMLTV.
  - Channel list parsed from M3U playlist.
  - Video playback using HTML5 + HLS.js.
  - Playback events logged with user + channel + timestamp.
- 📑 **Logging**
  - Activity log (`activity.log`) records authentication events, tuner changes, playback, and admin actions.
  - Admin-only **Logs page** with real-time log viewing.
  - **Log file size display with color coding (v2.3.1)**.
  - **Admin-only “Clear Logs” button to truncate logs (v2.3.1)**.
- 🎨 **UI Enhancements**
  - Unified header across all pages (Guide, Logs, Add User, Delete User, Change Password, Change Tuner).
  - Active tuner display + live clock in header.
  - **Themes submenu** with multiple options:
    - Light
    - Dark
    - AOL/CompuServe
    - TV Guide Magazine
  - Theme persistence stored in browser localStorage, applied instantly across all pages.
  - **About Page under Settings menu** — shows version, Python, OS, uptime, paths.
- ⚙️ **System**
  - Automatic initialization of `users.db` and `tuners.db` on first run.
  - SQLite databases use WAL mode for better concurrency.
  - Preloads tuner/channel/guide data from DB on startup.
  - **Cross-platform installers (Linux/Windows)**.
  - **Uninstaller scripts (Linux/Windows)**.
  - **Automated version bump tool (`bump_version.py`)**.

---

## 🌐 Browser Compatibility
This project is designed to work with **all major browsers**.  
It has been tested on:  
- Firefox  
- Chrome  
- Safari  
- Edge  

## 💻 Tested Devices & OS
The web interface has been tested on:  
- **Ubuntu (desktop/server)**  
- **iOS (mobile/tablet)**
- **Android (Samsung Mobile Phone)**
- **macOS**
- **Windows 10/11**
- **MacOS**
- **Windows**

## 🛠️ Installation Platform
- **Debian Based Linux (desktop/server)**
- **Windows 10/11**

## 📺 Screenshots

## 📺 Guide Page
![Guide Screenshot](docs/screenshots/guide.png)

## 📺 Video Pop Out
![Video Pop Out](docs/screenshots/guide_with_video_breakout.png)

## 📺 Video Pop Out on Desktop
![Desktop Pop Out](docs/screenshots/video_breakout_desktop.png)

## 📺 TV Guide Magazine Theme
![TV Guide Theme](docs/screenshots/TV_Guide_Theme.png)

## 📺 AOL / CompuServe Theme
![AOL / CompuServe Theme](docs/screenshots/AOL_Compuserve_Theme.png)

---

## 🤝 Contributing
Contributions are welcome! Here’s how you can help:  
1. **Report Issues**: Found a bug or want to suggest a feature? Open an [issue](../../issues).  
2. **Submit Pull Requests**: Fork the repo, make changes, and submit a PR. Please ensure code is tested before submitting.  
3. **Improve Documentation**: Help refine the installation guide, add screenshots, or improve explanations in the README.  

All contributions will be reviewed by the project maintainer before merging.  
