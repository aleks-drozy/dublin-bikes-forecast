# Phase 2 Report — Offline Model

**Verdict: PASS — the model earns P3 deployment.**
Pre-registered gate (committed in the P2 spec before any model run): on the
held-out final test, long-horizon BSS > 0 vs BOTH baselines with day-clustered
bootstrap 95% CI excluding 0, per event. All four long-horizon CIs are
strictly positive — and so are the short-horizon ones, which the gate did not
even require.

Seed: 20260721. Full numbers: [metrics.json](metrics.json).

## Data

- 26 archive months used (2024-05 → 2026-06), 671,312 forecast rows.
- Rejected: 2024-01, 2024-02 (old CSV format); 2024-03/04 absent from the
  portal. 2024-09 is a partial month (2,508 rows survive).
- Dropped rows are counted per month in the run log (UNKNOWN/EXCLUDED grid
  instants and missing-issuance rows; largest: 2026-01 with 1,679 dropped
  labels). Nothing is silently imputed.

## Protocol

Expanding-window monthly CV (min 6 train months, 17 folds) on 2024-05 →
2026-03; final test **2026-04 → 2026-06 touched exactly once** after the CV
design froze. Baselines: Laplace-smoothed climatology
(station × window × day-type) and hard persistence. Model: one
HistGradientBoostingClassifier per event, issuance-time features only
(leakage-guard tested).

## Final test (held out)

| event/horizon | n | base rate | Brier model | clim | pers | BSS vs clim [95% CI] | BSS vs pers [95% CI] |
|---|---|---|---|---|---|---|---|
| bike / long | 20,556 | 0.899 | 0.0748 | 0.0819 | 0.1396 | 0.087 [0.073, 0.102] | 0.464 [0.444, 0.482] |
| bike / short | 20,901 | 0.899 | 0.0640 | 0.0819 | 0.1121 | 0.219 [0.192, 0.247] | 0.429 [0.398, 0.455] |
| dock / long | 20,556 | 0.972 | 0.0220 | 0.0274 | 0.0428 | 0.195 [0.160, 0.237] | 0.486 [0.452, 0.518] |
| dock / short | 20,901 | 0.972 | 0.0194 | 0.0273 | 0.0358 | 0.290 [0.261, 0.321] | 0.458 [0.426, 0.491] |

CV results (17 folds, 2025-11 → 2026-03 tail included) are consistent with
the test — no fold-shopping was possible: the gate froze before the test ran.

## Calibration

Reliability curves on the final test track the diagonal closely at every
probability level (see `reliability_*.png`). Per the spec rule, no isotonic
recalibration was applied.

## Honesty notes

- Weather features train on archived actuals as a proxy for the forecasts
  available at issuance live (documented spec approximation; horizons ≤ 17 h).
- Early stopping uses sklearn's internal random split within training data
  (the spec's "time-ordered tail" is not natively supported); no test data
  is involved.
- The archive is event-sampled; state was reconstructed per station on a
  5-min forward-filled grid with feed-outage (>30 min network silence),
  staleness (>24 h), and not-renting exclusion rules.
- Persistence is weaker than naively expected because hard 0/1 forecasts pay
  the full Brier penalty on every flip; beating climatology is the harder
  test here, and the margins there are the modest ones.
- These are OFFLINE results. No live claim is made until the P3/P4 ledger
  runs the pre-registered 28-day live gate.

## Next (P3)

Freeze this procedure; implement `scoring/eligibility.py` (owner decision);
live issuance at 07:00/16:00 Dublin; ledger + scoring workflows.
