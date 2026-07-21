from datetime import date

import numpy as np
import pandas as pd
import pytest

from bikes.backtest import (bootstrap_bss_ci, brier, bss, monthly_folds,
                            reliability_bins, run_cv)


def test_brier_and_bss_math():
    y = np.array([1, 0, 1, 0], dtype=float)
    p = np.array([0.8, 0.2, 0.6, 0.4], dtype=float)
    assert brier(p, y) == pytest.approx((0.04 + 0.04 + 0.16 + 0.16) / 4)
    ref = np.full(4, 0.5)
    assert bss(p, y, ref) == pytest.approx(1 - 0.1 / 0.25)


def test_reliability_bins_group_by_predicted_probability():
    p = np.array([0.05, 0.05, 0.95, 0.95])
    y = np.array([0, 0, 1, 1], dtype=float)
    bins = reliability_bins(p, y, n=10)
    assert len(bins) == 2
    assert bins.iloc[0]["y_rate"] == 0.0 and bins.iloc[1]["y_rate"] == 1.0
    assert bins.iloc[1]["count"] == 2


def test_bootstrap_ci_degenerate_cases():
    dates = pd.Series([date(2026, 1, d) for d in (1, 1, 2, 2)])
    y = np.array([1, 0, 1, 0], dtype=float)
    perfect = y.copy()
    ref = np.full(4, 0.5)
    lo, hi = bootstrap_bss_ci(perfect, y, ref, dates, n=200, seed=7)
    assert lo == pytest.approx(1.0) and hi == pytest.approx(1.0)
    lo0, hi0 = bootstrap_bss_ci(ref, y, ref, dates, n=200, seed=7)
    assert lo0 == pytest.approx(0.0) and hi0 == pytest.approx(0.0)


def test_monthly_folds_expanding_window():
    months = [f"2025-{m:02d}" for m in range(1, 10)]
    folds = monthly_folds(months, min_train=6)
    assert folds[0] == (months[:6], "2025-07")
    assert folds[-1] == (months[:8], "2025-09")


def _synthetic_ds():
    rng = np.random.default_rng(3)
    rows = []
    for month in range(1, 9):
        for day in (3, 10, 17):
            for sid in ("1", "2"):
                bikes = float(rng.integers(0, 10))
                rows.append({
                    "date": date(2025, month, day), "window": "morning",
                    "horizon": "short", "station_id": sid, "event": "bike",
                    "bikes": bikes, "docks": 10 - bikes, "fill": bikes / 10,
                    "d30": 0.0, "d60": 0.0, "capacity": 10.0,
                    "how": 8, "day_type": 0, "temp": 10.0, "precip": 0.0,
                    "wind": 5.0, "horizon_min": 90,
                    "y": bikes >= 1,
                })
    return pd.DataFrame(rows)


def test_run_cv_produces_per_fold_predictions():
    preds = run_cv(_synthetic_ds(), min_train=6)
    assert set(preds["val_month"]) == {"2025-07", "2025-08"}
    for col in ("p_model", "p_clim", "p_pers"):
        assert preds[col].between(0, 1).all()
    assert len(preds) == 12  # 2 val months x 3 days x 2 stations
