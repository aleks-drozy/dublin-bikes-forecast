import json
from datetime import datetime, timezone
from pathlib import Path

from bikes.gbfs import parse_station_information, parse_station_status

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_status_returns_well_formed_records():
    result = parse_station_status(load("station_status.json"))
    assert len(result.records) == 2  # station 99 lacks required fields
    assert result.skipped == 1
    r = result.records[0]
    assert r.station_id == "42"
    assert r.num_bikes_available == 5
    assert r.num_docks_available == 15
    assert r.is_renting is True
    assert r.last_reported == datetime(2026, 7, 21, 8, 39, tzinfo=timezone.utc)


def test_parse_status_feed_timestamp_is_utc():
    result = parse_station_status(load("station_status.json"))
    assert result.feed_last_updated == datetime(2026, 7, 21, 8, 40, tzinfo=timezone.utc)


def test_parse_status_missing_last_reported_is_none_not_skip():
    payload = load("station_status.json")
    del payload["data"]["stations"][0]["last_reported"]
    result = parse_station_status(payload)
    assert result.records[0].last_reported is None


def test_parse_information():
    result = parse_station_information(load("station_information.json"))
    assert len(result.records) == 2
    assert result.skipped == 0
    assert result.records[0].name == "Smithfield North"
    assert result.records[0].capacity == 20
