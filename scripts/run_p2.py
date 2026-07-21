"""Phase 2 end-to-end: archive -> dataset -> CV -> final test -> report.

Test months (2026-04..06) are touched exactly once, after CV. ASCII output.
"""
from __future__ import annotations

import calendar
import json
import sys
from datetime import date
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bikes.archive import download_months, load_month, resolve_month_urls  # noqa: E402
from bikes.backtest import (FEATURE_COLS, _fit_predict, bootstrap_bss_ci,  # noqa: E402
                            brier, bss, reliability_bins, run_cv)
from bikes.baselines import Climatology, persistence  # noqa: E402
from bikes.dataset import build_dataset  # noqa: E402
from bikes.grid import build_grid  # noqa: E402
from bikes.weather import load_or_fetch  # noqa: E402

CACHE = ROOT / ".cache" / "archive"
REPORTS = ROOT / "reports" / "p2"
TEST_MONTHS = ["2026-04", "2026-05", "2026-06"]
ATTEMPT = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13)
           if not (y == 2026 and m > 6)]
SEED = 20260721


def month_dates(month: str) -> list[date]:
    y, m = int(month[:4]), int(month[5:7])
    return [date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]


def main() -> None:
    urls = resolve_month_urls()
    paths = download_months(urls, ATTEMPT, CACHE)
    weather = load_or_fetch(ROOT / "data" / "weather" / "archive.parquet",
                            date(2024, 1, 1), date(2026, 6, 30))
    capacity: dict[str, float] = {}
    frames, used, rejected = [], [], []
    for month in ATTEMPT:
        if month not in paths:
            continue
        events = load_month(paths[month])
        if events is None:
            rejected.append(month)
            continue
        cap = events.groupby("station_id")["capacity"].last()
        capacity.update(cap.to_dict())
        grid = build_grid(events)
        ds = build_dataset(grid, weather, pd.Series(capacity), month_dates(month))
        if ds.empty:
            rejected.append(month)
            continue
        used.append(month)
        frames.append(ds)
        print(f"{month}: {len(ds)} rows "
              f"(dropped labels {ds.attrs['dropped_labels']}, "
              f"features {ds.attrs['dropped_features']})")
    full = pd.concat(frames, ignore_index=True)
    full["month"] = full["date"].astype(str).str[:7]
    print(f"dataset: {len(full)} rows, months used {len(used)}, "
          f"rejected {rejected}")

    cv_ds = full[~full["month"].isin(TEST_MONTHS)].drop(columns=["month"])
    test_ds = full[full["month"].isin(TEST_MONTHS)].drop(columns=["month"])

    print("running expanding-window CV...")
    cv_preds = run_cv(cv_ds, min_train=6, seed=SEED)

    def summarize(preds: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for (event, horizon), g in preds.groupby(["event", "horizon"]):
            y = g["y"].astype(float).values
            rows.append({
                "event": event, "horizon": horizon, "n": len(g),
                "base_rate": float(y.mean()),
                "brier_model": brier(g["p_model"].values, y),
                "brier_clim": brier(g["p_clim"].values, y),
                "brier_pers": brier(g["p_pers"].values, y),
                "bss_vs_clim": bss(g["p_model"].values, y, g["p_clim"].values),
                "bss_vs_pers": bss(g["p_model"].values, y, g["p_pers"].values),
            })
        return pd.DataFrame(rows)

    cv_summary = summarize(cv_preds)
    print(cv_summary.to_string(index=False))

    print("final test (2026-04..06), touched once...")
    stations = sorted(full["station_id"].unique())
    clim = Climatology().fit(cv_ds)
    test = test_ds.copy()
    test["p_model"] = np.nan
    for event in ("bike", "dock"):
        tr = cv_ds[cv_ds["event"] == event]
        va = test[test["event"] == event]
        test.loc[va.index, "p_model"] = _fit_predict(tr, va, stations, SEED)
    test["p_clim"] = clim.predict(test)
    test["p_pers"] = persistence(test)
    test_summary = summarize(test)

    cis = {}
    for (event, horizon), g in test.groupby(["event", "horizon"]):
        y = g["y"].astype(float).values
        cis[f"{event}/{horizon}"] = {
            "bss_vs_clim_ci": bootstrap_bss_ci(
                g["p_model"].values, y, g["p_clim"].values, g["date"], seed=SEED),
            "bss_vs_pers_ci": bootstrap_bss_ci(
                g["p_model"].values, y, g["p_pers"].values, g["date"], seed=SEED),
        }

    REPORTS.mkdir(parents=True, exist_ok=True)
    for (event, horizon), g in test.groupby(["event", "horizon"]):
        bins = reliability_bins(g["p_model"].values, g["y"].astype(float).values)
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot([0, 1], [0, 1], "--", color="grey", label="perfect")
        ax.plot(bins["p_mean"], bins["y_rate"], "o-", label="model")
        ax.set_xlabel("forecast probability")
        ax.set_ylabel("observed frequency")
        ax.set_title(f"Reliability - {event}, {horizon} horizon (final test)")
        ax.legend()
        fig.savefig(REPORTS / f"reliability_{event}_{horizon}.png", dpi=120,
                    bbox_inches="tight")
        plt.close(fig)

    # verdict per pre-registered P2 gate: long horizon, both events, both CIs > 0
    verdict_pass = all(
        cis[f"{e}/long"][k][0] > 0
        for e in ("bike", "dock") for k in ("bss_vs_clim_ci", "bss_vs_pers_ci"))
    verdict = "PASS - model earns P3 deployment" if verdict_pass \
        else "NOT PROVEN - see gate detail"

    metrics = {
        "verdict": verdict,
        "months_used": used, "months_rejected": rejected,
        "rows_total": int(len(full)),
        "cv_summary": cv_summary.to_dict(orient="records"),
        "test_summary": test_summary.to_dict(orient="records"),
        "test_bootstrap_cis": {k: {kk: list(vv) for kk, vv in v.items()}
                               for k, v in cis.items()},
        "seed": SEED,
    }
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2),
                                          encoding="utf-8")
    print("verdict:", verdict)
    print("wrote", REPORTS / "metrics.json")


if __name__ == "__main__":
    main()
