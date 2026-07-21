# Phase 3: Live Ledger — Design Spec

Date: 2026-07-21 · Status: Alex authorized ("go, start P3"). Parent specs
(P1 targets/gates, P2 procedure) remain binding. Inline-execution plan
deviation as in P2 (code appears once, in the TDD build).

## Goal

Before-the-fact forecasts, published to an append-only git ledger and scored
nightly against reality with the committed eligibility rule. After 28 live
days, P4 renders the pre-registered live verdict.

## Model freeze (v1)

- Train once on ALL 26 conforming archive months (2024-05 → 2026-06) —
  the former P2 test months are past; the live ledger is the only test that
  matters now. Two HGB models (bike, dock) serialized with joblib to
  `models/v1/` plus `climatology.json` (frozen baseline, human-readable) and
  `manifest.json` (months, seed, feature list, code commit). Committed —
  the model that makes every ledger claim is public and versioned.
- Reload-parity check before commit: serialized model must reproduce
  in-memory predictions exactly on a probe set.

## Issuance (on the VM, twice daily)

- Runs at 07:00 and 16:00 **Europe/Dublin**. Cron is UTC and DST-shifts, so
  cron fires HOURLY and the script exits unless the current Dublin hour is
  07 or 16 (DST-proof by construction; same zoneinfo as `windows.py`).
- The 07:00 run issues same-day 08:30 (short) + same-day 17:30 (long);
  the 16:00 run issues same-day 17:30 (short) + next-day 08:30 (long) —
  identical to P2's horizon structure.
- Live features mirror P2 exactly: latest poll state (rejected if older
  than 20 min — counted as UNISSUED), d30/d60 lookbacks from `data/raw`,
  capacity from `data/stations`, calendar, weather from the Open-Meteo
  **forecast** endpoint (the live counterpart of P2's documented actuals
  proxy), horizon minutes.
- Ledger row: `issued_at_utc, window, horizon, target_ts_utc, station_id,
  event, p_model, p_clim, p_pers, model_version`. Baselines are computed AT
  ISSUANCE and stored in the row — scoring never recomputes them, so there
  is no hindsight drift. CSV (`ledger/forecasts/YYYY-MM-DD.csv`, keyed by
  target date), chosen over parquet for public inspectability.
- Append-only + idempotent: re-running an issuance never duplicates a
  (target_ts, window, horizon, station, event) key and never rewrites an
  existing row. Commit + push immediately after writing — the git timestamp
  is the before-the-fact proof.

## Scoring (nightly, 23:45 UTC)

- Every ledger row whose target has passed and has no outcome yet: find the
  nearest observation in `data/raw` passing
  `scoring.eligibility.eligible_observation`; outcome classes:
  `SCORED` (y recorded), `UNSCOREABLE_GAP` (no eligible obs),
  `EXCLUDED_STATION` (eligible obs but not installed/renting).
- Outcomes appended to `ledger/outcomes/YYYY-MM-DD.csv` (same key), plus
  `ledger/summary.json` recomputed: per event × horizon running Brier for
  model/clim/pers, BSS, counts by status, day count — P4's data source.
- The 28-day live gate itself is NOT evaluated here; P4 renders it when
  28 scored days exist (pre-registered in the P1 spec).

## Off-schedule bootstrap note

The first ledger entries are issued tonight (off-schedule, `issued_at`
recorded honestly) targeting tomorrow 08:30 — this proves the pipeline
end-to-end a day early. `issued_at` makes the irregularity self-documenting;
the gate clock starts with P4, not tonight.

## VM changes

scikit-learn joins the VM venv (prediction needs it; ~150 MB transient
import RAM at two issuances/day is acceptable on the 1 GB box). Crons:
hourly issuance gate + 23:45 UTC scoring, both flock-guarded, logging to
`~/bikes-issue.log` / `~/bikes-score.log`. RUNBOOK updated.

## Non-goals (P3)

The public scoreboard page (P4), any model retraining cadence (v2 decision
after the live gate), backfilling forecasts for dates before the ledger
existed (impossible honestly — that is the point of the project).
