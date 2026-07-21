"""Assemble the model matrix: features x labels, melted per event."""
from __future__ import annotations

from datetime import date

import pandas as pd

from bikes.features import make_features
from bikes.grid import Grid
from bikes.labels import make_labels


def build_dataset(grid: Grid, weather: pd.DataFrame, capacity: pd.Series,
                  dates: list[date]) -> pd.DataFrame:
    labels = make_labels(grid, dates)
    feats = make_features(grid, weather, capacity, dates)
    if labels.empty or feats.empty:
        return pd.DataFrame()
    merged = feats.merge(labels, on=["date", "window", "station_id"], how="inner")
    parts = []
    for event, col in (("bike", "y_bike"), ("dock", "y_dock")):
        part = merged.drop(columns=["y_bike", "y_dock"]).copy()
        part["event"] = event
        part["y"] = merged[col].astype(bool)
        parts.append(part)
    out = pd.concat(parts, ignore_index=True)
    out.attrs["dropped_labels"] = labels.attrs.get("dropped", 0)
    out.attrs["dropped_features"] = feats.attrs.get("dropped", 0)
    return out
