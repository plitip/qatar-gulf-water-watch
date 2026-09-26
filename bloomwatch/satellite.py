"""
Downloading from Copernicus Marine.

Every scene the pipeline uses is one dataset cut down to one bounding box, so they all
go through download_subset(). It caches each file on disk, so running twice on the
same day doesn't download anything again.

Two kinds of failure matter:
- The date isn't published yet. Near-real-time data trails the calendar by a day or
  more, and copernicusmarine reports that as CoordinatesOutOfDatasetBounds. That's
  expected: callers either step back a day or record the day as missing.
- Anything else (login, network, a dataset ID that no longer exists) is a real error.

copernicusmarine is imported inside the functions, so everything else in the package,
and the tests, work without it installed.
"""

import logging
from datetime import date, timedelta
from pathlib import Path

from .config import MAX_LOOKBACK_DAYS

log = logging.getLogger(__name__)


def is_not_published(exc: Exception) -> bool:
    """True when copernicusmarine says the requested date isn't in the dataset (yet)."""
    # Matched by name, because the exception's import path has moved between
    # copernicusmarine versions.
    return type(exc).__name__ == "CoordinatesOutOfDatasetBounds"


def download_subset(dataset_id, variables, bbox, start, end, cache_dir: Path, filename: str) -> Path:
    """Download one dataset over one box and time range, or reuse the cached file."""
    path = cache_dir / filename
    if path.exists():
        log.info("Using cached %s", filename)
        return path

    import copernicusmarine

    cache_dir.mkdir(parents=True, exist_ok=True)
    request = dict(
        dataset_id=dataset_id,
        variables=list(variables),
        minimum_longitude=bbox["min_lon"],
        maximum_longitude=bbox["max_lon"],
        minimum_latitude=bbox["min_lat"],
        maximum_latitude=bbox["max_lat"],
        start_datetime=start,
        output_filename=filename,
        output_directory=str(cache_dir),
    )
    if end is not None:
        request["end_datetime"] = end
    copernicusmarine.subset(**request)
    return path


def download_day(dataset_id, variables, bbox, day: date, cache_dir: Path, prefix: str) -> Path:
    """One calendar day of a dataset, saved as <prefix>_<YYYY-MM-DD>.nc."""
    return download_subset(
        dataset_id,
        variables,
        bbox,
        start=f"{day.isoformat()}T00:00:00",
        end=f"{day.isoformat()}T23:59:59",
        cache_dir=cache_dir,
        filename=f"{prefix}_{day.isoformat()}.nc",
    )


def download_latest_day(download, start: date) -> tuple[Path, date]:
    """Call download(day) for `start`, then each day before it, until one is published.

    Returns the file and the date it's actually for. Stops at the first error that
    isn't "not published yet", because stepping back won't fix a login problem.
    """
    day = start
    for _ in range(MAX_LOOKBACK_DAYS):
        log.info("Trying scene for %s ...", day)
        try:
            return download(day), day
        except Exception as exc:
            if is_not_published(exc):
                log.info("No data yet for %s (not published), trying the day before ...", day)
                day -= timedelta(days=1)
                continue
            explain_download_error(exc)
            raise

    raise RuntimeError(
        f"No published scene in the last {MAX_LOOKBACK_DAYS} days (checked back from {start}). "
        "The dataset may be delayed longer than usual, or something upstream has changed."
    )


def explain_download_error(exc: Exception) -> None:
    """Log what a failed download most likely means and what to do about it."""
    if type(exc).__name__ == "DatasetNotFound":
        log.error(
            "The dataset ID isn't in the Copernicus Marine catalogue any more (IDs change when "
            "products are reprocessed). Run `python -m bloomwatch datasets` to find the current "
            "one and update it in bloomwatch/config.py."
        )
    else:
        log.error(
            "Could not download the satellite scene: %s: %s. This is usually a network or "
            "login problem: check that `copernicusmarine login` succeeded and that this machine "
            "can reach the Copernicus Marine servers.",
            type(exc).__name__,
            exc,
        )


def list_chlorophyll_datasets() -> list[str]:
    """Chlorophyll dataset IDs in the live catalogue, for when an ID stops working."""
    import copernicusmarine

    catalogue = copernicusmarine.describe(contains=["CHL"], disable_progress_bar=True)
    matches = set()
    for product in catalogue.products:
        for dataset in product.datasets:
            dataset_id = dataset.dataset_id.lower()
            if "plankton" in dataset_id or "chl" in dataset_id:
                matches.add(f"{dataset.dataset_id}    (product: {product.product_id})")
    return sorted(matches)
