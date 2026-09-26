"""
Offline tests for the parts that are pure logic: no satellite download, no login.

What they prove: the hotspot rule, the trend verdicts, the advection math, the
backtest's date stepping and lead time, the per-intake anomaly check, and the dashboard
update do what they claim. What they don't prove: that real satellite data behaves like
these made-up numbers.

Run from the repo root: python -m pytest
"""

import json
from datetime import date

import numpy as np

from bloomwatch import intake
from bloomwatch.backtest import BASE64_ALPHABET, checks_near_origin, encode_map_classes, map_classes, run_backtest
from bloomwatch.config import QATAR_REFERENCE_POINT
from bloomwatch.gulf import compute_trend, find_anomalies, haversine_km, keep_patches, recurring_area
from bloomwatch.projection import project_hotspot_path, summarize_path
from bloomwatch.publish import flags_from_run, publish_trajectory_to_dashboard, record_flags


# --- trajectory trend -----------------------------------------------------------------

def test_trend_detects_approaching():
    records = [{"date": f"d{i}", "nearest_km": 300 - 8 * i} for i in range(8)]
    result = compute_trend(records)
    assert result["verdict"] == "approaching"
    assert result["slope_km_per_day"] == -8.0


def test_trend_flat_is_no_clear_trend():
    records = [{"date": f"d{i}", "nearest_km": 150 + (5 if i % 2 == 0 else -5)} for i in range(8)]
    assert compute_trend(records)["verdict"] == "no_clear_trend"


def test_trend_detects_receding():
    records = [{"date": f"d{i}", "nearest_km": 100 + 10 * i} for i in range(8)]
    result = compute_trend(records)
    assert result["verdict"] == "receding"
    assert result["slope_km_per_day"] == 10.0


def test_trend_too_many_gaps_is_insufficient():
    records = [{"date": f"d{i}", "nearest_km": None if i % 3 else 200} for i in range(8)]
    result = compute_trend(records)
    assert result["verdict"] == "insufficient_data"
    assert result["slope_km_per_day"] is None


# --- hotspot rule: each pixel against its own normal ----------------------------------

def _normal(shape, typical_mg_m3, spread_log10=0.15):
    return np.full(shape, np.log10(typical_mg_m3)), np.full(shape, spread_log10)


def test_always_murky_water_is_not_a_hotspot():
    # Doha-style coastal water: 6 mg/m3 today, but 6 is normal for this spot.
    values = np.full((6, 6), 6.0)
    _, hotspots = find_anomalies(values, *_normal(values.shape, typical_mg_m3=6.0))
    assert not hotspots.any()


def test_normally_clear_water_that_turns_green_is_a_hotspot():
    values = np.full((6, 6), 0.5)
    values[1:3, 1:3] = 8.0  # a 2x2 patch jumps from 0.5 to 8 mg/m3
    z, hotspots = find_anomalies(values, *_normal(values.shape, typical_mg_m3=0.5))
    assert hotspots.sum() == 4 and hotspots[1:3, 1:3].all()
    assert z[1, 1] > 3


def test_single_pixel_spike_is_not_a_patch():
    values = np.full((6, 6), 0.5)
    values[4, 4] = 8.0
    _, hotspots = find_anomalies(values, *_normal(values.shape, typical_mg_m3=0.5))
    assert not hotspots.any()


def test_land_and_missing_pixels_are_never_hotspots():
    values = np.full((4, 4), np.nan)
    _, hotspots = find_anomalies(values, *_normal(values.shape, typical_mg_m3=0.5))
    assert not hotspots.any()


def test_keep_patches_counts_edge_neighbours_not_diagonals():
    diagonal = np.eye(5, dtype=bool)                       # 5 pixels, but none share an edge
    line = np.zeros((5, 5), dtype=bool)
    line[2, :4] = True                                      # 4 pixels in a row
    assert not keep_patches(diagonal, 4).any()
    assert keep_patches(line, 4).sum() == 4


