"""Chart helpers: downsample high-rate series for responsive UI."""

from __future__ import annotations

import numpy as np
import pandas as pd

SIGNAL_COLS = [
    "motor_current",
    "motor_speed",
    "torque",
    "vibration",
    "rolling_force",
    "temperature",
]

UNITS = {
    "motor_current": "A",
    "motor_speed": "RPM",
    "torque": "Nm",
    "vibration": "mm/s",
    "rolling_force": "kN",
    "temperature": "°C",
}


def downsample(df: pd.DataFrame, max_points: int = 1500) -> pd.DataFrame:
    """Keep at most max_points rows by uniform stride (preserves endpoints)."""
    n = len(df)
    if n <= max_points or max_points < 2:
        return df
    idx = np.linspace(0, n - 1, max_points, dtype=int)
    return df.iloc[np.unique(idx)].copy()


def summarize_signal(series: pd.Series) -> dict[str, float]:
    if series.empty:
        return {"mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0, "range": 0.0}
    return {
        "mean": float(series.mean()),
        "min": float(series.min()),
        "max": float(series.max()),
        "std": float(series.std(ddof=0)),
        "range": float(series.max() - series.min()),
    }
