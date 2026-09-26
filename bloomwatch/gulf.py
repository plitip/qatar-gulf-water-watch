"""
Wider-Gulf watch: is a bloom building out at sea, and is it heading for Qatar?

The intake check only sees water that has already reached the intakes. Real warning
time comes from spotting an elevated patch between the Strait of Hormuz and Qatar
days before it drifts in, the way the UAE's satellite system watches its own coast.

A pixel counts as a hotspot when it's unusual for that exact spot at that time of year:
more than 3 standard deviations above its own normal (every day of the same month in
2018-2025, compared as log10, because chlorophyll is heavily skewed), above 3.0 mg/m3,
and part of a patch of at least 4 touching pixels. A bloom is a patch, not one pixel.

This replaced a "top 5% of today's scene" rule. Run on real data (September 2026), that
rule flagged ~5% of pixels every day by definition (exactly 462 each day), and the
nearest was always Doha's permanently murky shoreline, so the trajectory couldn't see
anything offshore.

Why 3 standard deviations: the box has about 9,200 sea pixels, so a 2-SD cutoff would flag
~210 pixels a day by chance alone; 3 SD flags ~12, and the patch rule removes most of those.
The 2008 backtest is how this should be tuned.

STATUS: prototype. "Unusual" isn't the same as "bloom": sediment after a storm is
unusual too. The trajectory follows the nearest hotspot's distance day to day, not one
tagged patch of water, so if a patch near Qatar fades while an unrelated one appears
farther out, it reads as "receding" even though nothing moved.
"""

import calendar
import collections
import json
import logging
import math
from datetime import date, timedelta

import numpy as np

from .config import (
    CACHE_DIR,
    CHL_VARIABLE,
    DAILY_REPROCESSED_CHL_DATASET_ID,
    GULF_SNAPSHOT_FILE,
    GULF_TRAJECTORY_FILE,
    GULF_WATCH_BBOX,
    NORMAL_YEARS,
    NRT_CHL_DATASET_ID,
    QATAR_REFERENCE_POINT,
)
from .satellite import download_day, download_latest_day, download_subset, is_not_published

log = logging.getLogger(__name__)

ANOMALY_Z_THRESHOLD = 3.0  # standard deviations above the pixel's own normal
ELEVATED_MIN_VALUE = 3.0   # mg/m3; ignores clear water going from 0.1 to 0.4
MIN_PATCH_PIXELS = 4       # touching anomalous pixels needed to count as a patch
MIN_LOG_STD = 0.05         # floor on a pixel's spread, so a very steady pixel can't flag on a tiny change

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


def download_archive_month(year: int, month: int):
    """Every day of one month from the daily reprocessed archive, over the Gulf box, in one file."""
    last_day = calendar.monthrange(year, month)[1]
    return download_subset(
        DAILY_REPROCESSED_CHL_DATASET_ID,
        [CHL_VARIABLE],
        GULF_WATCH_BBOX,
        start=f"{year}-{month:02d}-01T00:00:00",
        end=f"{year}-{month:02d}-{last_day}T23:59:59",
        cache_dir=CACHE_DIR / "climatology",
        filename=f"gulf_daily_{year}-{month:02d}.nc",
    )


def load_monthly_normal(month: int) -> tuple[np.ndarray, np.ndarray]:
    """Each pixel's normal for a calendar month: mean and std of log10(chlorophyll) over
    every day of that month in NORMAL_YEARS. Built once per month (8 small downloads),
    then read from the cache.

    Built from daily data on purpose: a single day swings much more than a monthly
    average, so a normal made of monthly averages makes ordinary days look extreme.
    """
    path = CACHE_DIR / "climatology" / f"normal_{month:02d}.npz"
    if path.exists():
        saved = np.load(path)
        return saved["mean"], saved["std"]

    import xarray as xr

    log.info("Building the normal for month %d from %d-%d daily data ...", month, NORMAL_YEARS[0], NORMAL_YEARS[-1])
    days = []
    for year in NORMAL_YEARS:
        with xr.open_dataset(download_archive_month(year, month)) as data:
            days.append(data[CHL_VARIABLE].load())

    log_chl = np.log10(xr.concat(days, "time").where(lambda chl: chl > 0))
    mean, std = log_chl.mean("time").values, log_chl.std("time").values
    np.savez(path, mean=mean, std=std)
    return mean, std


