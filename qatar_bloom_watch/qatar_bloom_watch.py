"""
qatar_bloom_watch.py

Harmful algal bloom ("red tide") early-warning prototype for Qatar's
desalination intakes.

Qatar draws almost all of its drinking water from seawater desalination,
which makes it structurally exposed to a recurring Gulf hazard: harmful
algal blooms that clog intake filters and have repeatedly forced plants
elsewhere in the Gulf (UAE, Saudi Arabia) offline for days at a time.
The UAE and Saudi Arabia already run satellite-based early-warning
systems for their own plants; this script is a first step toward the
same thing for Qatar's Ras Laffan, Ras Abu Fontas, and Umm Al Houl
intakes, using free Copernicus Marine ocean-colour satellite data.

Because the Gulf is shallow, dusty, and sediment-heavy, raw chlorophyll
readings are noisy and a fixed global threshold produces constant false
alarms. Instead, each intake point is compared against its OWN recent
history (a rolling mean/std baseline), so an alert means "unusual for
this specific spot," not "unusual in general."

SETUP (one time):
    pip install -r requirements.txt
    copernicusmarine login          # free account at marine.copernicus.eu

RUN:
    python qatar_bloom_watch.py

STATUS: prototype. Before this could inform a real operational decision
it needs ground-truth validation against water samples, agreement with
Kahramaa/QEWC on the intake coordinates, and threshold tuning against
known historical bloom events.
"""

import json
import logging
import os
import sys
from datetime import date, timedelta

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("qatar_bloom_watch")


# --- Configuration -----------------------------------------------------

# Offshore coordinates near each plant's seawater intake. These are
# approximate — confirm against the actual facility footprint (e.g. via
# satellite imagery or QEWC/Kahramaa) before using this operationally.
DESAL_INTAKE_SITES = {
    "Ras Laffan": {"lat": 25.9200, "lon": 51.5900},
    "Ras Abu Fontas": {"lat": 25.1300, "lon": 51.6100},
    "Umm Al Houl": {"lat": 24.9500, "lon": 51.5700},
}

# Bounding box covering Qatar's coastline and nearby Gulf waters
QATAR_COAST_BBOX = {
    "min_lon": 50.5,
    "max_lon": 52.5,
    "min_lat": 24.4,
    "max_lat": 26.3,
}

# Copernicus Marine dataset supplying daily, gap-free chlorophyll-a.
# Dataset IDs occasionally change when Copernicus reprocesses a product.
# If this ID starts failing, find the current one with:
#   copernicusmarine describe --contains CHL
# and look for a "plankton" or "chl" dataset with "_P1D" (daily) in its id.
CHLOROPHYLL_DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D"
# (confirmed via `copernicusmarine describe --contains CHL`, product OCEANCOLOUR_GLO_BGC_L4_NRT_009_102)
CHLOROPHYLL_VARIABLE = "CHL"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SATELLITE_SCENE_DIR = os.path.join(PROJECT_DIR, "chl_data")
READING_HISTORY_FILE = os.path.join(PROJECT_DIR, "chl_history.json")

INTAKE_SAMPLE_RADIUS_DEG = 0.05    # ~5 km box averaged around each intake
BLOOM_ANOMALY_STD_THRESHOLD = 2.0  # flag readings this many std devs above baseline
MIN_BASELINE_DAYS = 14             # days of history required before trusting the baseline

# The near-real-time chlorophyll product isn't published instantly — it can
# lag several days behind the calendar date, depending on satellite pass
# and processing schedules. Rather than hardcode an assumed lag, we start
# at today and walk backward until we find a date the dataset actually has.
MAX_LOOKBACK_DAYS = 10


# --- Step 1: pull the most recent available satellite scene ----------------

def fetch_chlorophyll_scene_for_date(target_date: date) -> str:
    """Download (or reuse a cached) chlorophyll-a scene for a specific date."""
    import copernicusmarine

    os.makedirs(SATELLITE_SCENE_DIR, exist_ok=True)
    scene_filename = f"chl_{target_date.isoformat()}.nc"
    scene_path = os.path.join(SATELLITE_SCENE_DIR, scene_filename)

    if os.path.exists(scene_path):
        log.info("Using cached scene for %s (%s)", target_date, scene_filename)
        return scene_path

    copernicusmarine.subset(
        dataset_id=CHLOROPHYLL_DATASET_ID,
        variables=[CHLOROPHYLL_VARIABLE],
        minimum_longitude=QATAR_COAST_BBOX["min_lon"],
        maximum_longitude=QATAR_COAST_BBOX["max_lon"],
        minimum_latitude=QATAR_COAST_BBOX["min_lat"],
        maximum_latitude=QATAR_COAST_BBOX["max_lat"],
        start_datetime=f"{target_date.isoformat()}T00:00:00",
        end_datetime=f"{target_date.isoformat()}T23:59:59",
        output_filename=scene_filename,
        output_directory=SATELLITE_SCENE_DIR,
    )
    return scene_path


