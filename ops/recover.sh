#!/usr/bin/env bash
# Self-heal preamble sourced by every VM wrapper: if a previous run died
# between writing files and committing (the 2026-07-22 00:30 wedge), commit
# the stranded state so pull --rebase can proceed. Data written by a dead
# run is still real data; committing it is the honest recovery.
# Trigger scoped to the same paths that get staged: a dirty file anywhere
# else (an ops script edited mid-debug, a touched README) used to satisfy
# the unscoped check, stage nothing, and kill the sourcing wrapper on
# `git commit`'s "nothing added" exit under set -e - silently skipping the
# night's run. The commit is also non-fatal for the same reason: self-heal
# must never be the thing that takes the job down.
if ! git diff --quiet -- data ledger || ! git diff --cached --quiet -- data ledger; then
  git add data ledger
  git commit --quiet -m "data: recover stranded state $(date -u +'%Y-%m-%dT%H:%M:%SZ') [vm-selfheal]" || true
fi