def find_anomalies(values: np.ndarray, normal_mean: np.ndarray, normal_std: np.ndarray):
    """Which pixels are hotspots, and by how much. Returns (z-score grid, hotspot mask)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (np.log10(np.where(values > 0, values, np.nan)) - normal_mean) / np.maximum(normal_std, MIN_LOG_STD)
    mask = (z > ANOMALY_Z_THRESHOLD) & (values > ELEVATED_MIN_VALUE)  # NaN (land, no data) compares False
    return z, keep_patches(mask, MIN_PATCH_PIXELS)


def keep_patches(mask: np.ndarray, min_pixels: int) -> np.ndarray:
    """Drop flagged pixels that aren't part of a group of `min_pixels` touching pixels
    (touching = sharing an edge). Walks each group once with a stack."""
    keep = np.zeros_like(mask, dtype=bool)
    seen = np.zeros_like(mask, dtype=bool)
    rows, cols = mask.shape
    for start in zip(*np.nonzero(mask)):
        if seen[start]:
            continue
        seen[start] = True
        patch, stack = [], [start]
        while stack:
            r, c = stack.pop()
            patch.append((r, c))
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nr < rows and 0 <= nc < cols and mask[nr, nc] and not seen[nr, nc]:
                    seen[nr, nc] = True
                    stack.append((nr, nc))
        if len(patch) >= min_pixels:
            for pixel in patch:
                keep[pixel] = True
    return keep


def scan_for_hotspots(scene_path, normal=None) -> list[dict]:
    """Every hotspot pixel in a one-day scene file, nearest to Qatar first.

    `normal` is (mean, std) for the scene's month; by default it's loaded (or built)
    for whatever month the scene is from.
    """
    import xarray as xr

    with xr.open_dataset(scene_path) as scene:
        chl = scene[CHL_VARIABLE]
        month = int(np.atleast_1d(chl["time"].dt.month.values)[0])
        if "time" in chl.dims:
            chl = chl.mean(dim="time")  # a one-day file still has a time axis of length 1
        return hotspots_in_grid(chl.values, chl["latitude"].values, chl["longitude"].values, month, normal)


def hotspots_in_grid(values, lats, lons, month: int, normal=None) -> list[dict]:
    """Same as scan_for_hotspots, for one day's grid that's already in memory."""
    normal_mean, normal_std = normal if normal is not None else load_monthly_normal(month)
    if normal_mean.shape != values.shape:
        raise ValueError(f"Scene grid {values.shape} doesn't match the normal's grid {normal_mean.shape}.")

    z, hotspot_mask = find_anomalies(values, normal_mean, normal_std)
    hotspots = []
    for row, col in zip(*np.nonzero(hotspot_mask)):
        lat, lon = float(lats[row]), float(lons[col])
        hotspots.append({
            "lat": lat,
            "lon": lon,
            "value": float(values[row, col]),
            "anomaly_z": round(float(z[row, col]), 2),
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


def build_daily_series(end_date: date, window_days: int, pixel_counts=None) -> list[dict]:
    """One record per day, oldest first.

    nearest_km is None when there's nothing to measure. hotspot_count tells the two cases
    apart: 0 means the scene was checked and nothing was found, None means there was no
    scene. A missing day is left missing, never interpolated: a guessed value would
    manufacture a trend that isn't there. If `pixel_counts` (a Counter) is given, it
    counts on how many days each pixel was a hotspot.
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
            records.append({"date": day.isoformat(), "nearest_km": None, "hotspot_count": None})
            continue

        hotspots = scan_for_hotspots(scene_path)
        if pixel_counts is not None:
            pixel_counts.update((round(h["lat"], 4), round(h["lon"], 4)) for h in hotspots)
        records.append({
            "date": day.isoformat(),
            "nearest_km": round(hotspots[0]["distance_km"], 1) if hotspots else None,
            "hotspot_count": len(hotspots),
        })
    return records


COMPASS_POINTS = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
GRID_STEP_DEG = 1 / 24  # the 4 km product's grid spacing


def recurring_area(pixel_counts, days_with_patches: int, land_points) -> dict | None:
    """Where unusual water kept coming back over the window, in words the page can use.

    Takes the pixels that were hotspots on at least half the days that had any, keeps the
    largest group of touching ones, and describes its centre: distance and direction from
    Doha, and distance from the nearest land. None when nothing recurred.
    """
    if days_with_patches == 0:
        return None
    min_days = max(2, math.ceil(days_with_patches / 2))
    recurring = {p for p, n in pixel_counts.items() if n >= min_days}
    if not recurring:
        return None

    # Group touching squares on whole-number grid indices; adding 1/24 to rounded coordinates
    # drifts, and neighbours stop matching.
    by_index = {(math.floor(lat / GRID_STEP_DEG), math.floor(lon / GRID_STEP_DEG)): (lat, lon) for lat, lon in recurring}
    groups, seen = [], set()
    for start in by_index:
        if start in seen:
            continue
        seen.add(start)
        group, stack = [], [start]
        while stack:
            row, col = stack.pop()
            group.append(by_index[(row, col)])
            for neighbour in ((row + 1, col), (row - 1, col), (row, col + 1), (row, col - 1)):
                if neighbour in by_index and neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        groups.append(group)
    largest = max(groups, key=len)

    lat = sum(p[0] for p in largest) / len(largest)
    lon = sum(p[1] for p in largest) / len(largest)
    origin = QATAR_REFERENCE_POINT
    bearing = math.degrees(math.atan2(
        (lon - origin["lon"]) * math.cos(math.radians(origin["lat"])), lat - origin["lat"]
    )) % 360
    return {
        "pixels": len(largest),
        "min_days": min_days,
        "lat": round(lat, 3),
        "lon": round(lon, 3),
        "km_from_doha": round(distance_to_qatar_km(lat, lon)),
        "direction_from_doha": COMPASS_POINTS[round(bearing / 45) % 8],
        "km_from_shore": round(min(haversine_km(lat, lon, la, lo) for la, lo in land_points)) if land_points else None,
    }


