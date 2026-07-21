from datetime import datetime, timedelta, timezone

from scoring.eligibility import eligible_observation

TARGET = datetime(2026, 7, 22, 7, 30, tzinfo=timezone.utc)


def test_within_tolerance_both_sides():
    # last_reported must not sit in the poll's future - use the poll time itself
    early = TARGET - timedelta(minutes=9)
    late = TARGET + timedelta(minutes=9)
    assert eligible_observation(TARGET, early, early)
    assert eligible_observation(TARGET, late, late)


def test_boundary_is_inclusive_and_beyond_is_out():
    at10 = TARGET + timedelta(minutes=10)
    assert eligible_observation(TARGET, at10, at10)
    just_over = TARGET + timedelta(minutes=10, seconds=1)
    assert not eligible_observation(TARGET, just_over, just_over)
    early11 = TARGET - timedelta(minutes=11)
    assert not eligible_observation(TARGET, early11, early11)


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
