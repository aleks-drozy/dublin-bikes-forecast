from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from bikes.dataset import build_dataset
from bikes.features import make_features
from bikes.grid import build_grid
from bikes.labels import make_labels

UTC = timezone.utc
GRID_START = datetime(2026, 6, 14, 0, 0, tzinfo=UTC)
TARGET_MON = datetime(2026, 6, 15, 7, 30, tzinfo=UTC)   # 08:30 IST Mon Jun 15
ISSUE_MON = datetime(2026, 6, 15, 6, 0, tzinfo=UTC)     # 07:00 IST
DATES = [date(2026, 6, 15)]
CAPACITY = pd.Series({"1": 30, "2": 20})


@pytest.fixture(scope="module")
def grid():
    events = []
    ts = GRID_START
    while ts <= datetime(2026, 6, 16, 0, 0, tzinfo=UTC):
        for sid, bikes, docks in (("1", 10, 20), ("2", 2, 18)):
            if sid == "1" and ts == TARGET_MON:
                bikes, docks = 0, 30  # station 1 empty exactly at the target
            events.append({"ts": ts, "station_id": sid, "bikes": bikes,
                           "docks": docks, "is_installed": True,
                           "is_renting": True, "capacity": CAPACITY[sid]})
        ts += timedelta(minutes=5)
    return build_grid(pd.DataFrame(events))


@pytest.fixture(scope="module")
def weather():
    hours = pd.date_range(GRID_START, periods=48, freq="h")
    return pd.DataFrame({"ts": hours, "temp": hours.hour.astype(float),
                         "precip": 0.0, "wind": 5.0})


def test_labels_reflect_state_at_target(grid):
    labels = make_labels(grid, DATES)
    row = labels[(labels["window"] == "morning") & (labels["station_id"] == "1")]
    assert bool(row["y_bike"].iloc[0]) is False   # 0 bikes at 07:30 UTC
    assert bool(row["y_dock"].iloc[0]) is True
    row2 = labels[(labels["window"] == "morning") & (labels["station_id"] == "2")]
    assert bool(row2["y_bike"].iloc[0]) is True


def test_features_snapshot_deltas_calendar_weather(grid, weather):
    feats = make_features(grid, weather, CAPACITY, DATES)
    f = feats[(feats["window"] == "morning") & (feats["horizon"] == "short")
              & (feats["station_id"] == "1")].iloc[0]
    assert f["bikes"] == 10 and f["docks"] == 20
    assert f["d30"] == 0 and f["d60"] == 0
    assert f["fill"] == pytest.approx(10 / 30)
    assert f["how"] == 8            # Monday 08:30 Dublin -> 0*24 + 8
    assert f["day_type"] == 0
    assert f["horizon_min"] == 90
    assert f["temp"] == 7.0         # weather at floor(07:30 UTC) = 07:00


def test_long_horizon_issued_from_prior_evening(grid, weather):
    feats = make_features(grid, weather, CAPACITY, DATES)
    f = feats[(feats["window"] == "morning") & (feats["horizon"] == "long")
              & (feats["station_id"] == "1")].iloc[0]
    assert f["issue_ts"] == datetime(2026, 6, 14, 15, 0, tzinfo=UTC)
    assert f["horizon_min"] == 990


def test_rows_with_non_ok_issuance_are_dropped(grid, weather):
    grid.flags.loc[ISSUE_MON, "2"] = "UNKNOWN"
    try:
        feats = make_features(grid, weather, CAPACITY, DATES)
        sel = feats[(feats["window"] == "morning") & (feats["horizon"] == "short")]
        assert set(sel["station_id"]) == {"1"}
    finally:
        grid.flags.loc[ISSUE_MON, "2"] = "OK"


def test_leakage_guard_future_data_cannot_change_features(grid, weather):
    # Property: mutating grid data strictly AFTER a row's own issue_ts must
    # not change that row. Rows whose issuance lies inside the mutated span
    # (e.g. the evening run) legitimately differ and are excluded.
    before = make_features(grid, weather, CAPACITY, DATES)
    saved = grid.bikes.copy()
    try:
        grid.bikes.loc[grid.bikes.index > ISSUE_MON, :] = 999
        after = make_features(grid, weather, CAPACITY, DATES)
    finally:
        grid.bikes.loc[:, :] = saved
    unaffected = lambda df: (df[df["issue_ts"] <= ISSUE_MON]  # noqa: E731
                             .sort_values(["window", "horizon", "station_id"])
                             .reset_index(drop=True))
    assert len(unaffected(before)) > 0
    pd.testing.assert_frame_equal(unaffected(before), unaffected(after))


def test_build_dataset_joins_and_melts_events(grid, weather):
    ds = build_dataset(grid, weather, CAPACITY, DATES)
    assert set(ds["event"]) == {"bike", "dock"}
    row = ds[(ds["window"] == "morning") & (ds["horizon"] == "short")
             & (ds["station_id"] == "1") & (ds["event"] == "bike")].iloc[0]
    assert bool(row["y"]) is False
    assert row["bikes"] == 10
