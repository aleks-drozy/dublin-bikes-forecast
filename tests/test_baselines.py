from datetime import date

import pandas as pd
import pytest

from bikes.baselines import Climatology, persistence


def train_rows():
    return pd.DataFrame([
        # station 1, morning, bike: 2 of 3 true -> (2+1)/(3+2) = 0.6
        {"date": date(2026, 1, 5), "window": "morning", "station_id": "1",
         "event": "bike", "day_type": 0, "y": True},
        {"date": date(2026, 1, 6), "window": "morning", "station_id": "1",
         "event": "bike", "day_type": 0, "y": True},
        {"date": date(2026, 1, 7), "window": "morning", "station_id": "1",
         "event": "bike", "day_type": 0, "y": False},
        # a different station contributes to the window-level fallback
        {"date": date(2026, 1, 5), "window": "morning", "station_id": "2",
         "event": "bike", "day_type": 0, "y": False},
    ])


def test_climatology_laplace_smoothing():
    clim = Climatology().fit(train_rows())
    q = pd.DataFrame([{"window": "morning", "station_id": "1",
                       "event": "bike", "day_type": 0}])
    assert clim.predict(q)[0] == pytest.approx(0.6)


def test_climatology_falls_back_for_unseen_station():
    clim = Climatology().fit(train_rows())
    q = pd.DataFrame([{"window": "morning", "station_id": "99",
                       "event": "bike", "day_type": 0}])
    # window-level pool: 2 of 4 true -> (2+1)/(4+2) = 0.5
    assert clim.predict(q)[0] == pytest.approx(0.5)


def test_persistence_maps_issuance_state_to_hard_probability():
    rows = pd.DataFrame([
        {"event": "bike", "bikes": 3.0, "docks": 0.0},
        {"event": "bike", "bikes": 0.0, "docks": 20.0},
        {"event": "dock", "bikes": 3.0, "docks": 0.0},
        {"event": "dock", "bikes": 0.0, "docks": 20.0},
    ])
    assert list(persistence(rows)) == [1.0, 0.0, 0.0, 1.0]
