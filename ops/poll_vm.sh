#!/usr/bin/env bash
# One poll cycle on the VM: pull, poll, commit, push. Cron wraps this in
# flock so overlapping runs are impossible. Failures land in the quality
# ledger (the poller exits 0 by design); this script only fails on git/env
# breakage, which cron mails to the local log.
set -euo pipefail
cd /opt/dublin-bikes
git pull --rebase --quiet
.venv/bin/python -m bikes.poll
git add data
git diff --cached --quiet && exit 0
git commit --quiet -m "data: poll $(date -u +'%Y-%m-%dT%H:%M:%SZ') [vm]"
git push --quiet
