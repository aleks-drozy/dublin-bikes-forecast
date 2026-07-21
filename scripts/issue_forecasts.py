"""Issuance entry point (VM cron, hourly; acts only at 07:00/16:00 Dublin).

--bootstrap-tomorrow-morning: one-off before-the-fact issuance for the next
morning's targets outside the normal schedule (issued_at recorded honestly).
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bikes.forecast import FrozenModel, run_issuance, write_latest_json  # noqa: E402
from bikes.weather import fetch_forecast  # noqa: E402


def main() -> None:
    now = datetime.now(timezone.utc)
    force_sets = None
    if "--bootstrap-tomorrow-morning" in sys.argv:
        force_sets = [("morning", "long", now.date() + timedelta(days=1))]
    model = FrozenModel.load(ROOT / "models" / "v1")
    stations = pd.read_parquet(ROOT / "data" / "stations" / "stations.parquet")
    capacity = stations.set_index("station_id")["capacity"].astype(float)
    added = run_issuance(model, ROOT / "data" / "raw", capacity, fetch_forecast,
                         ROOT / "ledger", now, force_sets=force_sets)
    if added:
        write_latest_json(ROOT / "ledger", stations, now)


if __name__ == "__main__":
    main()
