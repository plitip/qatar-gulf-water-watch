"""
backtest_2008_red_tide.py

Validates the detection method (scan_for_hotspots / the nearest-hotspot
trajectory idea from scan_gulf_trajectory.py) against a REAL, documented
event instead of a hypothetical future one: the catastrophic 2008-2009
Cochlodinium polykrikoides red tide.

Per the peer-reviewed account (Richlen et al., "The catastrophic
2008-2009 red tide in the Arabian gulf region", Harmful Algae, 2010):
  - First observed late August 2008 near Dibba Al-Hassan, on the UAE's
    Gulf-of-Oman coast.
  - Spread through the Strait of Hormuz into the Arabian Gulf, reaching
    Qatar and Iran.
  - Persisted 8+ months, into at least May 2009.
  - Forced desalination plants in the UAE and Oman offline (that specific
    impact isn't documented for Qatar, but the bloom itself reached
    Qatari waters per this paper).

This script re-runs today's detection method against archived imagery
from that window and asks the useful question: if this method had been
running in 2008, how many days of lead time would it plausibly have
given before the event was first reported? That's a real, checkable
number -- unlike anything about a future bloom, which we can't check
at all.

STATUS: prototype, TWO unverified pieces:
  1. HISTORICAL_DAILY_DATASET_ID -- my best-known match for Copernicus
     Marine's DAILY (not monthly) reprocessed multi-year chlorophyll
     product. fetch_historical_trends.py already uses the confirmed
     MONTHLY version of this product family (_P1M); this assumes a
     _P1D sibling exists with the same naming pattern. Could not check
     the live catalogue from this sandbox (network-blocked, same as
     everywhere else in this project) -- run
         copernicusmarine describe --contains CHL
     and confirm before trusting this.
  2. Satellite coverage in 2008 was sparser than today (fewer sensors,
     earlier-generation processing), so expect more cloud/no-data gaps
     in this window than scan_gulf_trajectory.py sees on a recent
     10-day window. That's real signal about data quality, not a bug.

RUN:
    python backtest_2008_red_tide.py
    (needs a Copernicus Marine login; this downloads roughly one scene
    every BACKTEST_STEP_DAYS across ~9 months, so it's slow --
    budget real time for this one.)
"""

import json
import os
from datetime import date, timedelta

from qatar_bloom_watch import log
from scan_gulf_for_approaching_blooms import (
    GULF_WATCH_BBOX,
    QATAR_REFERENCE_POINT,
    haversine_km,
    scan_for_hotspots,
)

# Best-known match for Copernicus Marine's daily reprocessed ("_my_")
# multi-year gap-free chlorophyll product -- the daily sibling of the
# monthly HISTORICAL_DATASET_ID already confirmed in
# fetch_historical_trends.py. UNVERIFIED -- see docstring.
HISTORICAL_DAILY_DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1D"
HISTORICAL_VARIABLE = "CHL"

# Documented event window (Richlen et al. 2010) with a couple of weeks'
# padding before the documented "late August 2008" first sighting, so
# the backtest can show whether the signal was already building beforehand.
EVENT_WINDOW_START = date(2008, 8, 1)
EVENT_WINDOW_END = date(2009, 5, 31)
DOCUMENTED_FIRST_SIGHTING = date(2008, 8, 25)  # approximate, "late August 2008"

# Origin point of the bloom per the paper: near Dibba Al-Hassan, UAE
# (Gulf of Oman side, within GULF_WATCH_BBOX).
DIBBA_ORIGIN_POINT = {"lat": 25.59, "lon": 56.27}

# Fetching a scene for every single day across 9+ months is a lot of
# downloads; step through the window instead. 3 days is dense enough to
# catch a bloom's onset without taking forever to run.
BACKTEST_STEP_DAYS = 3

# Same detection threshold as the live scripts -- keep the method
# identical, or the backtest doesn't actually validate anything.
DETECTION_MIN_HOTSPOTS = 1  # any elevated pixel at all counts as "flagged"

SCENE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_2008_data")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_2008_red_tide.json")