def test_recurring_area_describes_the_biggest_repeat_patch():
    from collections import Counter
    step = 1 / 24
    north_of_doha = [(round(25.52 + i * step, 4), 51.5625) for i in range(3)]  # 3 touching squares
    counts = Counter({p: 5 for p in north_of_doha})
    counts[(26.6042, 50.6042)] = 5   # a lone square far away, also recurring
    counts[(25.1042, 51.6042)] = 1   # seen once: not recurring
    shore = [(25.52, 51.45)]         # a land point ~11 km west
    area = recurring_area(counts, days_with_patches=6, land_points=shore)
    assert area["pixels"] == 3 and area["min_days"] == 3
    assert area["direction_from_doha"] == "north"
    assert 25 < area["km_from_doha"] < 35
    assert 8 < area["km_from_shore"] < 14


def test_no_recurring_area_on_a_quiet_window():
    from collections import Counter
    assert recurring_area(Counter(), days_with_patches=0, land_points=[]) is None


# --- current projection ---------------------------------------------------------------

def _two_degrees_north_of_qatar():
    lat, lon = QATAR_REFERENCE_POINT["lat"] + 2.0, QATAR_REFERENCE_POINT["lon"]
    return lat, lon, haversine_km(lat, lon, QATAR_REFERENCE_POINT["lat"], QATAR_REFERENCE_POINT["lon"])


def test_advection_toward_qatar_arrives_on_expected_day():
    lat, lon, distance_km = _two_degrees_north_of_qatar()
    southward = -(distance_km / 5 * 1000) / 86400  # m/s that covers the distance in 5 days
    summary = summarize_path(project_hotspot_path(lat, lon, 0.0, southward, horizon_days=10))
    assert summary["closest_approach_day"] == 5
    assert summary["closest_approach_km"] < 1.0
    assert summary["reaches_coast_in_window"] is True


def test_advection_away_from_qatar_never_arrives():
    lat, lon, distance_km = _two_degrees_north_of_qatar()
    northward = (distance_km / 5 * 1000) / 86400
    summary = summarize_path(project_hotspot_path(lat, lon, 0.0, northward, horizon_days=10))
    assert summary["closest_approach_day"] == 0
    assert summary["reaches_coast_in_window"] is False


# --- 2008 backtest --------------------------------------------------------------------

def test_backtest_gap_handling_and_lead_time():
    def fake_download(day):
        return None if day < date(2008, 8, 10) else f"scene_{day.isoformat()}"  # early coverage gap

    def fake_scan(scene):
        day = date.fromisoformat(scene.removeprefix("scene_"))
        if day < date(2008, 8, 22):
            return []
        return [{"lat": 25.6, "lon": 56.3, "value": 5.0, "distance_km": 480.0}]

    result = run_backtest(date(2008, 8, 1), date(2008, 9, 15), 3, download=fake_download, scan=fake_scan)

    assert result["daily"][0]["hotspot_count"] is None
    assert result["summary"]["first_flagged_by_method"] == "2008-08-22"
    assert result["summary"]["lead_time_vs_documented_days"] == 3
    assert result["summary"]["usable_days"] == 13
    assert result["summary"]["total_days_in_window"] == 16
    assert result["summary"]["days_flagged"] == 9  # 22 Aug to 15 Sep, every 3 days
    before = result["summary"]["flags_before_sighting"]  # sighting is 25 Aug
    assert [f["date"] for f in before] == ["2008-08-22"]
    assert before[0]["km_to_origin"] < 5  # the fake hotspot sits next to Dibba


def test_comparison_counts_only_checks_with_a_patch_near_dibba():
    near_dibba = {"lat": 25.3, "lon": 56.5}   # ~40 km from the 2008 origin
    near_qatar = {"lat": 25.5, "lon": 51.6}   # ~470 km away
    by_day = {
        date(2011, 8, 1): [near_qatar],
        date(2011, 8, 4): [near_dibba, near_qatar],
        date(2011, 8, 7): [],
    }
    assert checks_near_origin(by_day) == 1
    assert checks_near_origin(by_day, radius_km=10) == 0


