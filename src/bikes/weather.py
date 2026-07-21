"""Open-Meteo archive weather for Dublin (keyless), cached to parquet.

Per the parent spec: training uses archived actuals as a documented proxy for
the forecast-at-issuance features served live.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

_URL = ("https://archive-api.open-meteo.com/v1/archive"
        "?latitude=53.35&longitude=-6.26"
        "&hourly=temperature_2m,precipitation,wind_speed_10m"
        "&timezone=UTC&start_date={start}&end_date={end}")


def _fetch_json(url: str, timeout: float = 60.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_archive(start: date, end: date, fetcher=_fetch_json) -> pd.DataFrame:
    payload = fetcher(_URL.format(start=start.isoformat(), end=end.isoformat()))
    hourly = payload["hourly"]
    return pd.DataFrame({
        "ts": pd.to_datetime(hourly["time"]).tz_localize("UTC"),
        "temp": hourly["temperature_2m"],
        "precip": hourly["precipitation"],
        "wind": hourly["wind_speed_10m"],
    })


def load_or_fetch(cache_path: Path, start: date, end: date,
                  fetcher=_fetch_json) -> pd.DataFrame:
    if cache_path.exists():
        return pd.read_parquet(cache_path)
    df = fetch_archive(start, end, fetcher=fetcher)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    return df
