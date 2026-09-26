# Architecture

## Data flow

```
Copernicus Marine (free account)
   │
   ├─ NRT daily chlorophyll (confirmed) ──► qatar_bloom_watch.py ──► chl_history.json
   │                                    │    (3 intake boxes, own-baseline anomaly check)
   │                                    │
   │                                    └─► scan_gulf_for_approaching_blooms.py ──► gulf_bloom_watch.json
   │                                         (wider Gulf, today's hotspots)
   │                                              │
   │                                              ├─► scan_gulf_trajectory.py ──► gulf_bloom_trajectory.json
   │                                              │    (last 10 days, is nearest hotspot closing in?)
   │                                              │         │
   │                                              │         └─► update_dashboard_gulf_panel.py ──► qatar_dashboard/index.html
   │                                              │
   │                                              └─► predict_gulf_bloom_trajectory.py ──► gulf_bloom_prediction.json
   │                                                   (+ currents dataset, UNVERIFIED ID)
   │
   ├─ Monthly reprocessed chlorophyll (confirmed) ──► fetch_historical_trends.py ──► historical_chl_trends.csv
   │                                                    (2018 → present, per intake; feeds the dashboard chart)
   │
   └─ Daily reprocessed chlorophyll (UNVERIFIED ID) ──► backtest_2008_red_tide.py ──► backtest_2008_red_tide.json
                                                        (Aug 2008 – May 2009, real historical event)

run_daily_watch.py = qatar_bloom_watch → scan_gulf_for_approaching_blooms → scan_gulf_trajectory → update_dashboard_gulf_panel
```

## Python pipeline — `qatar_bloom_watch/`

| Script | What it does | Output | Status |
|---|---|---|---|
| `qatar_bloom_watch.py` | Core module + daily intake check. Downloads the latest published NRT scene (walks back up to 10 days for publication lag), averages chlorophyll in a ~5 km box at each intake, compares against that intake's own rolling history (flag if > mean + 2 SD, after 14 days of baseline). Also defines the shared `log`, sites, and dataset IDs. | `chl_history.json`, `chl_data/*.nc` | Ran on the laptop (last seen: 2026-09-19 scene, "no anomalies", baseline still building) |
| `backfill_history.py` | One-off: fills the last 14 days of `chl_history.json` so the baseline is ready immediately. | `chl_history.json` | Written; not confirmed to have been run |
| `find_chl_dataset.py` | One-off diagnostic: lists catalogue dataset IDs containing plankton/chl. | `chl_dataset_ids.txt` | Used to find the NRT ID |
| `fetch_historical_trends.py` | One-off: monthly reprocessed chlorophyll 2018 → present at each intake. | `historical_chl_trends.csv` | Ran on the laptop (312 rows); data is in both dashboards |
| `scan_gulf_for_approaching_blooms.py` | Today's wider-Gulf scan (Strait of Hormuz → Qatar). A pixel is a hotspot if above the scene's 95th percentile AND above 3.0 mg/m³. Reports distance of each to Qatar's coast. | `gulf_bloom_watch.json`, `gulf_scan_data/` | Written; not confirmed to have run with real data |
| `scan_gulf_trajectory.py` | Repeats the scan for each of the last 10 days, fits a line to nearest-hotspot distance vs day. Slope ≤ −5 km/day = approaching, ≥ +5 = receding, else no clear trend. Needs ≥ 4 usable days. | `gulf_bloom_trajectory.json` | Logic tested offline; not confirmed to have run with real data |
| `update_dashboard_gulf_panel.py` | Replaces the `var GULF_TRAJECTORY = ...;` line in `../qatar_dashboard/index.html` with the trajectory JSON. Touches nothing else. | edits `index.html` | Tested with synthetic JSON |
| `run_daily_watch.py` | Runs the four daily steps in order; one failing step doesn't stop the rest; exits non-zero only if all fail. Meant for Task Scheduler / cron. | — | Syntax-checked only |
| `predict_gulf_bloom_trajectory.py` | For the 5 nearest hotspots, samples ocean current (u/v) and projects each forward 10 days assuming the current stays constant. Flags any that come within 20 km of the coast. Physics projection, **not** a trained model. | `gulf_bloom_prediction.json` | Math tested offline; dataset ID **unverified** |
| `backtest_2008_red_tide.py` | Runs the same hotspot detector over Aug 2008 – May 2009 (every 3 days) and reports the first date it would have flagged something vs the documented first sighting (~25 Aug 2008). | `backtest_2008_red_tide.json` | Logic tested offline; dataset ID **unverified**; slow (~100 downloads) |
| `test_offline_logic.py` | 7 offline tests (trend verdicts, advection arrival, backtest stepping/lead time). | — | 7/7 passing |

