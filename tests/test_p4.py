import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from bikes.forecast import write_latest_json
from bikes.score import evaluate_gate, score_ledger, write_summary
from tests.test_score import NOW, setup_fixture

UTC = timezone.utc


def synth_ledger(tmp_path, p_model_fn, n_days=28):
    ledger = tmp_path / "ledger"
    (ledger / "forecasts").mkdir(parents=True)
    (ledger / "outcomes").mkdir(parents=True)
    for i in range(n_days):
        d = date(2026, 8, 1) + timedelta(days=i)
        target = datetime(d.year, d.month, d.day, 7, 30, tzinfo=UTC)
        frows, orows = [], []
        for sid in ("1", "2", "3", "4"):
            y = (int(sid) + i) % 2
            for event in ("bike", "dock"):
                key = {"target_ts_utc": target.isoformat(), "window": "morning",
                       "horizon": "long", "station_id": sid, "event": event}
                frows.append({"issued_at_utc": (target - timedelta(hours=16)).isoformat(),
                              **key, "p_model": p_model_fn(y), "p_clim": 0.5,
                              "p_pers": 0.5, "model_version": "v1"})
                orows.append({**key, "status": "SCORED", "y": y,
                              "obs_poll_ts": target.isoformat()})
        pd.DataFrame(frows).to_csv(ledger / "forecasts" / f"{d}.csv", index=False)
        pd.DataFrame(orows).to_csv(ledger / "outcomes" / f"{d}.csv", index=False)
    return ledger


def test_gate_pending_before_28_days(tmp_path):
    ledger, raw = setup_fixture(tmp_path)
    score_ledger(ledger, raw, NOW)
    evaluate_gate(ledger)
    gate = json.loads((ledger / "gate.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PENDING"
    assert gate["scored_days"] == 1 and gate["required_days"] == 28


def test_gate_pass_with_skill(tmp_path):
    ledger = synth_ledger(tmp_path, lambda y: 0.95 if y else 0.05)
    evaluate_gate(ledger)
    gate = json.loads((ledger / "gate.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS"
    for event in ("bike", "dock"):
        assert gate["detail"][event]["bss_vs_clim_ci"][0] > 0
        assert gate["detail"][event]["bss_vs_pers_ci"][0] > 0


def test_gate_not_proven_without_skill(tmp_path):
    ledger = synth_ledger(tmp_path, lambda y: 0.5)
    evaluate_gate(ledger)
    gate = json.loads((ledger / "gate.json").read_text(encoding="utf-8"))
    assert gate["status"] == "NOT_PROVEN"


def test_summary_includes_reliability_bins(tmp_path):
    ledger, raw = setup_fixture(tmp_path)
    score_ledger(ledger, raw, NOW)
    write_summary(ledger)
    s = json.loads((ledger / "summary.json").read_text(encoding="utf-8"))
    g = s["groups"][0]
    assert "reliability" in g and len(g["reliability"]) >= 1
    assert {"bin_mid", "p_mean", "y_rate", "count"} <= set(g["reliability"][0])


def test_latest_json_keeps_newest_issuance_per_key(tmp_path):
    ledger = tmp_path / "ledger"
    (ledger / "forecasts").mkdir(parents=True)
    target = datetime(2026, 7, 23, 7, 30, tzinfo=UTC)
    key = {"target_ts_utc": target.isoformat(), "window": "morning",
           "horizon": "long", "station_id": "42", "event": "bike"}
    rows = [
        {"issued_at_utc": "2026-07-22T15:05:00+00:00", **key, "p_model": 0.7,
         "p_clim": 0.9, "p_pers": 1.0, "model_version": "v1"},
        {"issued_at_utc": "2026-07-22T20:00:00+00:00", **{**key, "horizon": "short"},
         "p_model": 0.85, "p_clim": 0.9, "p_pers": 1.0, "model_version": "v1"},
    ]
    pd.DataFrame(rows).to_csv(ledger / "forecasts" / "2026-07-23.csv", index=False)
    stations = pd.DataFrame([{"station_id": "42", "name": "SMITHFIELD NORTH",
                              "lat": 53.35, "lon": -6.28, "capacity": 30}])
    write_latest_json(ledger, stations, now=datetime(2026, 7, 22, 21, 0, tzinfo=UTC))
    latest = json.loads((ledger / "latest.json").read_text(encoding="utf-8"))
    entries = [e for e in latest["forecasts"]
               if e["station_id"] == "42" and e["event"] == "bike"]
    assert len(entries) == 1
    assert entries[0]["p"] == 0.85           # newest issuance wins
    assert entries[0]["name"] == "SMITHFIELD NORTH"
