# Qatar Bloom Watch

Early-warning prototype that watches satellite chlorophyll-a data near
Qatar's desalination intake points (Ras Laffan, Ras Abu Fontas, Umm Al
Houl) and flags readings that spike above each plant's own recent
baseline — a possible sign of an incoming harmful algal bloom ("red
tide"), the kind of event that has repeatedly shut down desalination
plants elsewhere in the Gulf.

## Setup (one time)

1. Install Python 3.9+ if you don't have it.
2. From this folder, install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Create a free account at https://marine.copernicus.eu, then log in
   from the command line:

   ```
   copernicusmarine login
   ```

## Run it

```
python qatar_bloom_watch.py
```

Each run:
- Downloads today's chlorophyll-a satellite scene for a bounding box
  around Qatar's coast (cached in `chl_data/`, so re-runs on the same
  day don't re-download).
- Averages the chlorophyll reading in a small box around each plant.
- Appends today's value to `chl_history.json`.
- Once at least 14 days of history exist, flags any plant whose
  reading is more than 2 standard deviations above its own recent
  average.

## Run it daily

For this to be useful, it needs to run every day so the baseline (and
any alert) actually means something. On Windows, the simplest way is
Task Scheduler:

1. Open Task Scheduler -> Create Basic Task.
2. Trigger: Daily, pick a time.
3. Action: Start a program -> point it at `python.exe`, with
   `qatar_bloom_watch.py` (full path) as the argument, and this
   folder as "Start in".

## Status

This is a working prototype, not an operational system. Before it
could be trusted for real decisions it still needs:
- Verification of the exact intake coordinates against the real
  facilities.
- Validation against known historical bloom events and real water
  samples, to tune `ANOMALY_STD_THRESHOLD` properly.
- A real notification channel (email/Telegram/Slack) instead of the
  current console print — see the `TODO` in `qatar_bloom_watch.py`.
- Ideally, a conversation with Kahramaa/QEWC about ground-truthing it.

## Files

- `qatar_bloom_watch.py`: the core pipeline and shared config (fetch -> sample -> check -> alert).
- `backfill_history.py`: one-off, fills the last 14 days of history.
- `find_chl_dataset.py`: one-off, lists chlorophyll dataset IDs in the catalogue.
- `fetch_historical_trends.py`: one-off, monthly history 2018 -> present for the dashboard.
- `scan_gulf_for_approaching_blooms.py`: today's wider-Gulf hotspot scan.
- `scan_gulf_trajectory.py`: 10-day nearest-hotspot trend (approaching / receding).
- `update_dashboard_gulf_panel.py`: writes the trajectory into `../qatar_dashboard/index.html`.
- `run_daily_watch.py`: runs the daily steps in order (point Task Scheduler at this).
- `predict_gulf_bloom_trajectory.py`: current-based projection of hotspots (dataset ID unverified).
- `backtest_2008_red_tide.py`: runs the detector against the real 2008-09 bloom (dataset ID unverified).
- `test_offline_logic.py`: offline tests for the pure-logic parts.
- `requirements.txt`: Python dependencies.
- `chl_data/`, `gulf_scan_data/`, etc.: cached satellite scenes (created automatically, gitignored).
- `chl_history.json`: running history of daily readings per plant (created automatically, gitignored).

For the full picture (data flow, dataset status, decisions, next steps), see `../docs/`.