## Copernicus datasets

| Purpose | Dataset ID | Variable(s) | Confirmed? |
|---|---|---|---|
| Daily near-real-time chlorophyll | `cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D` | `CHL` | **Yes**: ran on the laptop (dataset version 202311) |
| Monthly reprocessed chlorophyll | `cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1M` | `CHL` | **Yes**: downloaded 2018 → present (version 202603) |
| Ocean currents | `cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m` | `uo`, `vo` | **No**: best-known match. Check with `describe --contains uo` |
| Daily reprocessed chlorophyll (for 2008) | `cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1D` | `CHL` | **No**: assumed daily sibling of the monthly one. Check with `describe --contains CHL` |

The NRT product only keeps a rolling recent window (about two weeks), and
publication lags the calendar by a day or more. That's why scripts walk back from today.
For anything historical, use the reprocessed ("_my_") products.

## Key configuration values

| Name | Value | Where |
|---|---|---|
| Ras Laffan intake | 25.92 N, 51.59 E (approximate, unverified) | `qatar_bloom_watch.py` |
| Ras Abu Fontas intake | 25.13 N, 51.61 E (approximate, unverified) | `qatar_bloom_watch.py` |
| Umm Al Houl intake | 24.95 N, 51.57 E (approximate, unverified) | `qatar_bloom_watch.py` |
| Qatar coast box | lon 50.5–52.5, lat 24.4–26.3 | `QATAR_COAST_BBOX` |
| Intake sample radius | 0.05° (~5 km) | `INTAKE_SAMPLE_RADIUS_DEG` |
| Anomaly threshold | mean + 2 SD, after 14 days | `BLOOM_ANOMALY_STD_THRESHOLD`, `MIN_BASELINE_DAYS` |
| Wider Gulf box | lon 49–57, lat 24–27.5 | `GULF_WATCH_BBOX` |
| Qatar reference point | 25.3 N, 51.5 E | `QATAR_REFERENCE_POINT` |
| Hotspot rule | > 95th percentile AND > 3.0 mg/m³ | `ELEVATED_PERCENTILE`, `ELEVATED_MIN_VALUE` |
| Trajectory | 10-day window, ≥ 4 points, ±5 km/day | `scan_gulf_trajectory.py` |
| Projection | 10 days ahead, 20 km arrival, top 5 hotspots | `predict_gulf_bloom_trajectory.py` |
| 2008 bloom origin | Dibba Al-Hassan, 25.59 N, 56.27 E | `backtest_2008_red_tide.py` |

## Dashboards

**`qatar_dashboard/index.html`** is a single self-contained file. Open it by double-clicking,
no server needed. Sections: three stat tiles (latest month vs the same month in past
years), a monthly chlorophyll chart 2018 → Aug 2026 with hover tooltip and a table
toggle, the Gulf trajectory panel (placeholder until real data exists), and a "Has this
happened before?" panel on the 2008–09 event. Data is embedded as JS literals (`DATA`,
`GULF_TRAJECTORY`) because `fetch()` of local files fails under `file://`.
`chl_data.json` and `historical_chl_trends.csv` next to it are the source data. There
is no script that regenerates the embedded `DATA` block yet (see [ROADMAP.md](ROADMAP.md)).

**`qatar_dashboard_react/`** is the same design as Vite + React 18, and it's the version
deployed to Vercel. Components: `StatCards`, `ChlorophyllChart` (hover tooltip, clickable
legend to dim series, table toggle), `GulfPanel`, `HistoryPanel` (the 2008–09 event),
`ThemeToggle` (auto → forced light/dark, saved in localStorage). Data:
`src/data/chlHistory.js` (generated from the CSV) and `src/data/gulfTrajectory.json`
(`null` until a real scan is copied in).

Animations use GSAP in `src/animations/`: the headline, card count-ups, chart lines
drawing in, and panels revealing on scroll. Two rules they all follow: the real value is
in the HTML before any animation runs, and `prefers-reduced-motion` turns them off.

Security headers (CSP, HSTS, frame and referrer policy) are defined once in
`vercel.json`; `npm run preview` serves the same headers locally so a policy mistake shows
up before deploy.
