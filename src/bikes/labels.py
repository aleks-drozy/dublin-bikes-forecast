"""Binary commute-window labels from the state grid (OK instants only)."""
from __future__ import annotations

from datetime import date

import pandas as pd

from bikes.grid import Grid
from bikes.windows import window_instants


def make_labels(grid: Grid, dates: list[date]) -> pd.DataFrame:
    rows, dropped = [], 0
    for d in dates:
        for window, (_, target) in window_instants(d).items():
            if target not in grid.flags.index:
                dropped += len(grid.flags.columns)
                continue
            for sid in grid.flags.columns:
                if grid.flags.at[target, sid] != "OK":
                    dropped += 1
                    continue
                rows.append({
                    "date": d, "window": window, "station_id": sid,
                    "y_bike": bool(grid.bikes.at[target, sid] >= 1),
                    "y_dock": bool(grid.docks.at[target, sid] >= 1),
                })
    out = pd.DataFrame(rows)
    out.attrs["dropped"] = dropped
    return out
