## Changelog

All notable changes to this project will be documented here. 
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/). 
This project follows [Semantic Versioning](https://semver.org/). 

---

## v4.9.4 - 2026-04-09

### Added
- Added deprecation warning for the Windows installer: the Windows installer (`.bat` / `.ps1`) will be discontinued in **v5.0**. Docker is the recommended deployment going forward.
  - Warning banner is displayed at startup in `retroiptv_windows.bat`.
  - Warning banner is displayed at startup in `retroiptv_windows.ps1`.
  - Deprecation notice added to the Windows Installation section of `INSTALL.md`.
  - Deprecation note added to `ROADMAP.md` under Installer Enhancements.
  - Deprecation notice shown on the **About** page when RetroIPTVGuide is running on Windows.
- Added structured wiki documentation under `docs/wiki/`:
  - `Home.md` — wiki landing page with navigation table
  - `Installation.md` — full installation guide covering Docker, Linux, Raspberry Pi, and Windows
  - `Configuration.md` — tuner setup, settings, environment variables, and data directory
  - `Virtual-Channels.md` — overview of all 9 built-in virtual channels with configuration details
  - `FAQ.md` — frequently asked questions
  - `Troubleshooting.md` — common problems and step-by-step fixes
- Updated `README.md` to link to the new wiki pages.

---

## v4.9.3 - 2026-04-08

### Added
- Added new virtual channels:
  - Updates / Announcements
  - Sports
  - NASA
  - On This Day
  - Channel Mix (composite virtual channel)
- Added supporting assets for new virtual channels including logos, loop videos, overlay scripts, standalone templates, and icon packs.
- Added database-backed activity logging, replacing the previous flat-file `activity.log`.
- Added new diagnostics endpoint support for querying activity logs from the database.
- Added `scripts/reset_admin_password.py` to reset the admin account password from the command line.
- Added support for forcing the admin account to change its password on next login via a new `must_change_password` user flag.
- Added automatic `users` table schema migration support for the new `must_change_password` column.
- Added expanded test coverage for:
  - virtual channel behavior and defaults
  - Channel Mix logic and switching behavior
  - database-backed activity logging
  - forced password change on login
  - admin password reset workflow
- Added forced-change notice styling and UI messaging to the change password page.

### Changed
- Refactored admin diagnostics and logging system to use SQLite-backed activity logs instead of file-based logging.
- Enhanced Virtual Channels management UI to support configuration and status for all channels, including new additions.
- Improved guide fullscreen behavior to support additional virtual channels and dynamic Channel Mix switching.
- Updated overlay rendering and frontend handling for more consistent behavior across all virtual channel types.
- Updated logs UI to display activity entries instead of raw file size.
- Updated login flow so users flagged with `must_change_password` are required to update their password before accessing the app.
- Updated password change flow to clear the forced-reset flag after successful update.
- Updated default admin bootstrap account to require a password change on first login.
- Updated health checks and diagnostics to validate expected `users` table columns including:
  - `last_login`
  - `assigned_tuner`
  - `must_change_password`
- Updated default Updates channel behavior to hide prerelease/beta items by default.
- Updated project documentation (`README.md`, `INSTALL.md`, `SECURITY.md`, `SECURITY_MODEL.md`, `ROADMAP.md`) to reflect current behavior and guidance.

### Fixed
- Fixed fullscreen rendering issues for virtual channels to ensure proper aspect ratio and prevent stretching.
- Fixed guide behavior when switching between virtual channels, including Channel Mix updates.
- Fixed empty/unconfigured states for News and Weather channels to provide clearer user feedback.
- Fixed inconsistencies in activity log handling by standardizing on database-backed storage.
- Fixed admin password reset handling so CLI resets properly require a password change on next login.
- Fixed first-login admin security by preventing continued use of default/bootstrap credentials.
- Fixed change password UX to clearly indicate when a forced password update is required.
- Fixed diagnostics schema validation to properly detect missing expected columns.
- Fixed reset script behavior for partially initialized databases.

### Security
- Reduced exposure of sensitive log data by removing direct file-based activity log access.
- Improved control over diagnostics log access through structured database queries.
- Hardened admin account recovery with a controlled reset flow requiring password change on next login.
- Hardened default admin account handling to enforce credential rotation on first use.
- Expanded schema validation to better detect incomplete or outdated database state.

### Tests
- Added `tests/test_forced_password_change.py`.
- Expanded coverage around admin diagnostics and virtual channel behavior.

---

## v4.9.2 - 2026-03-30


### Added
- Added stricter internal error handling for diagnostics endpoints so dependency-check failures return sanitized error responses instead of raw exception details.
- Added new test coverage for redirect safety and wake-lock behavior:
  - `tests/test_url_redirect_safety.py`
  - `tests/test_wake_lock.py`

### Changed
- Moved `users.db` and `tuners.db` to use the configured data directory instead of fixed local filenames, improving persistence behavior for container and mounted-data deployments.
- Added `RETROIPTV_DATA_DIR=/app/config` to the Docker environment to better support persistent app data in containerized installs.
- Updated tuner creation validation so XMLTV URLs are now required and must be valid `http://` or `https://` URLs.
- Hardened login and post-login redirect handling to only allow safe same-site relative redirect targets.
- Hardened quick tuner switching redirect behavior to ignore unsafe referrers and fall back safely to the guide.
- Restricted the `/_debug/vlcinfo` debug endpoint to authenticated users only.
- Updated diagnostics and health-check utilities to log detailed failures server-side while returning safer, generic browser-facing error messages.
- Refined traffic incident rendering to build DOM content more safely instead of relying on raw HTML string assembly.
- Updated GitHub Actions workflow permissions to use more restrictive `contents: read` settings where appropriate.

### Fixed
- Fixed an open-redirect risk in login flow handling by sanitizing `next` redirect targets.
- Fixed an open-redirect risk in active tuner quick-switch flow by validating and reducing referrer redirects to safe same-origin paths only.
- Fixed diagnostics responses that could expose raw internal exception details to the browser.
- Fixed multiple diagnostics and validation helpers to avoid leaking stack traces, raw exception messages, DNS errors, filesystem errors, and fetch failures directly in UI/API responses.
- Fixed unsafe debug endpoint exposure by requiring authentication for debug information.
- Fixed traffic incident escaping to also handle double quotes more safely in rendered attributes/content.

### Security
- Hardened redirect handling against open-redirect attacks in login and tuner switching flows.
- Hardened admin diagnostics, startup diagnostics, tuner diagnostics, stream detection, health checks, dependency checks, log readers, and related utility modules to reduce sensitive error disclosure.
- Hardened debug endpoint access by requiring authentication for diagnostic information.
- Hardened frontend traffic rendering against unsafe content injection.

### CI
- Tightened GitHub Actions workflow permissions.
- Limited `python-app.yml` push execution to `main`.

---

## v4.9.1 - 2026-03-22

### Added
- Added stricter client-side media URL sanitization in tuner playback logic, blocking unsafe protocols such as `javascript:`, `data:`, and `vbscript:`.
- Added HTML escaping for guide summary and channel-name rendering to prevent unsafe content injection in the TV Guide UI.
- Added path traversal protection for traffic demo road cache file generation.
- Added strict stream URL validation and instance ID validation before invoking stream start/stop subprocesses.
- Added filesystem boundary checks for uploaded audio files and custom logo uploads to prevent writes outside their intended upload directories.
- Added expanded security-focused test coverage for:
  - SSRF address filtering and DNS resolution behavior
  - DNS rebinding protection in stream detection
  - safe partial-fetch behavior using resolved IPs
  - traffic demo cache path traversal protection
  - tuner validation behavior under the new URL validation model
- Added `tests/test_stream_command_injection.py`.

### Changed
- Refined traffic demo tests to validate the exact OpenStreetMap tile host instead of relying on a broad substring match.
- Refined guide channel-name rendering to build DOM elements safely instead of injecting raw HTML.
- Refined tuner validation tests to match the new hostname/IP validation flow instead of the previous HTTP reachability check.

### Fixed
- Removed the previous M3U URL reachability `HEAD` request during tuner creation and replaced it with hostname/IP-based validation, avoiding false negatives from servers that reject or mishandle `HEAD` requests.
- Fixed tuner URL validation to explicitly reject private, reserved, unspecified, and multicast IP targets.
- Fixed mobile navigation link handling to reject additional unsafe URI schemes beyond `javascript:`.
- Fixed potential XSS exposure in guide summary rendering for program titles, descriptions, times, and fallback channel names.
- Fixed potential XSS exposure when rendering channel logos and names in the guide.
- Fixed potential path traversal risk in traffic demo disk cache path construction.
- Fixed potential path traversal risk in uploaded audio file destinations.
- Fixed potential path traversal risk in custom logo uploads by sanitizing `tvg_id`-derived filenames and verifying final destination paths.
- Fixed potential command injection risk in stream start/stop endpoints by enforcing strict allowlists for stream URLs and instance IDs.
- Fixed stream detection SSRF handling by:
  - validating resolved addresses more thoroughly
  - checking hostname DNS results for restricted targets
  - adding DNS rebinding protection at connection time
  - using the resolved IP directly for HTTP fetches while preserving the original `Host` header

### Security
- Hardened tuner URL validation against SSRF by blocking localhost, link-local, private, reserved, unspecified, and multicast targets.
- Hardened stream detection against DNS rebinding and restricted-address access.
- Hardened frontend rendering paths against XSS in guide summary and channel display.
- Hardened media playback URL handling against unsafe protocol injection.
- Hardened file upload and cache path handling against path traversal.
- Hardened subprocess launch inputs for stream management against command injection.

---

## v4.9.0 - 2026-03-15

### Added
- New **Admin Diagnostics** panel with tools for tuner checks, system health, logs, dependency checks, and support bundle generation.
- New Theme: **TV Guide (Classic)**
- **Custom logo uploads** for Virtual Channels with reset-to-default option.
- Traffic virtual channel improvements including cached road data and startup prewarming.
- New documentation: `AI_POLICY.md`, `ARCHITECTURE.md`, `DATA_FLOW.md`, `PROJECT_STRUCTURE.md`, `SECURITY_MODEL.md`, and `SYSTEM_OVERVIEW.md`.

### Changed
- Reworked **Settings / Administration navigation** and added Diagnostics access for admins.
- Improved **traffic demo backend** with disk caching and more reliable road data handling.
- Improved **Virtual Channels UI** for traffic and logo management.
- Added `Pillow` dependency for traffic basemap generation.

### Fixed
- Improved **startup error handling and logging**.
- Fixed persistence and reset behavior for **custom virtual channel logos**.

---

## v4.8.0 - 2026-03-05

### Added
- **Virtual Channels system**
  - Added a new Virtual Channels framework that allows RetroIPTVGuide to create built-in guide channels independent of tuner sources.
  - Virtual channels are merged directly into the guide and include synthetic EPG data so they behave like regular channels.

- **Built-in virtual channels**
  - Added **News Now**
  - Added **Weather Now**
  - Added **System Status**
  - Added **Traffic Now (SIMULATED)**

- **Virtual channel playback**
  - Virtual channels now play inside the existing video player using local looping video assets.
  - Added per-channel loop assets, overlay types, refresh intervals, and virtual-channel metadata.

- **Overlay engine**
  - Added a frontend overlay engine for dynamic virtual channel overlays.
  - Added dedicated overlay renderers for News, Weather, Status, and Traffic.

- **Virtual Channels admin page**
  - Added a dedicated Virtual Channels management page.
  - Added enable/disable controls for each virtual channel.
  - Added persistent virtual channel ordering.
  - Added per-channel settings panels.

- **News channel configuration**
  - Added support for up to 6 configurable RSS/Atom feed URLs.
  - Added standalone News preview page.

- **Weather channel configuration**
  - Added weather configuration for latitude, longitude, location name, and units.
  - Added ZIP code lookup workflow.
  - Added standalone Weather preview page.

- **Traffic channel configuration**
  - Added simulated traffic channel with locally generated traffic/demo data.
  - Added city rotation controls, city enable/disable toggles, weighting, and bulk actions.
  - Added standalone Traffic preview page.

- **Status channel**
  - Added standalone Status preview page and system-status virtual overlay rendering.

- **Background music for virtual channels**
  - Added support for selecting uploaded audio files as virtual-channel background music.

- **Virtual channel fullscreen controls**
  - Added fullscreen and mute controls for virtual channels.

- **Navigation**
  - Added Virtual Channels entry to the admin/header navigation.

- **Tests**
  - Added test coverage for audio handling, virtual channels, weather, and traffic demo functionality.

### Changed
- Updated guide playback logic to support virtual channels alongside normal tuner channels.
- Split administration more cleanly between Tuner Management and Virtual Channels.
- Updated display-size and video-resize handling to support virtual overlay/fullscreen behavior.

### Fixed
- Improved persistence and validation for virtual channel settings, including feed URLs, weather configuration, traffic demo settings, and per-channel audio selection.
- Improved guide behavior when switching between normal tuner channels and virtual channels.

---

## v4.7.1 - 2026-02-28

### Fixed
- **Guide page returning 500/503 after login**
  - `get_tuners()` crashed on existing databases that lacked the new `tuner_type` and `sources` columns. Added safe `ALTER TABLE` migration guards and a schema-fallback query path so the function works on both old and new databases.
  - `get_user_prefs()` crashed when the `user_preferences` table did not yet exist on existing installs. Added automatic table creation in `init_db()` and a safe `sqlite3.OperationalError` fallback in `save_user_prefs()`.
  - Guide route now calls `get_user_prefs()` to pass `user_prefs` and `user_default_theme` to the template; previously these variables were missing, causing a `TemplateRuntimeError`.

- **Manage Users page returning 500**
  - `manage_users` SELECT queried the non-existent `assigned_tuner` column on fresh or pre-4.7 databases. Added `ALTER TABLE users ADD COLUMN assigned_tuner TEXT` migration in `init_db()` so the column is created automatically on startup.
  - Channel lists for users assigned to non-active or combined tuners now load correctly: `manage_users` now calls `load_tuner_data()` (which handles combined tuners) and caches results per tuner to avoid redundant network fetches within a single request.
  - Added `Cache-Control: no-store` response header via `make_response()` to prevent stale admin pages from being served from the browser cache after back-navigation.

- **Combined tuner creation blocked by "M3U URL is required" error**
  - The `Add Tuner` POST handler unconditionally called `add_tuner()` regardless of the selected tuner mode, so creating a combined tuner (which has no M3U/XML URLs) always raised a validation error.
  - Fixed by reading `tuner_mode` from the form and routing to `add_combined_tuner()` when mode is `combined`; standard and single-stream paths are unchanged.

- **Switching to a combined tuner left guide data empty**
  - The `switch_tuner` action previously called `parse_m3u()` and `parse_epg()` directly, which does not work for combined tuners (no M3U/XML URLs).
  - Changed to call `load_tuner_data()`, which merges channels and EPG from all source tuners, so `cached_channels` is correctly populated after a switch.

- **Open redirect vulnerability in login `?next=` parameter**
  - The login route blindly redirected to any value in `?next=` without validation, allowing an attacker to redirect users to an external URL after authentication.
  - Added `is_safe_url()` helper that validates the redirect target is on the same host; invalid targets now return HTTP 400.

- **Missing database schema columns caused crashes on existing installs**
  - `user_preferences` table not created → crash on any route that reads user prefs.
  - `users.assigned_tuner` column absent → crash in `manage_users`.
  - `tuners.tuner_type` and `tuners.sources` columns absent → crash in `get_tuners()`.
  - All three are now created automatically at startup with backward-compatible `IF NOT EXISTS` / `ALTER TABLE … ADD COLUMN` guards.

---

## v4.7.0 - 2026-02-28

### Added
- **Per-user Auto-Load Channel (server-side)**
  - Each user can designate one channel that automatically begins playing when the guide page opens.
  - Playback starts after a short delay once the page has fully loaded.
  - Regular users set this via **Settings → Channel Preferences → Set Auto-Load Channel**.
  - Admins can set or clear Auto-Load Channel for any user from the **Manage Users** page.

- **Assigned Tuner per User**
  - Admins can assign a specific tuner to each user from the Manage Users page.
  - Users only see channels from their assigned tuner.
  - Safeguards prevent invalid auto-load channel references when tuner assignments change.

- **Combined Tuner Mode**
  - New tuner type that merges channels and EPG data from multiple existing tuners.
  - Combined tuners behave like standard tuners for playback and guide rendering.
  - Health indicators adjust appropriately for combined sources.

- **About / Diagnostics Improvements**
  - Displays effective EPG source.
  - Shows loaded channel count, channels with EPG, and total program count.

- **Improved Autoplay Handling**
  - If browser audio autoplay is blocked, playback falls back to muted.
  - An on-screen **Unmute** button is displayed when needed.

### Database Migration
- **New table: `user_preferences`**
  - Schema: `(username TEXT PRIMARY KEY, prefs TEXT NOT NULL DEFAULT '{}')`
  - Automatically created on first startup.
  - Automatically created during upgrade after process restart.
  - Safe fallback handling if table does not yet exist during hot reload.

---

## v4.6.0 - 2026-02-23

### Added
- **Auto-Scroll menu enhancements with flyout submenus**
  - Settings dropdown now contains a nested Auto-Scroll flyout with Enable/Disable toggle and a Scroll Speed sub-flyout (Slow / Medium / Fast).
  - Speed preference persisted to `localStorage` and restored on load; applied to the live `__autoScroll` API when already running.
  - Display Size (Large / Medium / Small) added as a second flyout entry in the same Settings dropdown.
  - All flyout entries use the existing `.submenu` / `.submenu-content` CSS pattern so they are consistent across themes.
- **Tuner validation, duplicate prevention, and single-channel M3U8 support**
  - New `_validate_url()` helper enforces non-empty, `http`/`https` scheme, and valid hostname on all tuner URLs before they are written to the database.
  - `add_tuner()` now checks for an existing tuner with the same name and raises `ValueError` before inserting, preventing silent duplicates.
  - `parse_m3u()` extended to detect single-channel M3U8 files (a bare URL with no `#EXTINF` entries); channel name is auto-derived from the URL filename.
  - New **Single Stream Mode** in Tuner Management UI — a radio-button toggle switches the Add Tuner form between Standard Playlist mode (separate XML + M3U fields) and Single Stream mode (one M3U8 URL field). Server-side `single_stream` branch in `change_tuner` POST handler mirrors this.
  - Unit tests added: `tests/test_tuner_validation.py` (URL validation + M3U parsing) and `tests/test_single_stream_mode.py` (single-stream and duplicate-prevention flows).
- **Flash message display on Tuner Management page**
  - `change_tuner.html` now renders categorised flash messages (`flash-info`, `flash-warning`, `flash-success`, `flash-default`) in a dedicated container below the page header.
  - Each flash message includes a close (×) button for dismissal.
  - Validation results from `validate_tuner_url()` (reachability, DNS resolution, scheme checks) surface immediately as inline flash messages after each tuner operation.
- **Display Size setting (Large / Medium / Small) for all themes**
  - New persistent display size selector accessible from the Settings menu on every theme.
  - Three presets: Large (100%), Medium (80%), Small (67%) — matches the visual result of browser zoom without cross-browser layout quirks.
  - Implemented via `transform: scale` on a top-level `#appZoomRoot` wrapper in `display-size.js`.
  - Setting is persisted to `localStorage` and restored before first paint to prevent flash of unstyled content.
  - Fixed viewport gap at the bottom of the guide that appeared at non-100% zoom levels.
- **Fire TV (Silk) / Android TV — DPAD remote navigation + TV-mode UI scaling** (`tv-remote-nav.js`)
  - New JS module `static/js/tv-remote-nav.js` injected only when a TV user-agent is detected (AFT, Silk, Android TV, GoogleTV, etc.).
  - Up/Down DPAD navigates channels; OK/Enter triggers playback via existing handler.
  - `scrollIntoView` keeps the selected channel visible; `tv-focused` / `tv-focused-row` CSS classes provide a clear 10-foot UI highlight.
  - Proportional TV-mode UI scaling (video, header, channel column, program cells, fixed time bar) applied via injected `body.tv-mode` CSS.
  - Fixed time bar re-measured after `tv-mode` class is applied to avoid layout offset on load.
  - Auto-scroll defaults to slow speed on TV mode; existing user preference is respected.
  - Login page reworked for TV viewports: stacked logo+form layout with proportional scaling.
- **Video player aspect-ratio-locked resize handle** (`video-resize.js`)
  - Resize handle moved outside the video element bounds (`bottom: -20px; left: -20px`) to prevent browser native controls from blocking interaction.
  - Drag vector projected onto the SW–NE diagonal so resizing is always aspect-ratio-locked.
  - Triangle indicator fixed (now points to bottom-left corner) and reduced to a compact 12×12 visual with a 20×20 hit area.
  - Video and channel column can also be resized via drag handles; guide height recomputed on each resize event.

### Changed
- **Fixed time bar normalized across all themes**
  - All themes now share the same cell padding (`6px 10px`) and a consistent `border-bottom` on the fixed time bar, matching the RetroIPTV theme style as the baseline.
  - Theme-specific overrides (RetroIPTV 2px border, tvguide1990 compact padding, mobile `!important` rules) remain unaffected.
- `auto-scroll.js`: removed hardcoded `maxHeight: calc(100vh - 420px)` from `ensureStyles()` — `flex: 1` on `.guide-outer` now handles height at every zoom level.
- `video-resize.js`: `updateGuideHeight()` now clears any stale inline `maxHeight` alongside `height` and `flex` on resize/zoom events.
- `#appZoomRoot` changed to `position: fixed` flex-column to prevent ancestor `overflow: hidden` from clipping pre-scale layout.
- Tuner Management form radio buttons (`tuner_mode_standard`, `tuner_mode_single_stream`) given explicit `id` attributes and matching `for` attributes on their `<label>` elements for full keyboard/screen-reader accessibility.

### Fixed
- Fixed viewport gap at bottom of guide at Medium/Small display sizes.
- Fixed mispositioned fixed time bar on Fire TV load when TV-mode scaling was applied after `DOMContentLoaded`.
- Fixed overlapping logo/form on TV viewport login page.
- SSRF hardening: private-IP block now covers loopback, link-local, and all RFC-1918 ranges; scheme restricted to `http`/`https`; redirects disabled.

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
