"""One poll cycle: fetch -> parse -> store -> account. ASCII output only."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from bikes.gbfs import (GBFS_INFO_URL, GBFS_STATUS_URL, fetch_json,
                        parse_station_information, parse_station_status)
from bikes.quality import record_poll
from bikes.store import append_status, upsert_stations


def run_poll(root: Path, fetcher=fetch_json, now: datetime | None = None) -> bool:
    poll_ts = now or datetime.now(timezone.utc)
    started = time.monotonic()
    try:
        payload = fetcher(GBFS_STATUS_URL)
    except Exception as exc:  # noqa: BLE001 - every failure becomes a ledger row
        fetch_ms = int((time.monotonic() - started) * 1000)
        record_poll(root, poll_ts, ok=False, fetch_ms=fetch_ms, status_count=0,
                    skipped=0, feed_age_s=None, error=f"{type(exc).__name__}: {exc}")
        print(f"poll FAILED after {fetch_ms} ms: {type(exc).__name__}")
        return False

    fetch_ms = int((time.monotonic() - started) * 1000)
    result = parse_station_status(payload)
    append_status(result.records, poll_ts, result.feed_last_updated, root)
    feed_age_s = None
    if result.feed_last_updated is not None:
        feed_age_s = (poll_ts - result.feed_last_updated).total_seconds()
    record_poll(root, poll_ts, ok=True, fetch_ms=fetch_ms,
                status_count=len(result.records), skipped=result.skipped,
                feed_age_s=feed_age_s, error=None)

    try:  # station_information is best-effort; status data must survive its loss
        info = parse_station_information(fetcher(GBFS_INFO_URL))
        if info.records:
            upsert_stations(info.records, root)
    except Exception as exc:  # noqa: BLE001
        print(f"info fetch skipped: {type(exc).__name__}")

    print(f"poll ok: {len(result.records)} stations, {result.skipped} skipped, "
          f"{fetch_ms} ms, feed_age_s={feed_age_s}")
    return True


if __name__ == "__main__":
    run_poll(Path("data"))
    raise SystemExit(0)
