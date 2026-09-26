"""
Intake check: is the water at each desalination intake unusual today?

Each intake is judged against its own history, not a fixed threshold. The Gulf is
shallow, dusty and full of sediment, so one Gulf-wide chlorophyll cutoff would raise
constant false alarms. "Unusual for this exact spot" is the useful question.

Also here: backfilling that history so the baseline works from day one, and the
monthly 2018-present series the dashboards chart.

STATUS: the daily check and the monthly history have both run against real data. The
anomaly threshold hasn't been tuned against a real bloom, and the intake coordinates
are approximate.
"""

import csv
import json
import logging
from datetime import date, timedelta

import numpy as np

from .config import (
    CACHE_DIR,
    CHL_VARIABLE,
    DESAL_INTAKE_SITES,
    INTAKE_HISTORY_FILE,
    MONTHLY_CHL_DATASET_ID,
    MONTHLY_HISTORY_CSV,
    NRT_CHL_DATASET_ID,
    QATAR_COAST_BBOX,
)
from .satellite import download_day, download_latest_day, download_subset, is_not_published

log = logging.getLogger(__name__)

INTAKE_SAMPLE_RADIUS_DEG = 0.05    # ~5 km box averaged around each intake
BLOOM_ANOMALY_STD_THRESHOLD = 2.0  # flag readings this many std devs above the baseline
MIN_BASELINE_DAYS = 14             # readings needed before the baseline means anything
BACKFILL_DAYS = 14
MONTHLY_HISTORY_START = date(2018, 1, 1)


def download_intake_scene(day: date):
    return download_day(NRT_CHL_DATASET_ID, [CHL_VARIABLE], QATAR_COAST_BBOX, day, CACHE_DIR / "intake", "chl")


def _box_around(field, coord):
    return field.sel(
        latitude=slice(coord["lat"] - INTAKE_SAMPLE_RADIUS_DEG, coord["lat"] + INTAKE_SAMPLE_RADIUS_DEG),
        longitude=slice(coord["lon"] - INTAKE_SAMPLE_RADIUS_DEG, coord["lon"] + INTAKE_SAMPLE_RADIUS_DEG),
    )


def sample_intake_readings(scene_path) -> dict[str, float | None]:
    """Mean chlorophyll-a (mg/m3) in the box around each intake. None where it's all cloud."""
    import xarray as xr

    readings = {}
    with xr.open_dataset(scene_path) as scene:
        for site, coord in DESAL_INTAKE_SITES.items():
            value = float(_box_around(scene[CHL_VARIABLE], coord).mean(skipna=True).values)
            readings[site] = None if np.isnan(value) else value
    return readings


def load_reading_history(path=INTAKE_HISTORY_FILE) -> dict:
    """{site: [[date, value], ...]}, oldest first."""
    if path.exists():
        return json.loads(path.read_text())
    return {site: [] for site in DESAL_INTAKE_SITES}


def save_reading_history(history: dict, path=INTAKE_HISTORY_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2))


def find_bloom_anomalies(readings: dict, history: dict, day: str) -> list[str]:
    """Compare each intake's reading with that intake's own past readings.

    Adds the reading to `history` and returns one alert message per anomalous intake.
    A date that's already in the history is skipped: when publication lags, two daily
    runs can land on the same scene, and counting it twice would skew the baseline.
    """
    alerts = []
    for site, value in readings.items():
        if value is None:
            log.warning("No usable chlorophyll data for %s on %s (cloud cover?)", site, day)
            continue
        if any(recorded_day == day for recorded_day, _ in history[site]):
            log.info("%s: already have a reading for %s, not counting it twice", site, day)
            continue

        past = [past_value for _, past_value in history[site]]
        history[site].append([day, value])

        if len(past) < MIN_BASELINE_DAYS:
            log.info(
                "%s: %.2f mg/m3 (baseline still building: %d/%d days)",
                site, value, len(past), MIN_BASELINE_DAYS,
            )
            continue

        mean, std = np.mean(past), np.std(past)
        if std > 0 and value > mean + BLOOM_ANOMALY_STD_THRESHOLD * std:
            # Shown word for word in the dashboard's flag table, so it's written for a reader.
            alerts.append(
                f"{site}: {value:.1f} mg/m³, against a recent daily average of {mean:.1f} "
                f"(usual spread {std:.1f}, flag threshold {mean + BLOOM_ANOMALY_STD_THRESHOLD * std:.1f})"
            )
        else:
            log.info("%s: %.2f mg/m3 (within normal range)", site, value)
    return alerts