def fetch_historical_daily_scene(target_date: date) -> str | None:
    """Download (or reuse a cached) daily reprocessed scene for one date.
    Returns None (not raises) if that date simply has no data -- 2008-era
    coverage has real gaps, and a backtest needs to represent that
    honestly rather than treating every gap as a script bug."""
    import copernicusmarine

    os.makedirs(SCENE_DIR, exist_ok=True)
    filename = f"chl_daily_{target_date.isoformat()}.nc"
    scene_path = os.path.join(SCENE_DIR, filename)
    if os.path.exists(scene_path):
        return scene_path

    try:
        copernicusmarine.subset(
            dataset_id=HISTORICAL_DAILY_DATASET_ID,
            variables=[HISTORICAL_VARIABLE],
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
    except Exception as exc:
        if type(exc).__name__ in ("CoordinatesOutOfDatasetBounds",):
            return None
        log.error("Unexpected error fetching %s: %s: %s", target_date, type(exc).__name__, exc)
        return None


def run_backtest() -> dict:
    daily = []
    day = EVENT_WINDOW_START
    while day <= EVENT_WINDOW_END:
        log.info("Backtest: checking %s ...", day)
        scene_path = fetch_historical_daily_scene(day)
        if scene_path is None:
            daily.append({"date": day.isoformat(), "nearest_km_to_qatar": None,
                          "nearest_km_to_origin": None, "hotspot_count": None})
            day += timedelta(days=BACKTEST_STEP_DAYS)
            continue

        # CHL_VARIABLE grid reuse of scan_for_hotspots -- reads the same
        # variable name it expects (CHL), works unmodified against a
        # daily-frequency file same shape as the near-real-time one.
        hotspots = scan_for_hotspots(scene_path)
        nearest_qatar = min((h["distance_km"] for h in hotspots), default=None)
        nearest_origin = (
            min(haversine_km(h["lat"], h["lon"], DIBBA_ORIGIN_POINT["lat"], DIBBA_ORIGIN_POINT["lon"]) for h in hotspots)
            if hotspots else None
        )
        daily.append({
            "date": day.isoformat(),
            "nearest_km_to_qatar": round(nearest_qatar, 1) if nearest_qatar is not None else None,
            "nearest_km_to_origin": round(nearest_origin, 1) if nearest_origin is not None else None,
            "hotspot_count": len(hotspots),
        })
        day += timedelta(days=BACKTEST_STEP_DAYS)

    # First date (in our stepped series) with at least DETECTION_MIN_HOTSPOTS
    # hotspots anywhere in the wider Gulf box -- our method's own "we'd have
    # flagged something here" moment, for comparison against the documented
    # first sighting.
    first_flagged = next(
        (d["date"] for d in daily if d["hotspot_count"] is not None and d["hotspot_count"] >= DETECTION_MIN_HOTSPOTS),
        None,
    )
    lead_time_days = None
    if first_flagged:
        lead_time_days = (DOCUMENTED_FIRST_SIGHTING - date.fromisoformat(first_flagged)).days

    return {
        "event_window": {"start": EVENT_WINDOW_START.isoformat(), "end": EVENT_WINDOW_END.isoformat()},
        "documented_first_sighting": DOCUMENTED_FIRST_SIGHTING.isoformat(),
        "step_days": BACKTEST_STEP_DAYS,
        "daily": daily,
        "summary": {
            "first_flagged_by_method": first_flagged,
            "lead_time_vs_documented_days": lead_time_days,
            "usable_days": sum(1 for d in daily if d["hotspot_count"] is not None),
            "total_days_in_window": len(daily),
        },
    }


def main() -> None:
    result = run_backtest()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f, indent=2)

    summary = result["summary"]
    if summary["lead_time_vs_documented_days"] is not None:
        log.warning(
            "Method would have first flagged elevated chlorophyll on %s -- %d day(s) %s the documented "
            "first sighting (%s).",
            summary["first_flagged_by_method"],
            abs(summary["lead_time_vs_documented_days"]),
            "before" if summary["lead_time_vs_documented_days"] > 0 else "after",
            DOCUMENTED_FIRST_SIGHTING.isoformat(),
        )
    else:
        log.warning("Method never flagged a hotspot across the whole window -- check data coverage before "
                     "concluding anything from that.")
    log.info("Usable days: %d / %d in window. Full results written to %s",
              summary["usable_days"], summary["total_days_in_window"], OUTPUT_FILE)


if __name__ == "__main__":
    main()
