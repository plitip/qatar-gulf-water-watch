"""
Where would today's hotspots drift if the current held steady?

This is a physics projection, not a trained prediction. There aren't nearly enough
confirmed Gulf blooms to train or validate a model, and pretending otherwise would
dress a guess up as something more rigorous.

For each of the nearest hotspots: sample the ocean current (eastward / northward
velocity) where it sits, then move it forward in straight daily steps assuming that
same current holds for the whole window. Currents change day to day, so read the
output as "if today's current kept going, this patch would be closest to the coast
around day N", not as an arrival time.

STATUS: the path math is tested on synthetic cases. The currents dataset ID is confirmed,
but this hasn't been run against real current data yet.
"""

import json
import logging
import math
from datetime import date

from .config import (
    CACHE_DIR,
    CURRENT_U_VARIABLE,
    CURRENT_V_VARIABLE,
    CURRENTS_DATASET_ID,
    GULF_WATCH_BBOX,
    PROJECTION_FILE,
)
from .gulf import distance_to_qatar_km, download_gulf_scene, scan_for_hotspots
from .satellite import download_day, download_latest_day

log = logging.getLogger(__name__)

CURRENT_SAMPLE_RADIUS_DEG = 0.1  # one grid cell's current is noisy; average a small box
PROJECTION_HORIZON_DAYS = 10
ARRIVAL_THRESHOLD_KM = 20        # this close to the coast counts as "reached it"
TOP_N_HOTSPOTS = 5               # projecting dozens of hotspots buries the signal

SECONDS_PER_DAY = 86_400
METERS_PER_DEGREE_LAT = 111_320  # WGS84 approximation, fine at this scale


def download_current_scene(day: date):
    return download_day(
        CURRENTS_DATASET_ID,
        [CURRENT_U_VARIABLE, CURRENT_V_VARIABLE],
        GULF_WATCH_BBOX,
        day,
        CACHE_DIR / "currents",
        "currents",
    )


def sample_current_at_point(scene_path, lat: float, lon: float) -> tuple[float, float]:
    """Mean near-surface (u, v) in m/s in a small box around the point."""
    import xarray as xr

    with xr.open_dataset(scene_path) as scene:
        box = scene.sel(
            latitude=slice(lat - CURRENT_SAMPLE_RADIUS_DEG, lat + CURRENT_SAMPLE_RADIUS_DEG),
            longitude=slice(lon - CURRENT_SAMPLE_RADIUS_DEG, lon + CURRENT_SAMPLE_RADIUS_DEG),
        )
        if "depth" in box.dims:
            box = box.isel(depth=0)  # shallowest level
        if "time" in box.dims:
            box = box.mean(dim="time")
        u = float(box[CURRENT_U_VARIABLE].mean(skipna=True).values)
        v = float(box[CURRENT_V_VARIABLE].mean(skipna=True).values)
    return u, v


def project_hotspot_path(lat: float, lon: float, u: float, v: float, horizon_days: int) -> list[dict]:
    """Position and distance to Qatar for day 0..horizon_days, under a constant (u, v) in m/s."""
    meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(lat))
    path = []
    for day in range(horizon_days + 1):
        seconds = day * SECONDS_PER_DAY
        proj_lat = lat + (v * seconds) / METERS_PER_DEGREE_LAT
        proj_lon = lon + ((u * seconds) / meters_per_degree_lon if meters_per_degree_lon else 0.0)
        path.append({
            "day": day,
            "lat": round(proj_lat, 4),
            "lon": round(proj_lon, 4),
            "distance_km": round(distance_to_qatar_km(proj_lat, proj_lon), 1),
        })
    return path


def summarize_path(path: list[dict]) -> dict:
    closest = min(path, key=lambda p: p["distance_km"])
    return {
        "closest_approach_day": closest["day"],
        "closest_approach_km": closest["distance_km"],
        "reaches_coast_in_window": closest["distance_km"] <= ARRIVAL_THRESHOLD_KM,
    }


def project_hotspots(today: date | None = None) -> dict:
    """Project the nearest hotspots in the newest scene. Writes gulf_bloom_prediction.json."""
    scene_path, scene_date = download_latest_day(download_gulf_scene, today or date.today())
    hotspots = scan_for_hotspots(scene_path)[:TOP_N_HOTSPOTS]
    result = {"date": scene_date.isoformat(), "projections": []}

    if not hotspots:
        log.info("No hotspots to project for %s.", scene_date)
    else:
        # Currents for the same day as the chlorophyll scene, so both describe the same water.
        current_scene = download_current_scene(scene_date)
        for hotspot in hotspots:
            u, v = sample_current_at_point(current_scene, hotspot["lat"], hotspot["lon"])
            path = project_hotspot_path(hotspot["lat"], hotspot["lon"], u, v, PROJECTION_HORIZON_DAYS)
            summary = summarize_path(path)
            result["projections"].append({
                "start": {"lat": hotspot["lat"], "lon": hotspot["lon"], "value": hotspot["value"]},
                "current_m_s": {"u": round(u, 3), "v": round(v, 3)},
                "path": path,
                "summary": summary,
            })
            if summary["reaches_coast_in_window"]:
                log.warning(
                    "Hotspot at (%.2f, %.2f) comes within %.0f km of the coast around day %d "
                    "if today's current (%.2f, %.2f m/s) holds.",
                    hotspot["lat"], hotspot["lon"], summary["closest_approach_km"],
                    summary["closest_approach_day"], u, v,
                )
            else:
                log.info(
                    "Hotspot at (%.2f, %.2f): closest approach %.0f km on day %d, not projected to "
                    "reach the coast within %d days.",
                    hotspot["lat"], hotspot["lon"], summary["closest_approach_km"],
                    summary["closest_approach_day"], PROJECTION_HORIZON_DAYS,
                )

    PROJECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECTION_FILE.write_text(json.dumps(result, indent=2))
    log.info("Results written to %s", PROJECTION_FILE)
    return result
