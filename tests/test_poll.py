import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from bikes.gbfs import GBFS_INFO_URL, GBFS_STATUS_URL
from bikes.poll import run_poll

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 7, 21, 8, 40, 12, tzinfo=timezone.utc)


def fake_fetcher(url, timeout=30.0):
    name = "station_status.json" if url == GBFS_STATUS_URL else "station_information.json"
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_successful_poll_writes_all_three_stores(tmp_path):
    assert run_poll(tmp_path, fetcher=fake_fetcher, now=NOW) is True
    raw = pd.read_parquet(tmp_path / "raw" / "2026-07-21.parquet")
    assert len(raw) == 2
    assert (tmp_path / "stations" / "stations.parquet").exists()
    quality = pd.read_parquet(tmp_path / "quality" / "2026-07-21.parquet")
    assert quality.loc[0, "ok"]
    assert quality.loc[0, "status_count"] == 2
    assert quality.loc[0, "skipped"] == 1


def test_fetch_failure_still_writes_quality_row(tmp_path):
    def broken(url, timeout=30.0):
        raise OSError("connection refused")
    assert run_poll(tmp_path, fetcher=broken, now=NOW) is False
    quality = pd.read_parquet(tmp_path / "quality" / "2026-07-21.parquet")
    assert not quality.loc[0, "ok"]
    assert "connection refused" in quality.loc[0, "error"]
    assert not (tmp_path / "raw").exists()


def test_info_failure_does_not_lose_status_data(tmp_path):
    def status_only(url, timeout=30.0):
        if url == GBFS_INFO_URL:
            raise OSError("info feed down")
        return fake_fetcher(url, timeout)
    assert run_poll(tmp_path, fetcher=status_only, now=NOW) is True
    assert (tmp_path / "raw" / "2026-07-21.parquet").exists()
    quality = pd.read_parquet(tmp_path / "quality" / "2026-07-21.parquet")
    assert quality.loc[0, "ok"]
