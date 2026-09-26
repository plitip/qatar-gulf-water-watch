# Architecture

## Data flow

```
Copernicus Marine (free account)
   │
   ├─ NRT daily chlorophyll (confirmed) ──► intake.check_intakes ──► chl_history.json
   │                                    │    (3 intake boxes, own-baseline anomaly check)
   │                                    │
   │                                    └─► gulf.scan_today ──► gulf_bloom_watch.json
   │                                         (wider Gulf, today's hotspots)
   │                                              │
   │                                              ├─► gulf.track_trajectory ──► gulf_bloom_trajectory.json
   │                                              │    (last 10 days: is the nearest hotspot closing in?)
   │                                              │         │
   │                                              │         └─► gulf.publish_trajectory_to_dashboard ──► qatar_dashboard/index.html
   │                                              │
   │                                              └─► projection.project_hotspots ──► gulf_bloom_prediction.json
   │                                                   (+ currents dataset, UNVERIFIED ID)
   │
   ├─ Monthly reprocessed chlorophyll (confirmed) ──► intake.export_monthly_history ──► historical_chl_trends.csv
   │                                                    (2018 → present, per intake; feeds the dashboard chart)
   │
   └─ Daily reprocessed chlorophyll (UNVERIFIED ID) ──► backtest.run_backtest ──► backtest_2008_red_tide.json
                                                        (Aug 2008 – May 2009, real historical event)

python -m bloomwatch daily = check → scan → trajectory → dashboard. Output files go in data/.
```

## Python package: `bloomwatch/`

Everything runs as `python -m bloomwatch <command>` from the repo root, or as
`bloomwatch <command>` after `pip install -e .`.

| Module | What's in it | Commands | Status |
|---|---|---|---|
| `config.py` | Intake coordinates, bounding boxes, dataset IDs, file paths. | | Coordinates approximate |
| `satellite.py` | The one Copernicus download function: caching, "not published yet" handling, stepping back to the newest published day, error explanations, catalogue lookup. | `datasets` | Run against real data |
| `intake.py` | Averages a ~5 km box at each intake and compares it with that intake's own history (flag if > mean + 2 SD, after 14 days); a date that's already recorded isn't counted twice. Also the 14-day backfill and the monthly 2018 → present history. | `check`, `backfill`, `history` | Run against real data |
| `gulf.py` | Hotspot scan of the wider Gulf (> 95th percentile AND > 3.0 mg/m³), the 10-day nearest-hotspot trend (≤ −5 km/day approaching, ≥ +5 receding, needs ≥ 4 usable days), and writing the trajectory into the static dashboard. | `scan`, `trajectory`, `dashboard` | Run against real data; the hotspot rule has a known problem (DECISIONS.md) |
| `projection.py` | Moves the 5 nearest hotspots along the sampled ocean current, held constant for 10 days, and flags any that come within 20 km of the coast. Physics, not a trained model. | `project` | Math tested offline; currents dataset ID unverified |
| `backtest.py` | Runs the same detector over Aug 2008 – May 2009 (every 3 days) and compares its first flag with the documented first sighting (~25 Aug 2008). | `backtest` | Logic tested offline; dataset ID unverified; ~100 downloads |
| `__main__.py` | The command line. `daily` runs check → scan → trajectory → dashboard; one failing step doesn't stop the rest, and it exits non-zero only if every step failed. | `daily` | Run against real data |

`tests/test_logic.py` has 10 offline tests: trend verdicts, advection arrival, backtest
stepping and lead time, the intake anomaly check, and the dashboard update. Run them with
`python -m pytest`. Downloaded scenes are cached in `data/cache/<kind>/`, one file per day.

## Copernicus datasets

| Purpose | Dataset ID | Variable(s) | Confirmed? |
|---|---|---|---|
| Daily near-real-time chlorophyll | `cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D` | `CHL` | **Yes**: ran on the laptop (dataset version 202311) |
| Monthly reprocessed chlorophyll | `cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1M` | `CHL` | **Yes**: downloaded 2018 → present (version 202603) |
| Ocean currents | `cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m` | `uo`, `vo` | **No**: best-known match. Check with `describe --contains uo` |
| Daily reprocessed chlorophyll (for 2008) | `cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1D` | `CHL` | **No**: assumed daily sibling of the monthly one. Check with `describe --contains CHL` |

The NRT product only keeps a rolling recent window (about two weeks), and
publication lags the calendar by a day or more. That's why the code walks back from today.
For anything historical, use the reprocessed ("_my_") products.

## Key configuration values

| Name | Value | Where |
|---|---|---|
| Ras Laffan intake | 25.92 N, 51.59 E (approximate, unverified) | `config.py` |
| Ras Abu Fontas intake | 25.13 N, 51.61 E (approximate, unverified) | `config.py` |
| Umm Al Houl intake | 24.95 N, 51.57 E (approximate, unverified) | `config.py` |
| Qatar coast box | lon 50.5–52.5, lat 24.4–26.3 | `QATAR_COAST_BBOX` |
| Intake sample radius | 0.05° (~5 km) | `INTAKE_SAMPLE_RADIUS_DEG` |
| Anomaly threshold | mean + 2 SD, after 14 days | `BLOOM_ANOMALY_STD_THRESHOLD`, `MIN_BASELINE_DAYS` |
| Wider Gulf box | lon 49–57, lat 24–27.5 | `GULF_WATCH_BBOX` |
| Qatar reference point | 25.3 N, 51.5 E | `QATAR_REFERENCE_POINT` |
| Hotspot rule | > 95th percentile AND > 3.0 mg/m³ | `ELEVATED_PERCENTILE`, `ELEVATED_MIN_VALUE` |
| Trajectory | 10-day window, ≥ 4 points, ±5 km/day | `gulf.py` |
| Projection | 10 days ahead, 20 km arrival, top 5 hotspots | `projection.py` |
| 2008 bloom origin | Dibba Al-Hassan, 25.59 N, 56.27 E | `backtest.py` |

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
