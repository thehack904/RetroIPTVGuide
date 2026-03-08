"""Stream type detection utility for the RetroIPTVGuide Admin Diagnostics subsystem.

``detect_stream_type(url)`` performs a lightweight server-side probe of a stream
URL and classifies it as one of the known stream types:

  * **HLS Direct**        – M3U8 master playlist (``#EXT-X-STREAM-INF`` / no
                             ``#EXT-X-MEDIA-SEQUENCE``).  The client plays the
                             best-matching variant — good for on-demand or
                             multi-bitrate live.
  * **HLS Segmenter**     – M3U8 live media playlist (``#EXT-X-MEDIA-SEQUENCE``
                             present).  The server assembles TS segments in real
                             time; suitable for live IPTV.
  * **MPEG-TS**           – Raw MPEG-2 Transport Stream (0x47 sync byte,
                             confirmed by Content-Type or binary inspection).
  * **MPEG-TS over HTTP** – Same as MPEG-TS but served over plain HTTP without
                             M3U8 wrapping.
  * **DASH**              – MPEG-DASH manifest (.mpd / Content-Type
                             ``application/dash+xml``).
  * **MP4 / fMP4**        – Progressive download or fragmented MP4.
  * **RTMP**              – Real-Time Messaging Protocol (``rtmp://`` / ``rtmps://``).
  * **M3U Channel List**  – IPTV multi-channel playlist (``#EXTINF`` lines with
                             tvg-id / group-title attributes, no HLS ``#EXT-X-*``
                             tags).  The result includes a ``channels`` list so the
                             caller can present a per-channel stream test UI.
  * **Unknown**           – Could not determine; raw details are included.

Only the first ~256 KB of the stream body is fetched, so the probe is fast
even for large streams.  The larger window also allows more channels to be
parsed from M3U playlists for the channel dropdown feature.
"""

from __future__ import annotations

import re
import socket
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum bytes to read from the stream body for content-based detection.
#: 256 KB is enough to detect stream type and parse ~1 000+ M3U channel entries.
_PROBE_BYTES = 256 * 1024

#: HTTP request timeout (seconds).  Keep short — this is a UI-triggered probe.
_TIMEOUT = 20

#: User-Agent header sent with all probe requests.
_UA = "RetroIPTVGuide-StreamProbe/1.0"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Compatibility mapping: stream types that are known to work (True) or not
# work (False) with RetroIPTVGuide's HLS.js-based player.  Types not listed
# here return None (unknown / neutral) from detect_stream_type().
_COMPATIBLE_TYPES: Dict[str, bool] = {
    "HLS Direct":    True,
    "HLS Segmenter": True,
    "MPEG-TS":          False,
    "MPEG-TS (likely)": False,
    "MPEG-TS segment":  False,
    "DASH":  False,
    "RTMP":  False,
}

