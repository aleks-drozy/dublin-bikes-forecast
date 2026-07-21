# Ops Runbook — dublin-bikes-forecast

## VM poller (primary since 2026-07-21)

GitHub Actions cron proved unreliable for this repo (measured ~90-min gaps
vs the requested 10). Polling therefore runs on the shared Oracle VM
(`ubuntu@<vm>`, same box as ghost-bus) under the ubuntu user's crontab:

```
*/10 * * * * flock -n /tmp/bikes-repo.lock /opt/dublin-bikes/ops/poll_vm.sh >> /home/ubuntu/bikes-poll.log 2>&1
5 * * * *    flock -n /tmp/bikes-repo.lock /opt/dublin-bikes/ops/issue_vm.sh >> /home/ubuntu/bikes-issue.log 2>&1
45 23 * * *  flock -n /tmp/bikes-repo.lock /opt/dublin-bikes/ops/score_vm.sh >> /home/ubuntu/bikes-score.log 2>&1
```

All three share ONE lock (`bikes-repo.lock`): they pull/commit/push the same
clone, so their git operations must serialize. The issuance cron fires
hourly at :05 (fresh :00 poll on disk) and `issuance_sets()` exits unless
the Dublin hour is 07 or 16 — DST-proof without touching crontab twice a
year. Scoring runs 23:45 UTC, after both targets have matured year-round.

Layout on the VM:
- `/opt/dublin-bikes` — clone via the `github-bikes` SSH alias (deploy key
  `~/.ssh/bikes_deploy`, write-scoped to this repo only).
- `.venv` with pandas + pyarrow + scikit-learn + holidays (P3: issuance
  loads the frozen models, so sklearn joined the venv 2026-07-21; matplotlib
  stays off the box — plotting is P4/local). `pip install -e . --no-deps`.
- Log: `~/bikes-poll.log` (poll summaries + any git errors).

The Actions workflow keeps `workflow_dispatch` for manual/backfill polls but
its schedule trigger was removed — one primary data source, honestly
accounted, instead of two racing ones.

## Health checks

- Recent data commits: `git log --oneline -5 -- data/` (expect `[vm]` suffix
  every ~10 min).
- Poll quality: `data/quality/<today>.parquet` — `ok` column, `fetch_ms`,
  gaps visible as missing 10-min slots.
- VM side: `tail ~/bikes-poll.log`, `crontab -l`.

## Removal

`crontab -e` (remove the bikes line), `rm -rf /opt/dublin-bikes`, delete the
deploy key from the repo settings. Nothing else on the VM is touched;
ghost-bus services are entirely separate.
