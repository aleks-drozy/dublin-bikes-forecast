"""Parquet persistence: daily raw partitions + station registry."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from bikes.gbfs import StationInfo, StatusRecord


def append_status(records: list[StatusRecord], poll_ts: datetime,
                  feed_last_updated: datetime | None, root: Path) -> Path:
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{poll_ts.date().isoformat()}.parquet"
    df = pd.DataFrame([asdict(r) for r in records])
    df["poll_ts"] = pd.Timestamp(poll_ts)
    df["feed_last_updated"] = pd.Timestamp(feed_last_updated) if feed_last_updated else pd.NaT
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    df.to_parquet(path, index=False)
    return path


def upsert_stations(infos: list[StationInfo], root: Path) -> bool:
    stations_dir = root / "stations"
    stations_dir.mkdir(parents=True, exist_ok=True)
    path = stations_dir / "stations.parquet"
    df = pd.DataFrame([asdict(i) for i in infos]).sort_values("station_id").reset_index(drop=True)
    if path.exists():
        existing = pd.read_parquet(path)
        if existing.equals(df):
            return False
    df.to_parquet(path, index=False)
    return True
