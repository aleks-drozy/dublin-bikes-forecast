#!/usr/bin/env bash
# Nightly scoring cycle: pull, score matured forecasts, push outcomes.
set -euo pipefail
cd /opt/dublin-bikes
source ops/recover.sh
git pull --rebase --quiet
.venv/bin/python scripts/score_forecasts.py
git add ledger
git diff --cached --quiet && exit 0
git commit --quiet -m "ledger: outcomes scored $(date -u +'%Y-%m-%dT%H:%M:%SZ') [vm]"
git push --quiet
