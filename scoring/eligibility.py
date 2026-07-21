"""Scoring eligibility: which observation may stand in for a target instant.

Decided 2026-07-21 (delegated by Alex; evidence in reports/p2 + vault DECISIONS):

1. Tolerance +/-10 min, symmetric, boundary-inclusive — the spec's provisional
   bound, kept because once polling cadence is fixed to a true 10-min cycle,
   the nearest poll is always within 5 min of the target; a wider window
   would weaken the public claim ("scored against state within 10 minutes of
   08:30") for no coverage gain.
2. Observations after the target are as valid as before it — scoring happens
   after the fact, so nothing leaks; a 08:35 poll is better evidence about
   08:30 than a 08:20 poll.
3. last_reported does NOT gate on age: the live feed's per-station timestamps
   are demonstrably broken (median ~16 h stale, p99 in decades) while the
   feed header is fresh (~3 s). Gating on it would disqualify everything.
   Only pathological clocks are rejected: a last_reported from the future.
   Feed-level freshness is enforced upstream in the quality ledger.
"""
from __future__ import annotations

from datetime import datetime, timedelta

TOLERANCE = timedelta(minutes=10)
CLOCK_SLACK = timedelta(minutes=5)


def eligible_observation(target_ts: datetime, poll_ts: datetime,
                         last_reported: datetime | None) -> bool:
    if abs(poll_ts - target_ts) > TOLERANCE:
        return False
    if last_reported is not None and last_reported > poll_ts + CLOCK_SLACK:
        return False
    return True
