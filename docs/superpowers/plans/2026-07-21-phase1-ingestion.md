# Phase 1: Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GitHub-Actions-hosted poller that records dublinbikes GBFS station state every 10 minutes into daily parquet partitions, with every poll's health honestly accounted.

**Architecture:** Git-scraping: an Actions cron job runs `python -m bikes.poll`, which fetches the keyless GBFS feeds, appends station rows to `data/raw/<UTC-date>.parquet`, appends one health row to `data/quality/<UTC-date>.parquet`, and the workflow commits the result. Parsing, storage, and health accounting are separate modules with network access injected, so all tests are network-free.

**Tech Stack:** Python 3.12, pandas + pyarrow, pytest, stdlib `urllib` for fetching, GitHub Actions cron.

## Global Constraints

- All stored timestamps are UTC (`datetime` with `timezone.utc`); Europe/Dublin conversions happen only at read time (spec: DST discipline).
- All file I/O uses explicit `encoding="utf-8"`; console output is ASCII-only (Windows cp1252 guard).
- Tests never touch the network — fetching is injected as a callable.
- Failures are counted, never hidden: a failed fetch still writes a quality row.
- Feed URLs (spec): `https://api.cyclocity.fr/contracts/dublin/gbfs/v2/station_status.json` and `.../station_information.json`.

---

