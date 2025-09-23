# Changelog

## v0.1.1 (BETA) - 2025-09-23
### Added
- Installer now creates and configures dedicated `iptv` system user automatically.
- Ensured installation under `/home/iptv/iptv-server` owned by `iptv`.
- Added `tests/test_placeholder.py` to guarantee passing CI builds until real tests are added.

### Changed
- Updated `iptv-server.service` to run under `iptv` user with correct working directory.
- Cleaned `requirements.txt` by removing invalid dependencies (e.g., hls.js).
- Updated `INSTALL.md` to document new install path and `iptv` user handling.

---

## v0.1.0 (BETA) - Initial Release
- Initial scaffold with Flask IPTV web interface.
- Basic login, guide, and service integration.
- Packaged with systemd service file and install script.
