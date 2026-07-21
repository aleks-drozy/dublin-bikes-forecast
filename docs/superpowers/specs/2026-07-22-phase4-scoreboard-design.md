# Phase 4: Public Scoreboard — Design Spec

Date: 2026-07-22 (session of 07-21) · Status: Alex authorized ("start P4").

## Goal

The public face: a GitHub Pages site over the live ledger. Two audiences,
one page: commuters ("will there be a bike at my station at 08:30?") and
auditors (is the model actually skillful, judged by the pre-registered gate).

## Architecture

Pages serves the repo root, so the site is static files reading the SAME
artifacts the auditors would: `ledger/summary.json`, `ledger/gate.json`,
`ledger/latest.json`, plus links to raw forecast CSVs and the commit
history (the before-the-fact proof). No build step, no framework, no CDN —
one `index.html` with inline CSS/JS.

## Data plumbing (Python, tested — no statistics in JavaScript)

- `evaluate_gate(ledger_dir)` (score.py), called nightly after scoring:
  writes `ledger/gate.json`. While scored_days < 28: `{"status": "PENDING",
  "scored_days": n, "required_days": 28}`. At ≥28: evaluates the
  PRE-REGISTERED live gate (P1 spec): long-horizon BSS > 0 vs BOTH baselines,
  day-clustered bootstrap 95% CI excluding 0, per event → PASS or NOT_PROVEN
  with all CIs included either way. Gate code ships now, before outcomes
  exist — same discipline as P2.
- `write_latest_json(ledger_dir, stations)` (forecast.py), called at each
  issuance: `ledger/latest.json` = most recent forecast per station × window
  × event with station names — the commuter feed.
- `write_summary` gains reliability bins (10) per event × horizon so the
  page can draw calibration dots without recomputing anything.

## Page sections (top to bottom)

1. **Verdict banner** — PENDING n/28 (neutral), PASS (green), NOT PROVEN
   (amber, shown just as prominently). One-sentence gate explanation +
   spec link.
2. **Commuter lookup** — station select (searchable datalist), shows
   P(bike)/P(dock) for the next windows with issued-at times.
3. **Evidence** — BSS table (model vs climatology vs persistence, per
   event × horizon), reliability dots (inline SVG), status counts
   (SCORED / UNSCOREABLE_GAP / EXCLUDED_STATION shown, never hidden).
4. **Methodology footer** — honesty rules, ledger + commit-history links
   ("verify the timestamps yourself"), model manifest link, repo link.

Design: single column, mobile-first, system font stack, OKLCH accent
palette, `prefers-color-scheme` aware, no external requests of any kind.

## Non-goals

Map view (v2 — needs a tile provider or inline geometry; the list serves
the commuter question), historical charts beyond reliability, retraining.
