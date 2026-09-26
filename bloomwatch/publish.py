"""
Everything the dashboards show comes out of here.

- The latest 10-day trajectory, into both dashboards.
- The flag log: every time the daily run flags something (an intake reading unusual for
  that intake, or the Gulf trajectory turning "approaching"), it's added to
  data/alert_log.json with review = "not reviewed". Reviewing a flag means editing that
  field by hand to "likely real" or "false alarm", so the log doubles as a record of how
  often the system is wrong.
- status.json: when the daily run last ran, what it saw, and the flag log, for the
  "Daily watch" panel.
- The 2008 backtest summary.

Nothing here notifies anyone. Flags are recorded and shown on the dashboard, and that's
all the system does with them today.
"""

import json
import logging
import re
from datetime import datetime, timezone

from .config import ALERT_LOG_FILE, GULF_TRAJECTORY_FILE, REACT_DATA_DIR, REACT_PUBLIC_DATA_DIR, STATIC_DASHBOARD_HTML

log = logging.getLogger(__name__)

REVIEW_STATES = ("not reviewed", "likely real", "false alarm")
FLAGS_SHOWN_ON_DASHBOARD = 30

# The static dashboard embeds its data as JS literals, because fetch() of a local JSON
# file fails when the page is opened as file://. Only this one line is replaced.
DASHBOARD_TRAJECTORY_LINE = re.compile(r"var GULF_TRAJECTORY = .*?;", re.DOTALL)


def publish_trajectory_to_dashboard(
    trajectory_file=GULF_TRAJECTORY_FILE,
    html_file=STATIC_DASHBOARD_HTML,
    react_file=REACT_DATA_DIR / "gulfTrajectory.json",
) -> None:
    """Put the latest trajectory into both dashboards. In the static one, only the
    `var GULF_TRAJECTORY = ...;` line changes; the rest stays byte-for-byte."""
    if not trajectory_file.exists():
        raise FileNotFoundError(f"{trajectory_file} not found. Run `python -m bloomwatch trajectory` first.")

    trajectory = json.loads(trajectory_file.read_text(encoding="utf-8"))
    html = html_file.read_text(encoding="utf-8")
    if not DASHBOARD_TRAJECTORY_LINE.search(html):
        raise ValueError(f"Couldn't find 'var GULF_TRAJECTORY = ...;' in {html_file}.")

    replacement = "var GULF_TRAJECTORY = " + json.dumps(trajectory) + ";"
    html_file.write_text(DASHBOARD_TRAJECTORY_LINE.sub(lambda _: replacement, html, count=1), encoding="utf-8", newline="")
    _write_json(react_file, trajectory)
    log.info(
        "Dashboards updated with trajectory data through %s (trend: %s).",
        trajectory["window_end_date"], trajectory["trend"]["verdict"],
    )


def load_alert_log(path=ALERT_LOG_FILE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def record_flags(new_flags: list[dict], path=ALERT_LOG_FILE) -> list[dict]:
    """Add flags ({flagged_on, source, message}) to the log, skipping any already in it
    (a rerun on the same scene raises the same flag). Returns the full log, newest first."""
    flag_log = load_alert_log(path)
    already = {(f["flagged_on"], f["source"], f["message"]) for f in flag_log}
    for flag in new_flags:
        if (flag["flagged_on"], flag["source"], flag["message"]) not in already:
            flag_log.append({**flag, "review": "not reviewed"})
            log.warning("Flag recorded: %s", flag["message"])

    unknown = {f["review"] for f in flag_log} - set(REVIEW_STATES)
    if unknown:
        raise ValueError(f"Unknown review value(s) in {path.name}: {sorted(unknown)}. Use one of {REVIEW_STATES}.")

    flag_log.sort(key=lambda f: f["flagged_on"], reverse=True)
    _write_json(path, flag_log)
    return flag_log


def flags_from_run(intake_result: dict | None, trajectory: dict | None) -> list[dict]:
    """Turn one daily run's results into flags."""
    flags = []
    if intake_result:
        for alert in intake_result["alerts"]:
            flags.append({"flagged_on": intake_result["scene_date"], "source": "intake", "message": alert})
    if trajectory and trajectory["trend"]["verdict"] == "approaching":
        flags.append({
            "flagged_on": trajectory["window_end_date"],
            "source": "gulf trajectory",
            "message": trajectory["trend"]["message"],
        })
    return flags


def write_status(steps_ok: dict, intake_result, gulf_snapshot, flag_log, path=REACT_DATA_DIR / "status.json") -> dict:
    """What the dashboard's "Daily watch" panel shows."""
    status = {
        "last_run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "steps": steps_ok,
        "intake": None if intake_result is None else {
            "scene_date": intake_result["scene_date"],
            "readings": {site: None if v is None else round(v, 2) for site, v in intake_result["readings"].items()},
        },
        "gulf": None if gulf_snapshot is None else {
            "scene_date": gulf_snapshot["date"],
            "hotspot_count": gulf_snapshot["hotspot_count"],
            "nearest_km": gulf_snapshot["nearest_km"],
        },
        "flags_total": len(flag_log),
        "flags_by_review": {state: sum(1 for f in flag_log if f["review"] == state) for state in REVIEW_STATES},
        "recent_flags": flag_log[:FLAGS_SHOWN_ON_DASHBOARD],
    }
    _write_json(path, status)
    return status


def publish_backtest_summary(result: dict, path=REACT_DATA_DIR / "backtest2008.json") -> None:
    """The part of the 2008 backtest the dashboard shows (the daily detail stays in data/)."""
    _write_json(path, {
        "documented_first_sighting": result["documented_first_sighting"],
        "event_window": result["event_window"],
        "step_days": result["step_days"],
        **result["summary"],
        "early_august_comparison": result.get("early_august_comparison"),
    })


def publish_backtest_maps(frames: dict, path=REACT_PUBLIC_DATA_DIR / "redtide2008.json") -> None:
    """The 2008 map frames. A static file the site fetches when the section comes into view,
    so ~500 KB of map data isn't bundled into the page's JavaScript."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(frames, separators=(",", ":")), encoding="utf-8")
    log.info("Wrote %d map frames to %s", len(frames["frames"]), path)


def _write_json(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
