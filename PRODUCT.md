# PRODUCT.md — Dublin Bikes Forecast

## What this is

A self-scoring forecasting service for Dublin Bikes availability at commute
windows. Forecasts are committed to a public git ledger before their targets
exist, then scored nightly against reality under a pre-registered verdict
gate. The public page is the product's face: one page that must convince two
audiences at once.

## Users

1. **The auditor** (quant researcher, hiring engineer, statistician):
   arrives skeptical from a CV link, on a laptop, in daylight. Wants to
   check the claim in under a minute: where is the ledger, where are the
   baselines, what happens when the model loses. Trust is won by
   specificity: counts, CIs, timestamps, links to raw files.
2. **The commuter** (Dubliner on a phone at 07:50 on a wet street): wants
   one number for their station and no reading.

## Register

brand — the page is a portfolio artifact; its design carries the argument
that the work is careful. But it must never look like marketing: it borrows
the authority of a public record, not the persuasion of a landing page.

## Tone

A civic instrument. A published ledger, a notice in a public office,
a broadsheet table of record. Sober, typographic, evidence-first, quietly
confident. States its own failure conditions in the same voice as its
successes.

## Anti-references

- Dark "quant dashboard" with neon sparklines (the category reflex).
- SaaS landing pages: hero metrics, gradient text, icon card grids, badges.
- Crypto-trader aesthetics; anything that oversells.
- Generic Bootstrap/Tailwind-default look.

## Strategic principles

1. The page reads the SAME files an auditor would (ledger/*.json) — the
   design must make that verifiability legible, not just claim it.
2. NOT PROVEN must look as designed-for as PASS. The honesty brand is the
   product.
3. Zero dependencies, zero external requests, one file. Constraint is part
   of the credibility.
