"""Commute windows and issuance instants, Europe/Dublin -> UTC (DST-aware)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DUBLIN = ZoneInfo("Europe/Dublin")

ISSUE_TIMES = {"morning": time(7, 0), "evening": time(16, 0)}
TARGET_TIMES = {"morning": time(8, 30), "evening": time(17, 30)}


def _local_to_utc(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=DUBLIN).astimezone(timezone.utc)


def window_instants(d: date) -> dict[str, tuple[datetime, datetime]]:
    return {w: (_local_to_utc(d, ISSUE_TIMES[w]), _local_to_utc(d, TARGET_TIMES[w]))
            for w in ("morning", "evening")}


def long_issuance(d: date, window: str) -> datetime:
    if window == "morning":  # issued at the prior day's evening run
        return _local_to_utc(d - timedelta(days=1), ISSUE_TIMES["evening"])
    return _local_to_utc(d, ISSUE_TIMES["morning"])  # evening: same-day morning run
