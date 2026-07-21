"""Poll-health ledger: every poll leaves a row, especially the failures."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def record_poll(root: Path, poll_ts: datetime, ok: bool, fetch_ms: int,
                status_count: int, skipped: int, feed_age_s: float | None,
                error: str | None) -> Path:
    quality_dir = root / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    path = quality_dir / f"{poll_ts.date().isoformat()}.parquet"
    row = pd.DataFrame([{
        "poll_ts": pd.Timestamp(poll_ts), "ok": ok, "fetch_ms": fetch_ms,
        "status_count": status_count, "skipped": skipped,
        "feed_age_s": feed_age_s, "error": error,
    }])
    if path.exists():
        row = pd.concat([pd.read_parquet(path), row], ignore_index=True)
    row.to_parquet(path, index=False)
    return path
