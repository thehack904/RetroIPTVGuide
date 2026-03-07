"""Channel conflict detector for the RetroIPTVGuide Admin Diagnostics subsystem.

Analyses the live in-memory channel cache for duplicate identifiers that
can cause guide-mapping failures, incorrect stream playback, or confusing
guide grids.

Three conflict classes are detected:

* **Duplicate channel names** (case-insensitive) — same display name across
  different guide entries; confuses the EPG grid and search.
* **Duplicate TVG-IDs** (guide identifiers) — two or more channels share a
  ``tvg-id``; the guide data for one silently overwrites the other.
* **Duplicate stream URLs** — two channels point at the exact same stream;
  often a copy/paste error in the M3U playlist.

Public API
----------
* ``detect_channel_conflicts()`` → ``Dict[str, Any]``
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


def detect_channel_conflicts() -> Dict[str, Any]:
    """Scan the live channel cache and return a structured conflict report.

    Reads ``cached_channels`` from the running ``app`` module (the same list
    that the guide/play routes use) so results are always current without
    requiring a DB re-parse.

    Returns
    -------
    dict with keys:

    ``status``
        ``"PASS"`` – no conflicts found
        ``"WARN"`` – conflicts detected (may indicate config problems)
        ``"ERROR"`` – could not access the channel cache

    ``detail``
        One-line human-readable summary.

    ``duplicate_names``
        List of dicts ``{name, count, channels}`` for names appearing >1 time.

    ``duplicate_tvg_ids``
        List of dicts ``{tvg_id, count, channels}`` for guide IDs appearing >1 time.

    ``duplicate_urls``
        List of dicts ``{url, count, channels}`` for stream URLs appearing >1 time.

    ``channel_count``
        Total number of channels in the live cache.
    """
    try:
        import app as app_module  # noqa: PLC0415
        channels: List[Dict[str, Any]] = list(
            getattr(app_module, "cached_channels", []) or []
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "detail": f"Could not access channel cache: {type(exc).__name__}: {exc}",
            "duplicate_names": [],
            "duplicate_tvg_ids": [],
            "duplicate_urls": [],
            "channel_count": 0,
            "remediation": "Ensure the application has started and refreshed its channel cache.",
        }

    if not channels:
        return {
            "status": "PASS",
            "detail": "Channel cache is empty — no conflicts to detect.",
            "duplicate_names": [],
            "duplicate_tvg_ids": [],
            "duplicate_urls": [],
            "channel_count": 0,
            "remediation": "",
        }

    # --- Collect by name (case-insensitive), tvg_id, url ---
    name_map: Dict[str, List[Dict]] = defaultdict(list)
    tvg_id_map: Dict[str, List[Dict]] = defaultdict(list)
    url_map: Dict[str, List[Dict]] = defaultdict(list)

    for ch in channels:
        name = (ch.get("name") or "").strip()
        tvg_id = (ch.get("tvg_id") or "").strip()
        url = (ch.get("url") or "").strip()

        if name:
            name_map[name.lower()].append(ch)
        if tvg_id:
            tvg_id_map[tvg_id].append(ch)
        if url:
            url_map[url].append(ch)

    # --- Build conflict lists ---
    def _channel_summary(ch: Dict[str, Any]) -> Dict[str, str]:
        return {
            "name": ch.get("name") or "",
            "tvg_id": ch.get("tvg_id") or "",
        }

    dup_names = [
        {
            "name": entries[0].get("name") or key,
            "count": len(entries),
            "channels": [_channel_summary(c) for c in entries],
        }
        for key, entries in name_map.items()
        if len(entries) > 1
    ]

    dup_tvg_ids = [
        {
            "tvg_id": tvg_id,
            "count": len(entries),
            "channels": [_channel_summary(c) for c in entries],
        }
        for tvg_id, entries in tvg_id_map.items()
        if len(entries) > 1
    ]

    dup_urls = [
        {
            "url": url,
            "count": len(entries),
            "channels": [_channel_summary(c) for c in entries],
        }
        for url, entries in url_map.items()
        if len(entries) > 1
    ]

    # Sort by conflict count descending for readability
    dup_names.sort(key=lambda x: x["count"], reverse=True)
    dup_tvg_ids.sort(key=lambda x: x["count"], reverse=True)
    dup_urls.sort(key=lambda x: x["count"], reverse=True)

    total_conflicts = len(dup_names) + len(dup_tvg_ids) + len(dup_urls)
    if total_conflicts == 0:
        status = "PASS"
        detail = f"{len(channels)} channel(s) checked — no conflicts detected."
        remediation = ""
    else:
        status = "WARN"
        parts = []
        if dup_names:
            parts.append(f"{len(dup_names)} duplicate name(s)")
        if dup_tvg_ids:
            parts.append(f"{len(dup_tvg_ids)} duplicate TVG-ID(s)")
        if dup_urls:
            parts.append(f"{len(dup_urls)} duplicate URL(s)")
        detail = f"{len(channels)} channels checked. Conflicts: {', '.join(parts)}."
        remediation = (
            "Review your M3U playlist(s) for duplicate entries. "
            "Duplicate TVG-IDs cause guide data to be overwritten; "
            "duplicate URLs waste bandwidth and may cause playback issues."
        )

    return {
        "status": status,
        "detail": detail,
        "duplicate_names": dup_names,
        "duplicate_tvg_ids": dup_tvg_ids,
        "duplicate_urls": dup_urls,
        "channel_count": len(channels),
        "remediation": remediation,
    }
