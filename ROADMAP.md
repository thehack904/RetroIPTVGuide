# 📌 RetroIPTVGuide — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, but provide a development path for future releases.

---
# Current Version: **v4.2.1 (2025-11-10)**
This version adds horizontal scroll/refresh as time moves forward, API dynamic guide timing refresh

## 🔮 Feature Upgrades

### 1. Tuner Management
- [x] Add ability to **add/remove tuners** from the UI (v2.3.0).  
- [x] Add ability to rename tuners via the UI (v2.3.0).  
- [ ] Support for **.m3u8 single-channel playlists** as tuner sources (planned v3.2.0).  
- [x] Validate tuner URLs (ping/check format before saving) (v2.0.0).  
- [ ] Optional auto-refresh of tuner lineup on a schedule.  
- [ ] Add per-user tuner assignment and default tuner preferences. *(v4.3.x planned)*  
- [ ] Introduce combined tuner builder (custom tuner aggregation). *(v5.x.x planned)*  

---

### 2. Logging & Monitoring
- [ ] Move logs from flat file (`activity.log`) into **SQLite DB** for better querying.  
- [ ] Add filtering and pagination in logs view.  
- [ ] Add system health checks (tuner reachability, XMLTV freshness).  
- [x] **Admin log management**: clear logs + file size indicator (v2.3.1).  
- [x] Post-install HTTP service verification in Pi installer (v3.1.0).  
- [x] Unified “Refresh Guide” scheduler. *(v4.2.0)*  

---

### 3. Guide & Playback
- [x] **Auto-Scroll feature** added for the Live Guide (v4.1.0).  
  - Uses `requestAnimationFrame` for smooth scroll with fallback watchdog.  
  - Deterministic looping and localStorage preference tracking.  
- [x] Improved auto-scroll performance and modular handling (v4.2.0).  
- [x] Added responsive layout for mobile devices (v4.2.0).  
- [ ] Add search/filter box to guide.  
- [ ] Add ability to set favorites.  
- [x] Fallback message for missing EPG info (v3.0.1).  
- [ ] Add reminders/notifications for upcoming programs.  
- [ ] Add EPG caching for faster guide reloads. *(v5.x.x planned)*  

---

### 4. User Management
- [x] Add **manage_users.html** for integrated user control panel. *(v4.0.0)*  
- [ ] Role-based access control (admin/user/read-only).  
- [ ] Add email or 2FA support for login.  
- [ ] Show last login time in admin panel.  
- [ ] User role/channel restrictions. *(v5.x.x planned)*  

---

### 5. UI/UX Improvements
- [x] Unified theming across all templates (v2.3.2).  
- [x] Android / Fire / Google TV optimized. *(v4.0.0)*  
- [x] Consolidated UI templates (`guide.html`, `login.html`, etc.). *(v4.0.0)*  
- [x] **Refactored UI templates into shared `base.html` and `_header.html` (v4.1.0)**.  
- [x] **Modular CSS and JS added (v4.1.0)** – per-page styling and script loading.  
- [x] Introduced new JS modules: `auto-scroll.js`, `tuner-settings.js`.  
- [x] **Mobile responsive layout and navigation (v4.2.0)**. 
- [ ] Add dark/light theme auto-detect.  
- [ ] Frozen header timeline to prevent scrolling with channel listing.  
- [x] About page under Settings menu (v2.3.1).  

---

### 6. Cross-Platform
- [x] Unified Linux, Windows, and Raspberry Pi installers. *(v4.0.0)*  
- [x] Windows update/uninstall parity implemented. *(v4.1.0)*  
- [ ] Create MacOS install/executable.  
- [x] Validate/test installers on all Windows environments.  
- [ ] Explore TrueNAS SCALE App Catalog certification. *(v5.x.x planned)*  

---

### 7. New Features
- [ ] Add auto-play stream on login (ErsatzTV integration).  
- [ ] Default auto-play source selection.  
- [ ] Begin integration path for **PlutoTV / external IPTV services**. *(v5.x.x)*  

---

### 8. Planned Enhancements
- [ ] Add safety checks in `add_tuner()` (duplicate prevention + URL validation).  
- [x] GPU verification after `raspi-config` (v3.1.0).  
- [x] Suppress `rfkill` Wi-Fi message during GPU config (v3.1.0).  
- [x] Adaptive HTTP check loop (v3.1.0).  
- [x] **Project structure and documentation reorganized** *(v4.0.0–4.2.0)*  

---

## ⚙️ Technical Improvements
- [x] Add uninstall.sh (v2.3.0).  
- [ ] Validate/test uninstall script fully on Windows.  
- [ ] Add HTTPS + optional token-based authentication. *(v4.5.x)*  
- [x] Refactor tuner handling for unified DB. *(v4.0.0)*  
- [x] **Updated bump_version and installer scripts to auto-track new version (v4.1.0)**  
- [x] Containerize app (Dockerfile + Compose).  
- [ ] Add migrations for DB schema changes.  
- [ ] CI/CD automation for official builds. *(v5.x.x)*  
- [ ] Add test suite for tuner parsing, authentication, and logging.  

---

## 🍓 Installer Enhancements
- [x] Unified installer architecture. *(v4.0.0)*  
- [x] Windows update/uninstall parity complete. *(v4.1.0)*  
- [ ] Add kiosk/headless mode selector.  
- [ ] Add `--mode kiosk` flag for non-interactive installs.  
- [ ] Validate update/uninstall paths on all OSes.  

---
## User Submitted Enhancements
- [ ] Casting Support - (Chromecast Support)
- [ ] Resize Pop Out Video - (pop out the video player resize)
- [ ] Resize video on page (able to resize or change the layout of the video on the program guide page)
- [ ] Auto load Channel from Guide / Hidden Channel / Sizzle Reels    


## ✅ Completed (v4.2.0) 
- [x] Added mobile responsive layout.  
- [x] Improved auto-scroll handling and modular JS design.  
- [x] Updated documentation (CHANGELOG, README, INSTALL, ROADMAP).  
- [x] Added RetroIPTV Theme (default).  
- [x] Release tagged as **v4.2.0**  


