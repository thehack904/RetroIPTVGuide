# 📌 IPTV Flask Project — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, but provide a development path for future releases.

---

## 🔮 Feature Upgrades

### 1. Tuner Management
- [x] Add ability to **add/remove tuners** from the UI (v2.3.0).
- [x] Add ability to rename tuners via the UI (v2.3.0).  
- [ ] Support for **.m3u8 single-channel playlists** as tuner sources (planned v3.2.0).  
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
- [x] Post-install HTTP service verification added in Pi installer (v3.1.0)

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
- [x] Create installable container.  
- [ ] Create MacOS install/executable.  
- [x] Create Microsoft Windows install/executable (full support via PowerShell + NSSM service) (v3.0.0)  
- [x] Add uninstall_windows.ps1 and uninstall.bat (v3.0.0)  
- [x] Windows installer bootstraps Chocolatey, installs Python, Git, NSSM, and configures service (v3.0.0)  
- [x] Windows uninstaller cleans service, firewall rule, and optionally removes Chocolatey (v3.0.0)  
  - [ ] Validate/test installer fully on Windows environments  
- [x] **Add Raspberry Pi headless installer (v3.1.0)**  
  - Detects Pi 3 / 4 / 5 models and sets GPU memory dynamically  
  - Installs under `/home/iptv/iptv-server` using user `iptv`  
  - Adds post-install HTTP verification and log summary  
  - Logs full install to `/var/log/retroiptvguide/install-TIMESTAMP.log`

### 7. New Features
- [ ] Add the ability to have an auto play video stream upon login from a specific channel (Ersatz currently) to act similar to the 90/2000's tv guide that played "Commercials" until a channel was selected.  
- [ ] Option to play a known or unlisted channel when implemented on ErsatzTV for auto play video stream

### 8. Planned Enhancements
- [ ] Add **safety checks** in `add_tuner()`:
  - Prevent inserting duplicate tuner names.
  - Validate XML/M3U URLs are not empty before committing to DB.
- [x] Add **GPU verification** after `raspi-config` call (v3.1.0).
- [x] Suppress `rfkill` Wi-Fi message during GPU configuration (v3.1.0).
- [x] Post-install adaptive HTTP check loop (15s poll) (v3.1.0).

---

## ⚙️ Technical Improvements
- [x] Add uninstall.sh (v2.3.0).  
  - [ ] Validate/test uninstall script fully on Windows environments.  
- [ ] Add HTTPS support.  
- [ ] Refactor tuner handling to rely only on DB (remove in-memory fallback).  
- [ ] Add migrations for DB changes (via Alembic or custom script).  
- [ ] Containerize app (Dockerfile + Compose for deployment).  
- [ ] Add test suite for tuner parsing, authentication, and logging.  
- [x] **Automated version bump tool** (`bump_version.py`) now updates:  
  - `APP_VERSION` in `app.py`  
  - `install.sh`  
  - `retroiptv_rpi.sh`  
  - Adds new section in `CHANGELOG.md` (v3.1.0).  

---

## 📅 Priority Suggestions
- Short term: finalize Docker image testing across TrueNAS and generic Linux.
- Medium term: implement `.m3u8` tuner and DB log storage (v3.3.x).
- Long term: HTTPS support and mobile UI redesign.

---

## 🍓 Installer Enhancement: Kiosk vs Headless Mode (Planned)
**Target Version:** v3.2.0  
**Status:** Planned  
**Effort:** Medium  

- Add an interactive mode selector to the Raspberry Pi installer.
- Headless mode → install to `/home/iptv/iptv-server` with service user `iptv`.
- Kiosk mode → install to `/opt/RetroIPTVGuide` and auto-launch Chromium in fullscreen displaying RetroIPTVGuide.
- Support command-line flags: `--mode kiosk` or `--mode headless` for non-interactive installs.
- Ensure logs and services are properly separated between modes.

---
## ✅ Completed (v3.2.0)
- [x] **Containerization & TrueNAS Deployment Support**
  - Dockerfile and docker‑compose finalized for GHCR.
  - TrueNAS SCALE App chart added for persistent deployment.
  - CI/CD publishing pipeline via GitHub Actions and GHCR_PAT.
  - Updated documentation (INSTALL, README, CHANGELOG).

## ✅ Completed (v3.1.0)
- [x] **Raspberry Pi headless installer completed** (`retroiptv_rpi.sh`).  
- [x] Aligned Pi installer with Debian/Windows structure.  
- [x] Added logging to `/var/log/retroiptvguide/`.  
- [x] Added adaptive HTTP service verification.  
- [x] Added GPU verification with silent `raspi-config` call.  
- [x] Added system resource check (SD card size, RAM, swap).  
- [x] Integrated `--yes` and `--agree` installer flags.  
- [x] Verified functionality on Pi 3 and Pi 4.  

---

## ✅ Completed (v3.0.0)
- [x] Full Windows installer/uninstaller support with NSSM service, firewall rule, and Chocolatey integration.  
- [x] Documentation updates (README.md, INSTALL.md) to reflect Windows support.  
