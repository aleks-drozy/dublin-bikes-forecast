"""Live station state from the polled raw parquet partitions."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

MAX_AGE = timedelta(minutes=20)


def _read_window(raw_dir: Path, at: datetime) -> pd.DataFrame:
    frames = []
    for d in (at.date() - timedelta(days=1), at.date()):
        path = raw_dir / f"{d.isoformat()}.parquet"
        if path.exists():
            frames.append(pd.read_parquet(path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def latest_state(raw_dir: Path, at: datetime,
                 max_age: timedelta = MAX_AGE) -> pd.DataFrame:
    df = _read_window(raw_dir, at)
    if df.empty:
        return df
    df = df[(df["poll_ts"] <= at) & (df["poll_ts"] >= at - max_age)]
    if df.empty:
        return df
    df = (df.sort_values("poll_ts").groupby("station_id", as_index=False).last())
    return pd.DataFrame({
        "station_id": df["station_id"].astype(str),
        "bikes": df["num_bikes_available"].astype(float),
        "docks": df["num_docks_available"].astype(float),
        "is_installed": df["is_installed"].astype(bool),
        "is_renting": df["is_renting"].astype(bool),
        "poll_ts": df["poll_ts"],
    })
