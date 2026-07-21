from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd

from bikes.backtest import FEATURE_COLS
from bikes.forecast import (FrozenModel, append_ledger, build_issuance_rows,
                            issuance_sets, run_issuance)

UTC = timezone.utc
# 2026-07-22 06:00 UTC == 07:00 IST (summer): the morning run instant
NOW = datetime(2026, 7, 22, 6, 0, tzinfo=UTC)


def write_raw(tmp_path, stations=("1", "2")):
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rows = []
    for mins in (90, 60, 30, 3):
        for sid in stations:
            ts = NOW - timedelta(minutes=mins)
            rows.append({"station_id": sid, "num_bikes_available": 5 + mins // 30,
                         "num_docks_available": 15, "is_installed": True,
                         "is_renting": True, "is_returning": True,
                         "last_reported": ts, "poll_ts": ts,
                         "feed_last_updated": ts})
    pd.DataFrame(rows).to_parquet(raw / "2026-07-22.parquet", index=False)
    return raw


def fake_weather(*_a, **_k):
    hours = pd.date_range(NOW - timedelta(hours=2), periods=48, freq="h")
    return pd.DataFrame({"ts": hours, "temp": 12.0, "precip": 0.0, "wind": 4.0})


class StubPredictor:
    def __init__(self, p):
        self.p = p
        self.classes_ = np.array([False, True])

    def predict_proba(self, x):
        return np.column_stack([np.full(len(x), 1 - self.p),
                                np.full(len(x), self.p)])


def frozen():
    clim = {"full": {}, "pool": {}, "global": 0.9}
    manifest = {"version": "v1", "features": FEATURE_COLS,
                "stations": ["1", "2"]}
    return FrozenModel(bike=StubPredictor(0.8), dock=StubPredictor(0.95),
                       climatology=clim, manifest=manifest)


def test_issuance_sets_by_dublin_hour():
    assert issuance_sets(NOW) == [("morning", "short", date(2026, 7, 22)),
                                  ("evening", "long", date(2026, 7, 22))]
    evening = datetime(2026, 7, 22, 15, 0, tzinfo=UTC)  # 16:00 IST
    assert issuance_sets(evening) == [("evening", "short", date(2026, 7, 22)),
                                      ("morning", "long", date(2026, 7, 23))]
    off_hour = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)
    assert issuance_sets(off_hour) == []


def test_build_issuance_rows_mirrors_p2_features(tmp_path):
    raw = write_raw(tmp_path)
    capacity = pd.Series({"1": 20.0, "2": 20.0})
    rows, unissued = build_issuance_rows(
        raw, capacity, fake_weather, NOW,
        sets=[("morning", "short", date(2026, 7, 22))])
    assert unissued == 0
    assert set(FEATURE_COLS) <= set(rows.columns)
    r = rows[rows["station_id"] == "1"].iloc[0]
    assert r["bikes"] == 5.0          # 3-min-old poll: 5 + 3//30
    assert r["d30"] == -1.0           # 5 - 6 (state 30 min earlier)
    assert r["horizon_min"] == 90


def test_stale_station_is_unissued(tmp_path):
    raw = write_raw(tmp_path, stations=("1",))
    # station 2 exists in capacity but has no fresh poll
    capacity = pd.Series({"1": 20.0, "2": 20.0})
    rows, unissued = build_issuance_rows(
        raw, capacity, fake_weather, NOW,
        sets=[("morning", "short", date(2026, 7, 22))])
    assert set(rows["station_id"]) == {"1"}


def test_ledger_append_is_idempotent(tmp_path):
    ledger = tmp_path / "ledger"
    rows = pd.DataFrame([{
        "issued_at_utc": NOW.isoformat(), "window": "morning",
        "horizon": "short", "target_ts_utc": "2026-07-22T07:30:00+00:00",
        "station_id": "1", "event": "bike", "p_model": 0.8,
        "p_clim": 0.9, "p_pers": 1.0, "model_version": "v1"}])
    added1, skipped1 = append_ledger(rows, ledger)
    added2, skipped2 = append_ledger(rows, ledger)
    assert (added1, skipped1) == (1, 0)
    assert (added2, skipped2) == (0, 1)
    files = list((ledger / "forecasts").glob("*.csv"))
    assert len(files) == 1
    assert len(pd.read_csv(files[0])) == 1


def test_run_issuance_produces_both_events_and_probabilities(tmp_path):
    raw = write_raw(tmp_path)
    ledger = tmp_path / "ledger"
    capacity = pd.Series({"1": 20.0, "2": 20.0})
    added = run_issuance(frozen(), raw, capacity, fake_weather, ledger, NOW)
    df = pd.read_csv(ledger / "forecasts" / "2026-07-22.csv")
    # 2 sets x 2 stations x 2 events
    assert added == 8 and len(df) == 8
    bike = df[df["event"] == "bike"]
    assert (bike["p_model"] == 0.8).all()
    assert (df[df["event"] == "dock"]["p_model"] == 0.95).all()
    assert (bike["p_pers"] == 1.0).all()  # 5 bikes at issuance
    assert (df["p_clim"] == 0.9).all()    # global fallback


def test_run_issuance_noop_off_hours(tmp_path):
    raw = write_raw(tmp_path)
    ledger = tmp_path / "ledger"
    off = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)
    added = run_issuance(frozen(), raw, pd.Series({"1": 20.0}), fake_weather,
                         ledger, off)
    assert added == 0
    assert not (ledger / "forecasts").exists()
