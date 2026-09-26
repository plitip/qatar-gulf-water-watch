"""
Wider-Gulf watch: is a bloom building out at sea, and is it heading for Qatar?

The intake check only sees water that has already reached the intakes. Real warning
time comes from spotting an elevated patch between the Strait of Hormuz and Qatar
days before it drifts in, the way the UAE's satellite system watches its own coast.

A pixel counts as a hotspot when it's above both the scene's 95th percentile and
3.0 mg/m3. The percentile alone flags junk on a uniformly murky day; the floor alone
ignores the day's conditions.

STATUS: prototype. "Elevated" is a same-day statistical outlier, not a validated bloom
classifier. The trajectory follows the nearest hotspot's distance day to day, not one
tagged patch of water, so if a patch near Qatar fades while an unrelated one appears
farther out, it reads as "receding" even though nothing moved.
"""

import json
import logging
import math
import re
from datetime import date, timedelta

import numpy as np

from .config import (
    CACHE_DIR,
    CHL_VARIABLE,
    GULF_SNAPSHOT_FILE,
    GULF_TRAJECTORY_FILE,
    GULF_WATCH_BBOX,
    NRT_CHL_DATASET_ID,
    QATAR_REFERENCE_POINT,
    STATIC_DASHBOARD_HTML,
)
from .satellite import download_day, download_latest_day, is_not_published

log = logging.getLogger(__name__)

ELEVATED_PERCENTILE = 95
ELEVATED_MIN_VALUE = 3.0  # mg/m3

# Days in the trajectory window. Some will have no published or usable scene; those
# stay missing instead of being filled in.
TRAJECTORY_WINDOW_DAYS = 10

# Two points always make a line. Below this many usable days, don't call a trend.
MIN_POINTS_FOR_TREND = 4

# km/day. Blooms have been seen drifting tens of km a day on Gulf currents, so a few
# km/day is noise; a sustained 5+ km/day across the window is worth flagging.
APPROACHING_SLOPE_KM_PER_DAY = -5.0
RECEDING_SLOPE_KM_PER_DAY = 5.0

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two points, in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def distance_to_qatar_km(lat, lon) -> float:
    return haversine_km(lat, lon, QATAR_REFERENCE_POINT["lat"], QATAR_REFERENCE_POINT["lon"])


def download_gulf_scene(day: date):
    return download_day(NRT_CHL_DATASET_ID, [CHL_VARIABLE], GULF_WATCH_BBOX, day, CACHE_DIR / "gulf", "gulf")


def scan_for_hotspots(scene_path) -> list[dict]:
    """Every hotspot pixel in a scene, nearest to Qatar first."""
    import xarray as xr

    with xr.open_dataset(scene_path) as scene:
        chl = scene[CHL_VARIABLE]
        if "time" in chl.dims:
            chl = chl.mean(dim="time")  # a one-day file still has a time axis of length 1
        values = chl.values
        lats = chl["latitude"].values
        lons = chl["longitude"].values

    valid = values[~np.isnan(values)]
    if len(valid) == 0:
        return []

    cutoff = max(float(np.percentile(valid, ELEVATED_PERCENTILE)), ELEVATED_MIN_VALUE)
    hotspots = []
    for row, col in zip(*np.where(values > cutoff)):
        lat, lon = float(lats[row]), float(lons[col])
        hotspots.append({
            "lat": lat,
            "lon": lon,
            "value": float(values[row, col]),
            "distance_km": distance_to_qatar_km(lat, lon),
        })
    hotspots.sort(key=lambda h: h["distance_km"])
    return hotspots


def scan_today(today: date | None = None) -> dict:
    """Snapshot of the newest published scene. Writes gulf_bloom_watch.json."""
    scene_path, scene_date = download_latest_day(download_gulf_scene, today or date.today())
    log.info("Scanning the wider Gulf for elevated chlorophyll patches (%s) ...", scene_date)
    hotspots = scan_for_hotspots(scene_path)
    nearest = hotspots[0] if hotspots else None

    result = {
        "date": scene_date.isoformat(),
        "hotspot_count": len(hotspots),
        "nearest_km": round(nearest["distance_km"], 1) if nearest else None,
        "nearest_location": {"lat": nearest["lat"], "lon": nearest["lon"]} if nearest else None,
        "hotspots": hotspots[:50],
    }
    _write_json(GULF_SNAPSHOT_FILE, result)

    if nearest:
        log.warning(
            "%d elevated patch(es) in the wider Gulf. Nearest is ~%.0f km from Qatar's coast "
            "(%.2f mg/m3 at %.2f, %.2f).",
            len(hotspots), nearest["distance_km"], nearest["value"], nearest["lat"], nearest["lon"],
        )
    else:
        log.info("No elevated chlorophyll patches in the wider Gulf for %s.", scene_date)
    return result


