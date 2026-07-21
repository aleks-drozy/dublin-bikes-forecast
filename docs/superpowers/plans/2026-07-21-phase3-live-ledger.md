# Phase 3: Live Ledger Implementation Plan

> Inline-execution deviation as P2: interfaces and verification binding,
> code appears once in the TDD build.

**Global constraints:** parent + P3 spec; UTC storage; zoneinfo Dublin gates;
ASCII console; network/filesystem injected in tests.

### Task A: `scripts/freeze_model.py` → `models/v1/`
- Trains bike+dock HGB on all conforming cached months (reuses P2 modules),
  fits Climatology on the same rows, writes `bike.joblib`, `dock.joblib`,
  `climatology.json` (nested dict full/pool/global), `manifest.json`
  (months, seed 20260721, FEATURE_COLS, code commit hash).
- Verify: reload-parity assert inside the script (max |Δp| == 0 on a 1,000-row
  probe); models committed.

### Task B: `src/bikes/live.py`
- `latest_state(raw_dir, at, max_age=20min) -> DataFrame [station_id, bikes,
  docks, is_installed, is_renting, poll_ts]` — newest poll ≤ `at` per station
  from daily parquet(s), None-filtered by age; also
  `state_at(raw_dir, at, tolerance)` for lookbacks (nearest poll within
  tolerance, no max-age semantics).
- Tests: picks newest ≤ at; rejects stale; crosses midnight partitions.

### Task C: `src/bikes/forecast.py`
- `FrozenModel.load(models_dir)`; `build_issuance_rows(raw_dir, stations_path,
  weather_fetcher, now) -> DataFrame` (mirrors P2 FEATURE_COLS; UNISSUED
  counted); `append_ledger(rows, ledger_dir) -> (added, skipped)` idempotent
  on key (target_ts, window, horizon, station_id, event); `run_issuance(...)`
  gate: Dublin hour in {7, 16} unless `force=True`.
- Tests: feature parity columns; idempotency; hour gate; UNISSUED counting.

### Task D: `src/bikes/score.py`
- `score_ledger(ledger_dir, raw_dir, now) -> (n_scored, n_gap, n_excluded)`
  appending outcomes; `write_summary(ledger_dir)` → summary.json (Brier/BSS
  per event × horizon, status counts, scored-day count).
- Tests: eligibility applied via scoring.eligibility; statuses; summary math;
  never rescores an already-scored key.

### Task E: scripts + VM deploy + live verification
- `scripts/issue_forecasts.py` (hourly cron, Dublin-hour gate, commit+push),
  `scripts/score_forecasts.py` (23:45 UTC cron, commit+push); sklearn into VM
  venv; crontab lines; RUNBOOK update; one forced real issuance tonight for
  tomorrow 08:30; verify ledger CSV commit on GitHub before the target time.