def land_points_from_scene(scene_path) -> list[tuple[float, float]]:
    """Centres of the land (no-data) pixels in a scene: the gap-free product only leaves land empty."""
    import xarray as xr

    with xr.open_dataset(scene_path) as scene:
        chl = scene[CHL_VARIABLE]
        values = chl.values[0] if "time" in chl.dims else chl.values
        lats, lons = chl["latitude"].values, chl["longitude"].values
    rows, cols = np.nonzero(np.isnan(values))
    return [(float(lats[r]), float(lons[c])) for r, c in zip(rows, cols)]


def compute_trend(daily_records: list[dict]) -> dict:
    """Straight-line fit of nearest_km against day. Negative slope = getting closer."""
    usable = [(i, r["nearest_km"]) for i, r in enumerate(daily_records) if r["nearest_km"] is not None]

    if len(usable) < MIN_POINTS_FOR_TREND:
        return {
            "verdict": "insufficient_data",
            "slope_km_per_day": None,
            "usable_days": len(usable),
            "message": f"Only {len(usable)} day(s) with a measurable patch (at least {MIN_POINTS_FOR_TREND} needed), "
                       f"too few to judge movement.",
        }

    days = np.array([i for i, _ in usable], dtype=float)
    distances = np.array([km for _, km in usable], dtype=float)
    slope = float(np.polyfit(days, distances, 1)[0])

    if slope <= APPROACHING_SLOPE_KM_PER_DAY:
        verdict = "approaching"
        message = f"The nearest unusual patch moved about {-slope:.0f} km a day closer to Doha over {len(usable)} days."
    elif slope >= RECEDING_SLOPE_KM_PER_DAY:
        verdict = "receding"
        message = f"The nearest unusual patch moved about {slope:.0f} km a day away from Doha over {len(usable)} days."
    else:
        verdict = "no_clear_trend"
        message = f"The nearest unusual patch stayed at about the same distance from Doha ({slope:+.1f} km a day)."

    return {"verdict": verdict, "slope_km_per_day": round(slope, 2), "usable_days": len(usable), "message": message}


def track_trajectory(end_date: date | None = None, window_days: int = TRAJECTORY_WINDOW_DAYS) -> dict:
    """Nearest-hotspot distance over the last `window_days`. Writes gulf_bloom_trajectory.json."""
    end_date = end_date or date.today()

    # If today's snapshot already found the newest published day, end the window there,
    # so the snapshot and the trajectory agree on what "today" is.
    if GULF_SNAPSHOT_FILE.exists():
        snapshot_date = date.fromisoformat(json.loads(GULF_SNAPSHOT_FILE.read_text())["date"])
        end_date = min(end_date, snapshot_date)

    pixel_counts = collections.Counter()
    daily = build_daily_series(end_date, window_days, pixel_counts)
    trend = compute_trend(daily)
    days_with_patches = sum(1 for d in daily if d["hotspot_count"])
    land = []
    if days_with_patches:  # at least one scene exists, so the land mask can come from the latest one
        latest_scene_day = next(d["date"] for d in reversed(daily) if d["hotspot_count"] is not None)
        land = land_points_from_scene(download_gulf_scene(date.fromisoformat(latest_scene_day)))
    result = {
        "window_end_date": end_date.isoformat(),
        "window_days": window_days,
        "daily": daily,
        "trend": trend,
        "recurring_area": recurring_area(pixel_counts, days_with_patches, land),
    }
    _write_json(GULF_TRAJECTORY_FILE, result)

    if trend["verdict"] == "approaching":
        log.warning("TRAJECTORY: %s", trend["message"])
    else:
        log.info("TRAJECTORY: %s", trend["message"])
    return result


def _write_json(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    log.info("Results written to %s", path)
