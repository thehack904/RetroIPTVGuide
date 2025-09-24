# Changelog

## [2.0.0] - 2025-09-23
### Added
- Packaged the **Golden Trunk build** into a clean, versioned release for GitHub.
- Included all application files (Flask app, templates, static assets, configs, etc.) in a consistent scaffold.
- Initial **systemd service file** to manage the IPTV Flask server.
- `install.sh` script now creates a dedicated `iptv` system user and installs into `/home/iptv/iptv-server`.
- Updated install.sh to auto-install python3-venv if missing, ensuring clean setup on Debian/Ubuntu systems.

### Changed
- Project rebranded from *Golden Trunk* (internal name) to **RetroIPTVGuide** (public GitHub name).
- Directory structure aligned with `/home/iptv/iptv-server` for consistency across installs.
- Documentation (`INSTALL.md`, `README.md`) updated to reflect GitHub repo, new username (`thehack904`), and installation instructions.

### Fixed
- Requirements install path corrected so dependencies are properly installed inside the Python virtual environment.
- Removed erroneous `hls.js` entry from `requirements.txt` (now correctly included as client-side JavaScript in `guide.html`).
- Cleaned up GitHub Actions workflow so Python CI doesn’t break on frontend assets.

### Notes
- Default login credentials remain `admin / admin` until first password change.
- ⚠️ **Beta Notice**: This build is marked as a BETA release. Do not expose to the public internet without additional hardening.


## v1.1 (Current Release)
- Added automated installer (`install.sh`) with system user `iptv` and locked directory `/home/iptv/iptv-server`.
- Updated systemd service (`iptv-server.service`) to run under `iptv` user.
- Scaffold zip now includes Golden Build merged with installer and docs.
- Updated `INSTALL.md` with clearer install, access instructions, and beta warning.
- Updated `README.md` for clarity and links.
- Ensured LICENSE (CC BY-NC-SA 4.0) included in repo.
- Version rolled forward to v1.1.

## v1.0 (Initial Beta)
- First public beta release.
- Flask web interface.
- IPTV guide with .m3u + .xml support.
- Systemd integration.
- User management.
