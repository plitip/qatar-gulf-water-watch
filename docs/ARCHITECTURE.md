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
   │                                                   (+ currents dataset)
   │
   ├─ Monthly reprocessed chlorophyll (confirmed) ──► intake.export_monthly_history ──► historical_chl_trends.csv
   │                                                    (2018 → present, per intake; feeds the dashboard chart)
   │
   └─ Daily reprocessed chlorophyll ──► gulf.load_monthly_normal (each pixel's normal, 2018–2025)
                                    └─► backtest.run_backtest ──► backtest_2008_red_tide.json
                                         (Aug 2008 – May 2009, real historical event)

python -m bloomwatch daily = check → scan → trajectory → dashboard, then publish.py records
flags and writes status.json for the site. Output files go in data/.
```

## Python package: `bloomwatch/`

Everything runs as `python -m bloomwatch <command>` from the repo root, or as
`bloomwatch <command>` after `pip install -e .`.

| Module | What's in it | Commands | Status |
|---|---|---|---|
| `config.py` | Intake coordinates, bounding boxes, dataset IDs, file paths. | | Coordinates approximate |
| `satellite.py` | The one Copernicus download function: caching, "not published yet" handling, stepping back to the newest published day, error explanations, catalogue lookup. | `datasets` | Run against real data |
| `intake.py` | Averages a ~5 km box at each intake and compares it with that intake's own history (flag if > mean + 2 SD, after 14 days); a date that's already recorded isn't counted twice. Also the 14-day backfill and the monthly 2018 → present history. | `check`, `backfill`, `history` | Run against real data |
| `gulf.py` | Hotspot scan of the wider Gulf (each pixel > 3 SD above its own normal for the month, > 3.0 mg/m³, in a patch of ≥ 4 pixels), each month's per-pixel normal, the 10-day nearest-hotspot trend (≤ −5 km/day approaching, ≥ +5 receding, needs ≥ 4 usable days), and where unusual water kept recurring in that window (`recurring_area`: distance and direction from Doha, distance from shore). | `scan`, `trajectory` | Run against real data; the rule was redesigned after the first real runs (DECISIONS.md) |
| `publish.py` | Everything the dashboards show: the trajectory (both dashboards), the flag log (`data/alert_log.json`), `status.json` for the "Latest satellite check" section, and the backtest summary. | `dashboard` | Run against real data |
| `projection.py` | Moves the 5 nearest hotspots along the sampled ocean current, held constant for 10 days, and flags any that come within 20 km of the coast. Physics, not a trained model. | `project` | Math tested offline; not yet run on real currents |
| `backtest.py` | Runs the same detector over Aug 2008 – May 2009 (every 3 days) and compares its first flag with the documented first sighting (~25 Aug 2008); runs the same early-August checks for 14 comparison years; and exports every checked day as a small map for the site. | `backtest` | Run on real data, with the comparison years |
| `__main__.py` | The command line. `daily` runs check → scan → trajectory → dashboard, then records flags and writes the status; one failing step doesn't stop the rest, and it exits non-zero only if every step failed. | `daily` | Run against real data |

`tests/test_logic.py` has 22 offline tests: the hotspot rule, trend verdicts, where unusual
water recurs, advection arrival, backtest stepping and summary, the comparison count, the
map encoding, the intake anomaly check, the dashboard update and the flag log. Run them with
`python -m pytest`. Downloaded scenes are cached in `data/cache/<kind>/`, one file per day.

## Copernicus datasets

| Purpose | Dataset ID | Variable(s) | Confirmed? |
|---|---|---|---|
| Daily near-real-time chlorophyll | `cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D` | `CHL` | **Yes**: ran on the laptop (dataset version 202311) |
| Monthly reprocessed chlorophyll | `cmems_obs-oc_glo_bgc-plankton_my_l4-multi-4km_P1M` | `CHL` | **Yes**: downloaded 2018 → present (version 202603) |
| Ocean currents | `cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m` | `uo`, `vo` | **Yes**: in the live catalogue, June 2022 onward (checked 2026-09-26) |
| Daily reprocessed chlorophyll (normals, 2008 backtest) | `cmems_obs-oc_glo_bgc-plankton_my_l4-gapfree-multi-4km_P1D` | `CHL` | **Yes**: September 1997 onward (checked 2026-09-26). The ID first assumed, without `gapfree`, doesn't exist |

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
| Hotspot rule | > 3 SD above the pixel's own normal, > 3.0 mg/m³, patch ≥ 4 pixels | `ANOMALY_Z_THRESHOLD`, `ELEVATED_MIN_VALUE`, `MIN_PATCH_PIXELS` |
| Normal years | 2018–2025 | `NORMAL_YEARS` |
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

**`qatar_dashboard_react/`** is the version deployed to Vercel. From top to bottom: a
headline built from the data (at the moment, that August 2026 was higher than any August
since 2018 at all three intakes), the three intakes with one small chart each (2026 as a
line over the usual 2018–2025 range as a shaded band, hover and keyboard readable), the
monthly numbers as a table, the latest satellite check with the flag log, the 2008 red
tide with the backtest result, and a short "About the data". Components:
`StatusLine`, `IntakeOverview`, `SeasonalChart`, `MonthlyTable`, `LatestCheck`, `RedTide2008`, `RedTideMap`,
`ThemeToggle`. Data in `src/data/`: `chlHistory.js` (monthly history), and
`status.json`, `gulfTrajectory.json`, `backtest2008.json`, all written by `publish.py`. The
2008 map frames (~540 KB, ~60 KB gzipped) are `public/data/redtide2008.json`, fetched only
when that section comes near the screen: one character per three satellite squares, each
square one of land / normal / well above normal / flagged.
A section with no data doesn't render at all.

Design rules it follows: one typeface (Public Sans), no boxes around sections, one
decimal place, dates written out ("August 2026"), and colour with three jobs only: ink
for text, grey for the usual range, blue for this year. The page describes findings, not
the code; file names and implementation notes stay in these docs.

Animations use GSAP in `src/animations/`: numbers counting up, chart lines drawing in, and
sections revealing on scroll. The real value is in the HTML before any animation runs,
and `prefers-reduced-motion` turns them off.

Security headers (CSP, HSTS, frame and referrer policy) are defined once in
`vercel.json`; `npm run preview` serves the same headers locally so a policy mistake shows
up before deploy.
