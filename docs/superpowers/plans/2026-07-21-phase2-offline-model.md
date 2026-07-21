# Phase 2: Offline Model Implementation Plan

> Deviation from writing-plans convention, noted honestly: this plan is
> executed inline by its author in the same session, so complete code is not
> duplicated here — it appears once, in the TDD implementation. Interfaces,
> test intent, and verification commands are binding.

**Goal:** Archive-trained commute-window models + honest calibration report per the P2 spec.

**Global constraints:** parent + P2 spec rules (UTC storage, Dublin windows via zoneinfo, leakage ≤ issuance, ASCII console, UTF-8 I/O, network-free tests — CKAN/HTTP injected).

### Task A: `src/bikes/archive.py`
- `resolve_month_urls(fetcher) -> dict[str, str]` — CKAN package_show → {'YYYY-MM': url} for monthly station-status resources (both naming eras).
- `download_months(months, cache_dir, fetcher_bytes) -> dict[str, Path]` — skip-if-cached.
- `load_month(path) -> pd.DataFrame | None` — None + log if header lacks new-format columns; else normalized frame (utc-aware `ts`, str `station_id`, ints, bools).
- Tests: resolution from a fixture CKAN JSON; format detection (old-format header → None); normalization types; **UTC pin** (naive input → tz-aware UTC out).

### Task B: `src/bikes/windows.py`
- `window_instants(date, tz='Europe/Dublin') -> {'morning': (issue_utc, target_utc), 'evening': (...)}` plus `long_issuance(date, window)` (evening-before / morning-of per spec).
- Tests: June date → 07:30 UTC target for 08:30 IST; January date → 08:30 UTC (DST boundary is THE test); long-horizon pairs correct across midnight.

### Task C: `src/bikes/grid.py`
- `build_grid(events, freq='5min') -> (state: DataFrame indexed ts x station [bikes, docks], flags: DataFrame same shape str {OK, UNKNOWN, EXCLUDED})`
- Rules: global gap > 30 min → UNKNOWN span; ffill staleness > 24 h → UNKNOWN; is_installed/is_renting false → EXCLUDED.
- Tests: synthetic events exercising each rule + plain ffill continuity.

### Task D: `src/bikes/weather.py`
- `fetch_archive(start, end, fetcher) -> DataFrame [ts_utc, temp, precip, wind]`; `load_or_fetch(cache_path, ...)`.
- Test: fixture JSON → frame; cache short-circuit.

### Task E: `src/bikes/labels.py` + `src/bikes/features.py` + `src/bikes/dataset.py`
- `make_labels(state, flags, dates) -> DataFrame [date, window, station_id, event, y]` (drop+count UNKNOWN/EXCLUDED).
- `make_features(state, flags, weather, rows) -> DataFrame` — issuance snapshot, deltas 30/60m, fill ratio, capacity, hour-of-week, day-type (holidays), weather at target hour, horizon_min.
- `build_dataset(...)` joins both for the four (window × horizon) forecast sets.
- Tests: hand-computed tiny scenario; **leakage guard** — mutate all grid data strictly after issuance instant, features must be identical.

### Task F: `src/bikes/baselines.py`
- `Climatology.fit(train_labels)/predict(rows)` — (station, window, day_type) with Laplace +1/+2, fallback (window, day_type).
- `persistence(features) -> p` — hard 0/1 from issuance state.
- Tests: smoothing math, fallback path, persistence mapping.

### Task G: `src/bikes/backtest.py`
- `monthly_folds(months, min_train=6)`; `brier`, `bss`, `reliability_bins(10)`, `day_clustered_bootstrap_ci(pred, y, dates, base, n=2000, seed=...)`; `run_cv(dataset, model_factory)`.
- Tests: metric math on toy vectors; fold boundaries; bootstrap CI sane on synthetic skill/no-skill data.

### Task H: `scripts/run_p2.py` + report
- Orchestrate: resolve+download months → grids per month → dataset → CV → freeze → final test (2026-04..06) → `reports/p2/{REPORT.md, metrics.json, reliability_*.png}`.
- Verification: full pytest green; run script end-to-end on real archive; report committed; numbers in REPORT match metrics.json.

Execution order A→H, commit per task, push at the end (no co-author trailers in this repo).
