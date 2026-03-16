# Road Data — Bundled GeoJSON files

This directory contains pre-downloaded OpenStreetMap road geometry for the
RetroIPTVGuide traffic demo overlay. Bundling these files with the repository
means the app never needs to contact the Overpass API at runtime — even on
completely air-gapped or network-restricted deployments.

## File naming

Each file is named `<cityslug>.geojson` where `<cityslug>` is the lowercase
alphanumeric city name (e.g. `newyorkcity.geojson`, `losangeles.geojson`).
This matches the naming used for the basemap PNGs in `static/maps/traffic_demo/`.

## Contents

Each GeoJSON file is a `FeatureCollection` of `LineString` features representing
motorway and trunk-class roads within ~50 miles of the city centre (the same
area shown by the traffic demo at zoom level 10).

## Generating / refreshing the files

Run the pre-download script from any machine that has internet access:

```bash
# From the repository root:
pip install requests
python scripts/download_road_data.py
```

The script downloads data from the free [Overpass API](https://overpass-api.de)
(no API key required), converts it to GeoJSON, and saves one file per city.
Requests are staggered by 15 seconds to stay within Overpass fair-use limits.

Commit the generated files so every deployment benefits from offline road data.

## How the app uses these files

`get_traffic_demo_roads()` in `app.py` checks four sources in order:

1. **In-memory cache** (hot, 24 h TTL)
2. **Disk cache** (`data/roads_cache/`, persistent across restarts, 30 day TTL)
3. **Bundled static data** ← this directory (no expiry, no network required)
4. **Overpass API** (live network call — last resort only)
