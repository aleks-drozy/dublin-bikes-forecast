# Gate clarification amendment — 2026-07-24

Date: 2026-07-24 · Status: proposed, pending Alex's sign-off · Scored days at
time of writing: **1** (long horizon, per the corrected definition below)

Committed while the live gate is at 1 of 28 scored days, specifically so
this cannot be read as a rule chosen after seeing how the project was
doing. Amends [`2026-07-21-forecast-preregistration.md`](2026-07-21-forecast-preregistration.md)
on three points the original spec left ambiguous or got wrong.

## 1. "Scored days" counts distinct dates, not a run of 28 in a row

The original spec (line 85) says the gate fires "after 28 **consecutive**
days of live ledger." The code that has been running since P3 (`src/bikes/score.py`,
`evaluate_gate`) has never implemented that literally — it counts *distinct
scored calendar dates*, with no requirement that they be unbroken.

Ruling: the code's behaviour is what's pre-registered going forward. **28
scored days, not necessarily consecutive.** Reasoning: the project's own
honesty rule commits to counting and publishing gaps (missed polls,
`UNSCOREABLE_GAP`) rather than hiding them — a strict "consecutive" reading
would mean a single VM restart or feed outage resets the count to zero,
which punishes exactly the kind of honest failure the project is designed
to surface, and provides no statistical benefit (the bootstrap CI is already
day-clustered, so it doesn't assume adjacency between days).

## 2. A scored day must have a scored *long-horizon* target — this was a real bug

Found while drafting this amendment, not before: `evaluate_gate` counted a
date as "scored" if *either* horizon had a scored target that day, but the
actual pass/fail test (`bss_vs_clim_ci`, `bss_vs_pers_ci`) only ever
evaluates **long-horizon** rows. A date whose short-horizon target scored
but whose long-horizon target came back `UNSCOREABLE_GAP` would have
counted toward the 28 while contributing zero evidence to the thing being
tested — silently weakening the gate's statistical power in a way nothing
in `gate.json` would show.

Fixed in the same commit as this amendment: `scored_days` in both
`gate.json` and `summary.json` now counts distinct dates with a **SCORED
long-horizon** target, matching what `evaluate_gate` actually tests. Pinned
by a new regression test, `test_scored_days_excludes_a_short_only_date`
(`tests/test_score.py`), which fails on the pre-amendment code.

This does not change today's count — 2026-07-22 has both horizons scored —
but would have silently diverged on the first day it didn't.

## 3. Day 1's evening/long forecast counts, despite its non-standard lead time

The live ledger's first scored long-horizon row (2026-07-22, evening
window, target 16:30 UTC) was issued with a **7.41-hour** lead
(`issued_at_utc` ≈ 09:05 UTC), not the ~10.5 h a same-day 07:00 Dublin run
is designed to produce, or the ~16.5 h an overnight 16:00 run produces.
Cause: the ledger's very first issuance happened off the normal 07:00/16:00
schedule while the pipeline was starting up — confirmed one-off, not a
recurring pattern (`scripts/issue_forecasts.py` only fires at 07:00/16:00
Dublin from that point on; the docstring's `--bootstrap-tomorrow-morning`
path exists precisely to log an out-of-schedule issuance honestly rather
than disguise it as a normal run).

Ruling: **it counts.** The model does not receive a fixed per-bucket lead
time — `horizon_min` is computed at serving time as the true elapsed
minutes to target (`src/bikes/forecast.py:99`, `src/bikes/features.py:61`),
so the model was scored on the real 445-minute lead it actually had, not a
mislabelled one. The "long" bucket only decides which gate the observation
feeds into; it does not change how the model priced it. Excluding this
single point because its lead time is atypical, after already having seen
that it scored, is closer to the kind of after-the-fact exclusion the
pre-registration exists to prevent than including a slightly-early forecast
that the model handled correctly.

## What does not change

The verdict gate itself is untouched: per event, at the long horizon, BSS
> 0 vs both baselines with day-clustered bootstrap 95% CI excluding zero,
28 scored days, first possible pass ~2026-08-19. Nothing here relaxes or
tightens that test — it only defines, precisely and before the fact, what
counts as a scored day.
