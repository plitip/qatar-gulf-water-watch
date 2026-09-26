# Status and roadmap

## What's verified, and how

**Run against real satellite data:**
- The daily intake check (`bloomwatch check`) and the monthly 2018 → Aug 2026 history
  (`bloomwatch history`, 312 rows), shown on the dashboards.
- The wider-Gulf scan, the 10-day trajectory and the full `daily` run (September 2026). The
  first real runs exposed a flaw in the original hotspot rule, and it was redesigned
  (see [DECISIONS.md](DECISIONS.md#method)).
- The 2008 backtest, Aug 2008 to May 2009, every 3 days, all 102 days with usable images:
  - Flags before the documented first sighting (~25 Aug): 1 August (89 km from the bloom's
    origin near Dibba, followed by five empty checks), then 19 and 22 August (72 and 71 km
    from the origin), and flagged on every check through 28 August.
  - Early-August comparison: in the same checks (1 to 22 August) of 14 other years
    (2003–2007, 2009–2017), the check found flagged water within 100 km of Dibba only in
    2017 (3 of 8 checks, the same as 2008); the other 13 years had none.
  - After that, the flagged water follows the documented path: through the Strait of Hormuz
    in October and across the central Gulf by December. The September flags north of Qatar
    came before the bloom had passed the Strait, so they were probably unrelated.
  - 96 of the 102 checks flagged something somewhere. The early-August comparison covers
    the lead-time question; the flag rate over the whole season hasn't been compared yet.
- All four Copernicus dataset IDs, against the live catalogue (2026-09-26).

**Tested with synthetic data only** (`tests/test_logic.py`, 22 tests, run in CI): the
hotspot rule, trend verdicts, where unusual water recurs, advection math, backtest stepping
and summary, the comparison count, the map encoding, the intake anomaly check, dashboard
publishing and the flag log.

**Not verified yet:**
- The current projection on real current data.
- The GitHub Actions daily run (it needs the two Copernicus secrets added first).
- Intake coordinates (approximate, not checked against the actual facilities).
- Any check against water samples.

## Next

1. **Find out what happened off the UAE's east coast in August 2017.** It's the one
   comparison year where the check found water like 2008's. A reported bloom would make it
   a second hit; nothing reported makes it a false alarm.
2. **Look into Umm Al Houl.** Its 2026 readings were above range from January to June,
   concentrated in the one or two squares next to the intake (see DECISIONS.md).
   High-resolution imagery of that stretch of coast, and any construction or dredging
   there, would help tell a real change from a near-shore artefact.
3. **Compare the whole-season flag rate** (August to May) with a year without a major
   bloom, to judge how noisy the check is outside the early weeks.
4. **Add the two secrets and confirm the first automatic run** goes green on GitHub.
5. **Review flags as they come in** (`data/alert_log.json`), and keep the false ones.
6. Add `project` to the daily run and give it a dashboard panel.
7. A script that regenerates the dashboards' monthly history from `historical_chl_trends.csv`.
8. Verify intake coordinates against satellite imagery and public Kahramaa / QEWC info.
9. A real notification (email, or a GitHub issue that emails the owner) once the flags
   have a track record worth acting on.

## Later

- A UAE comparison site, to tell a Qatar-only spike from a Gulf-wide event.
- Sea surface temperature, then dissolved oxygen, alongside chlorophyll
  (see [DECISIONS.md](DECISIONS.md)).
- Tracking individual patches between days (optical-flow style) instead of the nearest
  patch's distance.
