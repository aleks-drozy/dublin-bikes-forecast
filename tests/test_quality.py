from datetime import datetime, timezone

import pandas as pd

from bikes.quality import record_poll

POLL_TS = datetime(2026, 7, 21, 8, 40, 12, tzinfo=timezone.utc)


def test_ok_poll_row(tmp_path):
    path = record_poll(tmp_path, POLL_TS, ok=True, fetch_ms=340,
                       status_count=117, skipped=1, feed_age_s=42.0, error=None)
    df = pd.read_parquet(path)
    assert path.name == "2026-07-21.parquet"
    assert df.loc[0, "ok"]
    assert df.loc[0, "status_count"] == 117
    assert df.loc[0, "feed_age_s"] == 42.0
    assert pd.isna(df.loc[0, "error"])


def test_failed_poll_is_recorded_not_hidden(tmp_path):
    path = record_poll(tmp_path, POLL_TS, ok=False, fetch_ms=30000,
                       status_count=0, skipped=0, feed_age_s=None,
                       error="URLError: timed out")
    df = pd.read_parquet(path)
    assert not df.loc[0, "ok"]
    assert df.loc[0, "error"] == "URLError: timed out"


def test_rows_accumulate(tmp_path):
    record_poll(tmp_path, POLL_TS, True, 300, 117, 0, 40.0, None)
    path = record_poll(tmp_path, POLL_TS.replace(minute=50), True, 310, 117, 0, 41.0, None)
    assert len(pd.read_parquet(path)) == 2
