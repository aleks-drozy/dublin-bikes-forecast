# DESIGN.md — Dublin Bikes Forecast scoreboard

## Concept

"Public record": warm paper ground, ink-dark type, a committed cobalt that
does the institutional work. Ledger rules (thin double lines) structure the
page instead of cards. Serif masthead voice for prose; monospace voice for
every number.

## Color (OKLCH; strategy: Committed cobalt on warm paper)

Light (default): bg `oklch(96.5% 0.012 85)` paper · ink `oklch(24% 0.015 60)`
· muted `oklch(45% 0.02 70)` · rule `oklch(85% 0.015 80)` · cobalt accent
`oklch(46% 0.17 262)` · pass green `oklch(52% 0.13 155)` · warn amber
`oklch(58% 0.13 70)`.
Dark: bg `oklch(20% 0.012 60)` warm charcoal · ink `oklch(90% 0.012 85)` ·
cobalt lifted to `oklch(72% 0.12 262)`; chroma reduced near extremes.
No pure black/white anywhere.

## Typography

- Masthead + prose: system serif stack (`'Iowan Old Style', 'Palatino
  Linotype', Palatino, Charter, Georgia, serif`).
- Data, labels, verdict status: `ui-monospace, 'Cascadia Code', Consolas`.
- Scale ratio ≥1.3; small-caps letterspaced labels for section heads.
- Body measure ≤ 68ch.

## Structure

Double-rule masthead → verdict notice (28-tick day strip) → station lookup
(list rows, not cards) → how-it-works as a numbered inline sequence →
evidence table → reliability SVGs → verify-us footer. No modals, no side
stripes, no gradients, no icon grids.

## Motion

Opacity/color transitions only, 150-250ms, ease-out; tick strip fills once
on load; everything gated by `prefers-reduced-motion`.
