# Configuration

This page explains how to configure RetroIPTVGuide after installation.

---

## First Login

Open `http://<server-ip>:5000` and sign in with the default admin credentials.
You are required to set a new password before the application can be used.

---

## Adding a Tuner

A **tuner** represents an IPTV source. At least one tuner must be configured before
the guide will display channels.

1. Log in as an administrator.
2. Navigate to **Tuner Management**.
3. Click **Add Tuner**.
4. Provide the following:

| Field | Description |
|-------|-------------|
| Name | A label for the tuner (e.g. `ErsatzTV`) |
| Playlist URL | URL to a `.m3u` or `.m3u8` playlist |
| XMLTV URL | URL to an XMLTV `.xml` or `.xml.gz` EPG file |

5. Click **Save**.

The guide will refresh using the new tuner's data.

### Supported Formats

- Playlists: `.m3u`, `.m3u8`
- EPG: XMLTV `.xml`, compressed `.xml.gz`

### XMLTV URL Requirement

XMLTV URLs must begin with `http://` or `https://`. Local file paths are not
supported through the UI.

---

## Managing Multiple Tuners

Multiple tuners can be configured and combined. Use the **Combined Tuner** option
to merge channels from several sources into a single guide view.

Each user account can be assigned a default tuner under **User Management**.

---

## Settings

The Settings page provides controls for:

| Setting | Description |
|---------|-------------|
| Theme | Choose a retro UI theme |
| Auto-scroll | Enable/disable automatic guide scrolling |
| Scroll speed | Adjust the guide scrolling rate |
| Display size | Adjust UI element sizes for TV/desktop use |
| Time zone | Displayed time zone for the guide |

---

## Environment Variables (Docker)

When running via Docker the following environment variables are available in `.env`:

| Variable | Description | Example |
|----------|-------------|---------|
| `TZ` | Timezone | `America/New_York` |
| `FLASK_ENV` | Flask environment | `production` |
| `SECRET_KEY` | Session secret key | `openssl rand -hex 32` |
| `RETROIPTV_DATA_DIR` | Path for persistent data | `/app/config` |

Generate a secure secret key:

```bash
openssl rand -hex 32
```

---

## Data Directory

By default RetroIPTVGuide stores SQLite databases and cached files in
`/app/config` (Docker) or the install directory (Linux).

The data directory contains:

| File | Description |
|------|-------------|
| `users.db` | User accounts and settings |
| `tuners.db` | Tuner configuration and EPG cache |

Mount these directories as Docker volumes to persist data across container updates:

```yaml
volumes:
  - ./config:/app/config
```

---

## User Management

Admin accounts can manage user accounts from **Admin → User Management**:

- Add and remove users
- Assign default tuners per user
- Force a password change on next login

---

## Auto-Refresh

Tuner playlists and EPG data can be refreshed automatically. Configure the refresh
interval in **Tuner Management** on a per-tuner basis.

---

## Next Steps

- [Virtual Channels](Virtual-Channels.md) — configure built-in virtual channels  
- [Troubleshooting](Troubleshooting.md) — if something isn't working
