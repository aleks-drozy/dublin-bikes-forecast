"""Fetch and parse the dublinbikes GBFS v2 feeds."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

GBFS_BASE = "https://api.cyclocity.fr/contracts/dublin/gbfs/v2"
GBFS_STATUS_URL = f"{GBFS_BASE}/station_status.json"
GBFS_INFO_URL = f"{GBFS_BASE}/station_information.json"

_STATUS_REQUIRED = ("station_id", "num_bikes_available", "num_docks_available")
_INFO_REQUIRED = ("station_id", "name", "lat", "lon", "capacity")


@dataclass(frozen=True)
class StatusRecord:
    station_id: str
    num_bikes_available: int
    num_docks_available: int
    is_installed: bool
    is_renting: bool
    is_returning: bool
    last_reported: datetime | None


@dataclass(frozen=True)
class StationInfo:
    station_id: str
    name: str
    lat: float
    lon: float
    capacity: int


@dataclass
class ParseResult:
    records: list = field(default_factory=list)
    feed_last_updated: datetime | None = None
    skipped: int = 0


def _epoch_utc(value) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def fetch_json(url: str, timeout: float = 30.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_station_status(payload: dict) -> ParseResult:
    result = ParseResult(feed_last_updated=_epoch_utc(payload.get("last_updated")))
    for raw in payload.get("data", {}).get("stations", []):
        if any(raw.get(k) is None for k in _STATUS_REQUIRED):
            result.skipped += 1
            continue
        result.records.append(StatusRecord(
            station_id=str(raw["station_id"]),
            num_bikes_available=int(raw["num_bikes_available"]),
            num_docks_available=int(raw["num_docks_available"]),
            is_installed=bool(raw.get("is_installed", True)),
            is_renting=bool(raw.get("is_renting", True)),
            is_returning=bool(raw.get("is_returning", True)),
            last_reported=_epoch_utc(raw.get("last_reported")),
        ))
    return result


def parse_station_information(payload: dict) -> ParseResult:
    result = ParseResult(feed_last_updated=_epoch_utc(payload.get("last_updated")))
    for raw in payload.get("data", {}).get("stations", []):
        if any(raw.get(k) is None for k in _INFO_REQUIRED):
            result.skipped += 1
            continue
        result.records.append(StationInfo(
            station_id=str(raw["station_id"]),
            name=str(raw["name"]),
            lat=float(raw["lat"]),
            lon=float(raw["lon"]),
            capacity=int(raw["capacity"]),
        ))
    return result
