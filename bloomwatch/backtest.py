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

STATUS: run on real 2008 data (September 2026). It flagged water ~70 km from the bloom's
origin on 19 and 22 August 2008, before the first sighting, but it also flagged 96 of the
102 days checked, so it needs the same run on a year without a major bloom before those
early flags can be called a warning. Slow the first time (~100 scenes plus a normal for
each month).
"""

import json
import logging
import math
from datetime import date, timedelta

import numpy as np

from .config import (
    BACKTEST_FILE,
    CACHE_DIR,
    CHL_VARIABLE,
    DAILY_REPROCESSED_CHL_DATASET_ID,
    GULF_WATCH_BBOX,
    QATAR_REFERENCE_POINT,
)
from .gulf import (
    download_archive_month,
    find_anomalies,
    haversine_km,
    hotspots_in_grid,
    load_monthly_normal,
    scan_for_hotspots,
)
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

# The fair test of the early flags: does the check also find unusual water near Dibba in
# the same August weeks of other years? If it does most years, 2008's early flags mean
# nothing. Comparison years avoid 2018-2025 (they define "normal", so they'd look quiet by
# construction) and 2008 itself.
COMPARISON_YEARS = [year for year in range(2003, 2018) if year != 2008]
NEAR_ORIGIN_KM = 100
EARLY_CHECK_DAYS = list(range(1, DOCUMENTED_FIRST_SIGHTING.day, BACKTEST_STEP_DAYS))  # 1, 4, ... 22 August


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

    return {
        "event_window": {"start": start.isoformat(), "end": end.isoformat()},
        "documented_first_sighting": DOCUMENTED_FIRST_SIGHTING.isoformat(),
        "step_days": step_days,
        "daily": daily,
        "summary": summarize_backtest(daily),
    }


def summarize_backtest(daily: list[dict]) -> dict:
    """What the backtest found, from its day-by-day records.

    Lead time alone overstates things: a single flag weeks early, followed by nothing,
    isn't a warning. So the summary also lists every flag before the documented sighting
    with its distance from where the bloom started, and how many of the checked days were
    flagged at all (if nearly every day is flagged, a comparison year is needed to tell
    the bloom apart from an over-sensitive check).
    """
    flagged = [d for d in daily if d["hotspot_count"] is not None and d["hotspot_count"] >= DETECTION_MIN_HOTSPOTS]
    first_flagged = flagged[0]["date"] if flagged else None
    lead_time_days = None
    if first_flagged:
        lead_time_days = (DOCUMENTED_FIRST_SIGHTING - date.fromisoformat(first_flagged)).days

    return {
        "first_flagged_by_method": first_flagged,
        "lead_time_vs_documented_days": lead_time_days,
        "days_flagged": len(flagged),
        "flags_before_sighting": [
            {"date": d["date"], "km_to_origin": d["nearest_km_to_origin"]}
            for d in flagged
            if date.fromisoformat(d["date"]) < DOCUMENTED_FIRST_SIGHTING
        ],
        "usable_days": sum(1 for d in daily if d["hotspot_count"] is not None),
        "total_days_in_window": len(daily),
    }


def checks_near_origin(hotspots_by_day: dict, radius_km: float = NEAR_ORIGIN_KM) -> int:
    """How many checked days found a hotspot within radius_km of where the 2008 bloom started."""
    return sum(
        1
        for hotspots in hotspots_by_day.values()
        if any(
            haversine_km(h["lat"], h["lon"], DIBBA_ORIGIN_POINT["lat"], DIBBA_ORIGIN_POINT["lon"]) <= radius_km
            for h in hotspots
        )
    )


def early_august_hotspots(year: int) -> dict:
    """Hotspots on each of the early-August check days of one year, from one month download."""
    import xarray as xr

    with xr.open_dataset(download_archive_month(year, 8)) as data:
        chl = data[CHL_VARIABLE].load()
    normal = load_monthly_normal(8)
    by_day = {}
    for day_of_month in EARLY_CHECK_DAYS:
        day = date(year, 8, day_of_month)
        grid = chl.sel(time=slice(day.isoformat(), day.isoformat()))
        if grid.sizes["time"] == 0:
            continue  # no image that day: left out, not counted as quiet
        by_day[day] = hotspots_in_grid(grid.values[0], chl["latitude"].values, chl["longitude"].values, 8, normal)
    return by_day


def compare_early_august(years=(2008, *COMPARISON_YEARS)) -> list[dict]:
    """For each year: how many early-August checks found unusual water near Dibba."""
    rows = []
    for year in years:
        log.info("Comparison: early August %d ...", year)
        by_day = early_august_hotspots(year)
        rows.append({"year": year, "checks": len(by_day), "checks_near_origin": checks_near_origin(by_day)})
    return rows


# Map classes for the site's 2008 map, 2 bits each.
MAP_LAND, MAP_NORMAL, MAP_ABOVE, MAP_FLAGGED = 0, 1, 2, 3
MAP_ABOVE_Z = 2.0  # "above normal" on the map; flagged still needs 3 SD, the floor and a patch
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def encode_map_classes(classes) -> str:
    """Pack a grid of map classes (0-3) into text, three cells per character, row by row."""
    flat = [int(c) for c in np.asarray(classes).ravel()]
    flat += [0] * (-len(flat) % 3)
    return "".join(BASE64_ALPHABET[flat[i] * 16 + flat[i + 1] * 4 + flat[i + 2]] for i in range(0, len(flat), 3))


def map_classes(values, normal) -> np.ndarray:
    """Land / normal / above normal / flagged for every pixel of one day's grid."""
    z, flagged = find_anomalies(values, *normal)
    classes = np.full(values.shape, MAP_NORMAL, dtype=np.uint8)
    classes[np.isnan(values)] = MAP_LAND
    classes[(z >= MAP_ABOVE_Z) & ~flagged] = MAP_ABOVE
    classes[flagged] = MAP_FLAGGED
    return classes


