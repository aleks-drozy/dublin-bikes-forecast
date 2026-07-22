#!/usr/bin/env bash
# Issuance cycle: pull, issue (script gates on Dublin hour 07/16), push.
set -euo pipefail
cd /opt/dublin-bikes
source ops/recover.sh
git pull --rebase --quiet
.venv/bin/python scripts/issue_forecasts.py "$@"
git add ledger
git diff --cached --quiet && exit 0
git commit --quiet -m "ledger: forecasts issued $(date -u +'%Y-%m-%dT%H:%M:%SZ') [vm]"
git push --quiet
