"""Issuance-time features. Every value must be knowable at issue_ts (leakage
rule, parent spec); the guard test mutates post-issuance data to enforce it."""
from __future__ import annotations

from datetime import date, timedelta

import holidays
import pandas as pd

from bikes.grid import Grid
from bikes.windows import DUBLIN, long_issuance, window_instants

_IE_HOLIDAYS = holidays.country_holidays("IE")


def _day_type(d: date) -> int:
    if d in _IE_HOLIDAYS:
        return 2
    return 1 if d.weekday() >= 5 else 0


def _state_at(grid: Grid, ts, sid):
    if ts not in grid.flags.index or grid.flags.at[ts, sid] != "OK":
        return None
    return float(grid.bikes.at[ts, sid]), float(grid.docks.at[ts, sid])


def make_features(grid: Grid, weather: pd.DataFrame, capacity: pd.Series,
                  dates: list[date]) -> pd.DataFrame:
    wx = weather.set_index("ts")
    rows, dropped = [], 0
    for d in dates:
        for window, (short_issue, target) in window_instants(d).items():
            for horizon, issue in (("short", short_issue),
                                   ("long", long_issuance(d, window))):
                target_local = target.astimezone(DUBLIN)
                how = target_local.weekday() * 24 + target_local.hour
                wx_ts = target.replace(minute=0, second=0, microsecond=0)
                wx_row = wx.loc[wx_ts] if wx_ts in wx.index else None
                for sid in grid.flags.columns:
                    state = _state_at(grid, issue, sid)
                    if state is None:
                        dropped += 1
                        continue
                    bikes, docks = state
                    deltas = {}
                    for name, mins in (("d30", 30), ("d60", 60)):
                        prev = _state_at(grid, issue - timedelta(minutes=mins), sid)
                        deltas[name] = bikes - prev[0] if prev else float("nan")
                    cap = float(capacity.get(sid, float("nan")))
                    rows.append({
                        "date": d, "window": window, "horizon": horizon,
                        "station_id": sid, "issue_ts": issue,
                        "bikes": bikes, "docks": docks,
                        "fill": bikes / cap if cap and cap == cap else float("nan"),
                        "d30": deltas["d30"], "d60": deltas["d60"],
                        "capacity": cap, "how": how, "day_type": _day_type(d),
                        "temp": float(wx_row["temp"]) if wx_row is not None else float("nan"),
                        "precip": float(wx_row["precip"]) if wx_row is not None else float("nan"),
                        "wind": float(wx_row["wind"]) if wx_row is not None else float("nan"),
                        "horizon_min": int((target - issue).total_seconds() // 60),
                    })
    out = pd.DataFrame(rows)
    out.attrs["dropped"] = dropped
    return out
