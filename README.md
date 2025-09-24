# RetroIPTVGuide

RetroIPTVGuide is an IPTV Web Interface inspired by 90s/2000s cable TV guides.  
It is designed to work with ErsatzTV but should support any `.m3u` and `.xml` IPTV source.  

⚠️ **Note:** This is an initial BETA release. It is not recommended for direct Internet/public-facing deployments.

- [Installation Guide](INSTALL.md)
- [Changelog](CHANGELOG.md)
- [Roadmap](ROADMAP.md)
- [License](LICENSE)

## ✨ Features (v2.0.0)
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
- 🎨 **UI Enhancements**
  - Unified header across all pages (Guide, Logs, Add User, Delete User, Change Password, Change Tuner).
  - Active tuner display + live clock in header.
  - Dark/Light theme toggle (stored in browser localStorage).
- ⚙️ **System**
  - Automatic initialization of `users.db` and `tuners.db` on first run.
  - SQLite databases use WAL mode for better concurrency.
  - Preloads tuner/channel/guide data from DB on startup.

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

## 🛠️ Installation Platform
The backend server should be installed on a **Debian/Ubuntu machine** for best compatibility.  

## 📺 Guide Page
![Guide Screenshot](docs/screenshots/guide.png)

## 📺 Video Pop Out
![Video Pop Out](docs/screenshots/guide_with_video_breakout.png)

## 📺 Video Pop Out on Desktop
![Desktop Pop Out](docs/screenshots/video_breakout_desktop.png)

