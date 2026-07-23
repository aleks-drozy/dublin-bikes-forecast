#!/usr/bin/env bash
# Nightly scoring cycle: pull, score matured forecasts, push outcomes.
set -euo pipefail
# One line per run, success or failure. This job runs once a day: its first
# scheduled run ever (2026-07-21) crashed and produced no commit, no log
# line and no page change - total silence. The trap makes failure loud in
# the log, and the OK line makes "did it run at all" a one-line check.
trap 'echo "FAIL scoring $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$?"' ERR
cd /opt/dublin-bikes
source ops/recover.sh
git pull --rebase --quiet
.venv/bin/python scripts/score_forecasts.py
git add ledger
git diff --cached --quiet && exit 0
git commit --quiet -m "ledger: outcomes scored $(date -u +'%Y-%m-%dT%H:%M:%SZ') [vm]"
git push --quiet
