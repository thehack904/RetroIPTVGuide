# 📌 RetroIPTVGuide — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, but provide a development path for future releases.

---
# Current Version: v4.0.0 (2025-10-19)
The 4.0.0 release merges all Testing branch updates into Main, introducing unified installers, new UI templates, and Android TV optimizations.

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
- [ ] Add per-user tuner assignment and default tuner preferences. 🆕 *(v4.1.x planned)*  
- [ ] Introduce combined tuner builder (custom tuner aggregation). 🆕 *(v5.x.x planned)*  

---

### 2. Logging & Monitoring
- [ ] Move logs from flat file (`activity.log`) into **SQLite DB** for better querying.  
- [ ] Add filtering and pagination in logs view (by user, action, or date).  
- [ ] Add system health checks (e.g., tuner reachability, XMLTV freshness) to logs.  
- [x] **Admin log management**: add button/route to clear logs (with confirmation) (v2.3.1).  
- [x] Display log file size on logs page (v2.3.1).  
- [x] Post-install HTTP service verification added in Pi installer (v3.1.0).  
- [ ] Add unified “Refresh Guide” scheduler (configurable intervals). 🆕 *(v4.2.x planned)*  

---

### 3. Guide & Playback
- [ ] Add **search/filter box** to guide for channels/programs.  
- [ ] Add ability to set **favorites** for quick channel access.  
- [x] Add fallback message (“No Guide Data Available”) for channels missing EPG info (v3.0.1).  
- [ ] Add **reminders/notifications** for upcoming programs.  
- [ ] Add EPG caching for faster guide reloads. 🆕 *(v5.x.x planned)*  

---

### 4. User Management
- [x] Add **manage_users.html** for integrated user control panel. ✅ *(v4.0.0)*  
- [ ] Add role-based access control (admin, regular user, read-only).  
- [ ] Add **email or 2FA support** for login (optional).  
- [ ] Show last login time in admin panel.  
- [ ] Enhance user management (roles, channel restrictions). 🆕 *(v5.x.x planned)*  

---

### 5. UI/UX Improvements
- [x] Unified theming across all templates (Light, Dark, AOL/CompuServe, TV Guide Magazine) (v2.3.2).  
- [x] Android / Fire / Google TV optimized mode with CRT glow header. ✅ *(v4.0.0)*  
- [x] Consolidated and modernized UI templates (`guide.html`, `login.html`, `about.html`, `logs.html`, etc.). ✅ *(v4.0.0)*  
- [ ] Unify CSS across all templates (minimize inline styles).  
- [ ] Make guide responsive (mobile/tablet view).  
- [ ] Add dark/light theme auto-detect from browser/system.  
- [ ] Frozen header timeline to prevent scrolling with channel listing.  
- [x] About page under Settings menu (v2.3.1).  

---

### 6. Cross-platform
- [x] Create installable container.  
- [x] Unified Linux, Windows, and Raspberry Pi installers. ✅ *(v4.0.0)*  
- [x] Windows installer via PowerShell + NSSM service (v3.0.0).  
- [x] Pi installer auto-configures GPU and verifies HTTP service (v3.1.0).  
- [x] Add **Windows update/uninstall parity planned**. 🆕 *(v4.1.x target)*  
- [ ] Create MacOS install/executable.  
- [x] Validate/test installers fully on all Windows environments.  
- [ ] Explore TrueNAS SCALE App Catalog certification. 🆕 *(v5.x.x planned)*  

---

### 7. New Features
- [ ] Add the ability to have an **auto-play video stream** upon login (ErsatzTV source).  
- [ ] Option to play a known or unlisted channel as default auto-play source.  
- [ ] Begin integration path for **PlutoTV / external IPTV services**. 🆕 *(v5.x.x)*  

---

### 8. Planned Enhancements
- [ ] Add **safety checks** in `add_tuner()`:
  - Prevent inserting duplicate tuner names.
  - Validate XML/M3U URLs before commit.  
- [x] Add **GPU verification** after `raspi-config` call (v3.1.0).  
- [x] Suppress `rfkill` Wi-Fi message during GPU configuration (v3.1.0).  
- [x] Post-install adaptive HTTP check loop (15s poll) (v3.1.0).  
- [x] Reorganized project structure and documentation. ✅ *(v4.0.0)*  

---

## ⚙️ Technical Improvements
- [x] Add uninstall.sh (v2.3.0).  
- [ ] Validate/test uninstall script fully on Windows environments.  
- [ ] Add HTTPS + optional token-based authentication. 🆕 *(v4.5.x)*  
- [x] Refactor tuner handling for unified DB structure. ✅ *(v4.0.0)*  
- [ ] Add migrations for DB schema changes.  
- [x] Containerize app (Dockerfile + Compose for deployment).  
- [x] Automated version bump tool updates all key scripts (v3.1.0).  
- [ ] Add CI/CD automation for official .deb and .zip builds. 🆕 *(v5.x.x)*  
- [ ] Add test suite for tuner parsing, authentication, and logging.  

---

## 🍓 Installer Enhancements
- [x] Unified Linux/Windows/RPi installer architecture. ✅ *(v4.0.0)*  
- [ ] Add interactive mode selector (Kiosk vs Headless).  
- [ ] Add command-line flag `--mode kiosk` for non-interactive installs.  
- [ ] Ensure logs/services properly isolated between modes.  
- [ ] Validate update/uninstall paths on all OSes.  

---

## ✅ Completed (v4.0.0)
- [x] Unified cross-platform installers (`retroiptv_linux.sh`, `retroiptv_windows.ps1`, `retroiptv_rpi.sh`)  
- [x] Android/Fire/Google TV mode added with animated CRT glow  
- [x] Added `manage_users.html` for full web-based user management  
- [x] Modernized `guide.html`, `login.html`, `about.html`, `logs.html`, etc.  
- [x] Refactored `app.py` for unified configuration + session logic  
- [x] Removed legacy installers (`install.*`, `uninstall.*`, `iptv-server.service`)  
- [x] Reorganized documentation (CHANGELOG, README, ROADMAP)  
- [x] Release tagged as **v4.0.0**  
