# 📌 RetroIPTVGuide — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, partially implemented, or completed in previous releases.

---
# Current Version: **v4.9.3 (2026-04-08)**

---

## 🔮 Feature Upgrades

### 1. Tuner Management
- [x] Add ability to **add/remove tuners** from the UI (v2.3.0).  
- [x] Add ability to rename tuners via the UI (v2.3.0).  
- [x] Support for **.m3u8 single-channel playlists** as tuner sources. *(v4.6.0)*
- [x] Validate tuner URLs *(v2.0.0 → improved v4.9.1–v4.9.2)*
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

---

### 3. Guide & Playback
- [x] Auto-Scroll *(v4.1.0 → v4.6.0 enhancements)*  
- [x] Responsive layout *(v4.2.0)*  
- [x] Fullscreen improvements for virtual channels *(v4.9.3)*  
- [x] Channel Mix dynamic fullscreen switching *(v4.9.3)*  
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
- [x] Virtual channel fullscreen enhancements *(v4.8.0–v4.9.3)*  

---

### 6. Cross-Platform
- [x] Linux / Windows / Raspberry Pi installers *(v4.0.0)*  
- [x] Windows parity *(v4.1.0)*  
- [ ] TrueNAS SCALE App Catalog certification  

---

### 7. New Features
- [ ] Favorites system (lightweight)  
- [ ] Smart filtering (simple implementation only)  

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
- [x] Security hardening *(v4.9.1–v4.9.2)*  
- [x] Database-backed activity logging *(v4.9.3)*  

---

## 🍓 Installer Enhancements
- [x] Unified installer architecture  
- [x] Windows parity  

---

## User Submitted Enhancements
- [x] Resize Pop Out Video *(v4.6.0)*
- [x] Resize video *(v4.6.0)*
- [ ] Auto load Channel from Guide  
- [x] Adjustable scrolling speed *(v4.6.0)*
- [x] Unraid Template *(BETA)*