def test_map_encoding_round_trips():
    classes = np.array([[0, 1, 2, 3, 1], [3, 3, 0, 2, 1]])
    text = encode_map_classes(classes)
    decoded = []
    for ch in text:
        n = BASE64_ALPHABET.index(ch)
        decoded += [n // 16, (n // 4) % 4, n % 4]
    assert decoded[: classes.size] == classes.ravel().tolist()
    assert len(text) == 4  # 10 cells, three per character, padded


def test_map_classes_mark_land_normal_above_and_flagged():
    values = np.full((6, 6), 0.5)
    values[0, 0] = np.nan              # land
    values[4, 4] = 1.2                 # well above its 0.5 normal, but a lone pixel under 3 mg/m3
    values[1:3, 1:3] = 8.0             # a flagged patch
    classes = map_classes(values, (np.full((6, 6), np.log10(0.5)), np.full((6, 6), 0.15)))
    assert classes[0, 0] == 0 and classes[5, 0] == 1 and classes[4, 4] == 2
    assert (classes[1:3, 1:3] == 3).all()


# --- intake anomaly check -------------------------------------------------------------

def _steady_history(value=1.0, days=20):
    """A baseline with a little day-to-day wobble, so the std dev isn't zero."""
    return {"Ras Laffan": [[f"2026-08-{d:02d}", value + (0.05 if d % 2 else -0.05)] for d in range(1, days + 1)]}


def test_anomaly_flags_reading_far_above_own_baseline():
    history = _steady_history()
    alerts = intake.find_bloom_anomalies({"Ras Laffan": 3.0}, history, "2026-09-01")
    assert len(alerts) == 1 and alerts[0].startswith("Ras Laffan")
    assert history["Ras Laffan"][-1] == ["2026-09-01", 3.0]


def test_anomaly_ignores_normal_reading_and_same_day_rerun():
    history = _steady_history()
    assert intake.find_bloom_anomalies({"Ras Laffan": 1.02}, history, "2026-09-01") == []
    # A second run that lands on the same published scene mustn't add the day twice.
    intake.find_bloom_anomalies({"Ras Laffan": 1.02}, history, "2026-09-01")
    assert [d for d, _ in history["Ras Laffan"]].count("2026-09-01") == 1


# --- publishing ------------------------------------------------------------------------

def test_dashboard_update_replaces_only_the_trajectory_line(tmp_path):
    html = tmp_path / "index.html"
    before = "<p>Ras Laffan · 2018–2026 →</p>\n<script>\nvar GULF_TRAJECTORY = null;\nvar DATA = [1, 2];\n</script>\n"
    html.write_text(before, encoding="utf-8")
    trajectory = {"window_end_date": "2026-09-19", "trend": {"verdict": "no_clear_trend"}, "daily": []}
    trajectory_file = tmp_path / "trajectory.json"
    trajectory_file.write_text(json.dumps(trajectory))

    react_json = tmp_path / "gulfTrajectory.json"
    publish_trajectory_to_dashboard(trajectory_file, html, react_json)

    after = html.read_text(encoding="utf-8")
    assert after == before.replace("var GULF_TRAJECTORY = null;", "var GULF_TRAJECTORY = " + json.dumps(trajectory) + ";")
    assert json.loads(react_json.read_text()) == trajectory


def test_flag_log_records_each_flag_once(tmp_path):
    log_file = tmp_path / "alert_log.json"
    run = {"scene_date": "2026-09-24", "readings": {}, "alerts": ["Ras Laffan: 3.0 mg/m3, well above normal"]}
    approaching = {"window_end_date": "2026-09-24", "trend": {"verdict": "approaching", "message": "closing in"}}

    first = record_flags(flags_from_run(run, approaching), log_file)
    again = record_flags(flags_from_run(run, approaching), log_file)  # a rerun on the same scene

    assert len(first) == len(again) == 2
    assert {f["source"] for f in again} == {"intake", "gulf trajectory"}
    assert all(f["review"] == "not reviewed" for f in again)


def test_quiet_run_raises_no_flags():
    quiet = {"window_end_date": "2026-09-24", "trend": {"verdict": "no_clear_trend", "message": "flat"}}
    assert flags_from_run({"scene_date": "2026-09-24", "readings": {}, "alerts": []}, quiet) == []
