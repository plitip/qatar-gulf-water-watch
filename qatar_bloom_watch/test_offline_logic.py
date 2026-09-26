"""
test_offline_logic.py

Offline checks for the parts of the pipeline that are pure logic (no
satellite download needed). These are the same synthetic checks that
were run by hand while the code was being written, saved here so they
can be re-run any time something changes.

What they prove: the trend math, the current-advection math, and the
backtest's date-stepping / lead-time math do what they claim.
What they do NOT prove: that the Copernicus dataset IDs are right, or
that real satellite data behaves like the fake data here. Those need a
real run with a Copernicus Marine login.

RUN (from inside qatar_bloom_watch/):
    python test_offline_logic.py
or, if pytest is installed:
    python -m pytest test_offline_logic.py -v
"""

from datetime import date


# --- scan_gulf_trajectory.compute_trend ---------------------------------

def test_trend_detects_approaching():
    from scan_gulf_trajectory import compute_trend
    records = [{"date": f"d{i}", "nearest_km": 300 - 8 * i} for i in range(8)]
    result = compute_trend(records)
    assert result["verdict"] == "approaching"
    assert result["slope_km_per_day"] == -8.0


def test_trend_flat_is_no_clear_trend():
    from scan_gulf_trajectory import compute_trend
    records = [{"date": f"d{i}", "nearest_km": 150 + (5 if i % 2 == 0 else -5)} for i in range(8)]
    assert compute_trend(records)["verdict"] == "no_clear_trend"


def test_trend_detects_receding():
    from scan_gulf_trajectory import compute_trend
    records = [{"date": f"d{i}", "nearest_km": 100 + 10 * i} for i in range(8)]
    result = compute_trend(records)
    assert result["verdict"] == "receding"
    assert result["slope_km_per_day"] == 10.0


def test_trend_too_many_gaps_is_insufficient():
    from scan_gulf_trajectory import compute_trend
    records = [{"date": f"d{i}", "nearest_km": None if i % 3 else 200} for i in range(8)]
    result = compute_trend(records)
    assert result["verdict"] == "insufficient_data"
    assert result["slope_km_per_day"] is None


# --- predict_gulf_bloom_trajectory.project_hotspot_path -----------------

def _start_point_2deg_north_of_qatar():
    from scan_gulf_for_approaching_blooms import QATAR_REFERENCE_POINT, haversine_km
    qlat, qlon = QATAR_REFERENCE_POINT["lat"], QATAR_REFERENCE_POINT["lon"]
    start_lat, start_lon = qlat + 2.0, qlon
    start_dist_km = haversine_km(start_lat, start_lon, qlat, qlon)
    return start_lat, start_lon, start_dist_km


def test_advection_toward_qatar_arrives_on_expected_day():
    from predict_gulf_bloom_trajectory import project_hotspot_path, summarize_path
    start_lat, start_lon, start_dist_km = _start_point_2deg_north_of_qatar()
    km_per_day = start_dist_km / 5  # chosen so it should arrive on day 5
    v_southward = -(km_per_day * 1000) / 86400
    path = project_hotspot_path(start_lat, start_lon, 0.0, v_southward, horizon_days=10)
    summary = summarize_path(path)
    assert summary["closest_approach_day"] == 5
    assert summary["closest_approach_km"] < 1.0
    assert summary["reaches_coast_in_window"] is True


def test_advection_away_from_qatar_never_arrives():
    from predict_gulf_bloom_trajectory import project_hotspot_path, summarize_path
    start_lat, start_lon, start_dist_km = _start_point_2deg_north_of_qatar()
    v_northward = (start_dist_km / 5 * 1000) / 86400
    path = project_hotspot_path(start_lat, start_lon, 0.0, v_northward, horizon_days=10)
    summary = summarize_path(path)
    assert summary["closest_approach_day"] == 0
    assert summary["reaches_coast_in_window"] is False


# --- backtest_2008_red_tide.run_backtest ---------------------------------

def test_backtest_gap_handling_and_lead_time():
    import backtest_2008_red_tide as bt

    def fake_fetch(target_date):
        if target_date < date(2008, 8, 10):
            return None  # simulate an early coverage gap
        return f"fake_scene_{target_date.isoformat()}.nc"

    def fake_scan(scene_path):
        d = date.fromisoformat(scene_path.replace("fake_scene_", "").replace(".nc", ""))
        if d < date(2008, 8, 22):
            return []
        return [{"lat": 25.6, "lon": 56.3, "value": 5.0,
                 "distance_km": bt.haversine_km(25.6, 56.3, bt.QATAR_REFERENCE_POINT["lat"],
                                                bt.QATAR_REFERENCE_POINT["lon"])}]

    originals = (bt.fetch_historical_daily_scene, bt.scan_for_hotspots,
                 bt.EVENT_WINDOW_START, bt.EVENT_WINDOW_END, bt.BACKTEST_STEP_DAYS)
    try:
        bt.fetch_historical_daily_scene = fake_fetch
        bt.scan_for_hotspots = fake_scan
        bt.EVENT_WINDOW_START = date(2008, 8, 1)
        bt.EVENT_WINDOW_END = date(2008, 9, 15)
        bt.BACKTEST_STEP_DAYS = 3

        result = bt.run_backtest()
    finally:
        (bt.fetch_historical_daily_scene, bt.scan_for_hotspots,
         bt.EVENT_WINDOW_START, bt.EVENT_WINDOW_END, bt.BACKTEST_STEP_DAYS) = originals

    assert result["daily"][0]["hotspot_count"] is None
    assert result["summary"]["first_flagged_by_method"] == "2008-08-22"
    assert result["summary"]["lead_time_vs_documented_days"] == 3
    assert result["summary"]["usable_days"] == 13
    assert result["summary"]["total_days_in_window"] == 16


if __name__ == "__main__":
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