def check_intakes(today: date | None = None) -> dict:
    """The daily check, on the newest published scene.

    Returns {"scene_date", "readings": {site: mg/m3 or None}, "alerts": [message, ...]}.
    """
    today = today or date.today()
    scene_path, scene_date = download_latest_day(download_intake_scene, today)
    if scene_date != today:
        log.info("Using most recent available scene: %s (data lags behind today)", scene_date)

    history = load_reading_history()
    readings = sample_intake_readings(scene_path)
    alerts = find_bloom_anomalies(readings, history, scene_date.isoformat())
    save_reading_history(history)

    if alerts:
        log.warning("Possible bloom activity detected:")
        for alert in alerts:
            log.warning("  %s", alert)
        # TODO: send a real notification (email or Telegram) once the threshold is validated.
    else:
        log.info("No bloom anomalies detected for %s.", scene_date)
    return {"scene_date": scene_date.isoformat(), "readings": readings, "alerts": alerts}


def backfill_history(days: int = BACKFILL_DAYS, today: date | None = None) -> None:
    """Fill in the last `days` days, so the baseline is ready without waiting two weeks."""
    today = today or date.today()
    history = load_reading_history()
    added = skipped = 0

    for days_ago in range(days, 0, -1):
        day = today - timedelta(days=days_ago)
        if all(any(d == day.isoformat() for d, _ in history[site]) for site in DESAL_INTAKE_SITES):
            log.info("Already have %s, skipping", day)
            skipped += 1
            continue

        log.info("Backfilling %s ...", day)
        try:
            scene_path = download_intake_scene(day)
        except Exception as exc:
            if is_not_published(exc):
                log.info("No data available yet for %s, skipping", day)
            else:
                log.warning("Could not fetch %s (%s: %s), skipping", day, type(exc).__name__, exc)
            skipped += 1
            continue

        for site, value in sample_intake_readings(scene_path).items():
            if value is not None and not any(d == day.isoformat() for d, _ in history[site]):
                history[site].append([day.isoformat(), value])
        added += 1

    for site in history:
        history[site].sort(key=lambda reading: reading[0])
    save_reading_history(history)
    log.info("Backfill done: %d day(s) added, %d skipped.", added, skipped)


def export_monthly_history(start: date = MONTHLY_HISTORY_START, output=MONTHLY_HISTORY_CSV) -> int:
    """Monthly mean chlorophyll at each intake from `start` to now, as CSV. Returns row count.

    Uses the reprocessed archive, which goes back to 1997, unlike the near-real-time
    product the daily check uses (a rolling ~2 weeks). This is context for the
    dashboards, not an input to the daily check.
    """
    import xarray as xr

    log.info("Downloading monthly chlorophyll history from %s to present ...", start)
    scene_path = download_subset(
        MONTHLY_CHL_DATASET_ID,
        [CHL_VARIABLE],
        QATAR_COAST_BBOX,
        start=f"{start.isoformat()}T00:00:00",
        end=None,
        cache_dir=CACHE_DIR / "monthly",
        filename=f"chl_monthly_{start.isoformat()}_to_present.nc",
    )

    rows = []
    with xr.open_dataset(scene_path) as scene:
        for site, coord in DESAL_INTAKE_SITES.items():
            series = _box_around(scene[CHL_VARIABLE], coord).mean(dim=["latitude", "longitude"], skipna=True)
            for month, value in zip(series["time"].values, series.values):
                rows.append({
                    "site": site,
                    "month": str(month)[:7],
                    "chlorophyll_mg_m3": None if np.isnan(value) else round(float(value), 3),
                })

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["site", "month", "chlorophyll_mg_m3"])
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d rows to %s", len(rows), output)
    return len(rows)
