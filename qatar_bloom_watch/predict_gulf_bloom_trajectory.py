"""
predict_gulf_bloom_trajectory.py

A physics-based trajectory PROJECTION for the wider-Gulf hotspots found
by scan_gulf_for_approaching_blooms.py -- not a machine-learning
"prediction" in the statistical sense. There isn't remotely enough
confirmed-bloom ground truth in the Gulf to train or validate a model
like that; pretending otherwise would just dress up a guess as
something more rigorous than it is.

What this actually does: for each hotspot found today, sample the
ocean current (eastward/northward velocity) at that location from
Copernicus Marine's physics model, then advect the hotspot forward in
straight-line steps assuming that SAME current holds constant for the
whole projection window. That's a real simplification -- currents
shift day to day -- so treat the output as "if today's current kept
blowing this way, here's roughly where this patch would end up and
when it would be closest to the coast," not a guaranteed arrival time.
Good for a rough sense of urgency, not for anything operational.

STATUS: prototype, unverified dataset ID. CURRENT_DATASET_ID below is
my best-known match for Copernicus Marine's global ocean physics
analysis/forecast product (the one carrying eastward/northward
velocity, "uo"/"vo"), but I could not confirm it against the live
catalogue -- Copernicus Marine's servers aren't reachable from the
sandbox this was written in (same network restriction noted
elsewhere in this project). Before relying on this, run:
    copernicusmarine describe --contains uo
and confirm CURRENT_DATASET_ID / CURRENT_U_VARIABLE / CURRENT_V_VARIABLE
below still match a real, current dataset -- exactly like
qatar_bloom_watch.py already asks you to do for the chlorophyll ID if
that one ever starts failing.

RUN:
    python predict_gulf_bloom_trajectory.py
    (needs a Copernicus Marine login, same as the other scripts)
"""

import json
import math
import os
from datetime import date

from qatar_bloom_watch import log
from scan_gulf_for_approaching_blooms import (
    GULF_WATCH_BBOX,
    QATAR_REFERENCE_POINT,
    fetch_gulf_scene,
    haversine_km,
    scan_for_hotspots,
)

# Best-known match for Copernicus Marine's Global Ocean Physics
# Analysis and Forecast product (GLOBAL_ANALYSISFORECAST_PHY_001_024),
# split-variable "cur" (currents) dataset. UNVERIFIED -- see docstring.
CURRENT_DATASET_ID = "cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m"
CURRENT_U_VARIABLE = "uo"  # eastward velocity, m/s
CURRENT_V_VARIABLE = "vo"  # northward velocity, m/s

CURRENT_SCENE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gulf_current_data")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gulf_bloom_prediction.json")

# Box averaged around each hotspot to sample the current, same idea as
# INTAKE_SAMPLE_RADIUS_DEG in qatar_bloom_watch.py -- a single grid
# cell's current is noisy, a small local average is steadier.
CURRENT_SAMPLE_RADIUS_DEG = 0.1

# How many days ahead to project, and what counts as "reached the coast."
PROJECTION_HORIZON_DAYS = 10
ARRIVAL_THRESHOLD_KM = 20

# Only project the N nearest hotspots -- projecting all of them (can be
# dozens on a noisy day) would bury the signal in noise.
TOP_N_HOTSPOTS = 5

SECONDS_PER_DAY = 86400
METERS_PER_DEGREE_LAT = 111_320  # WGS84 approximation, good enough at this scale


def fetch_current_scene(target_date: date) -> str:
    """Download (or reuse a cached) current-velocity scene for a specific date."""
    import copernicusmarine

    os.makedirs(CURRENT_SCENE_DIR, exist_ok=True)
    filename = f"currents_{target_date.isoformat()}.nc"
    scene_path = os.path.join(CURRENT_SCENE_DIR, filename)
    if os.path.exists(scene_path):
        log.info("Using cached current scene for %s", target_date)
        return scene_path

    copernicusmarine.subset(
        dataset_id=CURRENT_DATASET_ID,
        variables=[CURRENT_U_VARIABLE, CURRENT_V_VARIABLE],
        minimum_longitude=GULF_WATCH_BBOX["min_lon"],
        maximum_longitude=GULF_WATCH_BBOX["max_lon"],
        minimum_latitude=GULF_WATCH_BBOX["min_lat"],
        maximum_latitude=GULF_WATCH_BBOX["max_lat"],
        start_datetime=f"{target_date.isoformat()}T00:00:00",
        end_datetime=f"{target_date.isoformat()}T23:59:59",
        output_filename=filename,
        output_directory=CURRENT_SCENE_DIR,
    )
    return scene_path


