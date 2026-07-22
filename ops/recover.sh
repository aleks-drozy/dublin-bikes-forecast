#!/usr/bin/env bash
# Self-heal preamble sourced by every VM wrapper: if a previous run died
# between writing files and committing (the 2026-07-22 00:30 wedge), commit
# the stranded state so pull --rebase can proceed. Data written by a dead
# run is still real data; committing it is the honest recovery.
if ! git diff --quiet || ! git diff --cached --quiet; then
  git add data ledger
  git commit --quiet -m "data: recover stranded state $(date -u +'%Y-%m-%dT%H:%M:%SZ') [vm-selfheal]"
fi
