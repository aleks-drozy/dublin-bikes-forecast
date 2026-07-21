"""Nightly scoring: matured ledger rows -> outcomes via the eligibility rule."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pandas as pd

from bikes.backtest import brier, bss
from scoring.eligibility import TOLERANCE, eligible_observation

KEY = ["target_ts_utc", "window", "horizon", "station_id", "event"]


def _load_raw_days(raw_dir: Path, dates) -> pd.DataFrame:
    frames = []
    for d in sorted(set(dates)):
        for offset in (-1, 0, 1):
            path = raw_dir / f"{(d + timedelta(days=offset)).isoformat()}.parquet"
            if path.exists():
                frames.append(pd.read_parquet(path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["station_id", "poll_ts"])


def score_ledger(ledger_dir: Path, raw_dir: Path, now) -> dict:
    forecasts_dir = ledger_dir / "forecasts"
    outcomes_dir = ledger_dir / "outcomes"
    counts = {"scored": 0, "gap": 0, "excluded": 0}
    for fpath in sorted(forecasts_dir.glob("*.csv")):
        fc = pd.read_csv(fpath, dtype={"station_id": str})
        fc["target_ts"] = pd.to_datetime(fc["target_ts_utc"])
        matured = fc[fc["target_ts"] + TOLERANCE < now]
        if matured.empty:
            continue
        opath = outcomes_dir / fpath.name
        done: set = set()
        existing = None
        if opath.exists():
            existing = pd.read_csv(opath, dtype={"station_id": str})
            done = set(map(tuple, existing[KEY].values))
        todo = matured[[tuple(r) not in done for r in matured[KEY].values]]
        if todo.empty:
            continue
        raw = _load_raw_days(raw_dir, todo["target_ts"].dt.date.unique())
        new_rows = []
        for _, r in todo.iterrows():
            obs = raw[raw["station_id"].astype(str) == r["station_id"]] \
                if not raw.empty else raw
            status, y, obs_ts = "UNSCOREABLE_GAP", "", ""
            if not obs.empty:
                obs = obs.assign(dist=(obs["poll_ts"] - r["target_ts"]).abs())
                obs = obs.sort_values("dist")
                for _, o in obs.iterrows():
                    if not eligible_observation(r["target_ts"], o["poll_ts"],
                                                o["last_reported"]):
                        break  # sorted by distance: first ineligible ends it
                    if not (o["is_installed"] and o["is_renting"]):
                        status = "EXCLUDED_STATION"
                    else:
                        status = "SCORED"
                        val = o["num_bikes_available"] if r["event"] == "bike" \
                            else o["num_docks_available"]
                        y = int(val >= 1)
                        obs_ts = o["poll_ts"].isoformat()
                    break
            counts["scored" if status == "SCORED" else
                   "excluded" if status == "EXCLUDED_STATION" else "gap"] += 1
            new_rows.append({**{k: r[k] for k in KEY}, "status": status,
                             "y": y, "obs_poll_ts": obs_ts})
        outcomes_dir.mkdir(parents=True, exist_ok=True)
        out = pd.DataFrame(new_rows)
        if existing is not None:
            out = pd.concat([existing, out], ignore_index=True)
        out.to_csv(opath, index=False)
    return counts


def write_summary(ledger_dir: Path) -> None:
    forecasts = pd.concat([pd.read_csv(p, dtype={"station_id": str})
                           for p in (ledger_dir / "forecasts").glob("*.csv")],
                          ignore_index=True)
    outcome_files = list((ledger_dir / "outcomes").glob("*.csv"))
    if not outcome_files:
        return
    outcomes = pd.concat([pd.read_csv(p, dtype={"station_id": str})
                          for p in outcome_files], ignore_index=True)
    merged = forecasts.merge(outcomes, on=KEY, how="inner")
    scored = merged[merged["status"] == "SCORED"].copy()
    groups = []
    for (event, horizon), g in scored.groupby(["event", "horizon"]):
        y = g["y"].astype(float).values
        groups.append({
            "event": event, "horizon": horizon, "n": int(len(g)),
            "base_rate": float(y.mean()),
            "brier_model": brier(g["p_model"].values, y),
            "brier_clim": brier(g["p_clim"].values, y),
            "brier_pers": brier(g["p_pers"].values, y),
            "bss_vs_clim": bss(g["p_model"].values, y, g["p_clim"].values),
            "bss_vs_pers": bss(g["p_model"].values, y, g["p_pers"].values),
        })
    summary = {
        "groups": groups,
        "status_counts": outcomes["status"].value_counts().to_dict(),
        "scored_days": int(scored["target_ts_utc"].str[:10].nunique()),
        "gate": "28 scored days; long-horizon BSS>0 vs both baselines, "
                "day-clustered bootstrap 95% CI excluding 0 (pre-registered)",
    }
    (ledger_dir / "summary.json").write_text(json.dumps(summary, indent=1),
                                             encoding="utf-8")
