"""Freeze v1: train on all conforming archive months, serialize, verify parity.

Security note on joblib/pickle: models are dumped and loaded exclusively from
THIS repo, and everything that loads them (VM cron, CI) already executes this
repo's shell/Python by design — repo write access is the trust boundary, and
the pickle adds no surface beyond it. sklearn models have no JSON-safe
serialization; joblib is the supported path.
"""
from __future__ import annotations

import calendar
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bikes.archive import load_month  # noqa: E402
from bikes.backtest import FEATURE_COLS  # noqa: E402
from bikes.baselines import Climatology  # noqa: E402
from bikes.dataset import build_dataset  # noqa: E402
from bikes.grid import build_grid  # noqa: E402
from bikes.weather import load_or_fetch  # noqa: E402

CACHE = ROOT / ".cache" / "archive"
OUT = ROOT / "models" / "v1"
SEED = 20260721


def month_dates(month: str) -> list[date]:
    y, m = int(month[:4]), int(month[5:7])
    return [date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]


def main() -> None:
    weather = load_or_fetch(ROOT / "data" / "weather" / "archive.parquet",
                            date(2024, 1, 1), date(2026, 6, 30))
    capacity: dict[str, float] = {}
    frames, used = [], []
    for path in sorted(CACHE.glob("*.csv")):
        events = load_month(path)
        if events is None:
            continue
        capacity.update(events.groupby("station_id")["capacity"].last().to_dict())
        ds = build_dataset(build_grid(events), weather, pd.Series(capacity),
                           month_dates(path.stem))
        if not ds.empty:
            used.append(path.stem)
            frames.append(ds)
    full = pd.concat(frames, ignore_index=True)
    print(f"training on {len(full)} rows from {len(used)} months")

    stations = sorted(full["station_id"].unique())

    def matrix(df):
        x = df[FEATURE_COLS].copy()
        x["station_id"] = pd.Categorical(x["station_id"], categories=stations)
        return x

    OUT.mkdir(parents=True, exist_ok=True)
    for event in ("bike", "dock"):
        sub = full[full["event"] == event]
        model = HistGradientBoostingClassifier(
            categorical_features="from_dtype", early_stopping=True,
            random_state=SEED)
        model.fit(matrix(sub), sub["y"].astype(bool).values)
        probe = sub.sample(n=1000, random_state=SEED)
        p_mem = model.predict_proba(matrix(probe))[:, 1]
        joblib.dump(model, OUT / f"{event}.joblib")
        p_disk = joblib.load(OUT / f"{event}.joblib").predict_proba(matrix(probe))[:, 1]
        assert np.array_equal(p_mem, p_disk), "reload parity failed"
        print(f"{event}: trained on {len(sub)}, reload parity OK")

    clim = Climatology().fit(full)
    (OUT / "climatology.json").write_text(json.dumps({
        "full": {"|".join(map(str, k)): v for k, v in clim._full.items()},
        "pool": {"|".join(map(str, k)): v for k, v in clim._pool.items()},
        "global": clim._global,
    }, indent=1), encoding="utf-8")

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    (OUT / "manifest.json").write_text(json.dumps({
        "version": "v1", "trained": "2026-07-21", "months": used,
        "rows": int(len(full)), "seed": SEED, "features": FEATURE_COLS,
        "stations": stations, "code_commit": commit,
    }, indent=1), encoding="utf-8")
    print("frozen to", OUT)


if __name__ == "__main__":
    main()
