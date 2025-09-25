# 📑 Changelog

All notable changes to this project will be documented here.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
This project follows [Semantic Versioning](https://semver.org/).  

---

## [Unreleased]

- Planned: add `.m3u8` tuner support.  
- Planned: move logs to SQLite DB.  
- Planned: add tuner add/remove via UI.  
- Planned: log filtering and pagination.  

---

## [v2.0.0] – 2025-09-24
### Added
- Tuner URL validation: new validate_tuner_url() function checks XML/M3U inputs before saving.
  - Detects invalid/empty URLs, unresolvable hostnames, and distinguishes between public vs. private IPs.
  - Results shown to the user via flash() messages.
- change_tuner.html updated to display flash messages under the header for immediate user feedback.
- Activity logging system (`activity.log`) with:
  - Successful logins, failed logins, and logouts.  
  - Password changes, user creation, and user deletion.  
  - Unauthorized access attempts (non-admin hitting admin routes).  
  - Tuner switched, tuner URLs updated.  
  - Channel playback started (user + channel + timestamp).  
  - Admin access to logs page.  
- New **logs.html** page with proper header, clock, active tuner display, and logs listing.  
- Database migration: tuners moved from in-memory dict to **tuners.db** (persistent).  
  - Added schema for tuners (`name`, `xml`, `m3u`) and settings (`current_tuner`).  
  - Bootstraps default tuners if DB is empty.  
- Updated **change_tuner.html**:  
  - Two sections: switch active tuner, update tuner URLs.  
  - URLs persist into `tuners.db`.  
- Updated **add_user.html**, **delete_user.html**, **change_password.html**, **logs.html** headers:  
  - Unified with `guide.html` header layout.  
  - Active tuner displayed next to clock.  
- Updated **guide.html**:  
  - Menu/header unified across templates.  
  - Playback logging integrated (`/play_channel`).  
- App startup now preloads tuners from `tuners.db` and initializes WAL mode for SQLite performance.  

### Changed
- Removed reliance on hardcoded `TUNERS` dict in `app.py`.  
- Headers across templates are consistent and styled to match `guide.html`.  

### Fixed
- Database locked errors reduced by using `timeout=10` and WAL mode.  
- Unauthorized deletion of `admin` user explicitly blocked and logged.  

---

## [v1.x.x] – 2025-09-01 → 2025-09-23
### Added
- Initial IPTV Flask application with:  
  - User authentication (login/logout, password change).  
  - Basic user management (add/delete).  
  - Guide page rendering from **hardcoded tuners** (`TUNERS` dict).  
  - XMLTV parsing for program guide and M3U parsing for channel list.  
  - Playback via HTML5 video with HLS.js support.  
- Configurable scale and grid sizing for EPG view.  
- Default admin user created on startup.  

### Limitations
- Tuners stored in memory only (changes lost on restart).  
- Logs were minimal (mostly printed to console).  
- UI headers inconsistent across templates.  
- No persistence for tuner updates or user activity logs.  