def detect_stream_type(url: str) -> Dict[str, Any]:
    """Probe *url* and return a stream-type detection result.

    Returns a dict with the following keys:

    ``stream_type``
        String identifier — one of the types listed in the module docstring,
        or ``"Unknown"`` if detection failed.

    ``confidence``
        ``"high"`` / ``"medium"`` / ``"low"`` / ``"none"`` — how confident the
        classifier is in the result.

    ``description``
        Human-readable description of the stream type and what it means for
        the player.

    ``tips``
        List of actionable hints (may be empty).

    ``channels``
        Present only when ``stream_type == "M3U Channel List"``.  A list of
        dicts, each with keys ``name``, ``url``, ``group``, ``tvg_id``.
        Capped at 300 entries.

    ``channel_count``
        Total number of channels parsed from the M3U (present alongside
        ``channels``).

    ``fetch``
        Sub-dict with HTTP metadata: ``status_code``, ``content_type``,
        ``content_length``, ``response_time_ms``, ``error``.

    ``dns``
        Sub-dict: ``hostname``, ``resolved_ip``, ``error``.

    ``signals``
        List of detection signal strings that led to the classification
        (useful for debugging).

    ``url``
        The URL that was probed.
    """
    url = (url or "").strip()

    result: Dict[str, Any] = {
        "url": url,
        "stream_type": "Unknown",
        "confidence": "none",
        "description": "Could not determine the stream type.",
        "compatible": None,   # True = works in RetroIPTVGuide, False = needs proxy/unsupported, None = unknown
        "tips": [],
        "fetch": None,
        "dns": None,
        "signals": [],
    }

    if not url:
        result["fetch"] = {"error": "No URL provided", "ok": False}
        result["tips"].append("Enter a stream URL to probe.")
        return result

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()

    # ── RTMP — no HTTP fetch needed ───────────────────────────────────────
    if scheme in ("rtmp", "rtmps", "rtmpe", "rtmpt", "rtmpte"):
        result["stream_type"] = "RTMP"
        result["confidence"] = "high"
        result["compatible"] = False
        result["description"] = (
            "RTMP (Real-Time Messaging Protocol) stream.  "
            "Most web browsers cannot play RTMP directly.  "
            "RetroIPTVGuide uses HLS.js which does not support RTMP."
        )
        result["signals"].append(f"URL scheme is '{scheme}'")
        result["tips"] = [
            "Use an RTMP-to-HLS proxy (e.g. nginx-rtmp, OBS Studio HLS output) "
            "to produce an HLS stream that browsers can play.",
            "Alternatively, use a tuner or middleware that converts RTMP to HLS.",
        ]
        result["dns"] = _check_dns(url)
        return result

    if scheme not in ("http", "https"):
        result["stream_type"] = "Unknown"
        result["confidence"] = "none"
        result["description"] = f"Unsupported URL scheme: {scheme!r}."
        result["tips"].append("Only http://, https://, rtmp://, and rtmps:// URLs are supported.")
        return result

    # ── Guard against SSRF to loopback / link-local addresses ─────────────
    # This is an admin-only tool so the SSRF risk is intentionally limited, but
    # we still block obvious local addresses as defense-in-depth.
    # Legitimate IPTV stream URLs are always external (non-loopback) hosts.
    _ssrf_err = _check_ssrf_risk(parsed)
    if _ssrf_err:
        result["stream_type"] = "Unknown"
        result["confidence"] = "none"
        result["description"] = _ssrf_err
        result["tips"].append(
            "Stream URLs must point to external hosts — probing loopback or "
            "link-local addresses is not permitted."
        )
        return result

    # ── DNS check ─────────────────────────────────────────────────────────
    result["dns"] = _check_dns(url)

    # ── HTTP probe ────────────────────────────────────────────────────────
    fetch = _fetch_partial(url)
    result["fetch"] = fetch

    if not fetch["ok"]:
        result["confidence"] = "none"
        result["description"] = f"HTTP probe failed: {fetch.get('error', 'unknown error')}."
        result["tips"].append("Verify the URL is reachable from the server, not just from your browser.")
        if result["dns"]["error"]:
            result["tips"].append(
                f"DNS resolution failed for '{result['dns']['hostname']}': {result['dns']['error']}"
            )
        return result

    # ── Classification ────────────────────────────────────────────────────
    ct = (fetch.get("content_type") or "").lower().split(";")[0].strip()
    raw = fetch.get("raw_bytes", b"")
    url_lower = url.lower().split("?")[0]  # path without query string
    signals: List[str] = []

    stream_type, confidence, description, tips = _classify(
        url_lower, ct, raw, signals
    )

    result["stream_type"] = stream_type
    result["confidence"] = confidence
    result["description"] = description
    result["tips"] = tips
    result["signals"] = signals

    # Derive compatibility with RetroIPTVGuide (HLS.js-based player).
    # True  → works out of the box
    # False → requires proxy / unsupported (shows warning-colour tips in the UI)
    # None  → unknown / neutral (e.g. channel list, undetermined)
    result["compatible"] = _COMPATIBLE_TYPES.get(stream_type, None)

    # ── M3U channel list: attach parsed channel data for the dropdown UI ──
    if stream_type == "M3U Channel List":
        try:
            text = raw.decode("utf-8", errors="ignore")
        except (UnicodeDecodeError, LookupError):
            text = ""
        channels = _parse_m3u_channels(text)
        result["channels"] = channels
        result["channel_count"] = len(channels)

    # Remove raw_bytes — not JSON-serialisable, not needed in response
    fetch.pop("raw_bytes", None)

    return result


