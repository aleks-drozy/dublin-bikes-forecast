from datetime import datetime, timedelta, timezone

from scoring.eligibility import eligible_observation

TARGET = datetime(2026, 7, 22, 7, 30, tzinfo=timezone.utc)


def test_within_tolerance_both_sides():
    assert eligible_observation(TARGET, TARGET - timedelta(minutes=9), TARGET)
    assert eligible_observation(TARGET, TARGET + timedelta(minutes=9), TARGET)


def test_boundary_is_inclusive_and_beyond_is_out():
    assert eligible_observation(TARGET, TARGET + timedelta(minutes=10), TARGET)
    assert not eligible_observation(TARGET, TARGET + timedelta(minutes=10, seconds=1), TARGET)
    assert not eligible_observation(TARGET, TARGET - timedelta(minutes=11), TARGET)


def test_ancient_last_reported_does_not_disqualify():
    # evidence-based call: the live feed's per-station timestamps are broken
    poll = TARGET + timedelta(minutes=2)
    assert eligible_observation(TARGET, poll, poll - timedelta(days=365))


def test_future_last_reported_is_rejected():
    poll = TARGET + timedelta(minutes=2)
    assert not eligible_observation(TARGET, poll, poll + timedelta(minutes=6))
    assert eligible_observation(TARGET, poll, poll + timedelta(minutes=4))  # slack


def test_missing_last_reported_is_eligible():
    assert eligible_observation(TARGET, TARGET, None)