def fetch_latest_available_scene(start_date: date) -> tuple[str, date]:
    """Try start_date, then walk backward until the dataset actually has data.

    The NRT chlorophyll product doesn't cover the current calendar date the
    moment it arrives — coverage trails by a variable number of days. We
    treat "out of bounds" as expected and keep stepping back; any other
    failure (auth, network, bad dataset id) is a real problem and stops
    the search immediately.
    """
    import copernicusmarine
    from copernicusmarine.catalogue_parser.models import DatasetNotFound

    candidate_date = start_date
    for attempt in range(MAX_LOOKBACK_DAYS):
        log.info("Trying chlorophyll scene for %s ...", candidate_date)
        try:
            scene_path = fetch_chlorophyll_scene_for_date(candidate_date)
            return scene_path, candidate_date
        except DatasetNotFound:
            log.error(
                "Dataset ID '%s' was not found in the Copernicus Marine catalogue. "
                "Dataset IDs change when products get reprocessed. Run:\n"
                "  copernicusmarine describe --contains CHL\n"
                "and update CHLOROPHYLL_DATASET_ID in this script with the current "
                "daily ('_P1D') chlorophyll ('plankton' or 'chl') dataset id.",
                CHLOROPHYLL_DATASET_ID,
            )
            raise
        except Exception as exc:
            if type(exc).__name__ == "CoordinatesOutOfDatasetBounds":
                log.info("No data yet for %s (not published), trying the day before ...", candidate_date)
                candidate_date -= timedelta(days=1)
                continue
            log.error(
                "Could not download the satellite scene: %s: %s\n"
                "This is usually a network/login issue or a permissions problem "
                "writing to the output folder. Check that 'copernicusmarine login' "
                "succeeded and that this machine can reach the Copernicus Marine "
                "servers.",
                type(exc).__name__, exc,
            )
            raise

    raise RuntimeError(
        f"No chlorophyll data found in the last {MAX_LOOKBACK_DAYS} days "
        f"(checked back from {start_date}). The dataset may be delayed "
        f"longer than usual, or something upstream has changed."
    )


# --- Step 2: average chlorophyll near each intake -------------------------

def sample_intake_readings(scene_path: str) -> dict[str, float]:
    """Average chlorophyll-a in a small box around each desal intake."""
    import xarray as xr

    readings = {}
    with xr.open_dataset(scene_path) as scene:
        for site_name, coord in DESAL_INTAKE_SITES.items():
            local_patch = scene[CHLOROPHYLL_VARIABLE].sel(
                latitude=slice(
                    coord["lat"] - INTAKE_SAMPLE_RADIUS_DEG,
                    coord["lat"] + INTAKE_SAMPLE_RADIUS_DEG,
                ),
                longitude=slice(
                    coord["lon"] - INTAKE_SAMPLE_RADIUS_DEG,
                    coord["lon"] + INTAKE_SAMPLE_RADIUS_DEG,
                ),
            )
            mean_value = float(local_patch.mean(skipna=True).values)
            readings[site_name] = mean_value if not np.isnan(mean_value) else None

    return readings


# --- Step 3: rolling baseline + bloom anomaly check ------------------------

def load_reading_history() -> dict:
    if os.path.exists(READING_HISTORY_FILE):
        with open(READING_HISTORY_FILE) as f:
            return json.load(f)
    return {site: [] for site in DESAL_INTAKE_SITES}


def save_reading_history(history: dict) -> None:
    with open(READING_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def find_bloom_anomalies(today_readings: dict, history: dict, today_str: str) -> list[str]:
    """Compare today's reading at each intake against that intake's own baseline."""
    alerts = []

    for site_name, today_value in today_readings.items():
        if today_value is None:
            log.warning("No usable chlorophyll data for %s on %s (cloud cover?)", site_name, today_str)
            continue

        past_values = [value for _, value in history[site_name]]
        history[site_name].append((today_str, today_value))

        if len(past_values) < MIN_BASELINE_DAYS:
            log.info(
                "%s: %.2f mg/m3 (baseline still building: %d/%d days)",
                site_name, today_value, len(past_values), MIN_BASELINE_DAYS,
            )
            continue

        baseline_mean = np.mean(past_values)
        baseline_std = np.std(past_values)

        if baseline_std > 0 and today_value > baseline_mean + BLOOM_ANOMALY_STD_THRESHOLD * baseline_std:
            alerts.append(
                f"{site_name}: chlorophyll-a = {today_value:.2f} mg/m3, "
                f"baseline {baseline_mean:.2f} +/- {baseline_std:.2f} "
                f"-> {BLOOM_ANOMALY_STD_THRESHOLD:.0f} std devs above normal, possible bloom signal"
            )
        else:
            log.info("%s: %.2f mg/m3 (within normal range)", site_name, today_value)

    return alerts


# --- Main ------------------------------------------------------------------

def main() -> int:
    try:
        scene_path, scene_date = fetch_latest_available_scene(date.today())
    except Exception:
        return 1

    scene_date_str = scene_date.isoformat()
    if scene_date != date.today():
        log.info("Using most recent available scene: %s (data lags behind today)", scene_date_str)

    readings = sample_intake_readings(scene_path)
    history = load_reading_history()
    alerts = find_bloom_anomalies(readings, history, scene_date_str)
    save_reading_history(history)

    if alerts:
        log.warning("Possible bloom activity detected:")
        for alert in alerts:
            log.warning("  %s", alert)
        # TODO: send a real notification here (email, Telegram bot, Slack webhook)
        # instead of just logging, once this has been validated.
    else:
        log.info("No bloom anomalies detected for %s.", scene_date_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
