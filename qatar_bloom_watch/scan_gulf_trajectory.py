"""
scan_gulf_trajectory.py

The honest version of "advance warning": scan_gulf_for_approaching_blooms.py
gives one day's snapshot of the wider Gulf, which tells you a hotspot
exists but not whether it's actually headed for Qatar -- Gulf currents
move water in all directions, and plenty of elevated patches drift away
or sit still. This script watches the same corridor over several days
and checks whether the nearest hotspot's distance to Qatar's coast is
actually shrinking -- a real trajectory, not a single frame.

RUN:
    python scan_gulf_trajectory.py

STATUS: prototype, same caveats as scan_gulf_for_approaching_blooms.py
("elevated" = same-day statistical outlier, not a validated bloom
classifier) plus one more: this tracks the *nearest hotspot distance*
day over day, not a single tagged patch of water. If one patch fades
out near Qatar while a new, unrelated patch appears further out, this
can misread as "receding" even though neither patch actually moved.
Good enough to flag "something worth watching," not a substitute for
looking at the actual scenes.
"""

import json
import os
from datetime import date, timedelta

import numpy as np

from qatar_bloom_watch import log
from scan_gulf_for_approaching_blooms import (
    fetch_gulf_scene,
    scan_for_hotspots,
    OUTPUT_FILE as SNAPSHOT_OUTPUT_FILE,
)

# How many calendar days back to look. Some of these will have no
# published scene yet (satellite/processing lag) or be cloud-blanked;
# those days just don't contribute a data point.
TRAJECTORY_WINDOW_DAYS = 10

# Need at least this many usable daily readings before a trend means
# anything -- two points always "trend," that's not a signal.
MIN_POINTS_FOR_TREND = 4

# A slope steeper than this (hotspot getting closer, km/day) counts as
# "approaching." Chosen loosely: the Gulf is ~800km end to end and blooms
# have been observed to drift tens of km/day on currents, so a few km/day
# is noise-level and >5 km/day sustained across the window is worth flagging.
APPROACHING_SLOPE_KM_PER_DAY = -5.0
RECEDING_SLOPE_KM_PER_DAY = 5.0

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gulf_bloom_trajectory.json")


def fetch_gulf_scene_if_published(target_date: date) -> str | None:
    """Like fetch_gulf_scene, but returns None instead of raising when the
    dataset simply doesn't have that date yet (rather than stepping back to
    a different day, which would break the daily cadence a trajectory needs).
    """
    try:
        return fetch_gulf_scene(target_date)
    except Exception as exc:
        if type(exc).__name__ == "CoordinatesOutOfDatasetBounds":
            return None
        raise


def build_daily_series(end_date: date, window_days: int) -> list[dict]:
    """One record per day, oldest first. nearest_km is None for days with
    no published/usable scene (skipped rather than interpolated -- guessing
    a value would manufacture a trend that isn't there)."""
    records = []
    for offset in range(window_days - 1, -1, -1):
        day = end_date - timedelta(days=offset)
        log.info("Trajectory: checking %s ...", day)
        scene_path = fetch_gulf_scene_if_published(day)
        if scene_path is None:
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
    """Fit a line through (day index, nearest_km) for days that actually
    have a reading. Returns the slope (km/day; negative = getting closer)
    and a plain-language verdict."""
    usable = [(i, r["nearest_km"]) for i, r in enumerate(daily_records) if r["nearest_km"] is not None]

    if len(usable) < MIN_POINTS_FOR_TREND:
        return {
            "verdict": "insufficient_data",
            "slope_km_per_day": None,
            "usable_days": len(usable),
            "message": f"Only {len(usable)} usable day(s) in the window (need {MIN_POINTS_FOR_TREND}+) "
                       f"-- too many gaps (cloud cover / publication lag) to call a trend.",
        }

    xs = np.array([i for i, _ in usable], dtype=float)
    ys = np.array([v for _, v in usable], dtype=float)
    slope, intercept = np.polyfit(xs, ys, 1)
    slope = float(slope)

    if slope <= APPROACHING_SLOPE_KM_PER_DAY:
        verdict = "approaching"
        message = f"Nearest hotspot has closed in by ~{-slope:.1f} km/day over the last {len(usable)} usable days."
    elif slope >= RECEDING_SLOPE_KM_PER_DAY:
        verdict = "receding"
        message = f"Nearest hotspot has been moving away, ~{slope:.1f} km/day over the last {len(usable)} usable days."
    else:
        verdict = "no_clear_trend"
        message = f"Nearest-hotspot distance is roughly flat (~{slope:+.1f} km/day) -- no clear approach or retreat."

    return {
        "verdict": verdict,
        "slope_km_per_day": round(slope, 2),
        "usable_days": len(usable),
        "message": message,
    }


def main() -> None:
    end_date = date.today()

    # Reuse today's single-day snapshot if it's already been run, so this
    # script and scan_gulf_for_approaching_blooms.py agree on "today" rather
    # than each independently walking back through lag on their own.
    if os.path.exists(SNAPSHOT_OUTPUT_FILE):
        with open(SNAPSHOT_OUTPUT_FILE) as f:
            snapshot_date = date.fromisoformat(json.load(f)["date"])
        if snapshot_date < end_date:
            end_date = snapshot_date

    daily = build_daily_series(end_date, TRAJECTORY_WINDOW_DAYS)
    trend = compute_trend(daily)

    result = {
        "window_end_date": end_date.isoformat(),
        "window_days": TRAJECTORY_WINDOW_DAYS,
        "daily": daily,
        "trend": trend,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2)

    if trend["verdict"] == "approaching":
        log.warning("TRAJECTORY: %s", trend["message"])
    else:
        log.info("TRAJECTORY: %s", trend["message"])
    log.info("Full results written to %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()
