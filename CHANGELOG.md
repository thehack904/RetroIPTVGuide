## Changelog

All notable changes to this project will be documented here. 
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). 
This project follows [Semantic Versioning](https://semver.org/). 

---

## v4.6.0 - 2026-02-22

### Fixed
- **Fire TV / Silk Browser – screen saver prevention (wakelock.js)**
  - Fixed a bug where the NoSleep canvas-stream video was paused by the browser
    when the guide page was hidden (e.g. user switched to another Fire TV app)
    but never resumed when the page became visible again, silently disabling
    screen-saver prevention for the rest of the session.
  - Fixed a race condition in the Screen Wake Lock API path where the sentinel's
    `release` event could fire *after* the page-visible `visibilitychange` event,
    leaving the lock unreleased with nothing to re-acquire it.
  - The `visibilitychange` handler now: resumes a paused NoSleep video immediately,
    re-requests the Wake Lock when the sentinel is gone, and pro-actively refreshes
    an existing sentinel to win any release-event race.

---

## v4.5.0 - 2026-02-15

### Added
- **Client-side search and pagination to logs view**
  - Added search bar to filter log entries by keyword
  - Added filter buttons to show all logs, activity logs, or security logs
  - Added pagination controls with customizable page size (10, 25, 50, 100 entries per page)
  - Log entries are now categorized as 'activity' or 'security' types for easy filtering
- **System theme auto-detection**
  - Added "Auto (System)" option to theme menu
  - Automatically detects dark/light mode preference via CSS `prefers-color-scheme`
  - Dynamically switches theme when system preference changes
  - Auto-detects system theme on first visit when no saved preference exists
- **Last login tracking**
  - Added `last_login` column to user database
  - Display last login timestamp in admin user management panel
  - Automatically updates timestamp on successful login
  - Shows "Never" for users who haven't logged in yet

### Changed
- Enhanced logs.html template with interactive filtering and pagination controls
- Improved user experience when viewing large log files
- Updated theme.js with system theme detection and dynamic switching
- Updated manage_users.html to display last login information

### Fixed
- Fixed scrolling issue on About, Logs, Tuner Management, and Manage Users pages
  - Scoped overflow-y rule to guide page only to prevent breaking other pages
- Added database temp files (*.db-shm, *.db-wal) to .gitignore
- Fixed LOG_PATH permission issues in test environments
- Added accessibility improvements (aria-labels) to search inputs
- Added guard against division by zero in pagination logic

---

## v4.4.0 - 2026-02-05

### Added
- (Windows Powershell Install Script) Better validation checks in Windows Powershell install script.  Added Ensure-AppFiles Function (NEW)
- Added *BETA* Unraid .xml for testing

### Changed
- (Windows Powershell Install Script) Enhanced Upgrade-PipAndInstallReqs Function, Ensure-Service Function, Do-Install Function 

### Fixed
- (Windows Powershell Install Script) Fixed update code bug from v.4.3.0, Fixed Syntax Errors, Update-RetroIPTVGuide Function, Ensure-Choco Function - Broken Chocolatey Detection
- Docker - Add persistant directories for:
/app/users.db → symlink to /app/config/users.db
/app/tuners.db → symlink to /app/config/tuners.db

---

## v4.3.0 - 2025-11-14

### Added
- New mobile UI assets including mobile.css, mobile-header.css, mobile-popup.css, and mobile-submenu.css to improve layout and usability on mobile devices.
- New mobile-related JavaScript files including mobile-nav.js, mobile-scroll-fix.js, and mobile-player-adapt.js.
- Added tuner management enhancements through the new tuner-settings.js script.
- New templates added: _header.html, about.html, change_tuner.html, manage_users.html, and logs.html to support expanded UI functionality.

### Changed
- Updated app.py to support the expanded template set, updated tuner handling, and new mobile behavior.
- Updated bump_version.py and bump_version.sh for compatibility with the current file layout and new release processes.
- Updated installation scripts: retroiptv_linux.sh, retroiptv_rpi.sh, retroiptv_windows.bat, and retroiptv_windows.ps1 to align with the new release structure.

---

## v4.2.1 - 2025-11-10

### Added
- Added horizontal scroll/refresh as time moves forward
- Added API dynamic guide timing refresh

---


## v4.2.0 - 2025-11-06
This version introduces mobile responsiveness, a new theme, refinements to auto-scroll, and backend API structures.

### Added
- Added mobile-friendly CSS and JS for improved viewing on mobile devices
- Added RetroIPTV Theme
- Added backend API structures for future updates / efforts

### Changed
- Enhanced auto-scroll handling with new modular files: `auto-scroll.js` and `auto-scroll-manager.js`.
- Improved responsive layout for guide and settings pages on small screens.

### Fixed
- Fixed font scaling and layout issues in mobile and embedded browsers.
- Fixed path references for Flask static files and templates.
- Resolved layout inconsistencies across themes and display sizes.
- General code cleanup and alignment for CI/CD consistency.

---

## v4.1.0 - 2025-10-25
### New Features
- **Auto-Scroll Guide System**
  - Added `static/js/auto-scroll.js` enabling smooth, continuous automatic scrolling of the live TV guide.
  - Uses `requestAnimationFrame` with a `setInterval` watchdog fallback for consistent performance.
  - Deterministic wraparound ensures seamless looping without scroll jitter.
  - Waits up to 5 seconds for guide data to populate before activating.
  - Stores preference in localStorage (`autoScrollEnabled`) and exposes simple APIs (`cloneNow`, `status`).
  
- **Per-Page Modular CSS**
  - Introduced separate per-page stylesheets: `about.css`, `change_password.css`, `change_tuner.css`, `logs.css`, and `manage_users.css`.
  - Shared global styling moved to `base.css` for consistency.

- **Unified Template Structure**
  - New `base.html` and `_header.html` templates consolidate common layout and navigation.
  - All major pages now extend from `base.html` for easier maintenance.

- **New JavaScript Modules**
  - Added `tuner-settings.js` for handling tuner selection and dynamic UI updates.

### Improvements
- Updated `INSTALL.md`, `README.md`, and `ROADMAP.md` to document the new layout and structure.
- `app.py` updated to serve new static assets and integrate template inheritance.
- All installer scripts (`retroiptv_linux.sh`, `retroiptv_rpi.sh`, `retroiptv_windows.ps1`) updated for v4.1.0 compatibility and new folder paths.

### Fixes
- Reduced redundancy across templates by introducing a unified base layout.
- Improved guide performance and browser compatibility with the new auto-scroll implementation.
- Minor visual and layout corrections across settings and guide pages.

---

## v4.0.0 — 2025-10-19
**Status:** Public Release (Feature Complete)

### Major Changes
- Introduced unified cross-platform installers:
  - `retroiptv_linux.sh` replaces all legacy shell installers
  - `retroiptv_windows.ps1` adds native PowerShell support
  - `retroiptv_rpi.sh` updated for Ubuntu 24.04.2 ARM builds
- Added Android/Fire/Google TV mode with glowing CRT-style header and TV-optimized layout
- Added `manage_users.html` for integrated user creation, management, and deletion
- Updated `app.py` for unified configuration handling, improved session persistence, and tuner logic cleanup
- Modernized UI templates: `guide.html`, `login.html`, `about.html`, `logs.html`, `change_password.html`, and `change_tuner.html`
- Refreshed `CHANGELOG.md`, `README.md`, and `ROADMAP.md` to match unified architecture

### Removed / Consolidated
- Removed legacy install/uninstall scripts (`install.*`, `uninstall.*`, `iptv-server.service`)
- Consolidated multiple user templates (`add_user.html`, `new_user.html`, etc.) into `manage_users.html`

### Known Limitations
- HTTPS mode remains experimental (local/internal network use recommended)
- Android TV session persistence under further testing
- Performance optimization ongoing for large EPG datasets

### Upcoming Development
- Optional HTTPS + token authentication
- Per-user tuner assignment system
- PlutoTV / custom tuner aggregation features
- Enhanced guide refresh logic for long-running sessions

---

## v3.3.0 - 2025-10-15
### Added

- Introduced **Comcast Theme** — a faithful recreation of the mid-2000s Comcast digital cable guide.  
  - Authentic deep-blue gradient backgrounds and bright blue grid tones.  
  - White-on-blue typography and yellow “Now Playing” program highlight.  
  - Red “TV Guide” badge in the top-right corner for a nostalgic touch.  
  - Refined dropdown and submenu styling to match the original Comcast on-screen menu look.

- Updated **DirecTV Theme** — redesigned for accuracy based on live reference captures.  
  - Corrected deep-blue gradient palette (`#001a66 → #003a8c`) with crisp white text.  
  - Reworked highlight color for active program tiles (`#ffd802`).  
  - Adjusted gradients and contrast in the header, info panel, and time bar for better readability.  
  - Clean white-and-blue hover effects with authentic DirecTV brightness and contrast levels.  
  - Added matching **red “TV Guide” badge** for uniform branding with Comcast.

---

## [v3.2.0] - 2025-10-11
### Added
- **Containerization & TrueNAS Deployment Support**
  - Added official Dockerfile and `docker-compose.yml` for cross‑platform container deployments.
  - Added **TrueNAS SCALE App chart** with persistent volume mapping (`/config`, `/logs`, `/data`).
  - Added GitHub Actions workflow for automatic GHCR image builds.
  - Docker image published at:  
    `ghcr.io/thehack904/retroiptvguide:latest`
- Integrated automatic build‑and‑push pipeline using GitHub Actions and GHCR_PAT authentication.
- Added healthcheck and restart policies in Docker configuration.

### Changed
- Documentation updated for container installation (Docker/TrueNAS) as the new primary method.
- Legacy Python and system installers moved to “manual install” section.

### Fixed
- Corrected GHCR tag formatting for TrueNAS (eliminated `:latest:latest` errors).
- Fixed workflow permissions with explicit `packages: write` and PAT authentication.

---

## v3.1.0 - 2025-10-09
### Added
- New **RetroIPTVGuide Raspberry Pi headless installer** (`retroiptv_rpi.sh`)  
  - Detects Raspberry Pi 3 / 4 / 5 models and auto-configures GPU memory  
  - Creates dedicated `iptv` user and installs to `/home/iptv/iptv-server`  
  - Logs all activity to `/var/log/retroiptvguide/install-YYYYMMDD-HHMMSS.log`  
  - Adds `--yes` and `--agree` flags for fully unattended installs  
  - Includes automatic environment checks for SD card size, RAM, and swap  

### Changed
- **Installer alignment:**  
  - Raspberry Pi installer now mirrors Debian / Windows structure  
  - Replaced all `apt` usage with `apt-get` for stable scripting  
  - Added verified, silenced `set_gpu_mem()` function that suppresses `rfkill` Wi-Fi warnings  
  - Enhanced post-install verification loop (up to 15 s) to confirm Flask web service readiness  
- **bump_version.py:** now updates both `install.sh` and `retroiptv_rpi.sh` versions automatically  
- Unified version tagging across all installers (`VERSION="x.y.z"` format)

### Fixed
- Eliminated false-positive Wi-Fi “blocked by rfkill” messages during GPU configuration  
- Corrected early-trigger HTTP service check timing on slower Pi 3/4 boards  
- Ensured consistent permissions and ownership under `/home/iptv`

---

## [v3.0.1] - 2025-10-07
### Added
- **EPG Fallback System**  
  - Channels without XMLTV data now display “No Guide Data Available”.  
  - Added `apply_epg_fallback()` helper to ensure all channels have at least one program entry.  
  - Fallback automatically applied after login and tuner switch.
- **Invalid XML Detection**  
  - If a user enters the same `.m3u` URL for both M3U and XML, the system treats it as invalid XML and loads fallback placeholders instead.
- **Visual Placeholders**  
  - `guide.html` updated to render gray, italicized “No Guide Data Available” banners in program grid.  
  - Works across all existing Light/Dark/Retro themes.

### Changed
- **Tuner Switching Behavior**  
  - Active tuner now refreshes immediately without requiring logout/relogin.  
  - Cached channel/EPG data reloaded dynamically when tuner changes.
- **Login Page UI**  
  - Redesigned with floating centered box, shadow, and right-aligned RetroIPTVGuide logo.

### Fixed
- **EPG Cache Sync**  
  - Prevented guide from displaying outdated EPG after tuner change.  
  - Corrected case where missing XML data produced empty grid.

---

## [3.0.0] - 2025-10-03
### Added
- **Windows Support**:
  - New `install_windows.ps1` and `install.bat` for automated setup.
  - New `uninstall_windows.ps1` and `uninstall.bat` for clean removal.
  - NSSM service created to run `venv\Scripts\python.exe app.py` automatically.
  - Windows installer bootstraps Chocolatey, installs `python`, `git`, and `nssm`.
  - Windows uninstaller removes the service, deletes firewall rule for port 5000, and lists remaining Chocolatey packages (with option to remove all).
- **Cross-platform Installer Enhancements**:
  - `install.sh` improved to detect Linux, WSL, or Git Bash environments.
  - Added pip upgrade check instead of always forcing upgrade.
  - Unified handling of venv paths for Linux (`bin/`) and Windows (`Scripts/`).
- **bump_version.py**:
  - Now also updates `install_windows.ps1`, `uninstall_windows.ps1`, and `uninstall.sh`.
  - Automatically inserts `APP_VERSION`/`VERSION` if missing.

### Changed
- **Documentation**:
  - Updated `README.md` with Windows one-liner install.
  - Updated `INSTALL.md` with new Windows instructions and update steps.
- **Uninstall Scripts**:
  - Windows uninstall output cleaned to avoid duplicate Chocolatey lists.
  - Linux/WSL uninstall script improved to fully remove `iptv-server` systemd service and venv.

### Fixed
- Consistent logging of user agreement and installer actions.
- Ensured firewall rule removal on Windows during uninstall.

---

## [2.3.2] - 2025-09-26
### Added
- Introduced unified **Themes submenu** (Light, Dark, AOL/CompuServe, TV Guide Magazine) across all admin and user pages.

### Changed
- Replaced old `toggleTheme()` logic with a centralized `setTheme(theme)` function.
- Applied consistent **Retro AOL** and **Retro TV Guide Magazine** CSS rules to all major templates:
  - `about.html`
  - `add_user.html`
  - `delete_user.html`
  - `change_tuner.html`
  - `logs.html`
  - `change_password.html`

### Fixed
- Theme persistence issues: selected theme now applies instantly and consistently on every page.
- AOL and Magazine themes now update **immediately** on About and other pages (previously only visible after navigating away).

---

## v2.3.1 - 2025-09-26

### Added
- **About Page**:
  - New `/about` route under Settings.
  - Shows dynamic system info: version, release date, Python version, OS, install path, database path, logs path, uptime.
- **Admin Log Management**:
  - Log file size shown on Logs page (human-readable + color-coded).
  - Admin-only â€śClear Logsâ€ť button added to truncate activity log.
- **Automated Version Bump Tool**:
  - Added `bump_version.py` to sync `APP_VERSION` in app.py with CHANGELOG.md.
  - Inserts new version section under `[Unreleased]`.
  - Optional `--commit` flag to auto-commit changes.
  
### Notes
- These features are improvements for admin usability.

---

## v2.3.0 - 2025-09-26
#### Added
- **Installer Enhancements**:
  - Added logging with timestamped log files (`install_YYYY-MM-DD_HH-MM-SS.log`).
  - Added environment detection (`Linux`, `WSL`, `Windows Git Bash`) with tailored install steps.
  - Unified `install.sh` into one cross-platform script.
- **Uninstaller**:
  - Added `uninstall.sh` with environment detection and privilege checks.
  - Linux/WSL: removes service, logs, `iptv` user, and venv.
  - Windows (Git Bash): stops Flask if running, deletes venv, reminds user to manually delete project folder.
- **About Page**:
  - New `/about` route under Settings menu.
  - Displays dynamic system info: version, release date, Python version, OS, install path, database path, log path, and uptime.
  - Data is pulled from `app.py` constants and runtime environment, no manual edits required.

#### Notes
- **Windows validation pending**: Installer and uninstaller are implemented but require verification on Windows; tracked in ROADMAP â€śPriority Suggestionsâ€ť.

---

### 2025-09-25
#### Added
- **Tuner Management via UI**:
  - Added ability to add new tuners (name, XML URL, M3U URL) from `change_tuner.html`.
  - Added ability to rename tuners directly from the UI.
  - Added ability to delete tuners from the UI (with safety check preventing deletion of the active tuner).
- Extended `/change_tuner` route to support new tuner actions (`add_tuner`, `rename_tuner`, `delete_tuner`).
- Created `add_tuner()` helper to insert tuners into the database.

#### Fixed
- Corrected tuner variable scoping in `/change_tuner` route to avoid `UnboundLocalError`.
- Fixed alignment of tuner forms with consistent dropdowns and validation.
- Ensured flash messages and logging work consistently across all tuner operations.

---

## [v2.0.0] 2025-09-24
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

## [v1.x.x] 2025-09-01 - 2025-09-23
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