# ---------------------------------------------------------------------------
# Internal — classification
# ---------------------------------------------------------------------------

def _classify(
    url_lower: str,
    ct: str,
    raw: bytes,
    signals: List[str],
) -> tuple:
    """Return (stream_type, confidence, description, tips)."""

    # ── Try text decode for playlist analysis ─────────────────────────────
    text = ""
    try:
        text = raw[:_PROBE_BYTES].decode("utf-8", errors="ignore")
    except (UnicodeDecodeError, LookupError):
        pass

    # ── Signal collection ─────────────────────────────────────────────────

    # Content-Type signals
    if "mpegurl" in ct or "x-mpegurl" in ct or "vnd.apple.mpegurl" in ct:
        signals.append(f"Content-Type indicates HLS playlist: {ct!r}")
    if "mp2t" in ct or "mpeg2-ts" in ct or "mpeg-ts" in ct or ct == "video/mp2t":
        signals.append(f"Content-Type indicates MPEG-TS: {ct!r}")
    if "dash+xml" in ct or "mpd" in ct:
        signals.append(f"Content-Type indicates MPEG-DASH: {ct!r}")
    if ct in ("video/mp4", "video/x-m4v", "audio/mp4"):
        signals.append(f"Content-Type indicates MP4: {ct!r}")
    if "flv" in ct or "x-flv" in ct:
        signals.append(f"Content-Type indicates FLV: {ct!r}")

    # URL extension signals
    if url_lower.endswith(".m3u8") or url_lower.endswith(".m3u"):
        signals.append("URL ends with .m3u8 / .m3u — HLS playlist extension")
    if url_lower.endswith(".ts"):
        signals.append("URL ends with .ts — MPEG-TS segment extension")
    if url_lower.endswith(".mpd"):
        signals.append("URL ends with .mpd — DASH manifest extension")
    if url_lower.endswith(".mp4") or url_lower.endswith(".m4v"):
        signals.append("URL ends with .mp4/.m4v — MP4 extension")
    if url_lower.endswith(".flv"):
        signals.append("URL ends with .flv — FLV extension")

    # M3U8 content signals
    is_m3u8 = "#extm3u" in text.lower()
    has_media_seq = "#ext-x-media-sequence" in text.lower()
    has_stream_inf = "#ext-x-stream-inf" in text.lower()
    has_endlist = "#ext-x-endlist" in text.lower()
    has_targetdur = "#ext-x-targetduration" in text.lower()

    if is_m3u8:
        signals.append("Body starts with #EXTM3U — valid HLS/M3U8 playlist")
    if has_media_seq:
        signals.append("#EXT-X-MEDIA-SEQUENCE present — live media playlist (HLS Segmenter)")
    if has_stream_inf:
        signals.append("#EXT-X-STREAM-INF present — master playlist with variant streams (HLS Direct)")
    if has_endlist:
        signals.append("#EXT-X-ENDLIST present — VOD or completed playlist")
    if has_targetdur:
        signals.append("#EXT-X-TARGETDURATION present — segment-based playlist")

    # MPEG-TS sync byte (0x47 = 71 decimal, every 188 bytes)
    ts_score = _count_ts_sync_bytes(raw)
    if ts_score >= 4:
        signals.append(f"MPEG-TS sync byte 0x47 found at {ts_score} expected offsets — binary MPEG-TS stream")
    elif ts_score >= 2:
        signals.append(f"MPEG-TS sync byte 0x47 found at {ts_score} expected offsets — possible MPEG-TS")

    # DASH MPD content
    is_mpd = bool(re.search(r"<MPD\b", text[:4096], re.IGNORECASE))
    if is_mpd:
        signals.append("Body contains <MPD> XML element — MPEG-DASH manifest")

    # MP4 ftyp box (first 4+4 = 8 bytes)
    is_mp4 = _is_mp4(raw)
    if is_mp4:
        signals.append("MP4 'ftyp' box found in binary header — MP4/fMP4 container")

    # ── Decision logic ────────────────────────────────────────────────────

    # MPEG-DASH
    if is_mpd or "dash+xml" in ct or url_lower.endswith(".mpd"):
        return (
            "DASH",
            "high" if (is_mpd or "dash+xml" in ct) else "medium",
            (
                "MPEG-DASH (Dynamic Adaptive Streaming over HTTP) manifest detected.  "
                "RetroIPTVGuide uses HLS.js, which does not natively support DASH.  "
                "Most IPTV providers that use DASH also offer an HLS variant."
            ),
            [
                "Check if the provider also offers an HLS (.m3u8) URL for the same stream.",
                "A DASH-to-HLS proxy (e.g. THEOplayer server-side, ffmpeg re-mux) could bridge the gap.",
            ],
        )

    # MP4
    if is_mp4 or ct in ("video/mp4", "video/x-m4v", "audio/mp4") or url_lower.endswith((".mp4", ".m4v")):
        return (
            "MP4",
            "high" if is_mp4 else "medium",
            (
                "Progressive MP4 or fragmented MP4 (fMP4) file.  "
                "Browsers can play MP4 directly if the codec is H.264/AAC.  "
                "RetroIPTVGuide will attempt to play it via the HTML5 <video> element."
            ),
            [
                "Ensure the MP4 uses H.264 video and AAC audio for maximum browser compatibility.",
                "For live streaming, prefer HLS — MP4 is not ideal for live content.",
            ],
        )

    # HLS — M3U8 content detected
    if is_m3u8 or "mpegurl" in ct or "x-mpegurl" in ct or "vnd.apple.mpegurl" in ct \
            or url_lower.endswith(".m3u8") or url_lower.endswith(".m3u"):

        if has_stream_inf and not has_media_seq:
            # Master playlist → HLS Direct
            tips = [
                "This is compatible with RetroIPTVGuide (HLS.js supports master playlists).",
                "The client selects the best variant stream based on bandwidth.",
            ]
            if has_endlist:
                tips.append("The playlist contains #EXT-X-ENDLIST — this is VOD, not live.")
            return (
                "HLS Direct",
                "high",
                (
                    "HLS master playlist detected.  The server provides multiple quality "
                    "variants (#EXT-X-STREAM-INF) and the player automatically picks the "
                    "best one.  This is the recommended format for multi-bitrate live TV."
                ),
                tips,
            )

        if has_media_seq or has_targetdur:
            # Media playlist → HLS Segmenter
            tips = [
                "This is fully compatible with RetroIPTVGuide (HLS.js supports live media playlists).",
                "The server refreshes the playlist at regular intervals (target segment duration).",
            ]
            if has_endlist:
                tips.append("The playlist contains #EXT-X-ENDLIST — this is a completed VOD recording, not live.")
            return (
                "HLS Segmenter",
                "high",
                (
                    "HLS live media playlist detected.  The server is segmenting the live "
                    "stream into short .ts chunks and advertising them via "
                    "#EXT-X-MEDIA-SEQUENCE.  This is the standard format for IPTV live "
                    "streams served by segmenters (e.g. nginx-rtmp HLS, ffmpeg HLS muxer)."
                ),
                tips,
            )

        # ── M3U channel list — IPTV multi-channel playlist ─────────────
        # An IPTV .m3u playlist has #EXTINF lines with tvg-id / group-title /
        # tvg-name attributes (or uses -1 duration) and NO HLS #EXT-X-* tags.
        # This is a channel directory, not a stream — the stream URLs are
        # embedded inside it.
        has_extinf = "#extinf:" in text.lower()
        has_iptv_attrs = (
            'tvg-id="' in text
            or 'group-title="' in text
            or 'tvg-name="' in text
            or "#extinf:-1" in text.lower()
        )
        if has_extinf and has_iptv_attrs and not (has_endlist or has_stream_inf or has_media_seq or has_targetdur):
            # Extra guard: all HLS-specific tags were already checked above (has_stream_inf
            # → HLS Direct, has_media_seq/has_targetdur → HLS Segmenter).  We also exclude
            # has_endlist here because that tag belongs to HLS VOD playlists.  At this point
            # we have a genuine IPTV channel list, not an HLS stream.
            signals.append(
                "#EXTINF lines with IPTV channel attributes (tvg-id/group-title) detected "
                "— this is a multi-channel IPTV playlist, not a direct stream"
            )
            return (
                "M3U Channel List",
                "high",
                (
                    "IPTV M3U channel playlist detected.  This file lists multiple channels "
                    "with their stream URLs — it is not a stream itself.  "
                    "Use the channel dropdown below to select a specific channel and test "
                    "its stream URL."
                ),
                [
                    "Select a channel from the dropdown and click 'Test Selected Channel' "
                    "to identify the stream type for that channel.",
                    "You can add this URL as a tuner M3U source in RetroIPTVGuide's tuner settings.",
                ],
            )

        # EXTM3U present but can't tell if master or media
        return (
            "HLS (type undetermined)",
            "medium",
            (
                "HLS/M3U8 playlist confirmed, but could not determine whether this is a "
                "master playlist or a live media playlist from the probe data alone.  "
                "RetroIPTVGuide should be able to play it — HLS.js handles both types."
            ),
            [
                "If the guide does not update, the playlist may be a one-time M3U channel list "
                "rather than a live HLS playlist — verify the URL is a .m3u8 not a .m3u channel list.",
            ],
        )

    # Raw MPEG-TS (confirmed by binary sync bytes)
    if ts_score >= 4:
        return (
            "MPEG-TS",
            "high",
            (
                "Raw MPEG-2 Transport Stream (MPEG-TS) detected directly in the HTTP body.  "
                "This stream is delivered as a continuous binary bitstream over HTTP — "
                "not wrapped in HLS segments.  Most web browsers (including Chrome and "
                "Firefox) cannot play raw MPEG-TS directly."
            ),
            [
                "RetroIPTVGuide uses HLS.js, which cannot play raw MPEG-TS over HTTP.  "
                "You may need a proxy that wraps this stream in HLS (e.g. ffmpeg -i <url> -c copy "
                "-f hls output.m3u8, or an IPTV proxy like Threadfin or xTeVe).",
                "If the stream is 'MPEG-TS over HTTP', some Kodi-type players can play it "
                "but standard browsers cannot.",
                "Check whether the provider also offers an HLS variant of this channel.",
            ],
        )

    if ts_score >= 2:
        return (
            "MPEG-TS (likely)",
            "medium",
            (
                "Binary data consistent with MPEG-2 Transport Stream detected.  "
                "The stream appears to be raw MPEG-TS, but confidence is medium because "
                "not enough sync bytes were seen in the probe window."
            ),
            [
                "Try playing the URL in VLC to confirm it is MPEG-TS.",
                "Web browsers and HLS.js cannot play raw MPEG-TS directly — "
                "an HLS proxy is required.",
            ],
        )

    # Content-Type gives us MPEG-TS even if binary analysis didn't confirm
    if "mp2t" in ct or "mpeg2-ts" in ct or "mpeg-ts" in ct:
        return (
            "MPEG-TS",
            "medium",
            (
                "Content-Type header indicates MPEG-TS ({}), but sync bytes were not "
                "confirmed in the probed data.  The stream is very likely MPEG-TS.".format(ct)
            ),
            [
                "Web browsers and HLS.js cannot play raw MPEG-TS — an HLS proxy is required.",
                "Use VLC or ffprobe to confirm: ffprobe -v quiet -show_format '{}'".format(url),
            ],
        )

    # URL ends with .ts without other signals
    if url_lower.endswith(".ts"):
        return (
            "MPEG-TS segment",
            "medium",
            (
                "URL ends with .ts which typically indicates a single MPEG-TS segment.  "
                "Individual TS segments are served as part of an HLS playlist — the player "
                "should be pointed at the .m3u8 playlist URL, not at an individual segment."
            ),
            [
                "Find and use the .m3u8 playlist URL instead of a single .ts segment URL.",
                "If this is a direct MPEG-TS stream (not HLS), an HLS proxy is required for browser playback.",
            ],
        )

    # Video content-type not otherwise classified
    if ct.startswith("video/") or ct.startswith("audio/"):
        return (
            "Media stream",
            "low",
            (
                "HTTP response has a media Content-Type ({}) but the stream type could not "
                "be determined precisely from the probed data.".format(ct or "(empty)")
            ),
            [
                "Check the URL in a media player (VLC, ffprobe) to confirm the exact codec "
                "and container.",
                "If it is not H.264/AAC in MP4 or HLS format, browser playback may fail.",
            ],
        )

    # No useful signals
    return (
        "Unknown",
        "none",
        (
            "The stream type could not be determined.  "
            "The server responded successfully but the content did not match any known "
            "stream format signature."
        ),
        [
            "Check the URL in VLC or run: ffprobe -v quiet -show_format -show_streams <URL>",
            "Verify that the URL points directly to a stream, not an HTML page.",
            f"Detected Content-Type: {ct!r}",
        ],
    )



# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

#: Maximum number of channels to return from an M3U channel list.
#: Large playlists can have thousands of channels; cap the dropdown at 300
#: to keep the JSON response manageable and the UI usable.
_MAX_CHANNELS = 300

#: How many lines after a ``#EXTINF`` tag to search for the stream URL.
#: A value of 4 accommodates playlists that insert ``#EXTVLCOPT`` or similar
#: extension tags between the ``#EXTINF`` and the URL.
_MAX_URL_LOOKAHEAD = 4


def _parse_m3u_channels(text: str) -> List[Dict[str, Any]]:
    """Parse an IPTV M3U playlist text and return a list of channel dicts.

    Each dict has keys:
        ``name``   – display name from the ``#EXTINF`` comma-suffix
        ``url``    – stream URL that follows the ``#EXTINF`` line
        ``group``  – value of ``group-title`` attribute, or ``""``
        ``tvg_id`` – value of ``tvg-id`` attribute, or ``""``

    Returns at most :data:`_MAX_CHANNELS` entries.  If the playlist contains
    more, the caller should surface that via ``channel_count`` (the total
    parsed before capping).
    """
    lines = text.splitlines()
    channels: List[Dict[str, Any]] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.upper().startswith("#EXTINF:"):
            continue

        # Channel name — everything after the last comma on the #EXTINF line
        name_match = re.search(r",(.+)$", stripped)
        name = name_match.group(1).strip() if name_match else ""

        # Attributes embedded in the #EXTINF line
        tvg_id_match = re.search(r'tvg-id="([^"]*)"', stripped, re.IGNORECASE)
        tvg_id = tvg_id_match.group(1).strip() if tvg_id_match else ""

        group_match = re.search(r'group-title="([^"]*)"', stripped, re.IGNORECASE)
        group = group_match.group(1).strip() if group_match else ""

        # The stream URL is on the next non-blank, non-comment line
        url = ""
        for j in range(i + 1, min(i + 1 + _MAX_URL_LOOKAHEAD, len(lines))):
            candidate = lines[j].strip()
            if candidate and not candidate.startswith("#"):
                url = candidate
                break

        channels.append({"name": name, "url": url, "group": group, "tvg_id": tvg_id})

        if len(channels) >= _MAX_CHANNELS:
            break

    return channels


