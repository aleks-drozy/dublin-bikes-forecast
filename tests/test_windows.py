from datetime import date, datetime, timezone

from bikes.windows import long_issuance, window_instants

UTC = timezone.utc


def test_summer_windows_are_ist_minus_one_hour():
    w = window_instants(date(2026, 6, 15))
    issue, target = w["morning"]
    assert issue == datetime(2026, 6, 15, 6, 0, tzinfo=UTC)    # 07:00 IST
    assert target == datetime(2026, 6, 15, 7, 30, tzinfo=UTC)  # 08:30 IST
    issue_e, target_e = w["evening"]
    assert issue_e == datetime(2026, 6, 15, 15, 0, tzinfo=UTC)
    assert target_e == datetime(2026, 6, 15, 16, 30, tzinfo=UTC)


def test_winter_windows_match_utc():
    w = window_instants(date(2026, 1, 15))
    issue, target = w["morning"]
    assert issue == datetime(2026, 1, 15, 7, 0, tzinfo=UTC)
    assert target == datetime(2026, 1, 15, 8, 30, tzinfo=UTC)


def test_long_issuance_morning_is_prior_evening_run():
    li = long_issuance(date(2026, 6, 15), "morning")
    assert li == datetime(2026, 6, 14, 15, 0, tzinfo=UTC)  # 16:00 IST day before


def test_long_issuance_evening_is_same_day_morning_run():
    li = long_issuance(date(2026, 6, 15), "evening")
    assert li == datetime(2026, 6, 15, 6, 0, tzinfo=UTC)  # 07:00 IST same day
