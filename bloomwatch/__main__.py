"""
Command line: python -m bloomwatch <command>

Run `python -m bloomwatch --help` for the list of commands. `daily` is the one to
schedule; the rest are for running one step on its own or for one-off jobs.
"""

import argparse
import logging
import sys
import time

from . import backtest, gulf, intake, projection, publish, satellite

log = logging.getLogger("bloomwatch")


def run_daily() -> int:
    """Check, scan, trajectory, then publish whatever worked to the dashboards.

    Each step runs even if an earlier one failed: a day's data being late shouldn't stop
    the dashboard from updating with the rest. Fails only if every step failed, so the
    scheduler flags a real breakage (login, network) but not a routine gap.
    """
    steps = [
        ("intake check", intake.check_intakes),
        ("Gulf scan", gulf.scan_today),
        ("trajectory", gulf.track_trajectory),
        ("dashboard update", publish.publish_trajectory_to_dashboard),
    ]
    results, succeeded = {}, {}
    for name, step in steps:
        log.info("=== %s ===", name)
        try:
            results[name] = step()
            succeeded[name] = True
        except Exception as exc:
            log.error("%s failed (%s: %s), carrying on with the rest.", name, type(exc).__name__, exc)
            succeeded[name] = False

    flag_log = publish.record_flags(publish.flags_from_run(results.get("intake check"), results.get("trajectory")))
    publish.write_status(succeeded, results.get("intake check"), results.get("Gulf scan"), flag_log)

    log.info("=== Summary ===")
    for name, ok in succeeded.items():
        log.info("  %s: %s", name, "OK" if ok else "FAILED")
    if not any(succeeded.values()):
        log.error("Every step failed: probably login, network, or a changed dataset ID.")
        return 1
    return 0


def run_backtest() -> None:
    result = backtest.run_and_save_backtest()
    publish.publish_backtest_summary(result)
    publish.publish_backtest_maps(backtest.backtest_map_frames(result))


def list_datasets() -> None:
    for line in satellite.list_chlorophyll_datasets() or ["No matches found."]:
        print(line)


COMMANDS = {
    "check": ("daily intake check, each intake against its own baseline", intake.check_intakes),
    "backfill": ("fill in the last 14 days of intake history (run once, first)", intake.backfill_history),
    "scan": ("today's hotspot snapshot for the wider Gulf", gulf.scan_today),
    "trajectory": ("10-day trend of the nearest hotspot's distance to Qatar", gulf.track_trajectory),
    "dashboard": ("write the latest trajectory into both dashboards", publish.publish_trajectory_to_dashboard),
    "daily": ("check, scan, trajectory, then publish results and flags (schedule this one)", run_daily),
    "project": ("drift today's hotspots along ocean currents", projection.project_hotspots),
    "history": ("monthly chlorophyll at each intake since 2018, as CSV", intake.export_monthly_history),
    "backtest": ("run the detector over the 2008-09 red tide (slow)", run_backtest),
    "datasets": ("list chlorophyll dataset IDs in the Copernicus catalogue", list_datasets),
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="bloomwatch",
        description="Satellite early warning for harmful algal blooms near Qatar's desalination intakes.",
        epilog="Most commands need a Copernicus Marine login (`copernicusmarine login`).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")
    for name, (help_text, _) in COMMANDS.items():
        subparsers.add_parser(name, help=help_text, description=help_text)

    args = parser.parse_args(argv)
    # Only our own loggers (bloomwatch.*) go through this handler. copernicusmarine prints
    # its own progress lines, and routing those through here too would show them twice.
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    # Importing copernicusmarine switches every formatter to UTC; keep ours on local time
    # so timestamps don't jump by hours halfway through a run.
    formatter.converter = time.localtime
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(logging.INFO)

    _, run = COMMANDS[args.command]
    if args.command == "daily":
        return run_daily()
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
