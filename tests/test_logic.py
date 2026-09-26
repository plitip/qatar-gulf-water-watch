"""
Offline tests for the parts that are pure logic: no satellite download, no login.

What they prove: the trend verdicts, the advection math, the backtest's date stepping
and lead time, the per-intake anomaly check, and the dashboard update do what they
claim. What they don't prove: that the dataset IDs are right, or that real satellite
data behaves like these made-up numbers.

Run from the repo root: python -m pytest
"""

import json
from datetime import date

from bloomwatch import intake
from bloomwatch.backtest import run_backtest
from bloomwatch.config import QATAR_REFERENCE_POINT
from bloomwatch.gulf import compute_trend, haversine_km, publish_trajectory_to_dashboard
from bloomwatch.projection import project_hotspot_path, summarize_path


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


# --- static dashboard update ----------------------------------------------------------

def test_dashboard_update_replaces_only_the_trajectory_line(tmp_path):
    html = tmp_path / "index.html"
    before = "<p>Ras Laffan · 2018–2026 →</p>\n<script>\nvar GULF_TRAJECTORY = null;\nvar DATA = [1, 2];\n</script>\n"
    html.write_text(before, encoding="utf-8")
    trajectory = {"window_end_date": "2026-09-19", "trend": {"verdict": "no_clear_trend"}, "daily": []}
    trajectory_file = tmp_path / "trajectory.json"
    trajectory_file.write_text(json.dumps(trajectory))

    publish_trajectory_to_dashboard(trajectory_file, html)

    after = html.read_text(encoding="utf-8")
    assert after == before.replace("var GULF_TRAJECTORY = null;", "var GULF_TRAJECTORY = " + json.dumps(trajectory) + ";")
