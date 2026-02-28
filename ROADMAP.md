# 📌 RetroIPTVGuide — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, partially implemented, or completed in previous releases.

---
# Current Version: **v4.7.0 (2026-02-28)**

---

## 🔮 Feature Upgrades

### 1. Tuner Management
- [x] Add ability to **add/remove tuners** from the UI (v2.3.0).  
- [x] Add ability to rename tuners via the UI (v2.3.0).  
- [x] Support for **.m3u8 single-channel playlists** as tuner sources. *(v4.6.0)*
- [x] Validate tuner URLs (ping/check format before saving) (v2.0.0).
- [x] Duplicate tuner name prevention in `add_tuner()`. *(v4.6.0)*  
- [x] Optional auto-refresh of tuner lineup on a schedule. *(v4.3.0)*  
- [ ] Add per-user tuner assignment and default tuner preferences.  
- [ ] Introduce combined tuner builder (custom tuner aggregation).  

---

### 2. Logging & Monitoring
- [ ] Move logs from flat file (`activity.log`) into **SQLite DB** for better querying.  
- [x] Add filtering and pagination in logs view. *(v4.5.0)*  
- [x] Add system health checks (tuner reachability, XMLTV freshness). *(v2.3.1)*  
- [x] Admin log management: clear logs + size indicator (v2.3.1).  
- [x] Post-install HTTP service verification in Pi installer (v3.1.0).  
- [x] Unified “Refresh Guide” scheduler. (v4.2.0)  

---

### 3. Guide & Playback
- [x] Auto-Scroll feature added for the Live Guide (v4.1.0).  
- [x] Improved auto-scroll performance and modular handling (v4.2.0).  
- [x] Auto-Scroll Settings flyout menu with Enable/Disable toggle and Slow/Medium/Fast speed sub-flyout. *(v4.6.0)*  
- [x] Added responsive layout for mobile devices (v4.2.0).  
- [ ] Add search/filter box to guide.  
- [ ] Add ability to set favorites.  
- [ ] Channel Info Banner (lower-third overlay with channel #, logo, current/next, progress bar).  
- [ ] Channel number entry with digit buffer + “Tuning to…” overlay.  
- [ ] Last channel quick return.  
- [ ] Browse mode (navigate without tuning until confirmed).  
- [ ] “What’s On Now” dashboard view.  
- [ ] Continue Watching row (per-user recent channels).  
- [ ] Channel health monitoring (stream indicators + pre-check).  
- [ ] Mini Guide overlay (video continues while grid overlays).  
- [x] Fallback message for missing EPG info (v3.0.1).  
- [ ] Add reminders/notifications for upcoming programs.  
- [ ] Add EPG caching for faster guide reloads.  

---

### 4. User Management
- [x] Add manage_users.html (v4.0.0)  
- [-] Role-based access control (basic admin-only gates exist, no RBAC roles).  
- [ ] Add email or 2FA support for login.  
- [x] Show last login time in admin panel. *(v4.5.0)*  
- [ ] User role/channel restrictions.  
- [ ] Per-user favorites storage.  
- [ ] Per-user continue watching history.  

---

### 5. UI/UX Improvements
- [x] Unified theming across all templates (v2.3.2).  
- [x] Android / Fire / Google TV optimized (v4.0.0).  
- [x] Consolidated UI templates (`guide.html`, `login.html`, etc.). (v4.0.0)  
- [x] Refactored UI templates into shared `base.html` and `_header.html` (v4.1.0).  
- [x] Modular CSS and JS added (v4.1.0).  
- [x] Introduced new JS modules: `auto-scroll.js`, `tuner-settings.js`.  
- [x] Mobile responsive layout and navigation (v4.2.0). 
- [x] Add dark/light theme auto-detect. *(v4.5.0)*  
- [x] Frozen header timeline to prevent scrolling with channel listing (v4.3.0).  
- [x] About page under Settings menu (v2.3.1).  
- [x] Added new mobile-specific CSS and JS (v4.3.0).  
- [x] Added new templates: change_tuner.html, manage_users.html, logs.html. (v4.3.0)  
- [x] Fixed scrolling on About, Logs, Tuner Management, and Manage Users pages. *(v4.5.0)*
- [x] Display size setting (Large/Medium/Small) for all themes via transform scale. *(v4.6.0)*
- [x] Fire TV / Android TV DPAD remote navigation + TV-mode proportional UI scaling. *(v4.6.0)*
- [x] Video player aspect-ratio-locked resize handle. *(v4.6.0)*
- [x] Fixed time bar style normalized across all themes. *(v4.6.0)*
- [ ] Retro Theme Packs (1997 Analog, 2002 Digital Cable, TV Guide style, Modern Clean).
- [ ] Advanced Mode toggle (hide/show power-user features).
- [ ] Screen saver / burn-in protection mode.
- [ ] Multi-device sync (same-user follow mode).

---

### 6. Cross-Platform
- [x] Unified Linux, Windows, and Raspberry Pi installers. (v4.0.0)  
- [x] Windows update/uninstall parity implemented. (v4.1.0)  
- [ ] Create MacOS install/executable.  
- [x] Validate/test installers on all Windows environments.  
- [ ] Explore TrueNAS SCALE App Catalog certification.  

---

### 7. New Features
- [ ] Multi-device Remote Control page (remote.html controlling active guide session).
- [ ] WebSocket-based same-user remote session routing.
- [ ] Favorites system (per-user channel starring).
- [ ] Smart filtering (genre, HD only, live now, favorites).
- [ ] Begin integration path for PlutoTV / external IPTV services.  
- [-] Add auto-play stream on login. *(partial JS scaffolding in tuner-settings.js)*  
- [-] Default auto-play source selection. *(partial JS only, not wired to UI)*  

---

### 8. Planned Enhancements
- [ ] Add safety checks in add_tuner() (duplicate prevention + URL validation).  
- [x] GPU verification after `raspi-config` (v3.1.0).  
- [x] Suppress `rfkill` Wi-Fi message during GPU config (v3.1.0).  
- [x] Adaptive HTTP check loop (v3.1.0).  
- [x] Project structure and documentation reorganized (v4.0.0–4.2.0).  

---

## ⚙️ Technical Improvements
- [x] Add uninstall.sh (v2.3.0).  
- [ ] Validate/test uninstall script fully on Windows.  
- [ ] Add HTTPS + optional token-based authentication.  
- [x] Refactor tuner handling for unified DB. (v4.0.0)  
- [x] Updated bump_version and installer scripts for new structure. (v4.3.0)  
- [x] Containerize app (Dockerfile + Compose).  
- [ ] Add migrations for DB schema changes.  
- [ ] CI/CD automation for official builds.  
- [-] Add test suite for tuner parsing, authentication, and logging. *(placeholder file only)*  

---

## 🍓 Installer Enhancements
- [x] Unified installer architecture. (v4.0.0)  
- [x] Windows update/uninstall parity complete. (v4.1.0)  
- [ ] Add kiosk/headless mode selector.  
- [ ] Add `--mode kiosk` flag for non-interactive installs.  
- [ ] Validate update/uninstall paths on all OSes.  

---

## User Submitted Enhancements
- [ ] Casting Support (Chromecast)
- [x] Resize Pop Out Video *(v4.6.0)*
- [x] Resize video on page *(v4.6.0)*
- [ ] Auto load Channel from Guide / Hidden Channel / Sizzle Reels
- [x] Adjustable scrolling speed of the Guide *(v4.6.0)*
- [ ] Output IPTV stream from built guide for re-broadcast as a channel
- [x] Unraid Template - in *BETA*