def _check_ssrf_risk(parsed) -> Optional[str]:
    """Return an error message string if the URL targets a loopback or link-local
    address, otherwise return ``None``.

    We only reject obvious loopback (127.x.x.x, ::1) and link-local
    (169.254.x.x, fe80::/10) addresses.  Private RFC-1918 ranges
    (10.x, 172.16-31.x, 192.168.x) are intentionally *not* blocked because
    many IPTV setups run on a LAN where the stream server is in a private range.
    """
    import ipaddress  # noqa: PLC0415

    hostname = parsed.hostname or ""
    if not hostname:
        return None

    # Try to parse as a literal IP address (v4 or v6)
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_loopback:
            return f"Loopback address '{hostname}' is not allowed."
        if addr.is_link_local:
            return f"Link-local address '{hostname}' is not allowed."
        # Block IPv4-mapped IPv6 loopback (::ffff:127.0.0.1, etc.)
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            mapped = addr.ipv4_mapped
            if mapped.is_loopback or mapped.is_link_local:
                return f"Address '{hostname}' maps to a restricted IPv4 address."
    except ValueError:
        # Not a literal IP — it's a hostname; DNS-based SSRF would require
        # DNS rebinding and is out of scope for this lightweight guard.
        pass

    # Reject 'localhost' explicitly
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        return f"Loopback hostname '{hostname}' is not allowed."

    return None


