import json
from datetime import date, datetime, timezone
from pathlib import Path

from bikes.weather import fetch_archive, load_or_fetch

FIXTURES = Path(__file__).parent / "fixtures"


def fake_fetcher(url, timeout=60.0):
    assert "start_date=2026-06-01" in url and "end_date=2026-06-01" in url
    return json.loads((FIXTURES / "open_meteo_archive.json").read_text(encoding="utf-8"))


def test_fetch_archive_parses_utc_hourly():
    df = fetch_archive(date(2026, 6, 1), date(2026, 6, 1), fetcher=fake_fetcher)
    assert list(df.columns) == ["ts", "temp", "precip", "wind"]
    assert df.loc[0, "ts"] == datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
    assert df.loc[1, "precip"] == 0.4
    assert len(df) == 3


def test_load_or_fetch_uses_cache(tmp_path):
    calls = []

    def counting(url, timeout=60.0):
        calls.append(url)
        return fake_fetcher(url, timeout)

    cache = tmp_path / "archive.parquet"
    df1 = load_or_fetch(cache, date(2026, 6, 1), date(2026, 6, 1), fetcher=counting)
    df2 = load_or_fetch(cache, date(2026, 6, 1), date(2026, 6, 1), fetcher=counting)
    assert len(calls) == 1
    assert df1.equals(df2)
