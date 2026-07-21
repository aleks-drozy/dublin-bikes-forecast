"""Scoring eligibility: which observation may stand in for a target instant.

DECISION POINT (Alex, P3): this rule is the honesty core of scoring.
Trade-offs:
  - tight tolerance -> more UNSCOREABLE_GAP days (less data, cleaner claim)
  - loose tolerance -> scoring against state that may not represent the
    target instant (more data, weaker claim)
  - feed staleness: an observation polled near the target may carry a
    last_reported minutes older; decide whether poll_ts or last_reported
    gates eligibility.
Spec provisional bound: +/- 10 minutes around the target instant.
"""
from __future__ import annotations

from datetime import datetime

# Filled in P3 by Alex (5-10 lines). Signature is fixed; P3 scoring code
# will import exactly this name.


def eligible_observation(target_ts: datetime, poll_ts: datetime,
                         last_reported: datetime | None) -> bool:
    raise NotImplementedError("P3 decision point - see module docstring")