def _check_dns(url: str) -> Dict[str, Any]:
    """Resolve the hostname from *url* and return a result dict."""
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            return {"hostname": None, "resolved_ip": None, "error": "No hostname in URL"}
        ip = socket.getaddrinfo(hostname, None)[0][4][0]
        return {"hostname": hostname, "resolved_ip": ip, "error": None}
    except socket.gaierror as exc:
        return {
            "hostname": urlparse(url).hostname,
            "resolved_ip": None,
            "error": f"DNS resolution failed: {exc}",
        }
    except (OSError, ValueError) as exc:
        return {"hostname": None, "resolved_ip": None, "error": str(exc)}


def _fetch_partial(url: str, timeout: int = _TIMEOUT) -> Dict[str, Any]:
    """Fetch the first ``_PROBE_BYTES`` bytes of *url* via streaming GET.

    Returns a dict compatible with the rest of the diagnostics system.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "status_code": None,
        "content_type": None,
        "content_length": None,
        "response_time_ms": None,
        "error": None,
        "raw_bytes": b"",
        "truncated": False,
    }
    t0 = time.monotonic()
    try:
        import requests as _req  # noqa: PLC0415
        # nosec B113 — intentional admin-only SSRF: URL has been validated against
        # loopback/link-local addresses by _check_ssrf_risk() before reaching here.
        # RFC-1918 private addresses are intentionally allowed because many IPTV
        # deployments run stream servers on a LAN.  This route is only reachable
        # by the 'admin' user (403 for all others — see blueprints/admin_diagnostics.py).
        resp = _req.get(  # noqa: S113
            url,
            timeout=timeout,
            stream=True,
            headers={"User-Agent": _UA},
        )
        result["status_code"] = resp.status_code
        result["content_type"] = resp.headers.get("Content-Type", "")
        result["content_length"] = resp.headers.get("Content-Length")
        resp.raise_for_status()

        raw = b""
        for chunk in resp.iter_content(chunk_size=8192):
            raw += chunk
            if len(raw) >= _PROBE_BYTES:
                result["truncated"] = True
                break

        result["response_time_ms"] = int((time.monotonic() - t0) * 1000)
        result["raw_bytes"] = raw
        result["ok"] = True
    except ImportError as exc:
        result["error"] = f"requests library not installed: {exc}"
        result["response_time_ms"] = int((time.monotonic() - t0) * 1000)
    except OSError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["response_time_ms"] = int((time.monotonic() - t0) * 1000)
    except Exception as exc:  # noqa: BLE001 – requests raises many types (HTTPError, Timeout, etc.)
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["response_time_ms"] = int((time.monotonic() - t0) * 1000)

    return result


def _count_ts_sync_bytes(data: bytes, packet_size: int = 188) -> int:
    """Count how many times the MPEG-TS sync byte (0x47) appears at expected
    188-byte packet boundaries.

    A valid MPEG-TS stream will have 0x47 at offsets 0, 188, 376, 564, …
    We look for the first occurrence and then count consecutive valid packets.
    """
    if len(data) < packet_size:
        return 0

    # Find the first 0x47 that could be a sync byte (i.e., data[offset+188] == 0x47)
    for start in range(min(len(data) - packet_size, 188)):
        if data[start] == 0x47 and data[start + packet_size] == 0x47:
            # Confirmed sync — count how many consecutive packets follow
            count = 1
            pos = start + packet_size
            while pos + packet_size <= len(data):
                if data[pos] == 0x47:
                    count += 1
                    pos += packet_size
                else:
                    break
            return count

    return 0


def _is_mp4(data: bytes) -> bool:
    """Return True if *data* starts with a valid MP4 ftyp box."""
    if len(data) < 8:
        return False
    # ftyp box: bytes 4..7 == b'ftyp'
    # Also accept b'free', b'mdat', b'moov' at offset 4 for fragmented MP4
    _MP4_BOXES = (b"ftyp", b"moov", b"free", b"mdat", b"pdin", b"moof")
    return data[4:8] in _MP4_BOXES
