# Changelog

All notable changes to **RetroIPTVGuide** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.0] - Initial BETA Release

### Added
- Initial scaffold for **RetroIPTVGuide** project.
- CC BY-NC-SA 4.0 license (non-commercial, share-alike).
- `.gitignore` tuned for Python + IPTV-specific artifacts.
- `README.md` with:
  - Project description and GitHub topics.
  - Build status and license badges.
  - ⚠️ BETA warning banner at the top.
- `INSTALL.md` with:
  - Prerequisites and installation steps.
  - Access instructions (URL + default credentials: admin/admin).
  - Updating instructions with `git pull` and systemd restart.
  - Security warning about BETA and LAN-only use.
  - License section at bottom.
- `install.sh` installer script with:
  - Virtual environment setup and dependency installation.
  - Systemd unit installation for auto-start.
  - Final echo output showing access URL, default credentials, and security warnings.
- `iptv-server.service` systemd unit for managing the Flask app.
- `.github/workflows/python-app.yml` GitHub Actions workflow with:
  - Python setup (3.11).
  - Dependency installation.
  - Flake8 linting.
  - Pytest execution (optional if tests exist).
  - Syntax verification of `app.py`.

### Notes
- This is the **initial BETA release**.
- For **LAN / personal use only**. Do not expose directly to the Internet.
- Future releases will add security hardening and additional features.
