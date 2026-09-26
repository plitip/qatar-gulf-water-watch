"""
run_daily_watch.py

Single entry point for a daily scheduled run: does everything this
project does in one go, so Task Scheduler only needs one job instead
of four.

Runs, in order:
    1. qatar_bloom_watch.py               -- intake-level anomaly check
    2. scan_gulf_for_approaching_blooms.py -- today's wider-Gulf snapshot
    3. scan_gulf_trajectory.py             -- 10-day trajectory trend
    4. update_dashboard_gulf_panel.py      -- refresh the dashboard panel

Each step's own errors are logged and do NOT stop the later steps --
e.g. if the trajectory scan fails because a day's data isn't published
yet, the intake check and dashboard update still happen. The script
exits non-zero only if every step failed, so Task Scheduler can flag a
genuinely broken run without flagging routine single-day data gaps.

RUN (manually, to test):
    python run_daily_watch.py

SCHEDULE IT (Windows):
    Task Scheduler -> Create Basic Task -> Trigger: Daily, pick a time
    -> Action: Start a program
         Program/script:  python
         Arguments:       run_daily_watch.py
         Start in:        (this folder's full path)
"""

import subprocess
import sys
from pathlib import Path

from qatar_bloom_watch import log

PROJECT_DIR = Path(__file__).resolve().parent

STEPS = [
    "qatar_bloom_watch.py",
    "scan_gulf_for_approaching_blooms.py",
    "scan_gulf_trajectory.py",
    "update_dashboard_gulf_panel.py",
]


def run_step(script_name: str) -> bool:
    log.info("=== Running %s ===", script_name)
    result = subprocess.run([sys.executable, str(PROJECT_DIR / script_name)], cwd=PROJECT_DIR)
    if result.returncode != 0:
        log.error("%s exited with code %d -- continuing with the remaining steps.", script_name, result.returncode)
        return False
    return True


def main() -> int:
    results = {step: run_step(step) for step in STEPS}

    log.info("=== Summary ===")
    for step, ok in results.items():
        log.info("  %s: %s", step, "OK" if ok else "FAILED")

    if not any(results.values()):
        log.error("Every step failed -- something is likely broken (auth, network, or a changed dataset ID).")
        return 1

    if not all(results.values()):
        log.warning("Some steps failed -- see above. Today's data may be incomplete, but the dashboard was "
                     "refreshed with whatever succeeded.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
