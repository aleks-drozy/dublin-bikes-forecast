"""Expanding-window monthly CV, Brier/BSS metrics, day-clustered bootstrap."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from bikes.baselines import Climatology, persistence

FEATURE_COLS = ["bikes", "docks", "fill", "d30", "d60", "capacity",
                "how", "day_type", "temp", "precip", "wind",
                "horizon_min", "station_id"]


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def bss(p: np.ndarray, y: np.ndarray, p_ref: np.ndarray) -> float:
    ref = brier(p_ref, y)
    return float("nan") if ref == 0 else 1.0 - brier(p, y) / ref


def reliability_bins(p: np.ndarray, y: np.ndarray, n: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"p": p, "y": np.asarray(y, dtype=float)})
    df["bin"] = np.clip((df["p"] * n).astype(int), 0, n - 1)
    out = df.groupby("bin").agg(p_mean=("p", "mean"), y_rate=("y", "mean"),
                                count=("y", "size")).reset_index()
    out["bin_mid"] = (out["bin"] + 0.5) / n
    return out


def bootstrap_bss_ci(p, y, p_ref, dates: pd.Series, n: int = 2000,
                     seed: int = 0) -> tuple[float, float]:
    df = pd.DataFrame({"p": p, "y": np.asarray(y, dtype=float),
                       "ref": p_ref, "date": np.asarray(dates)})
    groups = {d: g for d, g in df.groupby("date")}
    days = list(groups)
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n):
        sample = pd.concat([groups[d] for d in rng.choice(days, len(days))])
        stats.append(bss(sample["p"].values, sample["y"].values,
                         sample["ref"].values))
    return (float(np.nanpercentile(stats, 2.5)),
            float(np.nanpercentile(stats, 97.5)))


def monthly_folds(months: list[str], min_train: int = 6):
    months = sorted(months)
    return [(months[:i], months[i]) for i in range(min_train, len(months))]


def _month_key(dates: pd.Series) -> pd.Series:
    return dates.astype(str).str[:7]


def _fit_predict(train: pd.DataFrame, val: pd.DataFrame,
                 station_categories: list[str], seed: int = 0) -> np.ndarray:
    def matrix(df):
        x = df[FEATURE_COLS].copy()
        x["station_id"] = pd.Categorical(x["station_id"],
                                         categories=station_categories)
        return x

    y_train = train["y"].astype(bool).values
    if y_train.all() or not y_train.any():  # degenerate single-class fold
        return np.full(len(val), float(y_train[0]))
    model = HistGradientBoostingClassifier(
        categorical_features="from_dtype", early_stopping=True, random_state=seed)
    model.fit(matrix(train), y_train)
    proba = model.predict_proba(matrix(val))
    return proba[:, list(model.classes_).index(True)]


def run_cv(ds: pd.DataFrame, min_train: int = 6, seed: int = 0) -> pd.DataFrame:
    ds = ds.copy()
    ds["month"] = _month_key(ds["date"])
    stations = sorted(ds["station_id"].unique())
    outputs = []
    for train_months, val_month in monthly_folds(sorted(ds["month"].unique()),
                                                 min_train=min_train):
        train = ds[ds["month"].isin(train_months)]
        val = ds[ds["month"] == val_month]
        if train.empty or val.empty:
            continue
        preds = pd.DataFrame(index=val.index)
        preds["p_model"] = np.nan
        for event in ("bike", "dock"):
            tr, va = train[train["event"] == event], val[val["event"] == event]
            if va.empty:
                continue
            if tr.empty:
                continue
            preds.loc[va.index, "p_model"] = _fit_predict(tr, va, stations, seed)
        clim = Climatology().fit(train)
        out = val.copy()
        out["p_model"] = preds["p_model"]
        out["p_clim"] = clim.predict(val)
        out["p_pers"] = persistence(val)
        out["val_month"] = val_month
        outputs.append(out)
    return pd.concat(outputs, ignore_index=True)
