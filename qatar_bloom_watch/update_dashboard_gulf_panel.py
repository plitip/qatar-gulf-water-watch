"""
update_dashboard_gulf_panel.py

Refreshes the "Gulf-wide bloom trajectory" panel in the dashboard with
the latest results from scan_gulf_trajectory.py, without touching
anything else in the dashboard file (the monthly chlorophyll chart,
styling, etc. are left exactly as they are).

Run this AFTER scan_gulf_trajectory.py, whenever you want the
dashboard to reflect a fresh scan:

    python scan_gulf_trajectory.py
    python update_dashboard_gulf_panel.py

It does a single, narrow text substitution: it finds the line
  var GULF_TRAJECTORY = ...;
in the dashboard's <script> block and replaces the right-hand side
with the contents of gulf_bloom_trajectory.json. Everything else in
the file is byte-for-byte unchanged.
"""

import json
import os
import re

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAJECTORY_JSON = os.path.join(PROJECT_DIR, "gulf_bloom_trajectory.json")

# Adjust this if your dashboard folder lives somewhere else.
DASHBOARD_HTML = os.path.join(os.path.dirname(PROJECT_DIR), "qatar_dashboard", "index.html")

VAR_PATTERN = re.compile(r"var GULF_TRAJECTORY = .*?;", re.DOTALL)


def main() -> None:
    if not os.path.exists(TRAJECTORY_JSON):
        raise SystemExit(
            f"{TRAJECTORY_JSON} not found. Run scan_gulf_trajectory.py first."
        )
    if not os.path.exists(DASHBOARD_HTML):
        raise SystemExit(
            f"{DASHBOARD_HTML} not found. Update DASHBOARD_HTML in this script "
            f"if the dashboard lives somewhere else."
        )

    with open(TRAJECTORY_JSON) as f:
        trajectory = json.load(f)

    with open(DASHBOARD_HTML) as f:
        html = f.read()

    if not VAR_PATTERN.search(html):
        raise SystemExit(
            "Could not find 'var GULF_TRAJECTORY = ...;' in the dashboard file. "
            "Has the dashboard been regenerated in a way that changed that line?"
        )

    replacement = "var GULF_TRAJECTORY = " + json.dumps(trajectory) + ";"
    new_html = VAR_PATTERN.sub(lambda _m: replacement, html, count=1)

    with open(DASHBOARD_HTML, "w") as f:
        f.write(new_html)

    print(f"Updated {DASHBOARD_HTML} with trajectory data through {trajectory['window_end_date']} "
          f"(trend: {trajectory['trend']['verdict']}).")


if __name__ == "__main__":
    main()
