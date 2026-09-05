# PROJECT_STRUCTURE.md

This document describes the repository layout for RetroIPTVGuide.

## Root Structure

/app.py
/requirements.txt
/README.md

/static
/templates
/scripts
/docker

---

## Key Directories

static/
Contains frontend assets.

Subdirectories:
- css
- js
- images

templates/
Flask HTML templates rendered by the backend.

scripts/
Installer and maintenance scripts.

docker/
Container configuration and Docker build files.

---

## Backend Entry Point

app.py

This file initializes the Flask application, registers routes, loads configuration, and starts the server.

---

## Configuration Files

Configuration is typically stored in:

- environment variables
- local configuration files
- database tables

### Linux deployment layout (v4.9.9+)

The repository layout above is separate from the standardized Linux runtime layout:

- `/opt/retroiptvguide`
  - application code
  - Python virtual environment
  - installer scripts
- `/etc/retroiptvguide`
  - administrator-managed environment overrides
  - `retroiptvguide.env`
- `/var/lib/retroiptvguide`
  - mutable application state
  - SQLite databases
  - caches and runtime support files
  - application log files

The Linux systemd unit remains `retroiptvguide.service` and runs as the dedicated
`retroiptvguide` service account rather than the legacy shared `iptv` user.

---

## Static Asset Organization

static/css
Application styling

static/js
Client-side functionality

static/images
UI images and channel logos

---

## Template Organization

templates/
Contains Jinja templates used by Flask to render pages such as:

- guide interface
- tuner management
- settings pages
- diagnostics tools