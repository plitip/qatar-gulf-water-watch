"""
scan_gulf_for_approaching_blooms.py

The "advance warning" layer that qatar_bloom_watch.py is missing on its
own. qatar_bloom_watch.py only samples tiny boxes right at the three
intakes -- it can tell you the water is ALREADY unusual there, but not
that something is approaching. Real blooms are patches of ocean, often
tens to hundreds of km across, that drift on currents over days to
weeks. So real lead time comes from watching a much wider stretch of
the Gulf (roughly the Strait of Hormuz down to Qatar's coast) and
noticing an elevated patch before it reaches Qatar -- exactly what the
UAE's ESA-backed system does for its own coast.

This script scans that wider box, flags pixels with unusually high
chlorophyll (a local hotspot, not just Gulf-wide turbidity), and
reports how far the nearest one is from Qatar's coast.

RUN:
    python scan_gulf_for_approaching_blooms.py

STATUS: prototype. "Elevated" here is a same-day statistical outlier
within the scene (top 5%, above a floor value) -- a reasonable first
pass, not a validated bloom classifier. A real bloom also needs
tracking over several days to see if it's moving toward Qatar at all;
this script gives one day's snapshot, not a trajectory.
"""

import json
import math
import os
from datetime import date, timedelta

import numpy as np

from qatar_bloom_watch import (
    log,
    CHLOROPHYLL_DATASET_ID,
    CHLOROPHYLL_VARIABLE,
    MAX_LOOKBACK_DAYS,
)

# Strait of Hormuz down through the Gulf to Qatar's coast -- the
# corridor a bloom would actually travel through to reach Qatar.
GULF_WATCH_BBOX = {"min_lon": 49.0, "max_lon": 57.0, "min_lat": 24.0, "max_lat": 27.5}

# Reference point for "how far from Qatar" -- roughly the Qatari coastline
QATAR_REFERENCE_POINT = {"lat": 25.3, "lon": 51.5}

SCENE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gulf_scan_data")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gulf_bloom_watch.json")

# A pixel counts as a "hotspot" only if it's BOTH a real outlier for that
# day's scene (not just ambient Gulf turbidity) AND above an absolute
# floor, so a uniformly murky day doesn't get flagged as 100 hotspots.
ELEVATED_PERCENTILE = 95
ELEVATED_MIN_VALUE = 3.0  # mg/m3


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in kilometers."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def fetch_gulf_scene(target_date: date) -> str:
    import copernicusmarine

    os.makedirs(SCENE_DIR, exist_ok=True)
    filename = f"gulf_{target_date.isoformat()}.nc"
    scene_path = os.path.join(SCENE_DIR, filename)
    if os.path.exists(scene_path):
        log.info("Using cached Gulf-wide scene for %s", target_date)
        return scene_path

    copernicusmarine.subset(
        dataset_id=CHLOROPHYLL_DATASET_ID,
        variables=[CHLOROPHYLL_VARIABLE],
        minimum_longitude=GULF_WATCH_BBOX["min_lon"],
        maximum_longitude=GULF_WATCH_BBOX["max_lon"],
        minimum_latitude=GULF_WATCH_BBOX["min_lat"],
        maximum_latitude=GULF_WATCH_BBOX["max_lat"],
        start_datetime=f"{target_date.isoformat()}T00:00:00",
        end_datetime=f"{target_date.isoformat()}T23:59:59",
        output_filename=filename,
        output_directory=SCENE_DIR,
    )
    return scene_path


def find_latest_gulf_scene():
    """Same lag-handling as qatar_bloom_watch.py: try today, step back if not published yet."""
    candidate = date.today()
    for _ in range(MAX_LOOKBACK_DAYS):
        try:
            return fetch_gulf_scene(candidate), candidate
        except Exception as exc:
            if type(exc).__name__ == "CoordinatesOutOfDatasetBounds":
                log.info("No Gulf-wide data yet for %s, trying the day before ...", candidate)
                candidate -= timedelta(days=1)
                continue
            raise
    raise RuntimeError(f"No Gulf-wide scene found in the last {MAX_LOOKBACK_DAYS} days")


def scan_for_hotspots(scene_path: str) -> list[dict]:
    import xarray as xr

    with xr.open_dataset(scene_path) as scene:
        chl = scene[CHLOROPHYLL_VARIABLE]
        if "time" in chl.dims:
            chl = chl.mean(dim="time")  # collapse the single day's time dimension

        values = chl.values
        lats = chl["latitude"].values
        lons = chl["longitude"].values

        valid = values[~np.isnan(values)]
        if len(valid) == 0:
            return []

        cutoff = max(float(np.percentile(valid, ELEVATED_PERCENTILE)), ELEVATED_MIN_VALUE)

        hotspots = []
        rows, cols = np.where(values > cutoff)
        for r, c in zip(rows, cols):
            lat, lon = float(lats[r]), float(lons[c])
            hotspots.append({
                "lat": lat,
                "lon": lon,
                "value": float(values[r, c]),
                "distance_km": haversine_km(lat, lon, QATAR_REFERENCE_POINT["lat"], QATAR_REFERENCE_POINT["lon"]),
            })

    hotspots.sort(key=lambda h: h["distance_km"])
    return hotspots


def main() -> None:
    scene_path, scene_date = find_latest_gulf_scene()
    log.info("Scanning the wider Gulf for elevated chlorophyll patches (%s) ...", scene_date)
    hotspots = scan_for_hotspots(scene_path)

    result = {
        "date": scene_date.isoformat(),
        "hotspot_count": len(hotspots),
        "nearest_km": round(hotspots[0]["distance_km"], 1) if hotspots else None,
        "nearest_location": {"lat": hotspots[0]["lat"], "lon": hotspots[0]["lon"]} if hotspots else None,
        "hotspots": hotspots[:50],
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2)

    if hotspots:
        nearest = hotspots[0]
        log.warning(
            "%d elevated patch(es) found in the wider Gulf. Nearest is ~%.0f km from Qatar's coast "
            "(%.2f mg/m3 at %.2f, %.2f).",
            len(hotspots), nearest["distance_km"], nearest["value"], nearest["lat"], nearest["lon"],
        )
    else:
        log.info("No elevated chlorophyll patches found in the wider Gulf for %s.", scene_date)

    log.info("Full results written to %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()
