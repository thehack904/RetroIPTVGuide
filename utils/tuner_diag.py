"""Tuner data parse trace — deep diagnostic for M3U and XMLTV fetch/parse.

``parse_tuner_with_trace(name, tuner_db_path)`` performs a live HTTP fetch and
parse of a tuner's M3U and XMLTV URLs, returning rich structured trace data
that the admin diagnostics UI can display to answer:

  "Why is my guide empty?"
  "Is the data from the tuner actually valid?"
  "Do my M3U channel IDs match the XMLTV channel IDs?"
  "What raw data is the server actually returning?"
"""

from __future__ import annotations

import html
import re
import socket
import sqlite3
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_tuner_with_trace(tuner_name: str, tuner_db_path: str) -> Dict[str, Any]:
    """Fetch and parse a tuner's M3U + XMLTV, returning full trace data.

    Returns a dict with keys:
        tuner_name, tuner_type, m3u, xmltv, issues[], warnings[]
    Each of ``m3u`` and ``xmltv`` is a trace sub-dict described below.
    """
    # Load tuner config from DB
    try:
        tuner_cfg = _load_tuner_config(tuner_name, tuner_db_path)
    except Exception as exc:  # noqa: BLE001
        return {
            "tuner_name": tuner_name,
            "tuner_type": "unknown",
            "error": f"Could not load tuner config: {type(exc).__name__}: {exc}",
            "m3u": None,
            "xmltv": None,
            "issues": [str(exc)],
            "warnings": [],
        }

    tuner_type = tuner_cfg.get("tuner_type", "standard")
    m3u_url = tuner_cfg.get("m3u", "")
    xml_url = tuner_cfg.get("xml", "")

    m3u_trace = _trace_m3u(m3u_url) if m3u_url else _not_configured("M3U URL not set")
    xmltv_trace = _trace_xmltv(xml_url) if xml_url else _not_configured("XMLTV URL not set")

    # Cross-check: which M3U tvg-ids appear in the EPG and which don't
    # NOTE: _compute_epg_coverage reads raw_bytes from xmltv_trace before we strip it.
    coverage = _compute_epg_coverage(m3u_trace, xmltv_trace)

    # Strip raw_bytes (bytes objects) from fetch dicts — bytes are not JSON-serialisable
    # and would cause jsonify() to fail with a 500 HTML error response.
    _strip_raw_bytes(m3u_trace)
    _strip_raw_bytes(xmltv_trace)

    issues = _collect_issues(m3u_trace, xmltv_trace, coverage)
    warnings = _collect_warnings(m3u_trace, xmltv_trace, coverage)

    return {
        "tuner_name": tuner_name,
        "tuner_type": tuner_type,
        "m3u_url": m3u_url,
        "xml_url": xml_url,
        "m3u": m3u_trace,
        "xmltv": xmltv_trace,
        "epg_coverage": coverage,
        "issues": issues,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# M3U trace
# ---------------------------------------------------------------------------

def _trace_m3u(url: str) -> Dict[str, Any]:
    """Fetch and analyse an M3U playlist URL."""
    import requests as _req  # noqa: PLC0415

    trace: Dict[str, Any] = {
        "url": url,
        "fetch": None,
        "content_sample": None,
        "parse": None,
        "issues": [],
    }

    # DNS check
    dns_result = _check_dns(url)
    trace["dns"] = dns_result

    # HTTP fetch
    fetch = _fetch_url(url)
    trace["fetch"] = fetch

    if not fetch["ok"]:
        trace["issues"].append(f"HTTP fetch failed: {fetch['error']}")
        return trace

    raw = fetch["raw_bytes"]
    trace["content_sample"] = _safe_content_sample(raw, max_bytes=2048)

    # Detect content-type issues
    ct = fetch.get("content_type", "") or ""
    if ct and "html" in ct.lower():
        trace["issues"].append(
            f"Content-Type is '{ct}' — server returned HTML, not an M3U playlist. "
            "Possible login redirect or error page."
        )

    # Parse
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        trace["issues"].append(f"Could not decode response as UTF-8: {exc}")
        return trace

    trace["parse"] = _analyse_m3u_text(text)
    return trace


def _analyse_m3u_text(text: str) -> Dict[str, Any]:
    """Analyse the raw M3U text and return statistics + quality checks."""
    lines = text.splitlines()
    non_empty = [l.strip() for l in lines if l.strip()]

    has_extm3u = non_empty[0].startswith("#EXTM3U") if non_empty else False
    has_extinf = any(l.startswith("#EXTINF:") for l in non_empty)

    result: Dict[str, Any] = {
        "line_count": len(lines),
        "has_extm3u_header": has_extm3u,
        "has_extinf_tags": has_extinf,
        "channels": [],
        "channel_count": 0,
        "issues": [],
        "warnings": [],
        "quality": {},
    }

    if not non_empty:
        result["issues"].append("M3U response is empty — no content returned.")
        return result

    if not has_extm3u:
        result["warnings"].append(
            "Missing #EXTM3U header. File may not be a standard M3U playlist."
        )

    if not has_extinf:
        # Try single-stream mode
        urls = [l for l in non_empty if l.startswith(("http://", "https://")) and not l.startswith("#")]
        if len(urls) == 1:
            result["warnings"].append(
                "Single-stream playlist detected (no #EXTINF tags). "
                "Only one channel will be available."
            )
            result["channels"] = [{"name": "Live Stream", "url": urls[0], "tvg_id": "stream_1", "logo": ""}]
            result["channel_count"] = 1
        else:
            result["issues"].append(
                f"No #EXTINF tags found and {len(urls)} stream URL(s) detected. "
                "Playlist format may not be recognised."
            )
        return result

    # Full M3U parse
    channels = []
    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        info = line.strip()
        name_m = re.search(r",(.+)$", info)
        name = name_m.group(1).strip() if name_m else f"Channel {i}"
        logo_m = re.search(r'tvg-logo="([^"]+)"', info)
        logo = logo_m.group(1) if logo_m else ""
        tvg_id_m = re.search(r'tvg-id="([^"]+)"', info)
        tvg_id = tvg_id_m.group(1) if tvg_id_m else ""
        group_m = re.search(r'group-title="([^"]+)"', info)
        group = group_m.group(1) if group_m else ""

        url = ""
        for j in range(i + 1, min(i + 3, len(lines))):
            candidate = lines[j].strip()
            if candidate and not candidate.startswith("#"):
                url = candidate
                break

        channels.append({"name": name, "url": url, "tvg_id": tvg_id, "logo": logo, "group": group})

    result["channel_count"] = len(channels)
    result["channels"] = channels[:10]  # sample: first 10

    # Quality analysis
    no_name = sum(1 for c in channels if not c["name"] or c["name"].startswith("Channel "))
    no_url = sum(1 for c in channels if not c["url"])
    no_tvg_id = sum(1 for c in channels if not c["tvg_id"])
    non_http = sum(1 for c in channels if c["url"] and not c["url"].startswith(("http://", "https://")))
    all_tvg_ids = [c["tvg_id"] for c in channels if c["tvg_id"]]
    dup_tvg_ids = _find_duplicates(all_tvg_ids)
    groups = sorted({c["group"] for c in channels if c["group"]})

    result["quality"] = {
        "no_name_count": no_name,
        "no_url_count": no_url,
        "no_tvg_id_count": no_tvg_id,
        "non_http_url_count": non_http,
        "duplicate_tvg_id_count": len(dup_tvg_ids),
        "duplicate_tvg_id_examples": dup_tvg_ids[:5],
        "group_count": len(groups),
        "groups_sample": groups[:20],
    }

    if no_url > 0:
        result["issues"].append(
            f"{no_url} channel(s) have no stream URL — they will not be playable."
        )
    if no_tvg_id > len(channels) * 0.5 and len(channels) > 5:
        result["warnings"].append(
            f"{no_tvg_id}/{len(channels)} channels have no tvg-id — EPG matching will be limited."
        )
    if dup_tvg_ids:
        result["warnings"].append(
            f"{len(dup_tvg_ids)} duplicate tvg-id(s) found: {', '.join(dup_tvg_ids[:3])}. "
            "Duplicate IDs cause EPG data to overwrite each other."
        )

    return result


# ---------------------------------------------------------------------------
# XMLTV trace
# ---------------------------------------------------------------------------

def _trace_xmltv(url: str) -> Dict[str, Any]:
    """Fetch and analyse an XMLTV URL."""
    trace: Dict[str, Any] = {
        "url": url,
        "fetch": None,
        "content_sample": None,
        "parse": None,
        "issues": [],
    }

    # If user accidentally pasted an M3U URL as the XML URL
    lurl = url.lower()
    if lurl.endswith((".m3u", ".m3u8")) or "playlist" in lurl:
        trace["issues"].append(
            "XMLTV URL appears to be an M3U playlist URL. "
            "The guide requires a separate XMLTV (XML) feed for programme data."
        )
        trace["fetch"] = {"ok": False, "error": "URL looks like M3U, skipping fetch."}
        return trace

    # DNS check
    trace["dns"] = _check_dns(url)

    # HTTP fetch
    fetch = _fetch_url(url, timeout=20)
    trace["fetch"] = fetch

    if not fetch["ok"]:
        trace["issues"].append(f"HTTP fetch failed: {fetch['error']}")
        return trace

    raw = fetch["raw_bytes"]
    trace["content_sample"] = _safe_content_sample(raw, max_bytes=1024)

    ct = fetch.get("content_type", "") or ""
    if ct and "html" in ct.lower():
        trace["issues"].append(
            f"Content-Type is '{ct}' — server returned HTML, not XMLTV data. "
            "This is usually a login redirect or error page."
        )

    trace["parse"] = _analyse_xmltv_bytes(raw)
    return trace


def _analyse_xmltv_bytes(raw: bytes) -> Dict[str, Any]:
    """Parse raw bytes as XMLTV and return statistics."""
    result: Dict[str, Any] = {
        "valid_xml": False,
        "valid_xmltv": False,
        "root_tag": None,
        "channel_count": 0,
        "programme_count": 0,
        "earliest_programme": None,
        "latest_programme": None,
        "channels_sample": [],
        "issues": [],
        "warnings": [],
    }

    if not raw:
        result["issues"].append("XMLTV response is empty — no content returned.")
        return result

    # Check for BOM / encoding issues
    head = raw[:200]
    if b"<html" in head.lower() or b"<!doctype" in head.lower():
        result["issues"].append(
            "Response starts with HTML markup, not XML. "
            "The server is likely returning an error page."
        )
        return result

    # Try XML parse
    try:
        root = ET.fromstring(raw)
        result["valid_xml"] = True
        result["root_tag"] = root.tag
    except ET.ParseError as exc:
        result["issues"].append(
            f"Invalid XML: {exc}. "
            "The XMLTV data is malformed and cannot be parsed."
        )
        return result

    if root.tag != "tv":
        result["issues"].append(
            f"Root XML element is '{root.tag}', expected 'tv'. "
            "This may not be a valid XMLTV feed."
        )
    else:
        result["valid_xmltv"] = True

    # Channel analysis
    channels = root.findall("channel")
    result["channel_count"] = len(channels)
    cids = [c.attrib.get("id", "") for c in channels]
    result["channels_sample"] = [
        {
            "id": c.attrib.get("id", ""),
            "display_name": (c.find("display-name").text if c.find("display-name") is not None else ""),
        }
        for c in channels[:15]
    ]

    if not channels:
        result["issues"].append(
            "No <channel> elements found in XMLTV. "
            "This feed has no channel definitions."
        )

    # Programme analysis
    programmes = root.findall("programme")
    result["programme_count"] = len(programmes)

    if not programmes:
        result["warnings"].append(
            "No <programme> elements found. Guide will show no programme data."
        )
    else:
        # Time range
        starts = []
        for p in programmes:
            s = p.attrib.get("start", "")
            if s and len(s) >= 14:
                starts.append(s[:14])
        if starts:
            starts.sort()
            result["earliest_programme"] = starts[0]
            result["latest_programme"] = starts[-1]

        # Channels with programmes
        prog_cids = {p.attrib.get("channel", "") for p in programmes}
        channels_with_progs = len(prog_cids & set(cids))
        result["channels_with_programmes"] = channels_with_progs
        if channels_with_progs < len(channels) and len(channels) > 0:
            result["warnings"].append(
                f"Only {channels_with_progs}/{len(channels)} EPG channels have programme entries."
            )

    return result


# ---------------------------------------------------------------------------
# EPG coverage cross-check
# ---------------------------------------------------------------------------

def _compute_epg_coverage(m3u_trace: Dict[str, Any],
                           xmltv_trace: Dict[str, Any]) -> Dict[str, Any]:
    """Compare M3U tvg-ids against XMLTV channel IDs."""
    result: Dict[str, Any] = {
        "m3u_ids": [],
        "xmltv_ids": [],
        "matched": [],
        "unmatched_m3u": [],
        "unmatched_xmltv": [],
        "match_count": 0,
        "match_pct": None,
        "issues": [],
    }

    m3u_parse = (m3u_trace or {}).get("parse") or {}
    xmltv_parse = (xmltv_trace or {}).get("parse") or {}

    m3u_channels = m3u_parse.get("channels", [])
    xmltv_samples = xmltv_parse.get("channels_sample", [])

    # We only have the sample from XMLTV — get all channel IDs from fetch if possible
    xmltv_all_ids: List[str] = []
    raw = (xmltv_trace or {}).get("fetch", {})
    if raw and raw.get("ok") and raw.get("raw_bytes"):
        try:
            root = ET.fromstring(raw["raw_bytes"])
            xmltv_all_ids = [c.attrib.get("id", "") for c in root.findall("channel") if c.attrib.get("id")]
        except Exception:  # noqa: BLE001
            xmltv_all_ids = [s["id"] for s in xmltv_samples if s.get("id")]
    else:
        xmltv_all_ids = [s["id"] for s in xmltv_samples if s.get("id")]

    m3u_ids = [c["tvg_id"] for c in m3u_channels if c.get("tvg_id")]
    # Use all channels from parse, not just sample
    m3u_parse_full_count = m3u_parse.get("channel_count", 0)

    result["m3u_ids"] = m3u_ids[:20]  # sample
    result["xmltv_ids"] = xmltv_all_ids[:20]  # sample
    result["m3u_channel_count"] = m3u_parse_full_count
    result["xmltv_channel_count"] = len(xmltv_all_ids)

    if m3u_ids and xmltv_all_ids:
        xmltv_set = set(xmltv_all_ids)
        m3u_set = set(m3u_ids)
        matched = sorted(m3u_set & xmltv_set)
        unmatched_m3u = sorted(m3u_set - xmltv_set)
        unmatched_xmltv = sorted(xmltv_set - m3u_set)
        match_pct = int(100 * len(matched) / len(m3u_ids)) if m3u_ids else 0

        result["matched"] = matched[:20]
        result["unmatched_m3u"] = unmatched_m3u[:20]
        result["unmatched_xmltv"] = unmatched_xmltv[:20]
        result["match_count"] = len(matched)
        result["match_pct"] = match_pct

        if match_pct == 0 and m3u_ids and xmltv_all_ids:
            result["issues"].append(
                "0% of M3U tvg-ids match any XMLTV channel ID. "
                "The guide will show no programme data for any channel. "
                "Check that the M3U tvg-id values match the XMLTV <channel id='...'> attributes."
            )
        elif match_pct < 30:
            result["issues"].append(
                f"Only {match_pct}% of M3U channels have a matching EPG entry. "
                "Most channels will show no programme guide data."
            )
    elif m3u_ids and not xmltv_all_ids:
        result["issues"].append(
            "M3U has channels but XMLTV has no channel IDs — "
            "no EPG data will be available."
        )

    return result


# ---------------------------------------------------------------------------
# Issue / warning aggregation
# ---------------------------------------------------------------------------

def _collect_issues(m3u_trace: Dict, xmltv_trace: Dict, coverage: Dict) -> List[str]:
    issues = []
    if m3u_trace:
        issues.extend(m3u_trace.get("issues", []))
        if m3u_trace.get("parse"):
            issues.extend(m3u_trace["parse"].get("issues", []))
    if xmltv_trace:
        issues.extend(xmltv_trace.get("issues", []))
        if xmltv_trace.get("parse"):
            issues.extend(xmltv_trace["parse"].get("issues", []))
    issues.extend(coverage.get("issues", []))
    return issues


def _collect_warnings(m3u_trace: Dict, xmltv_trace: Dict, coverage: Dict) -> List[str]:
    warnings = []
    if m3u_trace and m3u_trace.get("parse"):
        warnings.extend(m3u_trace["parse"].get("warnings", []))
    if xmltv_trace and xmltv_trace.get("parse"):
        warnings.extend(xmltv_trace["parse"].get("warnings", []))
    return warnings


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_raw_bytes(trace: Optional[Dict[str, Any]]) -> None:
    """Remove ``raw_bytes`` from a trace dict's ``fetch`` sub-dict in-place.

    ``raw_bytes`` is a ``bytes`` object used internally for parsing but is not
    JSON-serialisable.  It must be removed before the trace is passed to
    ``flask.jsonify()``, otherwise jsonify raises a TypeError and Flask returns
    an HTML 500 error page — which the browser then sees as
    "SyntaxError: Unexpected token '<'".
    """
    if not trace:
        return
    fetch = trace.get("fetch")
    if isinstance(fetch, dict):
        fetch.pop("raw_bytes", None)

def _load_tuner_config(tuner_name: str, tuner_db_path: str) -> Dict[str, Any]:
    """Read a single tuner row from the DB."""
    with sqlite3.connect(tuner_db_path, timeout=5) as conn:
        cur = conn.execute(
            "SELECT name, xml, m3u, tuner_type, sources FROM tuners WHERE name=?",
            (tuner_name,),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"Tuner '{tuner_name}' not found in database.")
    import json  # noqa: PLC0415
    name, xml_url, m3u_url, tuner_type, sources_raw = row
    cfg: Dict[str, Any] = {
        "name": name,
        "xml": xml_url or "",
        "m3u": m3u_url or "",
        "tuner_type": tuner_type or "standard",
    }
    if sources_raw:
        try:
            cfg["sources"] = json.loads(sources_raw)
        except Exception:  # noqa: BLE001
            cfg["sources"] = []
    return cfg


def _check_dns(url: str) -> Dict[str, Any]:
    """Resolve the hostname from *url* and return a result dict."""
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            return {"hostname": None, "resolved_ip": None, "error": "No hostname in URL"}
        ip = socket.getaddrinfo(hostname, None)[0][4][0]
        return {"hostname": hostname, "resolved_ip": ip, "error": None}
    except socket.gaierror as exc:
        return {"hostname": urlparse(url).hostname, "resolved_ip": None,
                "error": f"DNS resolution failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"hostname": None, "resolved_ip": None, "error": str(exc)}


def _fetch_url(url: str, timeout: int = 15) -> Dict[str, Any]:
    """HTTP GET *url*, return fetch metadata + raw bytes (capped at 5 MB)."""
    import requests as _req  # noqa: PLC0415

    MAX_FETCH_BYTES = 5 * 1024 * 1024

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
        resp = _req.get(url, timeout=timeout,
                        stream=True,
                        headers={"User-Agent": "RetroIPTVGuide-Diagnostics/1.0"})
        result["status_code"] = resp.status_code
        result["content_type"] = resp.headers.get("Content-Type", "")
        result["content_length"] = resp.headers.get("Content-Length")
        resp.raise_for_status()

        raw = b""
        for chunk in resp.iter_content(chunk_size=65536):
            raw += chunk
            if len(raw) >= MAX_FETCH_BYTES:
                result["truncated"] = True
                break
        result["response_time_ms"] = int((time.monotonic() - t0) * 1000)
        result["raw_bytes"] = raw
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["response_time_ms"] = int((time.monotonic() - t0) * 1000)

    return result


def _safe_content_sample(raw: bytes, max_bytes: int = 1024) -> str:
    """Return an HTML-escaped sample of the raw bytes."""
    try:
        text = raw[:max_bytes].decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        text = repr(raw[:max_bytes])
    return html.escape(text)


def _not_configured(reason: str) -> Dict[str, Any]:
    return {
        "url": "",
        "fetch": None,
        "content_sample": None,
        "parse": None,
        "issues": [reason],
        "dns": None,
    }


def _find_duplicates(items: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    for item in items:
        seen[item] = seen.get(item, 0) + 1
    return [k for k, v in seen.items() if v > 1]
