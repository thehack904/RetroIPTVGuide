# DATA_FLOW.md

This document explains how data moves through RetroIPTVGuide.

---

# 1. Playlist Ingestion

The system retrieves playlist data from configured tuners.

Input formats:
- .m3u
- .m3u8

The playlist parser extracts:

- channel name
- stream URL
- group name
- channel ID

---

# 2. EPG Processing

The EPG processor loads XMLTV files.

Information extracted:

- program titles
- descriptions
- start/end times
- channel mappings

The processor indexes this data for quick lookups.

---

# 3. Channel Mapping

Channels from playlists are matched to EPG entries using channel identifiers.

Mapping fields may include:

- tvg-id
- channel name
- custom mappings

---

# 4. Guide Generation

The guide UI queries indexed program data.

The server builds a timeline grid including:

- channel list
- program blocks
- program descriptions

---

# 5. Playback

When a user selects a program:

1. Browser loads the stream URL.
2. HLS segments are requested directly.
3. Video plays inside the web player.

No transcoding is performed by RetroIPTVGuide.

---

# 6. Virtual Channel Generation

Virtual channels pull data from APIs or datasets and generate schedule blocks dynamically.

Examples:
- news
- weather
- traffic
- historical events