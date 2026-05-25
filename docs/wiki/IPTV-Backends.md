# IPTV Backends

This page lists IPTV server software that is compatible with RetroIPTVGuide, with
particular focus on backends that provide **HLS segmenter streams** — the delivery
mode required for reliable in-browser playback.

---

## What Is an HLS Segmenter?

An HLS segmenter takes a live video stream (from a TV tuner, IPTV source, or media
library), re-encodes it using FFmpeg or a similar tool, and outputs it as a sequence
of short `.ts` segment files advertised through a `.m3u8` media playlist.

This is the preferred delivery mode for RetroIPTVGuide because:

- Browsers can play `.m3u8` media playlists natively or via `hls.js`.
- The server handles the transcoding; no plugin is needed in the browser.
- Segment-based delivery is resilient to network hiccups.

---

## Compatible Backends

### Tunarr

**Type:** HLS Segmenter (FFmpeg-based) &nbsp;|&nbsp; **Licence:** Open-source (MIT)

[https://github.com/chrisbenincasa/tunarr](https://github.com/chrisbenincasa/tunarr)

Tunarr is the community-maintained successor project most closely inspired by
ErsatzTV. It creates virtual channels from your media library and IPTV sources,
uses FFmpeg to transcode content, and outputs HLS media playlists (`.m3u8`) with
`.ts` segments — the same delivery model as ErsatzTV's `?mode=segmenter` URL.

**Why it works with RetroIPTVGuide:** Tunarr's HLS output matches the stream type
that RetroIPTVGuide's stream detector classifies as `HLS Segmenter`. Tunarr also
exposes `.m3u` playlist and XMLTV EPG endpoints that can be added directly as a
RetroIPTVGuide tuner.

---

### dizqueTV

**Type:** HLS Segmenter (FFmpeg-based) &nbsp;|&nbsp; **Licence:** Open-source (GPL-3.0)

[https://github.com/vexorain/dizqueTV](https://github.com/vexorain/dizqueTV)

dizqueTV is the project that inspired ErsatzTV. It provides virtual channel
scheduling and uses FFmpeg to produce HLS output. While development has slowed,
it remains functional and produces HLS segmenter streams compatible with
RetroIPTVGuide.

---

### Channels DVR

**Type:** HLS Segmenter &nbsp;|&nbsp; **Licence:** Commercial (subscription)

[https://getchannels.com/dvr/](https://getchannels.com/dvr/)

Channels DVR supports OTA tuners, Cable Card, and IPTV sources. It transcodes
streams and serves them as HLS, making it fully compatible with RetroIPTVGuide.
Its IPTV source support accepts M3U playlists, and it exports a standard M3U +
XMLTV feed that can be added as a RetroIPTVGuide tuner.

---

### TVHeadend

**Type:** HLS Segmenter (via FFmpeg streaming profile) &nbsp;|&nbsp; **Licence:** Open-source (GPL-3.0)

[https://tvheadend.org/](https://tvheadend.org/)

TVHeadend is a mature TV streaming server supporting OTA, cable, and IPTV inputs.
Its native output is MPEG-TS; however, configuring an **HLS streaming profile**
(using the built-in FFmpeg transcoding pipeline) enables HLS segment output that
is compatible with RetroIPTVGuide.

**Note:** Streams accessed without an HLS profile will be MPEG-TS and will not
play in a browser. Confirm that your TVHeadend stream URL includes an HLS profile
or that the stream type is verified with the RetroIPTVGuide stream detector.

---

### Jellyfin (Live TV)

**Type:** HLS Segmenter (when transcoding is active) &nbsp;|&nbsp; **Licence:** Open-source (GPL-2.0)

[https://jellyfin.org/](https://jellyfin.org/)

Jellyfin's Live TV feature can ingest IPTV M3U sources and serve them as HLS
streams when transcoding is enabled. The resulting HLS output is compatible with
RetroIPTVGuide. Jellyfin also exposes an XMLTV-compatible EPG that can be used
as the guide data source.

**Note:** Jellyfin requires a TV tuner backend (e.g. TVHeadend) or an IPTV
M3U/XMLTV source configured under **Dashboard → Live TV** to provide channel
data. Direct playback of a source stream (without transcoding) may produce
MPEG-TS output that is not compatible with browser playback.

---

### Plex (Live TV & DVR)

**Type:** HLS Segmenter (when transcoding is active) &nbsp;|&nbsp; **Licence:** Commercial (freemium)

[https://www.plex.tv/](https://www.plex.tv/)

Plex supports Live TV and DVR with OTA tuners and compatible network tuners. When
transcoding is enabled, Plex serves streams as HLS and is compatible with
RetroIPTVGuide via its M3U and XMLTV export capabilities.

---

### Emby (Live TV)

**Type:** HLS Segmenter (when transcoding is active) &nbsp;|&nbsp; **Licence:** Commercial (freemium)

[https://emby.media/](https://emby.media/)

Emby's Live TV implementation is architecturally similar to Jellyfin (they share
a common origin). It supports IPTV sources and can serve streams as HLS when
transcoding is active, making it compatible with RetroIPTVGuide.

---

## Using FFmpeg Directly

For advanced users, FFmpeg can be run as a standalone HLS segmenter without a
dedicated IPTV server application. This is useful for testing or for integrating
a custom stream source.

Example — transcode an RTSP or MPEG-TS source to HLS:

```bash
ffmpeg -i "rtsp://camera/stream" \
  -c:v libx264 -c:a aac \
  -f hls \
  -hls_time 4 \
  -hls_list_size 6 \
  -hls_flags delete_segments \
  /path/to/web/stream.m3u8
```

Serve the `.m3u8` file and `.ts` segments over HTTP (e.g. via `nginx` or Python's
`http.server`) and use the URL as the stream source in a RetroIPTVGuide tuner.

---

## Checking Stream Compatibility

RetroIPTVGuide includes a built-in stream type detector. Before adding a new
backend:

1. Navigate to **Tuner Management → Stream Detect** (or use the URL diagnostics
   tool in the admin area).
2. Paste a channel stream URL from your IPTV backend.
3. The detector will classify the stream as one of:
   - **HLS Segmenter** — fully compatible ✅
   - **HLS Direct** — usually compatible ✅ (playback depends on source codec)
   - **MPEG-TS** — not playable in a browser ❌

If your backend returns MPEG-TS, configure a transcoding/HLS profile in the
backend before adding the stream URL to RetroIPTVGuide.

---

## See Also

- [Configuration](Configuration.md) — how to add a tuner to RetroIPTVGuide
- [Troubleshooting](Troubleshooting.md) — fixing stream playback issues
- [FAQ](FAQ.md) — general questions about backend compatibility
