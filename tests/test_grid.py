from datetime import datetime, timedelta, timezone

import pandas as pd

from bikes.grid import build_grid

T0 = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)


def ev(minutes, sid, bikes, docks, renting=True, installed=True):
    return {"ts": T0 + timedelta(minutes=minutes), "station_id": sid,
            "bikes": bikes, "docks": docks,
            "is_installed": installed, "is_renting": renting, "capacity": 30}


def frame(events):
    return pd.DataFrame(events)


def test_ffill_fills_quiet_slots_as_ok():
    g = build_grid(frame([ev(0, "1", 5, 25), ev(10, "1", 4, 26),
                          ev(0, "2", 0, 30), ev(10, "2", 1, 29)]))
    t5 = T0 + timedelta(minutes=5)
    assert g.bikes.loc[t5, "1"] == 5          # carried from 00:00
    assert g.flags.loc[t5, "1"] == "OK"
    assert g.bikes.loc[T0 + timedelta(minutes=10), "1"] == 4


def test_slots_before_first_event_are_unknown():
    g = build_grid(frame([ev(10, "1", 5, 25), ev(0, "2", 3, 27), ev(10, "2", 3, 27)]))
    assert g.flags.loc[T0, "1"] == "UNKNOWN"
    assert g.flags.loc[T0, "2"] == "OK"


def test_global_feed_gap_over_30min_marks_everyone_unknown():
    g = build_grid(frame([ev(0, "1", 5, 25), ev(60, "1", 4, 26),
                          ev(0, "2", 3, 27), ev(60, "2", 2, 28)]))
    inside_grace = T0 + timedelta(minutes=25)
    assert g.flags.loc[inside_grace, "1"] == "OK"       # within 30-min grace
    outage = T0 + timedelta(minutes=45)
    assert g.flags.loc[outage, "1"] == "UNKNOWN"
    assert g.flags.loc[outage, "2"] == "UNKNOWN"
    assert g.flags.loc[T0 + timedelta(minutes=60), "1"] == "OK"  # recovers


def test_single_station_silence_stays_ok_until_staleness_cap():
    events = [ev(0, "1", 5, 25)]
    # station 2 keeps the network alive every 5 min for 25 hours
    events += [ev(m, "2", 3, 27) for m in range(0, 25 * 60 + 1, 5)]
    g = build_grid(frame(events))
    h23 = T0 + timedelta(hours=23)
    assert g.flags.loc[h23, "1"] == "OK"       # quiet but within 24 h cap
    h25 = T0 + timedelta(hours=25)
    assert g.flags.loc[h25, "1"] == "UNKNOWN"  # stale beyond cap
    assert g.flags.loc[h25, "2"] == "OK"


def test_not_renting_is_excluded_until_renting_returns():
    g = build_grid(frame([ev(0, "1", 5, 25, renting=False), ev(20, "1", 5, 25),
                          ev(0, "2", 3, 27), ev(20, "2", 3, 27)]))
    assert g.flags.loc[T0 + timedelta(minutes=10), "1"] == "EXCLUDED"
    assert g.flags.loc[T0 + timedelta(minutes=20), "1"] == "OK"