def build_daily_series(end_date: date, window_days: int) -> list[dict]:
    """One record per day, oldest first. nearest_km is None when there's no usable scene.

    A missing day is left missing, never interpolated: a guessed value would manufacture
    a trend that isn't there.
    """
    records = []
    for offset in range(window_days - 1, -1, -1):
        day = end_date - timedelta(days=offset)
        log.info("Trajectory: checking %s ...", day)
        try:
            scene_path = download_gulf_scene(day)
        except Exception as exc:
            if not is_not_published(exc):
                raise
            log.info("  no published scene for %s yet, skipping", day)
            records.append({"date": day.isoformat(), "nearest_km": None, "hotspot_count": 0})
            continue

        hotspots = scan_for_hotspots(scene_path)
        records.append({
            "date": day.isoformat(),
            "nearest_km": round(hotspots[0]["distance_km"], 1) if hotspots else None,
            "hotspot_count": len(hotspots),
        })
    return records


def compute_trend(daily_records: list[dict]) -> dict:
    """Straight-line fit of nearest_km against day. Negative slope = getting closer."""
    usable = [(i, r["nearest_km"]) for i, r in enumerate(daily_records) if r["nearest_km"] is not None]

    if len(usable) < MIN_POINTS_FOR_TREND:
        return {
            "verdict": "insufficient_data",
            "slope_km_per_day": None,
            "usable_days": len(usable),
            "message": f"Only {len(usable)} usable day(s) in the window (need {MIN_POINTS_FOR_TREND}+) "
                       f"-- too many gaps (cloud cover / publication lag) to call a trend.",
        }

    days = np.array([i for i, _ in usable], dtype=float)
    distances = np.array([km for _, km in usable], dtype=float)
    slope = float(np.polyfit(days, distances, 1)[0])

    if slope <= APPROACHING_SLOPE_KM_PER_DAY:
        verdict = "approaching"
        message = f"Nearest hotspot has closed in by ~{-slope:.1f} km/day over the last {len(usable)} usable days."
    elif slope >= RECEDING_SLOPE_KM_PER_DAY:
        verdict = "receding"
        message = f"Nearest hotspot has been moving away, ~{slope:.1f} km/day over the last {len(usable)} usable days."
    else:
        verdict = "no_clear_trend"
        message = f"Nearest-hotspot distance is roughly flat (~{slope:+.1f} km/day) -- no clear approach or retreat."

    return {"verdict": verdict, "slope_km_per_day": round(slope, 2), "usable_days": len(usable), "message": message}


def track_trajectory(end_date: date | None = None, window_days: int = TRAJECTORY_WINDOW_DAYS) -> dict:
    """Nearest-hotspot distance over the last `window_days`. Writes gulf_bloom_trajectory.json."""
    end_date = end_date or date.today()

    # If today's snapshot already found the newest published day, end the window there,
    # so the snapshot and the trajectory agree on what "today" is.
    if GULF_SNAPSHOT_FILE.exists():
        snapshot_date = date.fromisoformat(json.loads(GULF_SNAPSHOT_FILE.read_text())["date"])
        end_date = min(end_date, snapshot_date)

    daily = build_daily_series(end_date, window_days)
    trend = compute_trend(daily)
    result = {"window_end_date": end_date.isoformat(), "window_days": window_days, "daily": daily, "trend": trend}
    _write_json(GULF_TRAJECTORY_FILE, result)

    if trend["verdict"] == "approaching":
        log.warning("TRAJECTORY: %s", trend["message"])
    else:
        log.info("TRAJECTORY: %s", trend["message"])
    return result


# The static dashboard embeds its data as JS literals, because fetch() of a local JSON
# file fails when the page is opened as file://. Only this one line is replaced.
DASHBOARD_TRAJECTORY_LINE = re.compile(r"var GULF_TRAJECTORY = .*?;", re.DOTALL)


def publish_trajectory_to_dashboard(trajectory_file=GULF_TRAJECTORY_FILE, html_file=STATIC_DASHBOARD_HTML) -> None:
    """Put the latest trajectory into the static dashboard, leaving the rest byte-for-byte."""
    if not trajectory_file.exists():
        raise FileNotFoundError(f"{trajectory_file} not found. Run `python -m bloomwatch trajectory` first.")

    trajectory = json.loads(trajectory_file.read_text(encoding="utf-8"))
    html = html_file.read_text(encoding="utf-8")
    if not DASHBOARD_TRAJECTORY_LINE.search(html):
        raise ValueError(f"Couldn't find 'var GULF_TRAJECTORY = ...;' in {html_file}.")

    replacement = "var GULF_TRAJECTORY = " + json.dumps(trajectory) + ";"
    html = DASHBOARD_TRAJECTORY_LINE.sub(lambda _: replacement, html, count=1)
    html_file.write_text(html, encoding="utf-8", newline="")
    log.info(
        "Updated %s with trajectory data through %s (trend: %s).",
        html_file.name, trajectory["window_end_date"], trajectory["trend"]["verdict"],
    )


def _write_json(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    log.info("Results written to %s", path)
