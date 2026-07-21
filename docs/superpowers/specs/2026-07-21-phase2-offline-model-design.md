# Phase 2: Offline Model — Design Spec

Date: 2026-07-21 · Status: Alex authorized autonomous design + implementation
(2026-07-21, "go, start the P2 design and implementation work autonomously").
Parent spec: `2026-07-21-dublin-bikes-forecast-design.md` (targets, gates, and
leakage rules defined there remain binding).

## Goal

Train and honestly evaluate the commute-window probability model on the Smart
Dublin archive, producing a calibration report. **No live claims** — P2's
output is an offline verdict and a frozen modelling procedure for P3.

## Data

- **Training/validation source:** Smart Dublin monthly CSVs, new GBFS format
  only (detected by header; empirically ≈2024 onward), 2024-01 → 2026-06
  attempted, non-conforming months dropped and logged. Resolved via the CKAN
  `package_show` API (resource URLs are UUID-based, not guessable).
  Files cached in `.cache/archive/` (gitignored — ~80 MB/month stays out of
  git). Assessment evidence (2026-07-21): 5-min event-sampled, UTC-naive
  timestamps proven by commute-flux, 115/116 station overlap.
- **Weather:** Open-Meteo archive API (keyless), Dublin 53.35/-6.26, hourly
  `temperature_2m, precipitation, wind_speed_10m`, UTC. Cached to
  `data/weather/archive.parquet` (~18k rows — small enough to commit).
  Per parent spec: training on actuals is a documented proxy for the
  forecast-at-issuance features used live.
- **Own live capture is NOT used in P2** — it stays pure live out-of-sample
  for the P3 ledger.

## State reconstruction (event rows → grid)

- Per station, resample events to a 5-minute UTC grid, forward-fill.
- **UNKNOWN rules (provisional, counted in the report):**
  1. *Feed outage:* any global gap with zero rows across all stations for
     > 30 min marks every station UNKNOWN for that span (absence of everyone
     is an outage; absence of one station is usually a stable state).
  2. *Staleness cap:* a station's ffilled state older than 24 h is UNKNOWN
     (a dead station must not project its last state forever).
  3. A station whose last event has `is_installed=false` or
     `is_renting=false` is EXCLUDED at that instant (parent-spec class).
- Labels drawn from UNKNOWN/EXCLUDED instants are dropped and counted.

## Windows, labels, horizons

- Windows 08:30 / 17:30 **Europe/Dublin** (zoneinfo, DST-aware) converted to
  UTC per date; issuance 07:00 / 16:00 Dublin likewise.
- Labels per station × date × window: `BIKE = bikes ≥ 1`, `DOCK = docks ≥ 1`
  at the target grid instant.
- Horizons per parent spec: short (same-run, ~90 min) and long (prior run:
  07:00→17:30 same day, 16:00→next-day 08:30). Horizon-minutes is a feature;
  metrics are always reported per horizon.

## Features (all strictly ≤ issuance instant; leakage-guard tested)

Station state at issuance: bikes, docks, fill ratio (bikes/capacity);
deltas over 30/60 min; station_id (categorical); capacity;
calendar: hour-of-week, day-type (weekday/weekend/Irish bank holiday via
`holidays` package); weather at target hour (proxy, see above);
horizon minutes.

## Baselines (pre-registered in parent spec, implemented here)

- **Climatology:** event frequency over training folds keyed
  (station, window, day-type), Laplace-smoothed (+1/+2); fallback key
  (window, day-type) for unseen combos.
- **Persistence:** event state at issuance as hard 0/1 probability.

## Model

One `HistGradientBoostingClassifier` per event (BIKE, DOCK), default-ish
hyperparameters (early stopping on a time-ordered validation tail; no
hyperparameter search in P2 — YAGNI until calibration says otherwise).
Calibration inspected via reliability bins; isotonic recalibration only if
validation reliability is visibly off (parent-spec rule).

## Evaluation protocol

- **Expanding-window monthly CV:** for each validation month m in the CV
  range, train on all conforming months < m (minimum 6 months of training
  data before the first fold). Climatology refit per fold on that fold's
  training months only.
- **Final held-out test: 2026-04 → 2026-06** (3 most recent months),
  touched exactly once, after the CV design is frozen.
- **Metrics:** Brier per event × horizon × window; BSS vs each baseline;
  reliability bins (10); base rates; UNKNOWN/EXCLUDED counts.
- **Day-clustered bootstrap 95% CI** on final-test BSS (resample dates with
  replacement, 2,000 draws) — the same machinery the live P4 gate will use.
- **P2 offline verdict gate (pre-registered here, before any model run):**
  the model earns P3 deployment iff final-test BSS > 0 vs BOTH baselines
  with CI excluding 0, per event, at the long horizon; at the short horizon
  losing to persistence is tolerated (expected) but must be reported.
  Anything less: published as-is, P3 proceeds with baselines only or not at
  all — decision documented, not hidden.

## Deliverables

`reports/p2/REPORT.md` (verdict up top), `metrics.json`, reliability PNGs
(matplotlib), all committed. New deps: scikit-learn, holidays, matplotlib,
tzdata. Modules: `archive.py, grid.py, windows.py, labels.py, weather.py,
features.py, baselines.py, dataset.py, backtest.py` + `scripts/run_p2.py`
(ASCII-only console output; UTF-8 file I/O).
