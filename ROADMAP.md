# 📌 RetroIPTVGuide — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, partially implemented, or completed in previous releases.

---

# Current Version: **v4.9.9 (2026-07-21)**

---

## 🔮 Feature Upgrades

### 1. Tuner Management
- [x] Add ability to **add/remove tuners** from the UI (v2.3.0).  
- [x] Add ability to rename tuners via the UI (v2.3.0).  
- [x] Support for **.m3u8 single-channel playlists** as tuner sources. *(v4.6.0)*
- [x] Validate tuner URLs *(v2.0.0 → improved v4.9.1–v4.9.2)*
- [x] Duplicate tuner name prevention *(v4.6.0)*  
- [x] Optional auto-refresh of tuner lineup *(v4.3.0)*  
- [x] Per-user tuner assignment and default preferences *(v4.7.0 → enforced across guide APIs in v4.9.8)*  
- [x] Combined tuner builder *(v4.7.0)*  
- [x] Reworked Tuner Management UI *(v4.8.0)*  
- [x] Virtual Channels split from Tuner Management *(v4.8.0)*  
- [x] Manual selected-tuner JSON cache refresh *(v4.9.8)*

---

### 2. Logging & Monitoring
- [x] Move logs from flat file to **SQLite DB** *(v4.9.3)*  
- [x] Filtering and pagination *(v4.5.0)*  
- [x] System health checks *(v2.3.1)*  
- [x] Admin log management *(v2.3.1)*  
- [x] Post-install verification *(v3.1.0)*  
- [x] Unified guide refresh scheduler *(v4.2.0 → playback-aware deferral in v4.9.8)*  
- [x] Sanitized diagnostics and error responses *(v4.9.1–v4.9.2 → improved v4.9.8)*  
- [x] Channel health indicators (lightweight only) *(v4.9.7)*

---

### 3. Guide & Playback
- [x] Auto-Scroll *(v4.1.0 → v4.6.0 enhancements)*  
- [x] Responsive layout *(v4.2.0)*  
- [x] Fullscreen improvements for virtual channels *(v4.9.3)*  
- [x] Channel Mix dynamic fullscreen switching *(v4.9.3)*  
- [x] Search/filter box *(v4.9.6 → channel-number search added v4.9.8)* 
- [x] Favorites (lightweight) *(v4.9.6)*  
- [x] Channel Info Banner *(v4.9.6)*  
- [x] Channel number entry *(v4.9.6)*  
- [x] Last channel return *(v4.9.6)*  
- [x] Browse mode *(v4.9.8)*
- [x] "What's On Now" view *(v4.9.7 → assigned-tuner aware in v4.9.8)*
- [x] EPG caching *(v4.9.8)*
- [x] Missing EPG fallback *(v3.0.1 → stale disk-cache fallback in v4.9.8)*  
- [x] Reminders/notifications *(v4.9.7)*
- [x] Mini Guide layout *(v4.9.7; video-player overlay removed v4.9.8)*

---

### 4. User Management
- [x] User management UI *(v4.0.0)*  
- [x] Basic admin-only access model *(initial v1.x; expanded through v2.0.0, v4.0.0, v4.9.2, v4.9.3, and v4.9.8)* 
- [x] Last login tracking *(v4.5.0)*  
- [x] Auto-Load Channel *(v4.7.0)*  
- [x] Assigned Tuner per User *(v4.7.0 → guide/API enforcement improved v4.9.8)*  
- [x] User role/channel restrictions *(v4.7.0 / v4.9.5)*

---

### 5. UI/UX Improvements
- [x] Unified theming *(v2.3.2)*  
- [x] Android / Fire TV optimization *(v4.0.0)*  
- [x] DPAD navigation improvements *(v4.9.3)*  
- [x] Wake-lock support *(v4.9.2)*  
- [x] Modular UI architecture *(v4.1.0)*  
- [x] Mobile responsiveness *(v4.2.0)*  
- [x] Theme auto-detect *(v4.5.0)*  
- [x] Display size settings *(v4.6.0 → sticky/header scroll fix v4.9.8)*  
- [x] Virtual channel fullscreen enhancements *(v4.8.0–v4.9.3)*  
- [x] Mobile Program Info folding *(v4.9.8)*
- [x] RetroStation MC theme *(v4.9.8)*

---

### 6. Cross-Platform
- [x] Linux / Windows / Raspberry Pi installers *(v4.0.0 → v4.9.8 metadata updates)*  
- [x] Windows parity *(v4.1.0)*  
- [x] Shared `iptv` user uninstall protection for RetroStation MC coexistence *(v4.9.8)* 

---

### 7. New Features
- [x] Favorites system (lightweight) *(v4.9.6)*  
- [x] Smart filtering (simple implementation only) *(v4.9.6)* 

---

### 8. Virtual Channels
- [x] Virtual Channels framework *(v4.8.0)*  
- [x] Weather *(v4.8.0)*  
- [x] News *(v4.8.0)*  
- [x] Traffic *(v4.8.0)*  
- [x] System Status *(v4.8.0)*  
- [x] Updates *(v4.9.3)*  
- [x] Sports *(v4.9.3)*  
- [x] NASA *(v4.9.3)*  
- [x] On This Day *(v4.9.3)*  
- [x] Channel Mix *(v4.9.3)*  
- [x] Expanded Virtual Channels admin UI *(v4.9.3)*  
- [ ] Advanced Virtual Channel Composition Engine  
      - Scheduled rotation blocks  
      - Weighted/random playback  
      - Channel Mix enhancements  

---

## ⚙️ Technical Improvements
- [x] Docker containerization  
- [x] DB schema migration guards *(v4.7.1)*  
- [x] Security hardening *(v4.9.1–v4.9.2 → admin API hardening and sanitized diagnostics in v4.9.8)*  
- [x] Database-backed activity logging *(v4.9.3)*  
- [x] EPG disk cache with safe tuner-name path handling *(v4.9.8)*
- [x] Stale EPG disk-cache fallback when XMLTV reload returns empty data *(v4.9.8)*

---

## 🍓 Installer Enhancements
- [x] Unified installer architecture  
- [x] Windows parity  
- [x] Linux service rename to `retroiptvguide` with owned legacy-service cleanup *(v4.9.8)*
- [x] Preserve shared `iptv` user/home when RetroStation MC or another `iptv` service is detected *(v4.9.8)*
- [ ] **Deprecate Windows installer in v5.0** — Docker is the recommended deployment method going forward *(notice added v4.9.4; pending v5.0)*

---

## User Submitted Enhancements
- [x] Resize Pop Out Video *(v4.6.0)*
- [x] Resize video *(v4.6.0)*
- [x] Auto load Channel from Guide *(v4.8.0)*
- [x] Adjustable scrolling speed *(v4.6.0)*
- [x] Unraid Template
