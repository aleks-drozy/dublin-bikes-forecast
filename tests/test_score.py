import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from bikes.score import score_ledger, write_summary

UTC = timezone.utc
TARGET = datetime(2026, 7, 22, 7, 30, tzinfo=UTC)
NOW = datetime(2026, 7, 22, 23, 45, tzinfo=UTC)


def setup_fixture(tmp_path, include_gap_station=True):
    ledger = tmp_path / "ledger"
    (ledger / "forecasts").mkdir(parents=True)
    raw = tmp_path / "raw"
    raw.mkdir()

    def frow(sid, event, p):
        return {"issued_at_utc": (TARGET - timedelta(minutes=90)).isoformat(),
                "window": "morning", "horizon": "short",
                "target_ts_utc": TARGET.isoformat(), "station_id": sid,
                "event": event, "p_model": p, "p_clim": 0.9, "p_pers": 1.0,
                "model_version": "v1"}

    rows = [frow("1", "bike", 0.8), frow("1", "dock", 0.95),
            frow("2", "bike", 0.7), frow("3", "bike", 0.6),
            # future target: must not be scored tonight
            {**frow("1", "bike", 0.5),
             "target_ts_utc": (NOW + timedelta(hours=9)).isoformat()}]
    pd.DataFrame(rows[:4]).to_csv(ledger / "forecasts" / "2026-07-22.csv",
                                  index=False)
    pd.DataFrame([rows[4]]).to_csv(ledger / "forecasts" / "2026-07-23.csv",
                                   index=False)

    def obs(sid, mins_after, bikes, renting=True):
        ts = TARGET + timedelta(minutes=mins_after)
        return {"station_id": sid, "num_bikes_available": bikes,
                "num_docks_available": 20 - bikes, "is_installed": True,
                "is_renting": renting, "is_returning": True,
                "last_reported": ts, "poll_ts": ts, "feed_last_updated": ts}

    observations = [obs("1", 3, 0),                 # eligible: 0 bikes, 20 docks
                    obs("3", 2, 5, renting=False)]  # eligible but not renting
    if include_gap_station:
        observations.append(obs("2", 25, 4))        # outside +/-10 min
    pd.DataFrame(observations).to_parquet(raw / "2026-07-22.parquet",
                                          index=False)
    return ledger, raw


def test_scoring_statuses_and_outcomes(tmp_path):
    ledger, raw = setup_fixture(tmp_path)
    counts = score_ledger(ledger, raw, NOW)
    assert counts == {"scored": 2, "gap": 1, "excluded": 1}
    out = pd.read_csv(ledger / "outcomes" / "2026-07-22.csv",
                      dtype={"station_id": str})
    s1bike = out[(out["station_id"] == "1") & (out["event"] == "bike")].iloc[0]
    assert s1bike["status"] == "SCORED" and s1bike["y"] == 0
    s1dock = out[(out["station_id"] == "1") & (out["event"] == "dock")].iloc[0]
    assert s1dock["y"] == 1
    assert out[out["station_id"] == "2"].iloc[0]["status"] == "UNSCOREABLE_GAP"
    assert out[out["station_id"] == "3"].iloc[0]["status"] == "EXCLUDED_STATION"
    assert not (ledger / "outcomes" / "2026-07-23.csv").exists()


def test_poisoned_nearest_poll_does_not_mask_a_clean_neighbour(tmp_path):
    # The eligibility rule has two clauses and only one is monotonic in
    # |poll_ts - target|: the tolerance clause. The future-clock clause
    # (last_reported > poll_ts + 5 min) can reject the NEAREST poll while a
    # slightly farther poll is perfectly eligible - and this feed's
    # per-station timestamps are exactly broken enough to produce that.
    # Breaking on the first ineligible observation therefore recorded a
    # false UNSCOREABLE_GAP that is indistinguishable in the public ledger
    # from an honest data gap. The scan must skip past clause-2 rejects and
    # stop only when the distance itself leaves the tolerance window.
    ledger, raw = setup_fixture(tmp_path, include_gap_station=False)

    def obs(sid, mins_after, bikes, last_reported=None):
        ts = TARGET + timedelta(minutes=mins_after)
        return {"station_id": sid, "num_bikes_available": bikes,
                "num_docks_available": 20 - bikes, "is_installed": True,
                "is_renting": True, "is_returning": True,
                "last_reported": last_reported or ts, "poll_ts": ts,
                "feed_last_updated": ts}

    poisoned = obs("2", 1, 7, last_reported=TARGET + timedelta(hours=1))
    clean = obs("2", 6, 7)
    existing = pd.read_parquet(raw / "2026-07-22.parquet")
    pd.concat([existing, pd.DataFrame([poisoned, clean])]).to_parquet(
        raw / "2026-07-22.parquet", index=False)

    score_ledger(ledger, raw, NOW)
    out = pd.read_csv(ledger / "outcomes" / "2026-07-22.csv",
                      dtype={"station_id": str})
    s2 = out[out["station_id"] == "2"].iloc[0]
    assert s2["status"] == "SCORED", (
        "a future-clocked nearest poll must not hide the eligible poll "
        "sitting 6 minutes from the target")
    assert s2["y"] == 1


def test_rescoring_is_a_noop(tmp_path):
    ledger, raw = setup_fixture(tmp_path)
    score_ledger(ledger, raw, NOW)
    counts2 = score_ledger(ledger, raw, NOW)
    assert counts2 == {"scored": 0, "gap": 0, "excluded": 0}
    out = pd.read_csv(ledger / "outcomes" / "2026-07-22.csv")
    assert len(out) == 4


def test_summary_math(tmp_path):
    ledger, raw = setup_fixture(tmp_path)
    score_ledger(ledger, raw, NOW)
    write_summary(ledger)
    s = json.loads((ledger / "summary.json").read_text(encoding="utf-8"))
    bike_short = next(g for g in s["groups"]
                      if g["event"] == "bike" and g["horizon"] == "short")
    # scored bike rows: station 1 only (p=0.8, y=0) -> brier 0.64
    assert abs(bike_short["brier_model"] - 0.64) < 1e-9
    assert s["status_counts"]["SCORED"] == 2
    assert s["scored_days"] == 1
