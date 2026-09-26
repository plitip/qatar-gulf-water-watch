"""
Where things are: the intakes, the stretches of sea being watched, the Copernicus
Marine datasets, and the files the pipeline writes.

Tuning values that belong to one method (anomaly threshold, hotspot cutoff, trend
slopes...) live next to that method in its own module instead.

The intake coordinates are approximate and haven't been checked against the real
facilities. Two of the four dataset IDs are unconfirmed; they're marked below.
"""

from pathlib import Path

# Offshore points near each plant's seawater intake. Approximate: confirm against the
# real facility footprint (satellite imagery, QEWC / Kahramaa) before relying on them.
DESAL_INTAKE_SITES = {
    "Ras Laffan": {"lat": 25.9200, "lon": 51.5900},
    "Ras Abu Fontas": {"lat": 25.1300, "lon": 51.6100},
    "Umm Al Houl": {"lat": 24.9500, "lon": 51.5700},
}

# Qatar's coastline and nearby water: what the intake check downloads.
QATAR_COAST_BBOX = {"min_lon": 50.5, "max_lon": 52.5, "min_lat": 24.4, "max_lat": 26.3}

# Strait of Hormuz down to Qatar: the corridor a bloom would travel through to get here.
GULF_WATCH_BBOX = {"min_lon": 49.0, "max_lon": 57.0, "min_lat": 24.0, "max_lat": 27.5}

# "How far from Qatar" is measured to this point, roughly on the Qatari coastline.
QATAR_REFERENCE_POINT = {"lat": 25.3, "lon": 51.5}


# --- Copernicus Marine datasets -----------------------------------------------------
# IDs change when Copernicus reprocesses a product. If one stops working, list the
# current ones with `python -m bloomwatch datasets` (chlorophyll) or
# `copernicusmarine describe --contains uo` (currents).

# Daily near-real-time gap-free chlorophyll-a. Confirmed against the live catalogue
# (product OCEANCOLOUR_GLO_BGC_L4_NRT_009_102). Only keeps a rolling ~2-week window.
NRT_CHL_DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D"

# Monthly reprocessed chlorophyll-a, back to 1997. Confirmed
# (product OCEANCOLOUR_GLO_BGC_L4_MY_009_104).
MONTHLY_CHL_DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1M"

# Daily reprocessed chlorophyll-a, for the 2008 backtest. UNCONFIRMED: assumed to be the
# daily sibling of the monthly product above. Check it exists and reaches back to 2008.
DAILY_REPROCESSED_CHL_DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1D"

# Ocean surface currents (GLOBAL_ANALYSISFORECAST_PHY_001_024, "cur" split).
# UNCONFIRMED: best-known match, not yet checked against the live catalogue.
CURRENTS_DATASET_ID = "cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m"

CHL_VARIABLE = "CHL"
CURRENT_U_VARIABLE = "uo"  # eastward velocity, m/s
CURRENT_V_VARIABLE = "vo"  # northward velocity, m/s

# Near-real-time data is published a day or more after the calendar date, so "today's
# scene" means: try today, then step back a day at a time, up to this many days.
MAX_LOOKBACK_DAYS = 10


# --- Files ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"  # downloaded .nc scenes, one folder per kind

INTAKE_HISTORY_FILE = DATA_DIR / "chl_history.json"
MONTHLY_HISTORY_CSV = DATA_DIR / "historical_chl_trends.csv"
GULF_SNAPSHOT_FILE = DATA_DIR / "gulf_bloom_watch.json"
GULF_TRAJECTORY_FILE = DATA_DIR / "gulf_bloom_trajectory.json"
PROJECTION_FILE = DATA_DIR / "gulf_bloom_prediction.json"
BACKTEST_FILE = DATA_DIR / "backtest_2008_red_tide.json"

STATIC_DASHBOARD_HTML = REPO_ROOT / "qatar_dashboard" / "index.html"