### Task 1: Project scaffold + GBFS parsing

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/bikes/__init__.py`, `src/bikes/gbfs.py`
- Test: `tests/test_gbfs.py`, `tests/fixtures/station_status.json`, `tests/fixtures/station_information.json`

**Interfaces:**
- Produces: `StatusRecord` (frozen dataclass: `station_id: str`, `num_bikes_available: int`, `num_docks_available: int`, `is_installed: bool`, `is_renting: bool`, `is_returning: bool`, `last_reported: datetime | None`), `StationInfo` (frozen dataclass: `station_id: str`, `name: str`, `lat: float`, `lon: float`, `capacity: int`), `ParseResult` (dataclass: `records: list`, `feed_last_updated: datetime | None`, `skipped: int`), `parse_station_status(payload: dict) -> ParseResult`, `parse_station_information(payload: dict) -> ParseResult`, `GBFS_STATUS_URL: str`, `GBFS_INFO_URL: str`, `fetch_json(url: str, timeout: float = 30.0) -> dict`

- [ ] **Step 1: Write pyproject and gitignore**

`pyproject.toml`:
```toml
[project]
name = "dublin-bikes-forecast"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pandas>=2.0", "pyarrow>=15.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.setuptools.packages.find]
where = ["src"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

`.gitignore`:
```
__pycache__/
*.egg-info/
.pytest_cache/
.venv/
```

- [ ] **Step 2: Write fixtures (real GBFS v2 shape, 3 stations incl. one malformed)**

`tests/fixtures/station_status.json`:
```json
{
  "last_updated": 1753084800,
  "ttl": 60,
  "version": "2.3",
  "data": {
    "stations": [
      {"station_id": "42", "num_bikes_available": 5, "num_docks_available": 15,
       "is_installed": true, "is_renting": true, "is_returning": true,
       "last_reported": 1753084740},
      {"station_id": "7", "num_bikes_available": 0, "num_docks_available": 30,
       "is_installed": true, "is_renting": false, "is_returning": true,
       "last_reported": 1753084700},
      {"station_id": "99", "num_bikes_available": 3}
    ]
  }
}
```

`tests/fixtures/station_information.json`:
```json
{
  "last_updated": 1753084800,
  "ttl": 3600,
  "version": "2.3",
  "data": {
    "stations": [
      {"station_id": "42", "name": "Smithfield North", "lat": 53.349562,
       "lon": -6.278198, "capacity": 20},
      {"station_id": "7", "name": "High Street", "lat": 53.343565,
       "lon": -6.272120, "capacity": 30}
    ]
  }
}
```

- [ ] **Step 3: Write the failing tests**

`tests/test_gbfs.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path

from bikes.gbfs import parse_station_information, parse_station_status

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_status_returns_well_formed_records():
    result = parse_station_status(load("station_status.json"))
    assert len(result.records) == 2  # station 99 lacks required fields
    assert result.skipped == 1
    r = result.records[0]
    assert r.station_id == "42"
    assert r.num_bikes_available == 5
    assert r.num_docks_available == 15
    assert r.is_renting is True
    assert r.last_reported == datetime(2026, 7, 21, 8, 39, tzinfo=timezone.utc)


def test_parse_status_feed_timestamp_is_utc():
    result = parse_station_status(load("station_status.json"))
    assert result.feed_last_updated == datetime(2026, 7, 21, 8, 40, tzinfo=timezone.utc)


def test_parse_status_missing_last_reported_is_none_not_skip():
    payload = load("station_status.json")
    del payload["data"]["stations"][0]["last_reported"]
    result = parse_station_status(payload)
    assert result.records[0].last_reported is None


def test_parse_information():
    result = parse_station_information(load("station_information.json"))
    assert len(result.records) == 2
    assert result.skipped == 0
    assert result.records[0].name == "Smithfield North"
    assert result.records[0].capacity == 20
```

Note: fixture epoch 1753084800 = 2026-07-21 08:40:00 UTC is wrong — 1753084800 is 2025-07-21. Compute the real epoch for 2026-07-21 08:40 UTC (`1784709600`) and use it in both fixtures and tests. The implementer MUST verify with `python -c "from datetime import *; print(datetime.fromtimestamp(1784709600, timezone.utc))"` before writing the fixture, and adjust `last_reported` values to 60 s and 100 s earlier.

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_gbfs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bikes'`

- [ ] **Step 5: Implement `src/bikes/gbfs.py`**

```python
"""Fetch and parse the dublinbikes GBFS v2 feeds."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

GBFS_BASE = "https://api.cyclocity.fr/contracts/dublin/gbfs/v2"
GBFS_STATUS_URL = f"{GBFS_BASE}/station_status.json"
GBFS_INFO_URL = f"{GBFS_BASE}/station_information.json"

_STATUS_REQUIRED = ("station_id", "num_bikes_available", "num_docks_available")
_INFO_REQUIRED = ("station_id", "name", "lat", "lon", "capacity")


@dataclass(frozen=True)
class StatusRecord:
    station_id: str
    num_bikes_available: int
    num_docks_available: int
    is_installed: bool
    is_renting: bool
    is_returning: bool
    last_reported: datetime | None


@dataclass(frozen=True)
class StationInfo:
    station_id: str
    name: str
    lat: float
    lon: float
    capacity: int


@dataclass
class ParseResult:
    records: list = field(default_factory=list)
    feed_last_updated: datetime | None = None
    skipped: int = 0


def _epoch_utc(value) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def fetch_json(url: str, timeout: float = 30.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_station_status(payload: dict) -> ParseResult:
    result = ParseResult(feed_last_updated=_epoch_utc(payload.get("last_updated")))
    for raw in payload.get("data", {}).get("stations", []):
        if any(raw.get(k) is None for k in _STATUS_REQUIRED):
            result.skipped += 1
            continue
        result.records.append(StatusRecord(
            station_id=str(raw["station_id"]),
            num_bikes_available=int(raw["num_bikes_available"]),
            num_docks_available=int(raw["num_docks_available"]),
            is_installed=bool(raw.get("is_installed", True)),
            is_renting=bool(raw.get("is_renting", True)),
            is_returning=bool(raw.get("is_returning", True)),
            last_reported=_epoch_utc(raw.get("last_reported")),
        ))
    return result


def parse_station_information(payload: dict) -> ParseResult:
    result = ParseResult(feed_last_updated=_epoch_utc(payload.get("last_updated")))
    for raw in payload.get("data", {}).get("stations", []):
        if any(raw.get(k) is None for k in _INFO_REQUIRED):
            result.skipped += 1
            continue
        result.records.append(StationInfo(
            station_id=str(raw["station_id"]),
            name=str(raw["name"]),
            lat=float(raw["lat"]),
            lon=float(raw["lon"]),
            capacity=int(raw["capacity"]),
        ))
    return result
```

Also create empty `src/bikes/__init__.py`.

- [ ] **Step 6: Install editable and run tests to verify they pass**

Run: `pip install -e ".[dev]"` then `python -m pytest tests/test_gbfs.py -v`
Expected: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore src tests
git commit -m "feat: GBFS v2 parsing with honest skip accounting"
```

---

### Task 2: Parquet storage

**Files:**
- Create: `src/bikes/store.py`, `data/raw/.gitkeep`, `data/stations/.gitkeep`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `StatusRecord`, `StationInfo` from Task 1.
- Produces: `append_status(records: list[StatusRecord], poll_ts: datetime, feed_last_updated: datetime | None, root: Path) -> Path` (appends to `<root>/raw/YYYY-MM-DD.parquet`, UTC date of `poll_ts`, returns path), `upsert_stations(infos: list[StationInfo], root: Path) -> bool` (rewrites `<root>/stations/stations.parquet` only when content changed; returns True if written). Raw schema columns: `station_id, num_bikes_available, num_docks_available, is_installed, is_renting, is_returning, last_reported, poll_ts, feed_last_updated`.

- [ ] **Step 1: Write the failing tests**

`tests/test_store.py`:
```python
from datetime import datetime, timezone

import pandas as pd

from bikes.gbfs import StationInfo, StatusRecord
from bikes.store import append_status, upsert_stations


def rec(sid="42", bikes=5):
    return StatusRecord(
        station_id=sid, num_bikes_available=bikes, num_docks_available=15,
        is_installed=True, is_renting=True, is_returning=True,
        last_reported=datetime(2026, 7, 21, 8, 39, tzinfo=timezone.utc),
    )


POLL_TS = datetime(2026, 7, 21, 8, 40, 12, tzinfo=timezone.utc)


def test_append_creates_daily_partition_named_by_utc_date(tmp_path):
    path = append_status([rec()], POLL_TS, POLL_TS, tmp_path)
    assert path.name == "2026-07-21.parquet"
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert df.loc[0, "station_id"] == "42"
    assert df.loc[0, "poll_ts"] == pd.Timestamp(POLL_TS)


def test_append_twice_accumulates_rows(tmp_path):
    append_status([rec()], POLL_TS, POLL_TS, tmp_path)
    later = POLL_TS.replace(minute=50)
    path = append_status([rec(bikes=4)], later, later, tmp_path)
    df = pd.read_parquet(path)
    assert len(df) == 2
    assert sorted(df["num_bikes_available"]) == [4, 5]


def test_append_near_midnight_splits_partitions_by_utc(tmp_path):
    late = datetime(2026, 7, 21, 23, 55, tzinfo=timezone.utc)
    next_day = datetime(2026, 7, 22, 0, 5, tzinfo=timezone.utc)
    p1 = append_status([rec()], late, late, tmp_path)
    p2 = append_status([rec()], next_day, next_day, tmp_path)
    assert p1.name == "2026-07-21.parquet"
    assert p2.name == "2026-07-22.parquet"


def test_upsert_stations_writes_once_for_same_content(tmp_path):
    infos = [StationInfo("42", "Smithfield North", 53.34, -6.27, 20)]
    assert upsert_stations(infos, tmp_path) is True
    assert upsert_stations(infos, tmp_path) is False
    changed = [StationInfo("42", "Smithfield North", 53.34, -6.27, 25)]
    assert upsert_stations(changed, tmp_path) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bikes.store'`

- [ ] **Step 3: Implement `src/bikes/store.py`**

```python
"""Parquet persistence: daily raw partitions + station registry."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from bikes.gbfs import StationInfo, StatusRecord


def append_status(records: list[StatusRecord], poll_ts: datetime,
                  feed_last_updated: datetime | None, root: Path) -> Path:
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{poll_ts.date().isoformat()}.parquet"
    df = pd.DataFrame([asdict(r) for r in records])
    df["poll_ts"] = pd.Timestamp(poll_ts)
    df["feed_last_updated"] = pd.Timestamp(feed_last_updated) if feed_last_updated else pd.NaT
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    df.to_parquet(path, index=False)
    return path


def upsert_stations(infos: list[StationInfo], root: Path) -> bool:
    stations_dir = root / "stations"
    stations_dir.mkdir(parents=True, exist_ok=True)
    path = stations_dir / "stations.parquet"
    df = pd.DataFrame([asdict(i) for i in infos]).sort_values("station_id").reset_index(drop=True)
    if path.exists():
        existing = pd.read_parquet(path)
        if existing.equals(df):
            return False
    df.to_parquet(path, index=False)
    return True
```

Note for implementer: `poll_ts.date()` on a UTC-aware datetime yields the UTC
date, which is exactly the partition rule in the spec. Do not localize here.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_store.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/bikes/store.py tests/test_store.py data
git commit -m "feat: daily parquet partitions + change-only station registry"
```

---

### Task 3: Poll-quality ledger

**Files:**
- Create: `src/bikes/quality.py`, `data/quality/.gitkeep`
- Test: `tests/test_quality.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (standalone).
- Produces: `record_poll(root: Path, poll_ts: datetime, ok: bool, fetch_ms: int, status_count: int, skipped: int, feed_age_s: float | None, error: str | None) -> Path` appending one row to `<root>/quality/YYYY-MM-DD.parquet` (UTC date of `poll_ts`) with exactly those columns.

- [ ] **Step 1: Write the failing tests**

`tests/test_quality.py`:
```python
from datetime import datetime, timezone

import pandas as pd

from bikes.quality import record_poll

POLL_TS = datetime(2026, 7, 21, 8, 40, 12, tzinfo=timezone.utc)


def test_ok_poll_row(tmp_path):
    path = record_poll(tmp_path, POLL_TS, ok=True, fetch_ms=340,
                       status_count=117, skipped=1, feed_age_s=42.0, error=None)
    df = pd.read_parquet(path)
    assert path.name == "2026-07-21.parquet"
    assert df.loc[0, "ok"]
    assert df.loc[0, "status_count"] == 117
    assert df.loc[0, "feed_age_s"] == 42.0
    assert pd.isna(df.loc[0, "error"])


def test_failed_poll_is_recorded_not_hidden(tmp_path):
    path = record_poll(tmp_path, POLL_TS, ok=False, fetch_ms=30000,
                       status_count=0, skipped=0, feed_age_s=None,
                       error="URLError: timed out")
    df = pd.read_parquet(path)
    assert not df.loc[0, "ok"]
    assert df.loc[0, "error"] == "URLError: timed out"


def test_rows_accumulate(tmp_path):
    record_poll(tmp_path, POLL_TS, True, 300, 117, 0, 40.0, None)
    path = record_poll(tmp_path, POLL_TS.replace(minute=50), True, 310, 117, 0, 41.0, None)
    assert len(pd.read_parquet(path)) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_quality.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bikes.quality'`

- [ ] **Step 3: Implement `src/bikes/quality.py`**

```python
"""Poll-health ledger: every poll leaves a row, especially the failures."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


def record_poll(root: Path, poll_ts: datetime, ok: bool, fetch_ms: int,
                status_count: int, skipped: int, feed_age_s: float | None,
                error: str | None) -> Path:
    quality_dir = root / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    path = quality_dir / f"{poll_ts.date().isoformat()}.parquet"
    row = pd.DataFrame([{
        "poll_ts": pd.Timestamp(poll_ts), "ok": ok, "fetch_ms": fetch_ms,
        "status_count": status_count, "skipped": skipped,
        "feed_age_s": feed_age_s, "error": error,
    }])
    if path.exists():
        row = pd.concat([pd.read_parquet(path), row], ignore_index=True)
    row.to_parquet(path, index=False)
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_quality.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/bikes/quality.py tests/test_quality.py data/quality
git commit -m "feat: poll-quality ledger records failures as rows"
```

---

### Task 4: Poll orchestration CLI

**Files:**
- Create: `src/bikes/poll.py`
- Test: `tests/test_poll.py`

**Interfaces:**
- Consumes: everything above — `fetch_json`, `parse_station_status`, `parse_station_information`, `GBFS_STATUS_URL`, `GBFS_INFO_URL`, `append_status`, `upsert_stations`, `record_poll`.
- Produces: `run_poll(root: Path, fetcher=fetch_json, now=None) -> bool` (True if the status fetch+store succeeded) and `python -m bikes.poll` entry point using `data/` as root. `fetcher` and `now` are injected for tests.

- [ ] **Step 1: Write the failing tests**

`tests/test_poll.py`:
```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from bikes.gbfs import GBFS_INFO_URL, GBFS_STATUS_URL
from bikes.poll import run_poll

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 7, 21, 8, 40, 12, tzinfo=timezone.utc)


def fake_fetcher(url, timeout=30.0):
    name = "station_status.json" if url == GBFS_STATUS_URL else "station_information.json"
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_successful_poll_writes_all_three_stores(tmp_path):
    assert run_poll(tmp_path, fetcher=fake_fetcher, now=NOW) is True
    raw = pd.read_parquet(tmp_path / "raw" / "2026-07-21.parquet")
    assert len(raw) == 2
    assert (tmp_path / "stations" / "stations.parquet").exists()
    quality = pd.read_parquet(tmp_path / "quality" / "2026-07-21.parquet")
    assert quality.loc[0, "ok"]
    assert quality.loc[0, "status_count"] == 2
    assert quality.loc[0, "skipped"] == 1


def test_fetch_failure_still_writes_quality_row(tmp_path):
    def broken(url, timeout=30.0):
        raise OSError("connection refused")
    assert run_poll(tmp_path, fetcher=broken, now=NOW) is False
    quality = pd.read_parquet(tmp_path / "quality" / "2026-07-21.parquet")
    assert not quality.loc[0, "ok"]
    assert "connection refused" in quality.loc[0, "error"]
    assert not (tmp_path / "raw").exists()


def test_info_failure_does_not_lose_status_data(tmp_path):
    def status_only(url, timeout=30.0):
        if url == GBFS_INFO_URL:
            raise OSError("info feed down")
        return fake_fetcher(url, timeout)
    assert run_poll(tmp_path, fetcher=status_only, now=NOW) is True
    assert (tmp_path / "raw" / "2026-07-21.parquet").exists()
    quality = pd.read_parquet(tmp_path / "quality" / "2026-07-21.parquet")
    assert quality.loc[0, "ok"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_poll.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bikes.poll'`

- [ ] **Step 3: Implement `src/bikes/poll.py`**

```python
"""One poll cycle: fetch -> parse -> store -> account. ASCII output only."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from bikes.gbfs import (GBFS_INFO_URL, GBFS_STATUS_URL, fetch_json,
                        parse_station_information, parse_station_status)
from bikes.quality import record_poll
from bikes.store import append_status, upsert_stations


def run_poll(root: Path, fetcher=fetch_json, now: datetime | None = None) -> bool:
    poll_ts = now or datetime.now(timezone.utc)
    started = time.monotonic()
    try:
        payload = fetcher(GBFS_STATUS_URL)
    except Exception as exc:  # noqa: BLE001 - every failure becomes a ledger row
        fetch_ms = int((time.monotonic() - started) * 1000)
        record_poll(root, poll_ts, ok=False, fetch_ms=fetch_ms, status_count=0,
                    skipped=0, feed_age_s=None, error=f"{type(exc).__name__}: {exc}")
        print(f"poll FAILED after {fetch_ms} ms: {type(exc).__name__}")
        return False

    fetch_ms = int((time.monotonic() - started) * 1000)
    result = parse_station_status(payload)
    append_status(result.records, poll_ts, result.feed_last_updated, root)
    feed_age_s = None
    if result.feed_last_updated is not None:
        feed_age_s = (poll_ts - result.feed_last_updated).total_seconds()
    record_poll(root, poll_ts, ok=True, fetch_ms=fetch_ms,
                status_count=len(result.records), skipped=result.skipped,
                feed_age_s=feed_age_s, error=None)

    try:  # station_information is best-effort; status data must survive its loss
        info = parse_station_information(fetcher(GBFS_INFO_URL))
        if info.records:
            upsert_stations(info.records, root)
    except Exception as exc:  # noqa: BLE001
        print(f"info fetch skipped: {type(exc).__name__}")

    print(f"poll ok: {len(result.records)} stations, {result.skipped} skipped, "
          f"{fetch_ms} ms, feed_age_s={feed_age_s}")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_poll(Path("data")) else 0)
```

Note: the module exits 0 even on failure — transient feed outages must not
paint the Actions history red; the quality ledger is the honest record. The
workflow still surfaces chronic failure via the P4 scoreboard gap counts.

- [ ] **Step 4: Run all tests to verify they pass**

Run: `python -m pytest -v`
Expected: 14 PASS (4 gbfs + 4 store + 3 quality + 3 poll)

- [ ] **Step 5: Commit**

```bash
git add src/bikes/poll.py tests/test_poll.py
git commit -m "feat: poll cycle with injected fetcher and fail-open info fetch"
```

---

### Task 5: Actions workflow + eligibility stub + README

**Files:**
- Create: `.github/workflows/poll.yml`, `scoring/eligibility.py`, `README.md`

**Interfaces:**
- Consumes: `python -m bikes.poll` from Task 4.
- Produces: the live cron; `scoring/eligibility.py` stub whose final body is Alex's P3 contribution.

- [ ] **Step 1: Write `.github/workflows/poll.yml`**

```yaml
name: poll
on:
  schedule:
    - cron: "*/10 * * * *"
  workflow_dispatch:
concurrency:
  group: poll
  cancel-in-progress: false
permissions:
  contents: write
jobs:
  poll:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -e .
      - run: python -m bikes.poll
      - name: Commit data
        run: |
          git config user.name "bikes-poller"
          git config user.email "actions@users.noreply.github.com"
          git add data
          git diff --cached --quiet && exit 0
          git commit -m "data: poll $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
          git pull --rebase origin master
          git push
```

- [ ] **Step 2: Write `scoring/eligibility.py` (stub — Alex's P3 decision point)**

```python
"""Scoring eligibility: which observation may stand in for a target instant.

DECISION POINT (Alex, P3): this rule is the honesty core of scoring.
Trade-offs:
  - tight tolerance -> more UNSCOREABLE_GAP days (less data, cleaner claim)
  - loose tolerance -> scoring against state that may not represent the
    target instant (more data, weaker claim)
  - feed staleness: an observation polled near the target may carry a
    last_reported minutes older; decide whether poll_ts or last_reported
    gates eligibility.
Spec provisional bound: +/- 10 minutes around the target instant.
"""
from __future__ import annotations

from datetime import datetime

# Filled in P3 by Alex (5-10 lines). Signature is fixed; P3 scoring code
# will import exactly this name.


def eligible_observation(target_ts: datetime, poll_ts: datetime,
                         last_reported: datetime | None) -> bool:
    raise NotImplementedError("P3 decision point - see module docstring")
```

- [ ] **Step 3: Write `README.md`**

```markdown
# Dublin Bikes Forecast

Live, publicly scored probability forecasts for dublinbikes availability at
commute times: **P(at least one bike)** and **P(at least one free dock)** per
station at 08:30 and 17:30 (Europe/Dublin), issued before the fact at two
horizons (~90 min and overnight), scored against pre-registered baselines.

**Status: Phase 1 — data collection.** No forecasts exist yet. The verdict
gate (Brier skill vs climatology AND persistence, day-clustered bootstrap
95% CI, 28 live days) is pre-registered in
[the design spec](docs/superpowers/specs/2026-07-21-dublin-bikes-forecast-design.md)
and was committed before any data was collected or any model written.

## Honesty rules

- Forecasts enter an append-only ledger committed before target time.
- Missed polls, feed gaps, and unscoreable targets are counted and published.
- Baselines freeze before the live ledger starts; losing to persistence is
  published as NOT PROVEN, not hidden.

## Data

10-minute GBFS polls (keyless public feed) into daily parquet partitions
under `data/raw/`; poll health under `data/quality/`. All timestamps UTC.
```

- [ ] **Step 4: Validate workflow YAML parses**

Run: `python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/poll.yml').read_text(encoding='utf-8')); print('yaml ok')"`
(If PyYAML is absent: `pip install pyyaml` first.)
Expected: `yaml ok`

- [ ] **Step 5: Run full suite once more**

Run: `python -m pytest -v`
Expected: 14 PASS (the stub raises NotImplementedError only when called; no test imports it yet)

- [ ] **Step 6: Commit**

```bash
git add .github scoring README.md
git commit -m "feat: 10-min poll workflow, eligibility decision stub, honest README"
```

---

## Self-review notes

- Spec coverage: ingestion cadence (Task 5 cron), parquet partitions (Task 2), honest accounting incl. failed polls (Tasks 3-4), keyless feeds (Task 1), UTC-only storage (all), eligibility decision point (Task 5 stub). Weather/model/ledger/site are P2-P4, out of this plan by design.
- Fixture epoch caveat is flagged inline in Task 1 Step 3 (verify real epoch before writing fixtures).
- Types consistent: `ParseResult.records` consumed by `append_status`/`upsert_stations`; `run_poll` signature matches workflow's `python -m bikes.poll`.
