import json
from pathlib import Path

from bikes.archive import download_months, load_month, resolve_month_urls

FIXTURES = Path(__file__).parent / "fixtures"


def ckan_fetcher(url, timeout=60.0):
    return json.loads((FIXTURES / "ckan_package.json").read_text(encoding="utf-8"))


def test_resolve_month_urls_handles_both_naming_eras_and_ignores_noise():
    urls = resolve_month_urls(fetcher=ckan_fetcher)
    assert urls["2026-06"].endswith("station_status_062026.csv")
    assert urls["2024-10"].endswith("station_status_102024.csv")
    assert urls["2023-08"].endswith("dublinbike-historical-data-2023-08.csv")
    assert len(urls) == 3  # geojson + gbfs.json rows are not months


def test_download_months_skips_cached_files(tmp_path):
    calls = []

    def fake_bytes(url, timeout=300.0):
        calls.append(url)
        return b"csv-bytes"

    urls = {"2026-06": "https://example.test/a.csv"}
    paths = download_months(urls, ["2026-06"], tmp_path, fetcher_bytes=fake_bytes)
    assert paths["2026-06"].read_bytes() == b"csv-bytes"
    download_months(urls, ["2026-06"], tmp_path, fetcher_bytes=fake_bytes)
    assert len(calls) == 1  # second call served from cache


def test_load_month_normalizes_new_format():
    df = load_month(FIXTURES / "archive_new_format.csv")
    assert list(df.columns) == ["ts", "station_id", "bikes", "docks",
                                "is_installed", "is_renting", "capacity"]
    assert str(df["ts"].dt.tz) == "UTC"  # naive archive timestamps pinned to UTC
    assert df.loc[0, "station_id"] == "1"
    assert df.loc[0, "bikes"] == 20 and df.loc[0, "docks"] == 11
    assert bool(df.loc[1, "is_renting"]) is False
    assert df.loc[0, "capacity"] == 31


def test_load_month_rejects_old_format():
    assert load_month(FIXTURES / "archive_old_format.csv") is None
