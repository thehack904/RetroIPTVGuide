#!/usr/bin/env python3
"""Pre-download Overpass road data for the RetroIPTVGuide traffic demo.

Run this script ONCE from any machine that has internet access (your laptop,
home PC, Raspberry Pi, etc.).  The downloaded GeoJSON files are committed to the
repository so the app never needs to contact the Overpass API at runtime — even
on a completely air-gapped or network-restricted deployment.

Usage
-----
    # From the repository root:
    pip install requests
    python scripts/download_road_data.py

    # The 10 GeoJSON files will be saved to:
    #   static/data/roads/<cityslug>.geojson
    #
    # Commit them alongside the rest of the repository.  The app will detect
    # them automatically and use them in preference to any live Overpass query.

How it works
------------
Each file is a GeoJSON FeatureCollection containing motorway and trunk-class
road LineStrings within ~50 miles (80 467 m) of the city centre — the same
area shown by the traffic demo basemap at zoom level 10.

The data comes from the free OpenStreetMap Overpass API
(https://overpass-api.de).  No API key is required.  Requests are staggered
by 15 seconds to stay within the service's fair-use limits.
"""

import json
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' is not installed.  Run: pip install requests")

# ── Configuration ──────────────────────────────────────────────────────────────

OVERPASS_URL   = "https://overpass-api.de/api/interpreter"
RADIUS_M       = 80_467    # 50 miles — matches app.py _fetch_overpass_roads default
TIMEOUT_S      = 65        # request timeout in seconds
STAGGER_S      = 15        # seconds between requests (Overpass fair-use)
MAX_RETRIES    = 3         # per-city retry attempts on 429 / transient errors
BACKOFF_S      = 10        # initial back-off (doubles each retry)

UA = (
    "RetroIPTVGuide/1.0 road-data pre-download "
    "(github.com/thehack904/RetroIPTVGuide; one-time personal-use download)"
)

# Output directory relative to this script's location  (scripts/ → .. → static/data/roads/)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "static", "data", "roads"))

# Cities — must match _TRAFFIC_DEMO_CITIES_SEED in app.py
CITIES = [
    {"name": "New York City", "lat": 40.7128, "lon": -74.0060},
    {"name": "Los Angeles",   "lat": 34.0522, "lon": -118.2437},
    {"name": "Chicago",       "lat": 41.8781, "lon": -87.6298},
    {"name": "Houston",       "lat": 29.7604, "lon": -95.3698},
    {"name": "Phoenix",       "lat": 33.4484, "lon": -112.0740},
    {"name": "Philadelphia",  "lat": 39.9526, "lon": -75.1652},
    {"name": "San Antonio",   "lat": 29.4241, "lon": -98.4936},
    {"name": "San Diego",     "lat": 32.7157, "lon": -117.1611},
    {"name": "Dallas",        "lat": 32.7767, "lon": -96.7970},
    {"name": "San Jose",      "lat": 37.3382, "lon": -121.8863},
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def city_slug(name: str) -> str:
    """Lowercase alphanumeric slug — mirrors _city_slug() in app.py."""
    return "".join(c for c in name.lower() if c.isalnum())


def _overpass_query(lat: float, lon: float) -> str:
    return (
        f"[out:json][timeout:60];"
        f"(way[\"highway\"~\"^(motorway|trunk)$\"]"
        f"(around:{RADIUS_M},{lat},{lon}););"
        f"out body;>;out skel qt;"
    )


def fetch_overpass(lat: float, lon: float, session: requests.Session) -> dict:
    """Download raw Overpass JSON for a city with retry/back-off logic."""
    query   = _overpass_query(lat, lon)
    backoff = BACKOFF_S
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = session.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=TIMEOUT_S,
            )
            if resp.status_code == 429 and attempt < MAX_RETRIES:
                wait = int(resp.headers.get("Retry-After", backoff))
                logging.warning(
                    "  429 rate-limited (attempt %d/%d) — sleeping %ds …",
                    attempt + 1, MAX_RETRIES, wait,
                )
                time.sleep(wait)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt < MAX_RETRIES:
                logging.warning(
                    "  transient error (attempt %d/%d): %s — retrying in %ds …",
                    attempt + 1, MAX_RETRIES, exc, backoff,
                )
                time.sleep(backoff)
                backoff *= 2
            else:
                logging.exception("  all retries exhausted for lat=%s lon=%s", lat, lon)
    return {"elements": []}


def overpass_to_geojson(raw: dict) -> dict:
    """Convert raw Overpass JSON to a GeoJSON FeatureCollection."""
    nodes: dict = {}
    ways: list  = []
    for el in raw.get("elements", []):
        t = el.get("type")
        if t == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif t == "way":
            ways.append(el)

    features = []
    for way in ways:
        coords = [nodes[nid] for nid in way.get("nodes", []) if nid in nodes]
        if len(coords) < 2:
            continue
        tags = way.get("tags", {})
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "way_id":  way["id"],
                "name":    tags.get("name", ""),
                "highway": tags.get("highway", ""),
            },
        })
    return {"type": "FeatureCollection", "features": features}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    total     = len(CITIES)
    generated = 0
    skipped   = 0
    failed    = 0

    for i, city in enumerate(CITIES, 1):
        slug     = city_slug(city["name"])
        out_path = os.path.join(OUT_DIR, f"{slug}.geojson")

        if os.path.isfile(out_path):
            # Re-use existing file only if it contains real features
            try:
                with open(out_path, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
                if existing.get("features"):
                    logging.info("[%d/%d] SKIP %s — already downloaded (%s)",
                                 i, total, city["name"], out_path)
                    skipped += 1
                    continue
            except Exception:
                pass  # corrupt/empty file — re-download below

        logging.info("[%d/%d] Downloading road data for %s …", i, total, city["name"])
        raw     = fetch_overpass(city["lat"], city["lon"], session)
        geojson = overpass_to_geojson(raw)

        if not geojson["features"]:
            logging.error("  ✗ No features returned for %s — skipping save", city["name"])
            failed += 1
        else:
            # Atomic write: temp file then os.replace
            tmp = out_path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(geojson, fh, separators=(",", ":"))
                os.replace(tmp, out_path)
                size_kb = os.path.getsize(out_path) // 1024
                logging.info("  ✓ Saved %s (%d features, %d KB)",
                             out_path, len(geojson["features"]), size_kb)
                generated += 1
            except Exception as exc:
                logging.exception("  ✗ Failed to save %s: %s", out_path, exc)
                failed += 1

        if i < total:
            logging.info("  Waiting %ds before next request …", STAGGER_S)
            time.sleep(STAGGER_S)

    print()
    print(f"Done.  Downloaded: {generated}  Skipped: {skipped}  Failed: {failed}")
    if failed:
        print("Some cities failed — check the warnings above and re-run the script.")
    else:
        print(f"All GeoJSON files are in:  {OUT_DIR}")
        print("Commit them to the repository so the app can run without network access.")


if __name__ == "__main__":
    main()
