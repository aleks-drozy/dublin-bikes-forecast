"""Smart Dublin historical archive: resolve, download-with-cache, load.

Archive timestamps are naive UTC — proven 2026-07-21 by the commute-flux
check (weekday peaks at 07:00/16:00 naive = Dublin rush minus IST offset).
See docs/superpowers/specs/2026-07-21-phase2-offline-model-design.md.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

import pandas as pd

CKAN_PACKAGE_URL = ("https://data.smartdublin.ie/api/3/action/package_show"
                    "?id=33ec9fe2-4957-4e9a-ab55-c5e917c7a9ab")

# station_status_MMYYYY.csv (new era) | dublinbike-historical-data-YYYY-MM.csv (old era)
_NEW_RE = re.compile(r"station_status_(\d{2})(\d{4})\.csv$")
_OLD_RE = re.compile(r"historical-data-(\d{4})-(\d{2})\.csv$")

_NEW_FORMAT_COLS = {"last_reported", "station_id",
                    "num_bikes_available", "num_docks_available"}


def _fetch_ckan(url: str, timeout: float = 60.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_bytes(url: str, timeout: float = 300.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def resolve_month_urls(fetcher=_fetch_ckan) -> dict[str, str]:
    payload = fetcher(CKAN_PACKAGE_URL)
    urls: dict[str, str] = {}
    for res in payload["result"]["resources"]:
        url = res.get("url", "")
        if m := _NEW_RE.search(url):
            urls[f"{m.group(2)}-{m.group(1)}"] = url
        elif m := _OLD_RE.search(url):
            urls[f"{m.group(1)}-{m.group(2)}"] = url
    return urls


def download_months(urls: dict[str, str], months: list[str], cache_dir: Path,
                    fetcher_bytes=_fetch_bytes) -> dict[str, Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for month in months:
        if month not in urls:
            continue
        path = cache_dir / f"{month}.csv"
        if not path.exists():
            path.write_bytes(fetcher_bytes(urls[month]))
        paths[month] = path
    return paths


def load_month(path: Path) -> pd.DataFrame | None:
    header = set(pd.read_csv(path, nrows=0).columns)
    if not _NEW_FORMAT_COLS.issubset(header):
        return None
    df = pd.read_csv(
        path,
        usecols=["last_reported", "station_id", "num_bikes_available",
                 "num_docks_available", "is_installed", "is_renting", "capacity"],
    )
    out = pd.DataFrame({
        "ts": pd.to_datetime(df["last_reported"]).dt.tz_localize("UTC"),
        "station_id": df["station_id"].astype(str),
        "bikes": df["num_bikes_available"].astype(int),
        "docks": df["num_docks_available"].astype(int),
        "is_installed": df["is_installed"].astype(bool),
        "is_renting": df["is_renting"].astype(bool),
        "capacity": df["capacity"].astype(int),
    })
    return out.sort_values(["ts", "station_id"]).reset_index(drop=True)
