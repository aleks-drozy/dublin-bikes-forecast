"""Event rows -> regular 5-min state grid with honesty flags.

Flag semantics (spec P2):
  UNKNOWN  - state cannot be trusted: before a station's first event, during
             a network-wide feed gap (> GLOBAL_GAP), or ffilled beyond
             STALENESS_CAP.
  EXCLUDED - state known but the station was not installed / not renting.
  OK       - everything else; safe for labels and features.
Priority: UNKNOWN beats EXCLUDED beats OK.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

GLOBAL_GAP = pd.Timedelta(minutes=30)
STALENESS_CAP = pd.Timedelta(hours=24)


@dataclass
class Grid:
    bikes: pd.DataFrame   # index: 5-min UTC slots, columns: station_id
    docks: pd.DataFrame
    flags: pd.DataFrame   # same shape, values in {OK, UNKNOWN, EXCLUDED}


def build_grid(events: pd.DataFrame, freq: str = "5min") -> Grid:
    events = events.sort_values("ts")
    slots = pd.date_range(events["ts"].min().floor(freq),
                          events["ts"].max().ceil(freq), freq=freq)

    def wide(col):
        w = events.pivot_table(index="ts", columns="station_id", values=col,
                               aggfunc="last").sort_index()
        # union first: reindex(method="ffill") alone would leave NaN at slot
        # labels that already exist in the pivot from OTHER stations' events
        return w.reindex(slots.union(w.index)).ffill().reindex(slots)

    bikes = wide("bikes")
    docks = wide("docks")
    renting = wide("is_renting").astype("boolean")
    installed = wide("is_installed").astype("boolean")

    # per-station age of the ffilled state
    event_ts = (events.assign(event_ts=events["ts"])
                .pivot_table(index="ts", columns="station_id", values="event_ts",
                             aggfunc="last").sort_index())
    event_ts = event_ts.reindex(slots.union(event_ts.index)).ffill().reindex(slots)
    age = event_ts.rsub(pd.Series(slots, index=slots), axis=0)

    # network-wide silence: age of the most recent event from ANY station
    uniq = pd.DatetimeIndex(events["ts"].drop_duplicates().sort_values())
    network_last = pd.Series(uniq, index=uniq).reindex(slots, method="ffill")
    network_age = pd.Series(slots, index=slots) - network_last

    flags = pd.DataFrame("OK", index=slots, columns=bikes.columns)
    flags = flags.mask(~(renting.fillna(False) & installed.fillna(False)), "EXCLUDED")
    unknown = bikes.isna() | age.isna() | age.gt(STALENESS_CAP)
    unknown = unknown | pd.DataFrame({c: network_age.gt(GLOBAL_GAP)
                                      for c in bikes.columns})
    flags = flags.mask(unknown, "UNKNOWN")
    return Grid(bikes=bikes, docks=docks, flags=flags)
