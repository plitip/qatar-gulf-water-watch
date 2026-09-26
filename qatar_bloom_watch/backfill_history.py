"""
backfill_history.py

One-off: populate chl_history.json with the last BACKFILL_DAYS of
chlorophyll readings, so qatar_bloom_watch.py's anomaly baseline is
ready immediately instead of waiting ~2 weeks of daily runs.

Reuses the same fetch/sample logic as the main script, so both stay
consistent. Run once, then switch to running qatar_bloom_watch.py
daily (see README.md for the Task Scheduler setup) to keep the
history current going forward.

RUN:
    python backfill_history.py
"""

from datetime import date, timedelta

from qatar_bloom_watch import (
    DESAL_INTAKE_SITES,
    fetch_chlorophyll_scene_for_date,
    sample_intake_readings,
    load_reading_history,
    save_reading_history,
    log,
)

BACKFILL_DAYS = 14


def main() -> None:
    history = load_reading_history()
    already_have = {site: {d for d, _ in history[site]} for site in DESAL_INTAKE_SITES}

    filled = 0
    skipped = 0

    for days_ago in range(BACKFILL_DAYS, 0, -1):
        target_date = date.today() - timedelta(days=days_ago)
        target_date_str = target_date.isoformat()

        if all(target_date_str in already_have[site] for site in DESAL_INTAKE_SITES):
            log.info("Already have %s, skipping", target_date_str)
            skipped += 1
            continue

        log.info("Backfilling %s ...", target_date_str)
        try:
            scene_path = fetch_chlorophyll_scene_for_date(target_date)
        except Exception as exc:
            if type(exc).__name__ == "CoordinatesOutOfDatasetBounds":
                log.info("No data available yet for %s, skipping", target_date_str)
            else:
                log.warning("Could not fetch %s (%s: %s), skipping", target_date_str, type(exc).__name__, exc)
            skipped += 1
            continue

        readings = sample_intake_readings(scene_path)
        for site_name, value in readings.items():
            if value is None:
                continue
            if target_date_str not in already_have[site_name]:
                history[site_name].append((target_date_str, value))
        filled += 1

    save_reading_history(history)
    log.info("Backfill done: %d day(s) added, %d skipped.", filled, skipped)
    log.info("Run qatar_bloom_watch.py normally from now on to keep the history current.")


if __name__ == "__main__":
    main()
