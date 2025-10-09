# 📌 IPTV Flask Project — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, but provide a development path for future releases.

---

## 🔮 Feature Upgrades

### 1. Tuner Management
- [x] Add ability to **add/remove tuners** from the UI (v2.3.0).
- [x] Add ability to rename tuners via the UI (v2.3.0).  
- [ ] Support for **.m3u8 single-channel playlists** as tuner sources (planned v3.1.0).  
  - Option A: Special-case `.m3u8` handling in parser.  
  - Option B: Add explicit `hls` column to `tuners.db`.  
- [x] Validate tuner URLs (ping/check format before saving) (v2.0.0).  
- [ ] Optional auto-refresh of tuner lineup on a schedule.

### 2. Logging & Monitoring
- [ ] Move logs from flat file (`activity.log`) into **SQLite DB** for better querying.  
- [ ] Add filtering and pagination in logs view (by user, action, or date).  
- [ ] Add system health checks (e.g., tuner reachability, XMLTV freshness) to logs.  
- [x] **Admin log management**: add button/route to clear logs (with confirmation) (v2.3.1).
- [x] Display log file size on logs page (v2.3.1)

### 3. Guide & Playback
- [ ] Add **search/filter box** to guide for channels/programs.  
- [ ] Add ability to set **favorites** for quick channel access.  
- [x] Add fallback message (“No Guide Data Available”) for channels missing EPG info (v3.0.1).  
- [ ] Add **reminders/notifications** for upcoming programs.  

### 4. User Management
- [ ] Add role-based access control (admin, regular user, read-only).  
- [ ] Add **email or 2FA support** for login (optional).  
- [ ] Show last login time in admin panel.  

### 5. UI/UX Improvements
- [x] Unified theming across all templates (Light, Dark, AOL/CompuServe, TV Guide Magazine) (v2.3.2)
- [ ] Unify CSS across all templates (minimize inline styles).  
- [ ] Make guide responsive (mobile/tablet view).  
- [ ] Add dark/light theme auto-detect from browser/system.  
- [ ] Frozen header Timeline to prevent scrolling with channel listing
- [x] About page under Settings menu (v2.3.1)

### 6. Cross-platform
- [ ] Create installable container.  
- [ ] Create MacOS install/executable.
- [x] Create Microsoft Windows install/executable (full support via PowerShell + NSSM service) (v3.0.0)
- [x] Add uninstall_windows.ps1 and uninstall.bat (v3.0.0)
- [x] Windows installer now bootstraps Chocolatey, installs Python, Git, NSSM, and configures service (v3.0.0)
- [x] Windows uninstaller cleans service, firewall rule, and optionally removes Chocolatey (v3.0.0)  
  - [ ] Validate/test installer fully on Windows environments

### 7. New Features
- [ ] Add the ability to have an auto play video stream upon login from a specific channel (Ersatz currently) to act similar to the 90/2000's tv guide that played "Commercials" until a channel was selected.  
- [ ] Option to play a known or unlisted channel when implemented on ErsatzTV for auto play video stream

### 8. Planned Enhancements
- [ ] Add **safety checks** in `add_tuner()`:
  - Prevent inserting duplicate tuner names.
  - Validate XML/M3U URLs are not empty before committing to DB.

---

## ⚙️ Technical Improvements
- [x] Add uninstall.sh (v2.3.0)  
  - [ ] Validate/test uninstall script fully on Windows environments
- [ ] Add https support  
- [ ] Refactor tuner handling to rely only on DB (remove in-memory fallback).  
- [ ] Add migrations for DB changes (via Alembic or custom script).  
- [ ] Containerize app (Dockerfile + Compose for deployment).  
- [ ] Add test suite for tuner parsing, authentication, and logging.  
- [x] **Automated version bump tool** (`bump_version.py`) that updates `APP_VERSION` in `app.py` and creates a new section in `CHANGELOG.md` (v2.3.1).  

---

## 📅 Priority Suggestions
- Short term: (none — unified UI headers already completed in v2.0.0).  
- Medium term: log filtering (still pending).  
- Medium term: Test and harden installer/uninstaller on mixed Windows environments (v3.0.0 complete, further refinements planned).  
- Long term: .m3u8 support, DB logs, recording functionality.  

## 💻🥧 Installer Enhancement: Kiosk vs Headless Mode (Planned)
**Target Version:** v3.2.0  
**Status:** Planned  
**Effort:** Medium  

- Add an interactive mode selector to the Raspberry Pi installer.
- Headless mode → install to `/home/iptv/iptv-server` with service user `iptv`.
- Kiosk mode → install to `/opt/RetroIPTVGuide` and auto-launch Chromium in fullscreen displaying RetroIPTVGuide.
- Support command-line flags: `--mode kiosk` or `--mode headless` for non-interactive installs.
- Ensure logs and services are properly separated between modes.

---

## ✅ Completed
- [x] Unified theming across all admin/user pages with Themes submenu and persistent setTheme logic (v2.3.2)
- [x] Tuner add/remove via UI (v2.3.0).  
- [x] Tuner rename via UI (v2.3.0).  
- [x] Tuner delete via UI (v2.3.0).  
- [x] Tuner URL validation (v2.0.0).  
- [x] Unified UI headers across templates (v2.0.0).  
- [x] Installer logging (timestamped log files) (v2.3.0).  
- [x] Environment detection in `install.sh` (Linux, WSL, Git Bash) (v2.3.0).  
- [x] Unified cross-platform `install.sh` (v2.3.0).  
- [x] Cross-platform `uninstall.sh` with sudo/admin checks and safe cleanup (v2.3.0).  
- [x] Basic Windows installer support (Git Bash + PowerShell bootstrap) (v2.3.0).  


## ✅ Completed (v3.0.0)
- [x] Full Windows installer/uninstaller support with NSSM service, firewall rule, and Chocolatey integration (v3.0.0).
- [x] Documentation updates (README.md, INSTALL.md) to reflect Windows support (v3.0.0).
