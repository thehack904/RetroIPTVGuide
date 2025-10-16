## Changelog

All notable changes to this project will be documented here. 
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). 
This project follows [Semantic Versioning](https://semver.org/). 

---

## [Unreleased]

- Planned: add `.m3u8` tuner support. 
- Planned: move logs to SQLite DB. 
- Planned: log filtering and pagination. 

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

## v3.2.0 - 2025-10-11
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

## [v1.x.x] â€“ 2025-09-01 â†’ 2025-09-23
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
