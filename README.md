# Dublin Bikes Forecast

Live, publicly scored probability forecasts for dublinbikes availability at
commute times: **P(at least one bike)** and **P(at least one free dock)** per
station at 08:30 and 17:30 (Europe/Dublin), issued before the fact at two
horizons (~90 min and overnight), scored against pre-registered baselines.

**Status: Phase 1 — data collection.** No forecasts exist yet. The verdict
gate (Brier skill vs climatology AND persistence, day-clustered bootstrap
95% CI, 28 live days) is pre-registered in
[the design spec](docs/superpowers/specs/2026-07-21-dublin-bikes-forecast-design.md)
and was committed before any data was collected or any model written.

## Honesty rules

- Forecasts enter an append-only ledger committed before target time.
- Missed polls, feed gaps, and unscoreable targets are counted and published.
- Baselines freeze before the live ledger starts; losing to persistence is
  published as NOT PROVEN, not hidden.

## Data

10-minute GBFS polls (keyless public feed) into daily parquet partitions
under `data/raw/`; poll health under `data/quality/`. All timestamps UTC.

## Development

```
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

All tests are network-free; fetching is injected.