def backtest_map_frames(result: dict) -> dict:
    """Every checked day of the backtest as a small map, for the site to play through.

    Rows run north to south (the file's latitude is south to north, so it's flipped).
    """
    import xarray as xr

    frames, grid = [], None
    for record in result["daily"]:
        if record["hotspot_count"] is None:
            continue
        day = date.fromisoformat(record["date"])
        with xr.open_dataset(download_2008_scene(day)) as scene:
            chl = scene[CHL_VARIABLE]
            values = chl.values[0] if "time" in chl.dims else chl.values
            lats, lons = chl["latitude"].values, chl["longitude"].values
        classes = map_classes(values, load_monthly_normal(day.month))[::-1]
        if grid is None:
            grid = {
                "rows": int(values.shape[0]),
                "cols": int(values.shape[1]),
                "north": float(lats.max()),
                "south": float(lats.min()),
                "west": float(lons.min()),
                "east": float(lons.max()),
            }
        frames.append({
            "date": record["date"],
            "flagged_km2": int(round(float((classes == MAP_FLAGGED).sum()) * km2_per_pixel(float(np.mean(lats))))),
            "km_to_origin": record["nearest_km_to_origin"],
            "km_to_qatar": record["nearest_km_to_qatar"],
            "cells": encode_map_classes(classes),
        })
    return {
        "grid": grid,
        "origin": DIBBA_ORIGIN_POINT,
        "doha": QATAR_REFERENCE_POINT,
        "documented_first_sighting": DOCUMENTED_FIRST_SIGHTING.isoformat(),
        "frames": frames,
    }


def km2_per_pixel(latitude: float) -> float:
    """Area of one 1/24-degree grid square at this latitude (~19 km² across the Gulf)."""
    side_km = 111.32 / 24
    return side_km * side_km * math.cos(math.radians(latitude))


def run_and_save_backtest() -> dict:
    result = run_backtest()
    result["early_august_comparison"] = {
        "check_days": EARLY_CHECK_DAYS,
        "radius_km": NEAR_ORIGIN_KM,
        "years": compare_early_august(),
    }
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