def sample_current_at_point(scene_path: str, lat: float, lon: float) -> tuple[float, float]:
    """Average eastward/northward velocity in a small box around (lat, lon).
    Returns (u, v) in m/s. Depth: near-surface, take the shallowest level
    if the product has a depth dimension."""
    import xarray as xr

    with xr.open_dataset(scene_path) as scene:
        box = scene.sel(
            latitude=slice(lat - CURRENT_SAMPLE_RADIUS_DEG, lat + CURRENT_SAMPLE_RADIUS_DEG),
            longitude=slice(lon - CURRENT_SAMPLE_RADIUS_DEG, lon + CURRENT_SAMPLE_RADIUS_DEG),
        )
        if "depth" in box.dims:
            box = box.isel(depth=0)
        if "time" in box.dims:
            box = box.mean(dim="time")

        u = float(box[CURRENT_U_VARIABLE].mean(skipna=True).values)
        v = float(box[CURRENT_V_VARIABLE].mean(skipna=True).values)
        return u, v


# --- The actual physics: constant-velocity advection ------------------

def project_hotspot_path(lat: float, lon: float, u: float, v: float, horizon_days: int) -> list[dict]:
    """Step a starting point forward day by day assuming (u, v) [m/s]
    holds constant for the whole window -- a straight-line projection,
    not a real evolving-current forecast. Returns one record per day,
    day 0 being the starting position."""
    path = []
    for day in range(horizon_days + 1):
        elapsed_seconds = day * SECONDS_PER_DAY
        d_lat = (v * elapsed_seconds) / METERS_PER_DEGREE_LAT
        meters_per_degree_lon = METERS_PER_DEGREE_LAT * math.cos(math.radians(lat))
        d_lon = (u * elapsed_seconds) / meters_per_degree_lon if meters_per_degree_lon else 0.0

        proj_lat, proj_lon = lat + d_lat, lon + d_lon
        dist = haversine_km(proj_lat, proj_lon, QATAR_REFERENCE_POINT["lat"], QATAR_REFERENCE_POINT["lon"])
        path.append({"day": day, "lat": round(proj_lat, 4), "lon": round(proj_lon, 4), "distance_km": round(dist, 1)})
    return path


def summarize_path(path: list[dict]) -> dict:
    closest = min(path, key=lambda p: p["distance_km"])
    return {
        "closest_approach_day": closest["day"],
        "closest_approach_km": closest["distance_km"],
        "reaches_coast_in_window": closest["distance_km"] <= ARRIVAL_THRESHOLD_KM,
    }


# --- Main ---------------------------------------------------------------

def main() -> None:
    scene_path = fetch_gulf_scene(date.today())
    hotspots = scan_for_hotspots(scene_path)[:TOP_N_HOTSPOTS]

    if not hotspots:
        log.info("No hotspots to project today -- nothing to do.")
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"date": date.today().isoformat(), "projections": []}, f, indent=2)
        return

    current_scene_path = fetch_current_scene(date.today())

    projections = []
    for hotspot in hotspots:
        u, v = sample_current_at_point(current_scene_path, hotspot["lat"], hotspot["lon"])
        path = project_hotspot_path(hotspot["lat"], hotspot["lon"], u, v, PROJECTION_HORIZON_DAYS)
        summary = summarize_path(path)
        projections.append({
            "start": {"lat": hotspot["lat"], "lon": hotspot["lon"], "value": hotspot["value"]},
            "current_m_s": {"u": round(u, 3), "v": round(v, 3)},
            "path": path,
            "summary": summary,
        })
        if summary["reaches_coast_in_window"]:
            log.warning(
                "Projected hotspot at (%.2f, %.2f) comes within %.0fkm of the coast around day %d "
                "if today's current (%.2f, %.2f m/s) holds.",
                hotspot["lat"], hotspot["lon"], summary["closest_approach_km"], summary["closest_approach_day"], u, v,
            )
        else:
            log.info(
                "Projected hotspot at (%.2f, %.2f): closest approach %.0fkm on day %d -- not projected to reach "
                "the coast within %d days under a constant-current assumption.",
                hotspot["lat"], hotspot["lon"], summary["closest_approach_km"], summary["closest_approach_day"],
                PROJECTION_HORIZON_DAYS,
            )

    with open(OUTPUT_FILE, "w") as f:
        json.dump({"date": date.today().isoformat(), "projections": projections}, f, indent=2)
    log.info("Full results written to %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()
