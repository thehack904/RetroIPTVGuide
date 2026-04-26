# FAQ

Answers to frequently asked questions about RetroIPTVGuide.

---

## General

### What is RetroIPTVGuide?

RetroIPTVGuide is a self-hosted web application that displays IPTV channel listings
in a retro television guide style, similar to classic cable TV guides from the 1990s
and early 2000s. It aggregates IPTV playlists and XMLTV EPG data and presents them
through a browser-based interface.

### Is RetroIPTVGuide an IPTV server?

No. RetroIPTVGuide is a **guide interface only**. It does not host, transcode, or
distribute any media content. You need a separate IPTV backend (such as ErsatzTV,
Jellyfin, Plex, or a third-party provider) that supplies `.m3u` playlists and
XMLTV EPG data.

### What IPTV backends work with RetroIPTVGuide?

Any backend that provides:

- `.m3u` or `.m3u8` playlist URLs
- XMLTV `.xml` or `.xml.gz` EPG URLs
- **HLS segmented streams** for in-browser playback

ErsatzTV is particularly well-suited because it natively outputs HLS streams.

### Does RetroIPTVGuide work with MPEG-TS streams?

MPEG-TS streams are not directly playable in browsers. You need an IPTV backend
that provides HLS output for in-browser playback.

### Is RetroIPTVGuide safe to expose to the internet?

RetroIPTVGuide is designed for use within trusted networks. Exposing it directly to
the public internet without additional hardening is not recommended. Preferred access
methods are VPN (WireGuard / Tailscale), reverse proxy with authentication, or
restricted LAN access.

See [SECURITY_MODEL.md](../../SECURITY_MODEL.md) for the full security design.

---

## Installation

### What is the recommended installation method?

**Docker** is the recommended and best-supported method. A pre-built image is
available at `ghcr.io/thehack904/retroiptvguide:latest`.

### Can I install from a downloaded release archive without cloning?

Yes. As of v4.9.4 all three native installers (`retroiptv_linux.sh`,
`retroiptv_rpi.sh`, and `retroiptv_windows.ps1`) detect whether they are being run
from a directory that already contains the full release (identified by the presence of
`app.py` and `requirements.txt`). If those files are present the installer uses them
directly and does **not** clone from GitHub.

To use this method:

1. Download the `.zip` or `.tar.gz` from the
   [Releases page](https://github.com/thehack904/RetroIPTVGuide/releases).
2. Extract the archive.
3. Run the installer from inside the extracted directory.

```bash
# Linux / Raspberry Pi example
tar -xzf v4.9.4.tar.gz
cd RetroIPTVGuide-4.9.4
sudo bash retroiptv_linux.sh install --agree
```

If the installer is run as a standalone download (e.g. via `curl | bash`) and the
full release is **not** present alongside the script, it will ask for confirmation
before cloning from GitHub. Pass `--yes` (`-y`) to skip the prompt.

### What happened to the Windows installer?

The Windows installer (`.bat` / `.ps1`) is deprecated and will be discontinued in
**v5.0**. Docker is the recommended deployment method going forward.

### What are the minimum system requirements?

Python 3.10+, at least 512 MB RAM, and approximately 500 MB disk space (plus EPG
cache). An IPTV backend that serves HLS streams is required for in-browser playback.

### How do I reset a forgotten admin password?

Use the bundled reset script:

```bash
python3 /path/to/scripts/reset_admin_password.py --db /path/to/config/users.db
```

The script resets the admin password and flags the account to require a new password
on next login. See [Installation](Installation.md#admin-password-recovery) for
detailed steps.

---

## Configuration

### How do I add my IPTV source?

Navigate to **Tuner Management** → **Add Tuner** and provide a playlist URL and an
XMLTV EPG URL. See [Configuration](Configuration.md#adding-a-tuner) for details.

### Can I add multiple IPTV sources?

Yes. Add multiple tuners and use the **Combined Tuner** option to merge them into a
single guide view.

### Where is the configuration stored?

Configuration is stored in SQLite databases (`users.db`, `tuners.db`) in the data
directory (`/app/config` for Docker deployments). Mount this directory as a volume
to persist data across container updates.

### How do I change the UI theme?

Navigate to **Settings** and choose a theme. Several retro-style themes are
available, including TV Guide and AOL/CompuServe inspired designs.

---

## Virtual Channels

### What are virtual channels?

Virtual channels are synthetic channels built into RetroIPTVGuide that display
dynamic content (weather, news, traffic, etc.) in the guide alongside regular IPTV
channels. See [Virtual Channels](Virtual-Channels.md) for the full list.

### Do virtual channels require external accounts or API keys?

Most virtual channels use free, unauthenticated public APIs. The NASA channel can
optionally use a NASA API key for higher rate limits; without a key it falls back to
the free `DEMO_KEY`.

### Why is my Weather channel showing no data?

Ensure a location is configured in the Weather admin settings. The channel uses the
Open-Meteo API, which requires no API key but does need a valid location.

### What is Channel Mix?

Channel Mix is a composite virtual channel that cycles through a selection of other
virtual channels on a configurable schedule. Configure it under **Virtual Channels →
Channel Mix**.

---

## Playback

### Video won't play in my browser. What should I check?

1. Confirm your IPTV backend is serving **HLS streams** (not MPEG-TS).
2. Check that the stream URL is reachable from your browser.
3. Check the browser console for errors.
4. Try a different browser. HLS playback requires a modern browser.

### Can I pop out the video player?

Yes. Use the pop-out video button in the guide interface to open the player in a
separate resizable window.

---

## Updates

### How do I update RetroIPTVGuide?

- **Docker:** `docker compose pull && docker compose up -d`
- **Linux:** `sudo /home/iptv/iptv-server/retroiptv_linux.sh update --yes`
- **Raspberry Pi:** `sudo /home/iptv/iptv-server/retroiptv_rpi.sh update --yes`

### Where can I find the release history?

See [CHANGELOG.md](../../CHANGELOG.md) for the full release history.

---

## Contributing

### How do I report a bug?

Open an issue on the GitHub repository and include the RetroIPTVGuide version,
installation type, playlist provider, reproduction steps, and logs if available.

### How do I report a security vulnerability?

Report security issues privately via a GitHub Security Advisory:
https://github.com/thehack904/RetroIPTVGuide/security/advisories

Do not open a public issue for security vulnerabilities. See
[SECURITY.md](../../SECURITY.md) for the full policy.

### Can I contribute code?

Yes. Fork the repository, create a feature branch, make your changes, and submit a
pull request. See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.
