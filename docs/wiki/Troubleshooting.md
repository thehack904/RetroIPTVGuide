# Troubleshooting

This page covers common problems and how to fix them.

---

## Installer Asks to Clone from GitHub Unexpectedly

**Symptom:** Running the installer prompts:
> "The full RetroIPTVGuide repository was not detected in the current directory.
> The installer needs to clone it from GitHub…"

**Cause:** The installer checks for `app.py` and `requirements.txt` in the same
directory as the script. If those files are absent it assumes the full release was not
downloaded and offers to clone from GitHub.

**Common causes and fixes:**

| Situation | Fix |
|-----------|-----|
| Ran `curl … \| sudo bash` — full repo was never downloaded | Answer `yes` to let the installer clone, or use `--yes` to skip the prompt |
| Extracted the release ZIP but ran the script from a different directory | `cd` into the extracted directory first, then re-run the script |
| Only the installer script was downloaded, not the full archive | Download the full `.zip` or `.tar.gz` from the [Releases page](https://github.com/thehack904/RetroIPTVGuide/releases) and extract it, then run the script from inside that folder |
| Windows: running from a path other than the extracted folder | Open PowerShell **inside** the extracted folder and run `.\retroiptv_windows.ps1 install` |

---



**Symptom:** `http://<server-ip>:5000` does not load.

**Checks:**

1. Confirm the container or service is running:
   ```bash
   docker compose ps
   # or
   sudo systemctl status retroiptvguide
   ```
2. Confirm port 5000 is not blocked by a firewall:
   ```bash
   sudo ufw status
   ```
3. Confirm you are using the correct IP address of the server, not `localhost` when
   accessing from another device.
4. If running Docker with a custom port mapping, use the mapped host port.

---

## Guide Shows No Channels

**Symptom:** The guide loads but shows no channels or programs.

**Checks:**

1. Confirm at least one tuner is configured under **Tuner Management**.
2. Verify the playlist URL is reachable from the server:
   ```bash
   curl -I "http://your-playlist-url/playlist.m3u"
   ```
3. Verify the XMLTV EPG URL is reachable from the server:
   ```bash
   curl -I "http://your-epg-url/epg.xml"
   ```
4. Trigger a manual refresh from **Tuner Management** and check the application logs
   for errors.

---

## Video Will Not Play

**Symptom:** Clicking a channel shows a black player or an error.

**Checks:**

1. Confirm your IPTV backend provides **HLS segmented streams** (`.m3u8` segment
   manifests), not MPEG-TS. RetroIPTVGuide relies on the browser's native HLS
   support or `hls.js` for playback and cannot play MPEG-TS streams directly.
2. Open the browser developer console (F12) and check the **Console** and
   **Network** tabs for errors.
3. Confirm the stream URL is reachable from the client device (not just the server).
4. Test the stream URL directly in VLC or another player.
5. Try a different browser. Chromium-based browsers (Chrome, Edge) generally have
   the best HLS compatibility.

---

## Admin Password Lost

If the admin password is unknown it can be reset from the command line.

**Linux / Raspberry Pi:**

```bash
sudo -u iptv python3 /home/iptv/iptv-server/scripts/reset_admin_password.py \
  --db /home/iptv/iptv-server/config/users.db
```

**Docker:**

```bash
docker compose exec retroiptvguide \
  python3 /app/scripts/reset_admin_password.py --db /app/config/users.db
```

On success the password is reset and the account is flagged to require a new password
on next login.

### Permission Error on Reset

If the script reports a database write error, run it as the user that owns the
database file:

```bash
ls -la /home/iptv/iptv-server/config/users.db
sudo -u iptv python3 /home/iptv/iptv-server/scripts/reset_admin_password.py \
  --db /home/iptv/iptv-server/config/users.db
```

### Immutable File (Rare)

If the issue persists, check if the file has been made immutable:

```bash
lsattr /home/iptv/iptv-server/config/users.db
```

Remove the immutable flag if present:

```bash
sudo chattr -i /home/iptv/iptv-server/config/users.db
```

---

## Virtual Channel Shows No Data

**Symptom:** A virtual channel loads but displays an error or empty content.

**Checks:**

1. Confirm the channel is enabled under **Virtual Channels**.
2. Confirm the channel has been configured (location for Weather, RSS URLs for News,
   region for Traffic, etc.).
3. Check that the relevant external API is reachable from the server. Many virtual
   channels rely on public internet APIs:

   | Channel | External API |
   |---------|-------------|
   | Weather | `api.open-meteo.com` |
   | News | Configured RSS feed URLs |
   | Traffic | `overpass-api.de` |
   | Sports | User-configured external data source (RSS feeds or JSON scores endpoint) |
   | NASA | `api.nasa.gov` |
   | On This Day | `en.wikipedia.org` |

4. Run **Admin Diagnostics** to check connectivity to each virtual channel data
   source.

---

## Data Not Persisting After Docker Update

**Symptom:** Tuners, settings, or users are lost after updating the container.

**Cause:** The data directory is not mounted as a persistent volume.

**Fix:** Mount `/app/config` as a Docker volume in `docker-compose.yml`:

```yaml
volumes:
  - ./config:/app/config
```

After adding the volume, recreate the container:

```bash
docker compose down && docker compose up -d
```

---

## Database Errors on Startup

**Symptom:** Application logs show SQLite errors or schema migration warnings.

**Checks:**

1. Confirm the data directory is writable by the application user.
2. Check for disk space issues:
   ```bash
   df -h
   ```
3. If the database files are corrupt, stop the application, back up the files, and
   remove them. The application will recreate them on next start (you will need to
   reconfigure tuners and users).

---

## EPG Times Are Incorrect

**Symptom:** Program times in the guide are offset from the correct time.

**Checks:**

1. Confirm the `TZ` environment variable (Docker) or system timezone matches your
   local timezone.
2. Confirm the XMLTV EPG source includes correct timezone offsets in its timestamps.

---

## Running Admin Diagnostics

The built-in Admin Diagnostics page provides a comprehensive health check:

1. Log in as an administrator.
2. Navigate to **Admin → Diagnostics**.
3. Review the status of each check, including virtual channel connectivity, database
   schema, and system health.

Diagnostics check virtual channel external service connectivity, database schema
integrity, user account configuration, and more.

---

## Still Stuck?

Check the application logs for additional error details:

```bash
# Docker
docker compose logs -f

# Linux (systemd)
journalctl -u retroiptvguide -f
```

Open an issue on GitHub with the RetroIPTVGuide version, installation type, relevant
log output, and reproduction steps:
https://github.com/thehack904/RetroIPTVGuide/issues
