"""Regenerate ledger/latest.json from the current ledger (idempotent)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bikes.forecast import write_latest_json  # noqa: E402

if __name__ == "__main__":
    stations = pd.read_parquet(ROOT / "data" / "stations" / "stations.parquet")
    write_latest_json(ROOT / "ledger", stations, datetime.now(timezone.utc))
    print("latest.json written")
