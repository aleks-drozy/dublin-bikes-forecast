# Dublin Bikes Forecast — Design Spec

Date: 2026-07-21 · Status: approved by Alex (project + commute-window probabilities, 2026-07-21)

## What

A live, honest, publicly scored forecasting service for dublinbikes availability
at commute times. For every station and commute window it publishes, **before
the fact**, two probabilities:

- **P(BIKE)** — at least one bike available at the target time
- **P(DOCK)** — at least one open dock at the target time

Forecasts are written to an append-only, git-committed ledger *before* outcomes
exist, then scored against reality on a public scoreboard with calibration
plots and pre-registered baselines. The commuter-facing page answers: *"Will
there be a bike at my station at 08:30?"*

## Why (one line)

The profile's five quant repos are all retrospective; this adds the one thing
none of them have — live out-of-sample discipline — while shipping a second
production service with real commuter impact.

## Targets and horizons

- **Windows** (Europe/Dublin, DST-aware): morning **08:30**, evening **17:30**.
- **Events**: BIKE (≥1 `num_bikes_available`), DOCK (≥1 `num_docks_available`)
  per station per window. Binary, scored at the target instant (nearest
  observation within tolerance — see Scoring).
- **Issuance runs**: 07:00 and 16:00 Dublin time daily.
  - 07:00 run → same-day 08:30 (**short horizon**, ~90 min) and same-day 17:30
    (**long horizon**, ~10.5 h)
  - 16:00 run → same-day 17:30 (**short**, ~90 min) and next-day 08:30
    (**long**, ~16.5 h)
- Every target therefore gets exactly two forecasts (short + long), letting the
  scoreboard show skill decay across horizon — and letting persistence win
  where it honestly wins.

## Data

| Source | Access | Use |
|---|---|---|
| dublinbikes GBFS `station_status` + `station_information` (api.cyclocity.fr/contracts/dublin/gbfs) | keyless, minutely | occupancy history, features, outcomes |
| Open-Meteo forecast API | keyless | weather **forecast at issuance time** (feature) |
| Open-Meteo archive API | keyless | training-history weather (documented proxy — see Leakage) |
| Smart Dublin historical dublinbikes CSVs | open data | optional training bootstrap (P2 assesses usability) |

**Ingestion**: GitHub Actions cron, every 10 minutes (git-scraping pattern —
each poll appends to a daily parquet partition in `data/raw/` and commits).
No VM, no keys, fully reproducible from the repo alone.

**Honest accounting**: Actions cron is best-effort. Every poll records poll
latency and feed `last_reported`; missed polls and gaps are **counted and
published**, never hidden. Scoring classes: `SCORED`, `UNSCOREABLE_GAP` (no
eligible observation), `EXCLUDED_STATION` (not installed / not renting at
target). The scoreboard shows all three counts.

## Model and baselines

- **Baselines (pre-registered, immutable):**
  1. **Climatology** — historical event frequency for that station × window ×
     day-type (weekday/weekend + bank holidays via Irish holiday calendar).
  2. **Persistence** — event state at issuance time carried forward.
- **Model v1**: gradient-boosted classifier (sklearn HistGradientBoosting) on
  issuance-time features: current bikes/docks, 30/60-min deltas, fill ratio,
  hour/day-type, station identity, weather forecast (precip, temp, wind).
  Calibration checked on time-ordered validation; isotonic recalibration only
  if validation shows miscalibration.
- **Leakage rules**: a feature is legal iff its value was available at
  issuance time. Weather features at serving time are *forecasts*; training on
  archived actuals is a documented approximation (forecast ≈ actual at ≤17 h
  horizon), revisited if it ever flatters the model.
- **Time discipline**: storage in UTC only; windows derived via Europe/Dublin
  at read time (the FYP Phase-1 DST bug is the reason this is a spec line).

## Scoring and verdict gate (pre-registered 2026-07-21, before any data)

- **Score**: Brier per forecast; aggregates by horizon × window × event;
  reliability diagrams; Brier Skill Score (BSS) vs each baseline.
- **Outcome**: observation nearest the target instant within an eligibility
  tolerance. The eligibility rule (`scoring/eligibility.py`) is Alex's
  decision point — tight tolerance loses scoreable days, loose tolerance
  scores against non-representative state. Provisional bound: ±10 min.
- **Verdict gate**: after **28 consecutive days** of live ledger, per horizon:
  model BSS > 0 vs **both** baselines with day-clustered bootstrap 95% CI
  excluding 0. Anything less: **NOT PROVEN**, published as such. Short-horizon
  persistence is expected to be hard to beat; losing to it honestly is a
  finding, not a failure.
- **Anti-gaming**: ledger is append-only; forecast commits timestamped by git
  before target time; scoring code deterministic; baselines frozen at P3 start.

## Phases

1. **P1 — Ingestion (this week; live ASAP, every day of data matters)**:
   poller (fixture-tested, network-free tests), parquet storage, poll-quality
   log, Actions workflow, README skeleton.
2. **P2 — Offline model**: Smart Dublin bootstrap assessment, feature/label
   pipeline, time-series-CV backtest, calibration report. No live claims.
3. **P3 — Live ledger**: issuance + scoring workflows, eligibility rule
   finalized (Alex), baselines frozen, ledger begins.
4. **P4 — Public**: Pages scoreboard (verdict banner, BSS table, reliability
   diagrams, per-station "today" map) + commuter view. Verdict at day 28.

## Stack

Python 3.12 (pandas/pyarrow/scikit-learn, pytest), GitHub Actions, static
vanilla-JS + Leaflet site on Pages. Windows dev note: all file I/O explicit
UTF-8; no unicode in console output (cp1252 guard).

## Non-goals (v1)

Count regression / interval forecasts (the football-trajectory calibration
lesson), journey planning, non-Dublin systems, mobile app, paid infra.
