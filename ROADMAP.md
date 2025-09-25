# 📌 IPTV Flask Project — Roadmap

This document tracks **planned upgrades** and ideas for improving the IPTV Flask server.  
These are **not yet implemented**, but provide a development path for future releases.

---

## 🔮 Feature Upgrades

### 1. Tuner Management
- [ ] Add ability to **add/remove tuners** from the UI (instead of manually editing DB).  
- [ ] Support for **.m3u8 single-channel playlists** as tuner sources.  
  - Option A: Special-case `.m3u8` handling in parser.  
  - Option B: Add explicit `hls` column to `tuners.db`.  
- [x] Validate tuner URLs (ping/check format before saving).  
- [ ] Optional auto-refresh of tuner lineup on a schedule.

### 2. Logging & Monitoring
- [ ] Move logs from flat file (`activity.log`) into **SQLite DB** for better querying.  
- [ ] Add filtering and pagination in logs view (by user, action, or date).  
- [ ] Add system health checks (e.g., tuner reachability, XMLTV freshness) to logs.  
- [ ] **Admin log management**: add button/route to clear logs (with confirmation).  

### 3. Guide & Playback
- [ ] Add **search/filter box** to guide for channels/programs.  
- [ ] Add ability to set **favorites** for quick channel access.  
- [ ] Add **reminders/notifications** for upcoming programs.  
- [ ] (Future) Support recording/saving streams for offline playback.

### 4. User Management
- [ ] Add role-based access control (admin, regular user, read-only).  
- [ ] Add **email or 2FA support** for login (optional).  
- [ ] Show last login time in admin panel.  

### 5. UI/UX Improvements
- [ ] Unify CSS across all templates (minimize inline styles).  
- [ ] Make guide responsive (mobile/tablet view).  
- [ ] Add dark/light theme auto-detect from browser/system.

### 6. Cross-platform
- [ ] Create installable container.  
- [ ] Create MacOS install/executable.
- [ ] Create Microsoft Windows install/executable.

### 7. New Features
- [ ] Add the ability to have an auto play video stream upon login from a specific channel (Ersatz currently) to act similar to the 90/2000's tv guide that played "Commercials" until a channel was selected.  
---

## ⚙️ Technical Improvements
- [ ] Add uninstall.sh
- [ ] Add https support
- [ ] Refactor tuner handling to rely only on DB (remove in-memory fallback).  
- [ ] Add migrations for DB changes (via Alembic or custom script).  
- [ ] Containerize app (Dockerfile + Compose for deployment).  
- [ ] Add test suite for tuner parsing, authentication, and logging.  
- [ ] **Automated version bump tool** (`bump_version.py`) that updates `APP_VERSION` in `app.py` and creates a new section in `CHANGELOG.md`.  

---

## 📅 Priority Suggestions
- Short term: unify UI headers across templates (in progress).  
- Medium term: tuner add/remove UI + log filtering.  
- Long term: .m3u8 support, DB logs, recording functionality.  
