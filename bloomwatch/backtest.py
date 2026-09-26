"""
Would this method have seen the 2008-09 red tide coming?

Everything else in the project is about blooms that haven't happened, which can't be
checked. This runs the exact same hotspot detector over archived imagery of a real,
documented one and measures the lead time.

From Richlen et al., "The catastrophic 2008-2009 red tide in the Arabian gulf region",
Harmful Algae (2010): a Cochlodinium polykrikoides bloom was first seen in late August
2008 near Dibba Al-Hassan (UAE, Gulf of Oman side), spread through the Strait of
Hormuz, reached Qatari and Iranian waters, and lasted into at least May 2009. It forced
desalination plants in the UAE and Oman offline.

STATUS: date stepping and lead-time math are tested on synthetic data. Not yet run for
real: DAILY_REPROCESSED_CHL_DATASET_ID is unconfirmed (see config.py). Expect more
no-data days than a recent window; 2008 had fewer satellites. That's a real finding
about the data, not a bug. It's slow (~100 downloads).
"""

import json
import logging
from datetime import date, timedelta

from .config import BACKTEST_FILE, CACHE_DIR, CHL_VARIABLE, DAILY_REPROCESSED_CHL_DATASET_ID, GULF_WATCH_BBOX
from .gulf import haversine_km, scan_for_hotspots
from .satellite import download_day, is_not_published

log = logging.getLogger(__name__)

# The documented event, with a few weeks' padding before the first sighting so the
# backtest can show whether a signal was already building.
EVENT_WINDOW_START = date(2008, 8, 1)
EVENT_WINDOW_END = date(2009, 5, 31)
DOCUMENTED_FIRST_SIGHTING = date(2008, 8, 25)  # "late August 2008", approximate
DIBBA_ORIGIN_POINT = {"lat": 25.59, "lon": 56.27}

BACKTEST_STEP_DAYS = 3        # every day for 9+ months is too many downloads
DETECTION_MIN_HOTSPOTS = 1    # any hotspot at all counts as "flagged", same as the live scan


def download_2008_scene(day: date):
    """The reprocessed scene for one day, or None if that day has no data.

    2008 coverage has real gaps, and the backtest has to record them honestly, so a
    failed day is logged and counted as missing rather than stopping the run.
    """
    try:
        return download_day(
            DAILY_REPROCESSED_CHL_DATASET_ID, [CHL_VARIABLE], GULF_WATCH_BBOX, day,
            CACHE_DIR / "backtest_2008", "chl_daily",
        )
    except Exception as exc:
        if not is_not_published(exc):
            log.error("Unexpected error fetching %s: %s: %s", day, type(exc).__name__, exc)
        return None


def run_backtest(
    start: date = EVENT_WINDOW_START,
    end: date = EVENT_WINDOW_END,
    step_days: int = BACKTEST_STEP_DAYS,
    download=download_2008_scene,
    scan=scan_for_hotspots,
) -> dict:
    """Step through the window, scan each scene, and compare with the documented sighting.

    `download` and `scan` can be swapped for fakes, which is how the tests check the
    stepping and lead-time math without any satellite data.
    """
    daily = []
    day = start
    while day <= end:
        log.info("Backtest: checking %s ...", day)
        scene_path = download(day)
        if scene_path is None:
            daily.append({"date": day.isoformat(), "nearest_km_to_qatar": None,
                          "nearest_km_to_origin": None, "hotspot_count": None})
        else:
            hotspots = scan(scene_path)
            nearest_qatar = min((h["distance_km"] for h in hotspots), default=None)
            nearest_origin = min(
                (haversine_km(h["lat"], h["lon"], DIBBA_ORIGIN_POINT["lat"], DIBBA_ORIGIN_POINT["lon"])
                 for h in hotspots),
                default=None,
            )
            daily.append({
                "date": day.isoformat(),
                "nearest_km_to_qatar": None if nearest_qatar is None else round(nearest_qatar, 1),
                "nearest_km_to_origin": None if nearest_origin is None else round(nearest_origin, 1),
                "hotspot_count": len(hotspots),
            })
        day += timedelta(days=step_days)

    first_flagged = next(
        (d["date"] for d in daily if d["hotspot_count"] is not None and d["hotspot_count"] >= DETECTION_MIN_HOTSPOTS),
        None,
    )
    lead_time_days = None
    if first_flagged:
        lead_time_days = (DOCUMENTED_FIRST_SIGHTING - date.fromisoformat(first_flagged)).days

    return {
        "event_window": {"start": start.isoformat(), "end": end.isoformat()},
        "documented_first_sighting": DOCUMENTED_FIRST_SIGHTING.isoformat(),
        "step_days": step_days,
        "daily": daily,
        "summary": {
            "first_flagged_by_method": first_flagged,
            "lead_time_vs_documented_days": lead_time_days,
            "usable_days": sum(1 for d in daily if d["hotspot_count"] is not None),
            "total_days_in_window": len(daily),
        },
    }


def run_and_save_backtest() -> dict:
    result = run_backtest()
    BACKTEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKTEST_FILE.write_text(json.dumps(result, indent=2))

    summary = result["summary"]
    lead = summary["lead_time_vs_documented_days"]
    if lead is not None:
        log.warning(
            "Method would have first flagged elevated chlorophyll on %s, %d day(s) %s the documented "
            "first sighting (%s).",
            summary["first_flagged_by_method"], abs(lead), "before" if lead > 0 else "after",
            DOCUMENTED_FIRST_SIGHTING.isoformat(),
        )
    else:
        log.warning("Method never flagged a hotspot across the whole window. Check data coverage "
                    "before concluding anything from that.")
    log.info("Usable days: %d / %d. Results written to %s",
             summary["usable_days"], summary["total_days_in_window"], BACKTEST_FILE)
    return result
