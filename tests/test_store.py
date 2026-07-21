from datetime import datetime, timezone

import pandas as pd

from bikes.gbfs import StationInfo, StatusRecord
from bikes.store import append_status, upsert_stations


def rec(sid="42", bikes=5):
    return StatusRecord(
        station_id=sid, num_bikes_available=bikes, num_docks_available=15,
        is_installed=True, is_renting=True, is_returning=True,
        last_reported=datetime(2026, 7, 21, 8, 39, tzinfo=timezone.utc),
    )


POLL_TS = datetime(2026, 7, 21, 8, 40, 12, tzinfo=timezone.utc)


def test_append_creates_daily_partition_named_by_utc_date(tmp_path):
    path = append_status([rec()], POLL_TS, POLL_TS, tmp_path)
    assert path.name == "2026-07-21.parquet"
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert df.loc[0, "station_id"] == "42"
    assert df.loc[0, "poll_ts"] == pd.Timestamp(POLL_TS)


def test_append_twice_accumulates_rows(tmp_path):
    append_status([rec()], POLL_TS, POLL_TS, tmp_path)
    later = POLL_TS.replace(minute=50)
    path = append_status([rec(bikes=4)], later, later, tmp_path)
    df = pd.read_parquet(path)
    assert len(df) == 2
    assert sorted(df["num_bikes_available"]) == [4, 5]


def test_append_near_midnight_splits_partitions_by_utc(tmp_path):
    late = datetime(2026, 7, 21, 23, 55, tzinfo=timezone.utc)
    next_day = datetime(2026, 7, 22, 0, 5, tzinfo=timezone.utc)
    p1 = append_status([rec()], late, late, tmp_path)
    p2 = append_status([rec()], next_day, next_day, tmp_path)
    assert p1.name == "2026-07-21.parquet"
    assert p2.name == "2026-07-22.parquet"


def test_upsert_stations_writes_once_for_same_content(tmp_path):
    infos = [StationInfo("42", "Smithfield North", 53.34, -6.27, 20)]
    assert upsert_stations(infos, tmp_path) is True
    assert upsert_stations(infos, tmp_path) is False
    changed = [StationInfo("42", "Smithfield North", 53.34, -6.27, 25)]
    assert upsert_stations(changed, tmp_path) is True
