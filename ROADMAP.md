# 📌 RetroIPTVGuide — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, partially implemented, or completed in previous releases.

---
# Current Version: **v4.7.1 (2026-02-28)**

---

## 🔮 Feature Upgrades

### 1. Tuner Management
- [x] Add ability to **add/remove tuners** from the UI (v2.3.0).  
- [x] Add ability to rename tuners via the UI (v2.3.0).  
- [x] Support for **.m3u8 single-channel playlists** as tuner sources. *(v4.6.0)*
- [x] Validate tuner URLs (ping/check format before saving) (v2.0.0).
- [x] Duplicate tuner name prevention in `add_tuner()`. *(v4.6.0)*  
- [x] Optional auto-refresh of tuner lineup on a schedule. *(v4.3.0)*  
- [x] Add per-user tuner assignment and default tuner preferences. *(v4.7.0)*  
- [x] Introduce combined tuner builder (custom tuner aggregation). *(v4.7.0)*  
- [x] Reworked Tuner Management page: two-column layout, tabbed interface, drag-and-drop channel ordering. *(v4.8.0)*  
- [x] Separate **Virtual Channels** management page split from Tuner Management. *(v4.8.0)*  

---

### 2. Logging & Monitoring
- [ ] Move logs from flat file (`activity.log`) into **SQLite DB** for better querying.  
- [x] Add filtering and pagination in logs view. *(v4.5.0)*  
- [x] Add system health checks (tuner reachability, XMLTV freshness). *(v2.3.1)*  
- [x] Admin log management: clear logs + size indicator (v2.3.1).  
- [x] Post-install HTTP service verification in Pi installer (v3.1.0).  
- [x] Unified "Refresh Guide" scheduler. (v4.2.0)  

---

### 3. Guide & Playback
- [x] Auto-Scroll feature added for the Live Guide (v4.1.0).  
- [x] Improved auto-scroll performance and modular handling (v4.2.0).  
- [x] Auto-Scroll Settings flyout menu with Enable/Disable toggle and Slow/Medium/Fast speed sub-flyout. *(v4.6.0)*  
- [x] Added responsive layout for mobile devices (v4.2.0).  
- [ ] Add search/filter box to guide.  
- [ ] Add ability to set favorites.  
- [ ] Channel Info Banner (lower-third overlay with channel #, logo, current/next, progress bar).  
- [ ] Channel number entry with digit buffer + "Tuning to…" overlay.  
- [ ] Last channel quick return.  
- [ ] Browse mode (navigate without tuning until confirmed).  
- [ ] "What's On Now" dashboard view.  
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
- [x] Per-user Auto-Load Channel — server-side; each user can designate one channel to auto-play on guide load. *(v4.7.0)*  
- [x] Assigned Tuner per User — admins can restrict each user to a specific tuner's channel list. *(v4.7.0)*  
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
- [x] Default Display Size option to reset UI scaling back to initial state. *(v4.8.0)*
- [x] Fire TV / Android TV DPAD remote navigation + TV-mode proportional UI scaling. *(v4.6.0)*
- [x] Video player aspect-ratio-locked resize handle. *(v4.6.0)*
- [x] Fixed time bar style normalized across all themes. *(v4.6.0)*
- [x] Virtual channel fullscreen overlay with background music preservation. *(v4.8.0)*
- [x] Auto-hide virtual channel fullscreen button and in-overlay mute control after inactivity. *(v4.8.0)*
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
- [x] Add auto-play stream on login — per-user Auto-Load Channel now wired server-side. *(v4.7.0)*  
- [x] Default auto-play source selection — users can set a default auto-load channel via Channel Preferences. *(v4.7.0)*  

---

### 8. Virtual Channels
- [x] Virtual Channels framework: channels, EPG entries, API endpoints, and guide integration. *(v4.8.0)*  
- [x] **Weather Virtual Channel** — retro TV broadcast layout at `/weather`; US zip code auto-lookup; background music upload and looped playback. *(v4.8.0)*  
- [x] **News Virtual Channel** — `/news` route with RSS image/summary extraction and constant-speed news ticker. *(v4.8.0)*  
- [x] Multiple RSS feeds support — up to 6 RSS feeds on News Channel with server-driven time-based cycling. *(v4.8.0)*  
- [x] **Traffic Virtual Channel** — OSM Leaflet map with real GPS highway waypoints; Demo Mode rotates major US cities without requiring an API key; optional TomTom API key for live data. *(v4.8.0)*  
- [x] **System Status Virtual Channel** — TV-broadcast layout matching news/weather design. *(v4.8.0)*  
- [x] Per-channel overlay appearance settings (overlay preferences button per virtual channel). *(v4.8.0)*  
- [ ] Casting support for virtual channels.  
- [ ] DVR / recording integration for virtual channels.  

---

### 9. Planned Enhancements
- [x] Add safety checks in add_tuner() (duplicate prevention + URL validation). *(v4.6.0)*  
- [x] GPU verification after `raspi-config` (v3.1.0).  
- [x] Suppress `rfkill` Wi-Fi message during GPU config (v3.1.0).  
- [x] Adaptive HTTP check loop (v3.1.0).  
- [x] Project structure and documentation reorganized (v4.0.0–4.2.0).  
- [x] About/Diagnostics improvements: effective EPG source, loaded channel count, channels with EPG, and total program count. *(v4.7.0)*  

---

## ⚙️ Technical Improvements
- [x] Add uninstall.sh (v2.3.0).  
- [ ] Validate/test uninstall script fully on Windows.  
- [ ] Add HTTPS + optional token-based authentication.  
- [x] Refactor tuner handling for unified DB. (v4.0.0)  
- [x] Updated bump_version and installer scripts for new structure. (v4.3.0)  
- [x] Containerize app (Dockerfile + Compose).  
- [x] Automatic DB schema migration guards — backward-compatible `IF NOT EXISTS` / `ALTER TABLE` guards for `user_preferences`, `users.assigned_tuner`, and `tuners.tuner_type`/`sources` columns. *(v4.7.1)*  
- [x] Open redirect vulnerability in login `?next=` parameter fixed with `is_safe_url()` helper. *(v4.7.1)*  
- [ ] Add migrations for DB schema changes.  
- [ ] CI/CD automation for official builds.  
- [x] Test suite added: virtual channels, weather, audio, and traffic demo tests. *(v4.8.0)*  

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
