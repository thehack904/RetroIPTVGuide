# 📌 RetroIPTVGuide — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, partially implemented, or completed in previous releases.

---
# Current Version: **v4.9.4 (2026-04-25)**

---

## 🔮 Feature Upgrades

### 1. Tuner Management
- [x] Add ability to **add/remove tuners** from the UI *(v2.3.0)*  
- [x] Add ability to rename tuners via the UI *(v2.3.0)*  
- [x] Support for **.m3u8 single-channel playlists** as tuner sources *(v4.6.0)*  
- [x] Validate tuner URLs *(v2.0.0 → improved v4.9.1–v4.9.4)*  
- [x] Duplicate tuner name prevention *(v4.6.0)*  
- [x] Optional auto-refresh of tuner lineup *(v4.3.0)*  
- [x] Per-user tuner assignment and default preferences *(v4.7.0)*  
- [x] Combined tuner builder *(v4.7.0)*  
- [x] Reworked Tuner Management UI *(v4.8.0)*  
- [x] Virtual Channels split from Tuner Management *(v4.8.0)*  

---

### 2. Logging & Monitoring
- [x] Move logs from flat file to **SQLite DB** *(v4.9.3)*  
- [x] Filtering and pagination *(v4.5.0)*  
- [x] System health checks *(v2.3.1)*  
- [x] Admin log management *(v2.3.1)*  
- [x] Post-install verification *(v3.1.0)*  
- [x] Unified guide refresh scheduler *(v4.2.0)*  
- [x] Sanitized diagnostics and error responses *(v4.9.1–v4.9.2)*  
- [x] Expanded diagnostics/config reporting *(v4.9.4)*  

---

### 3. Guide & Playback
- [x] Auto-Scroll *(v4.1.0 → v4.6.0 enhancements)*  
- [x] Responsive layout *(v4.2.0)*  
- [x] Fullscreen improvements for virtual channels *(v4.9.3)*  
- [x] Channel Mix dynamic fullscreen switching *(v4.9.3 → improved v4.9.4)*  
- [x] XMLTV program icon support *(v4.9.4)*  
- [x] M3U `group-title` parsing *(v4.9.4)*  
- [x] Theme priority handling (server/admin defaults override stale browser storage) *(v4.9.4)*  
- [ ] Search/filter box  
- [ ] Favorites (lightweight)  
- [ ] Channel Info Banner  
- [ ] Channel number entry  
- [ ] Last channel return  
- [ ] Browse mode  
- [ ] "What's On Now" view  
- [ ] Channel health indicators (lightweight only)  
- [ ] Mini Guide overlay  
- [x] Missing EPG fallback *(v3.0.1)*  
- [ ] Reminders/notifications  
- [ ] EPG caching  

---

### 4. User Management
- [x] User management UI *(v4.0.0)*  
- [-] Basic admin-only access model  
- [x] Last login tracking *(v4.5.0)*  
- [x] Auto-Load Channel *(v4.7.0)*  
- [x] Assigned Tuner per User *(v4.7.0)*  
- [ ] User role/channel restrictions  

---

### 5. UI/UX Improvements
- [x] Unified theming *(v2.3.2)*  
- [x] Android / Fire TV optimization *(v4.0.0)*  
- [x] DPAD navigation improvements *(v4.9.3)*  
- [x] Wake-lock support *(v4.9.2)*  
- [x] Modular UI architecture *(v4.1.0)*  
- [x] Mobile responsiveness *(v4.2.0)*  
- [x] Theme auto-detect *(v4.5.0)*  
- [x] Display size settings *(v4.6.0)*  
- [x] Virtual channel fullscreen enhancements *(v4.8.0–v4.9.4)*  
- [x] New guide themes:
  - Classic Cable Style *(v4.9.4)*
  - Icon / ErsatzTV Style *(v4.9.4)*

---

### 6. Cross-Platform
- [x] Linux / Windows / Raspberry Pi installers *(v4.0.0)*  
- [x] Windows parity *(v4.1.0)*  
- [ ] TrueNAS SCALE App Catalog certification  
- [ ] Windows installer retirement in v5.0 (Docker-first direction)

---

### 7. New Features
- [ ] Favorites system (lightweight)  
- [ ] Smart filtering (simple implementation only)  

---

### 8. Virtual Channels
- [x] Virtual Channels framework *(v4.8.0)*  
- [x] Weather *(v4.8.0 → expanded v4.9.4)*  
- [x] News *(v4.8.0)*  
- [x] Traffic *(v4.8.0)*  
- [x] System Status *(v4.8.0)*  
- [x] Updates *(v4.9.3)*  
- [x] Sports *(v4.9.3 → reworked v4.9.4)*  
- [x] Space Channel *(renamed from NASA in v4.9.4)*  
- [x] On This Day *(v4.9.3)*  
- [x] Channel Mix *(v4.9.3)*  
- [x] Expanded Virtual Channels admin UI *(v4.9.3 → improved v4.9.4)*  
- [x] Virtual channels default disabled for safer deployments *(v4.9.4)*  
- [x] Weather segment rotation:
  - Current Conditions
  - 5-Day Forecast
  - Regional Radar
  - Severe Weather Alerts *(v4.9.4)*
- [x] Configurable weather segment duration *(v4.9.4)*
- [x] Regional radar generation using configured coordinates *(v4.9.4)*
- [x] External sports data opt-in only *(v4.9.4)*
- [x] User-configurable sports scores API base URL *(v4.9.4)*
- [ ] Advanced Virtual Channel Composition Engine  
      - Scheduled rotation blocks  
      - Weighted/random playback  
      - Channel Mix enhancements  

---

## ⚙️ Technical Improvements
- [x] Docker containerization  
- [x] DB schema migration guards *(v4.7.1)*  
- [x] Security hardening *(v4.9.1–v4.9.2)*  
- [x] Database-backed activity logging *(v4.9.3)*  
- [x] CodeQL workflow improvements *(v4.9.4)*  

---

## 🍓 Installer Enhancements
- [x] Unified installer architecture  
- [x] Windows parity  
- [x] Windows deprecation notices added *(v4.9.4)*  
- [ ] **Deprecate Windows installer in v5.0** — Docker is the recommended deployment method going forward

---

## 📚 Documentation
- [x] Added GitHub Wiki-ready documentation structure *(v4.9.4)*
  - Home
  - Installation
  - Configuration
  - Virtual Channels
  - FAQ
  - Troubleshooting
- [x] Updated README links to point users toward the new wiki documentation *(v4.9.4)*
- [x] Updated install documentation around Docker-first deployment direction *(v4.9.4)*

---

## User Submitted Enhancements
- [x] Resize Pop Out Video *(v4.6.0)*
- [x] Resize video *(v4.6.0)*
- [x] Auto load Channel from Guide  
- [x] Adjustable scrolling speed *(v4.6.0)*
- [x] Unraid Template