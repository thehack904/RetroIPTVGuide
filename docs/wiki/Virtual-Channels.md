# Virtual Channels

RetroIPTVGuide includes **9 built-in virtual channels** that generate dynamic content
from external data sources and display it as a retro TV broadcast.

Virtual channels appear in the guide alongside regular IPTV channels and support the
same fullscreen playback experience.

---

## Overview

| Channel | ID | Data Source |
|---------|----|-------------|
| [Weather](#weather) | `virtual.weather` | Open-Meteo API |
| [News](#news) | `virtual.news` | RSS feeds |
| [Traffic](#traffic) | `virtual.traffic` | Overpass API |
| [System Status](#system-status) | `virtual.status` | Internal system data |
| [Updates / Announcements](#updates--announcements) | `virtual.updates` | GitHub Releases RSS |
| [Sports](#sports) | `virtual.sports` | ESPN API / Sports RSS |
| [NASA](#nasa) | `virtual.nasa` | NASA APOD API |
| [On This Day](#on-this-day) | `virtual.on_this_day` | Wikipedia REST API |
| [Channel Mix](#channel-mix) | `virtual.channel_mix` | Composite of selected channels |

---

## Weather

Displays current conditions, a 5-day forecast, radar, and active weather alerts.

The channel cycles through four segments on a configurable timer:

| Segment | Content |
|---------|---------|
| 0 — Current | Current conditions at the configured location |
| 1 — Forecast | 5-day forecast |
| 2 — Radar | Radar map |
| 3 — Alerts | Active weather alerts |

**Configuration:**

- Location is set in the Weather admin settings.
- Rotation timer: 30–600 seconds per segment (default 300 s). Configurable via the
  `weather.seconds_per_segment` setting.

**API endpoint:** `GET /api/weather`

---

## News

Displays a live news ticker sourced from RSS feeds.

**Configuration:**

- Add one or more RSS feed URLs in the News admin settings.
- The ticker rotates through headlines automatically.

**API endpoint:** `GET /api/news`

---

## Traffic

Displays a live traffic map overlay using road data from the Overpass API.

**Configuration:**

- Set a geographic region in the Traffic admin settings.
- Road data can be pre-downloaded using `scripts/download_road_data.py`.

**API endpoint:** `GET /api/traffic`

---

## System Status

Displays live system health metrics including CPU, memory, disk usage, and
application diagnostics.

No external data source is required. All data is collected locally.

**API endpoint:** `GET /api/status`

---

## Updates / Announcements

Displays RetroIPTVGuide release notes and announcements sourced from GitHub Releases.

Pre-release and beta items are hidden by default. This can be changed in the
Updates admin settings.

**API endpoint:** `GET /api/updates`

---

## Sports

Displays live sports scores and recent results.

**Data sources:**

- ESPN API (live scores)
- Sports RSS feeds

**Configuration:**

- Select leagues and teams in the Sports admin settings.

**API endpoint:** `GET /api/sports`

---

## NASA

Displays NASA's Astronomy Picture of the Day (APOD) with a description.

**Data source:** NASA APOD API (`https://api.nasa.gov/planetary/apod`)

**Configuration:**

- Optionally provide a NASA API key in the NASA admin settings for higher rate limits.
  The `DEMO_KEY` is used when no key is configured.

**API endpoint:** `GET /api/nasa`

---

## On This Day

Displays historical events, notable births, and notable deaths that occurred on
today's date, sourced from Wikipedia.

**Data source:** Wikipedia REST API  
(`https://en.wikipedia.org/api/rest_v1/feed/onthisday/{type}/{month}/{day}`)

**Configuration:**

- Toggle which sources are shown (events, births, deaths) in the On This Day admin
  settings.
- Custom entries can be added through the admin settings.

**API endpoint:** `GET /api/on_this_day`

---

## Channel Mix

Channel Mix is a **composite virtual channel** that cycles through a selection of
other virtual channels on a wall-clock-aligned schedule.

**Configuration:**

- Choose which channels to include and set a rotation interval in the Channel Mix
  admin settings.
- The channel name is customizable.

Channel Mix is always listed last in the virtual channel order.

**API endpoint:** `GET /api/channel_mix`

---

## Managing Virtual Channels

1. Log in as an administrator.
2. Navigate to **Virtual Channels**.
3. Enable or disable individual channels using the toggle controls.
4. Click the settings icon next to a channel to configure it.

### Icon Packs

An optional icon pack provides styled PNG logos for virtual channels. Enable it
under **Virtual Channels → Icon Pack**. Individual channel logos can also be
replaced with custom uploads.

Logo priority: custom upload > icon pack > default SVG.

---

## Overlays

Each virtual channel uses a JavaScript overlay renderer located in
`static/overlays/`. The overlay is displayed on top of a looping background
video and refreshes its data from the corresponding API endpoint.

For integration notes see
[`docs/virtual-channels/INTEGRATION.md`](../virtual-channels/INTEGRATION.md).
