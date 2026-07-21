"""Live issuance: frozen model -> before-the-fact ledger rows.

Security note: FrozenModel.load reads joblib files from THIS repo only —
repo write access is already code execution here (cron runs repo scripts),
so the pickle adds no new surface. See scripts/freeze_model.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from bikes.features import _day_type
from bikes.live import latest_state
from bikes.windows import DUBLIN, window_instants

LEDGER_KEY = ["target_ts_utc", "window", "horizon", "station_id", "event"]


@dataclass
class FrozenModel:
    bike: object
    dock: object
    climatology: dict
    manifest: dict

    @classmethod
    def load(cls, models_dir: Path) -> "FrozenModel":
        import joblib  # deferred: poller-only VM paths never import sklearn
        return cls(
            bike=joblib.load(models_dir / "bike.joblib"),
            dock=joblib.load(models_dir / "dock.joblib"),
            climatology=json.loads((models_dir / "climatology.json")
                                   .read_text(encoding="utf-8")),
            manifest=json.loads((models_dir / "manifest.json")
                                .read_text(encoding="utf-8")),
        )

    def clim_p(self, station_id: str, window: str, event: str,
               day_type: int) -> float:
        full_key = f"{station_id}|{window}|{event}|{day_type}"
        pool_key = f"{window}|{event}|{day_type}"
        return self.climatology["full"].get(
            full_key, self.climatology["pool"].get(
                pool_key, self.climatology["global"]))


def issuance_sets(now: datetime) -> list[tuple[str, str, date]]:
    local = now.astimezone(DUBLIN)
    today = local.date()
    if local.hour == 7:
        return [("morning", "short", today), ("evening", "long", today)]
    if local.hour == 16:
        return [("evening", "short", today),
                ("morning", "long", today + timedelta(days=1))]
    return []


def build_issuance_rows(raw_dir: Path, capacity: pd.Series, weather_fetcher,
                        now: datetime,
                        sets: list[tuple[str, str, date]]) -> tuple[pd.DataFrame, int]:
    state = latest_state(raw_dir, now)
    if state.empty:
        return pd.DataFrame(), int(len(capacity)) * len(sets)
    state = state.set_index("station_id")
    back30 = latest_state(raw_dir, now - timedelta(minutes=30)).set_index("station_id")
    back60 = latest_state(raw_dir, now - timedelta(minutes=60)).set_index("station_id")
    weather = weather_fetcher().set_index("ts")

    rows, unissued = [], 0
    for window, horizon, target_date in sets:
        _, target = window_instants(target_date)[window]
        target_local = target.astimezone(DUBLIN)
        how = target_local.weekday() * 24 + target_local.hour
        wx_ts = target.replace(minute=0, second=0, microsecond=0)
        wx = weather.loc[wx_ts] if wx_ts in weather.index else None
        for sid in capacity.index.astype(str):
            if sid not in state.index or not state.at[sid, "is_renting"]:
                unissued += 1
                continue
            bikes = float(state.at[sid, "bikes"])
            docks = float(state.at[sid, "docks"])
            cap = float(capacity.get(sid, float("nan")))
            d30 = bikes - float(back30.at[sid, "bikes"]) if sid in back30.index else float("nan")
            d60 = bikes - float(back60.at[sid, "bikes"]) if sid in back60.index else float("nan")
            rows.append({
                "window": window, "horizon": horizon, "target_ts": target,
                "station_id": sid, "bikes": bikes, "docks": docks,
                "fill": bikes / cap if cap == cap and cap else float("nan"),
                "d30": d30, "d60": d60, "capacity": cap, "how": how,
                "day_type": _day_type(target_date),
                "temp": float(wx["temp"]) if wx is not None else float("nan"),
                "precip": float(wx["precip"]) if wx is not None else float("nan"),
                "wind": float(wx["wind"]) if wx is not None else float("nan"),
                "horizon_min": int((target - now).total_seconds() // 60),
            })
    return pd.DataFrame(rows), unissued


def append_ledger(rows: pd.DataFrame, ledger_dir: Path) -> tuple[int, int]:
    out_dir = ledger_dir / "forecasts"
    out_dir.mkdir(parents=True, exist_ok=True)
    added = skipped = 0
    rows = rows.copy()
    rows["target_date"] = rows["target_ts_utc"].str[:10]
    for target_date, g in rows.groupby("target_date"):
        path = out_dir / f"{target_date}.csv"
        g = g.drop(columns=["target_date"])
        if path.exists():
            existing = pd.read_csv(path, dtype={"station_id": str})
            have = set(map(tuple, existing[LEDGER_KEY].values))
            mask = [tuple(r) not in have for r in g[LEDGER_KEY].values]
            skipped += int(len(g) - sum(mask))
            g = g[pd.Series(mask, index=g.index)]
            if g.empty:
                continue
            combined = pd.concat([existing, g], ignore_index=True)
        else:
            combined = g
        combined.to_csv(path, index=False)
        added += len(g)
    return added, skipped


def run_issuance(model: FrozenModel, raw_dir: Path, capacity: pd.Series,
                 weather_fetcher, ledger_dir: Path, now: datetime,
                 force_sets: list | None = None) -> int:
    sets = force_sets if force_sets is not None else issuance_sets(now)
    if not sets:
        return 0
    feats, unissued = build_issuance_rows(raw_dir, capacity, weather_fetcher,
                                          now, sets)
    if feats.empty:
        print(f"no issuable rows (unissued={unissued})")
        return 0
    x = feats[self_features(model)].copy()
    x["station_id"] = pd.Categorical(feats["station_id"],
                                     categories=model.manifest["stations"])
    ledger_rows = []
    for event, predictor in (("bike", model.bike), ("dock", model.dock)):
        proba = predictor.predict_proba(x)
        p = proba[:, list(predictor.classes_).index(True)]
        state = feats["bikes"] if event == "bike" else feats["docks"]
        pers = np.where(state >= 1, 1.0, 0.0)
        for i, (_, r) in enumerate(feats.iterrows()):
            ledger_rows.append({
                "issued_at_utc": now.isoformat(), "window": r["window"],
                "horizon": r["horizon"],
                "target_ts_utc": r["target_ts"].isoformat(),
                "station_id": r["station_id"], "event": event,
                "p_model": round(float(p[i]), 4),
                "p_clim": round(model.clim_p(r["station_id"], r["window"],
                                             event, int(r["day_type"])), 4),
                "p_pers": float(pers[i]),
                "model_version": model.manifest["version"],
            })
    added, skipped = append_ledger(pd.DataFrame(ledger_rows), ledger_dir)
    print(f"issued {added} rows ({skipped} already present, "
          f"{unissued} stations unissued)")
    return added


def self_features(model: FrozenModel) -> list[str]:
    return [c for c in model.manifest["features"] if c != "station_id"]
