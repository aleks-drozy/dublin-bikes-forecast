"""Pre-registered baselines: climatology (Laplace-smoothed) and persistence."""
from __future__ import annotations

import numpy as np
import pandas as pd

_FULL_KEY = ["station_id", "window", "event", "day_type"]
_POOL_KEY = ["window", "event", "day_type"]


class Climatology:
    def fit(self, rows: pd.DataFrame) -> "Climatology":
        y = rows["y"].astype(float)
        agg = rows.assign(y=y).groupby(_FULL_KEY)["y"].agg(["sum", "count"])
        self._full = ((agg["sum"] + 1) / (agg["count"] + 2)).to_dict()
        pool = rows.assign(y=y).groupby(_POOL_KEY)["y"].agg(["sum", "count"])
        self._pool = ((pool["sum"] + 1) / (pool["count"] + 2)).to_dict()
        self._global = float((y.sum() + 1) / (len(y) + 2))
        return self

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        out = np.empty(len(rows))
        for i, r in enumerate(rows.itertuples(index=False)):
            full = (r.station_id, r.window, r.event, r.day_type)
            pool = (r.window, r.event, r.day_type)
            out[i] = self._full.get(full, self._pool.get(pool, self._global))
        return out


def persistence(rows: pd.DataFrame) -> np.ndarray:
    state = np.where(rows["event"] == "bike", rows["bikes"], rows["docks"])
    return (state >= 1).astype(float)
