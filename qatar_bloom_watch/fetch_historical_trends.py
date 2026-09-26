"""
fetch_historical_trends.py

One-off: pull several years of monthly chlorophyll-a history for Qatar's
three desal intakes from Copernicus Marine's reprocessed archive (the
"_my_" dataset, which goes back to 1997 — unlike the near-real-time
dataset used day-to-day, which only keeps a rolling ~2 week window).

This is for context/visualization (a "how does today compare to years
of normal variation" dashboard), not for the daily anomaly detector —
that still runs on qatar_bloom_watch.py with the NRT dataset.

Output: historical_chl_trends.csv, one row per (site, month).

RUN:
    python fetch_historical_trends.py
"""

import csv
import os
from datetime import date

from qatar_bloom_watch import DESAL_INTAKE_SITES, INTAKE_SAMPLE_RADIUS_DEG, log

# Monthly, gap-free, reprocessed ("multi-year") chlorophyll-a.
# Confirmed via `copernicusmarine describe --contains CHL`
# (product OCEANCOLOUR_GLO_BGC_L4_MY_009_104).
HISTORICAL_DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1M"
HISTORICAL_VARIABLE = "CHL"

START_DATE = date(2018, 1, 1)   # how far back to go; adjust freely
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
SCENE_DIR = os.path.join(OUTPUT_DIR, "chl_historical_data")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "historical_chl_trends.csv")


def fetch_full_history_scene() -> str:
    """Download one file covering the whole date range in one shot."""
    import copernicusmarine

    os.makedirs(SCENE_DIR, exist_ok=True)
    scene_filename = f"chl_monthly_{START_DATE.isoformat()}_to_present.nc"
    scene_path = os.path.join(SCENE_DIR, scene_filename)

    if os.path.exists(scene_path):
        log.info("Using cached historical scene (%s)", scene_filename)
        return scene_path

    # Bounding box covering Qatar's coastline (same as the daily script)
    bbox = {"min_lon": 50.5, "max_lon": 52.5, "min_lat": 24.4, "max_lat": 26.3}

    log.info("Downloading monthly chlorophyll history from %s to present ...", START_DATE)
    copernicusmarine.subset(
        dataset_id=HISTORICAL_DATASET_ID,
        variables=[HISTORICAL_VARIABLE],
        minimum_longitude=bbox["min_lon"],
        maximum_longitude=bbox["max_lon"],
        minimum_latitude=bbox["min_lat"],
        maximum_latitude=bbox["max_lat"],
        start_datetime=f"{START_DATE.isoformat()}T00:00:00",
        output_filename=scene_filename,
        output_directory=SCENE_DIR,
    )
    return scene_path


def extract_site_time_series(scene_path: str) -> list[dict]:
    """Turn the downloaded cube into one row per (site, month)."""
    import xarray as xr

    rows = []
    with xr.open_dataset(scene_path) as scene:
        for site_name, coord in DESAL_INTAKE_SITES.items():
            site_series = scene[HISTORICAL_VARIABLE].sel(
                latitude=slice(
                    coord["lat"] - INTAKE_SAMPLE_RADIUS_DEG,
                    coord["lat"] + INTAKE_SAMPLE_RADIUS_DEG,
                ),
                longitude=slice(
                    coord["lon"] - INTAKE_SAMPLE_RADIUS_DEG,
                    coord["lon"] + INTAKE_SAMPLE_RADIUS_DEG,
                ),
            ).mean(dim=["latitude", "longitude"], skipna=True)

            for time_value, chl_value in zip(site_series["time"].values, site_series.values):
                month_str = str(time_value)[:7]  # "YYYY-MM"
                rows.append({
                    "site": site_name,
                    "month": month_str,
                    "chlorophyll_mg_m3": None if chl_value != chl_value else round(float(chl_value), 3),
                })
    return rows


def main() -> None:
    scene_path = fetch_full_history_scene()
    rows = extract_site_time_series(scene_path)

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["site", "month", "chlorophyll_mg_m3"])
        writer.writeheader()
        writer.writerows(rows)

    log.info("Wrote %d rows to %s", len(rows), OUTPUT_CSV)


if __name__ == "__main__":
    main()
