# ARCHITECTURE.md

## RetroIPTVGuide System Architecture

RetroIPTVGuide is a web-based IPTV guide and tuner management platform designed to provide a retro television guide experience for modern IPTV environments.

It aggregates IPTV playlists and EPG metadata and presents them through a browser-based interface optimized for desktops, mobile devices, and television displays.

---

# 1. High-Level Architecture

RetroIPTVGuide follows a server–client architecture.

IPTV Sources (.m3u / .xml)
        |
        v
RetroIPTVGuide Flask Server
        |
        v
Web Browser Interface

The application acts as a middle layer between IPTV providers and the user interface.

---

# 2. Backend Application

The backend is built using Flask.

Primary entry point:
app.py

Responsibilities:
- HTTP request handling
- playlist ingestion
- EPG parsing
- tuner configuration
- virtual channel generation
- admin tools
- UI rendering

---

# 3. Data Inputs

RetroIPTVGuide consumes two main data formats.

Playlists:
- .m3u
- .m3u8

Electronic Program Guide:
- XMLTV (.xml)
- compressed XML (.xml.gz)

---

# 4. Core Modules

Tuner Management
Defines IPTV data sources including playlist URLs and EPG feeds.

Playlist Parser
Extracts channel metadata and stream URLs from playlists.

EPG Processor
Parses XMLTV files and indexes program schedules.

Virtual Channel Engine
Creates synthetic channels (news, weather, traffic, etc).

Playback Layer
Relies on browser-compatible HLS streams.

---

# 5. Frontend Structure

Frontend components live in:

static/
templates/

Technologies used:
- HTML
- CSS
- JavaScript
- Flask Jinja templates

---

# 6. Storage

Typical storage components:

- SQLite database
- cached EPG files
- configuration files

---

# 7. Deployment Options

Supported deployment models:

Linux install:
/opt/retroiptvguide

Docker container

Raspberry Pi installations

---

# 8. Networking

Default web interface:

http://<server>:5000

---

# 9. Security

Current protections:

- admin authentication
- server-side validation
- restricted admin actions

Future improvements include stronger validation and automated security scanning.