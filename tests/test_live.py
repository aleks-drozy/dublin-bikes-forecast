from datetime import datetime, timedelta, timezone

import pandas as pd

from bikes.live import latest_state

UTC = timezone.utc
AT = datetime(2026, 7, 22, 6, 0, tzinfo=UTC)


def write_raw(tmp_path, rows):
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    for day, g in df.groupby(df["poll_ts"].dt.date):
        g.to_parquet(raw / f"{day.isoformat()}.parquet", index=False)
    return raw


def poll(ts, sid, bikes):
    return {"station_id": sid, "num_bikes_available": bikes,
            "num_docks_available": 20 - bikes, "is_installed": True,
            "is_renting": True, "is_returning": True,
            "last_reported": ts, "poll_ts": ts, "feed_last_updated": ts}


def test_latest_state_full(tmp_path):
    rows = [poll(AT - timedelta(minutes=25), "1", 9),
            poll(AT - timedelta(minutes=5), "1", 7),
            poll(AT + timedelta(minutes=5), "1", 3),      # future: ignored
            poll(AT - timedelta(minutes=45), "2", 4)]     # stale: dropped
    raw = write_raw(tmp_path, rows)
    state = latest_state(raw, AT)
    assert list(state["station_id"]) == ["1"]
    assert state.iloc[0]["bikes"] == 7
    assert state.iloc[0]["poll_ts"] == AT - timedelta(minutes=5)


def test_latest_state_crosses_midnight_partitions(tmp_path):
    at = datetime(2026, 7, 22, 0, 5, tzinfo=UTC)
    rows = [poll(at - timedelta(minutes=10), "1", 5)]  # lives in the 07-21 file
    raw = write_raw(tmp_path, rows)
    state = latest_state(raw, at)
    assert list(state["station_id"]) == ["1"]
