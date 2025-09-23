# Changelog

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
