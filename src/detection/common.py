"""Shared constants and helpers for detectors."""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from logging_setup import setup_logging

log = setup_logging("monoegde.detection")

DEFAULT_SCORE_COLS = (
    "vibration",
    "torque",
    "motor_current",
    "motor_speed",
    "rolling_force",
    "temperature",
)
DEFAULT_W = 200  # ticks @ 20 ms ≈ 4 s
DEFAULT_TICK_S = 0.02
DEFAULT_NORMAL_QUANTILE = 0.99


class MillBaseline(BaseModel):
    """Per-mill NORMAL LOAD mean/std for scoring columns."""

    model_config = ConfigDict(frozen=True)

    mu: dict[str, float] = Field(..., description="Per-signal mean on NORMAL LOAD")
    sd: dict[str, float] = Field(..., description="Per-signal std on NORMAL LOAD")


class TickResult(BaseModel):
    """Score for one mill after a live tick update."""

    mill_id: str
    z_score: float
    window_score: float | None = None
    flag: bool = False
    ready: bool = Field(
        default=False,
        description="True once the ring buffer has enough samples",
    )


def prepare_labeled_frame(
    df: pd.DataFrame, score_cols: tuple[str, ...]
) -> pd.DataFrame:
    """Validate columns, parse timestamps, sort by mill + time."""
    required = {"mill_id", "ground_truth_state", "pass_profile", *score_cols}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"historical data missing columns: {sorted(missing)}")

    ts = df.copy()
    if "timestamp" in ts.columns:
        ts["timestamp"] = pd.to_datetime(ts["timestamp"], utc=True)
        ts = ts.sort_values(["mill_id", "timestamp"]).reset_index(drop=True)
    return ts


def fit_normal_baselines(
    ts: pd.DataFrame, score_cols: tuple[str, ...]
) -> dict[str, MillBaseline]:
    """μ/σ per mill on NORMAL LOAD rows."""
    normal = ts[
        (ts["ground_truth_state"] == "LOAD") & (ts["pass_profile"] == "NORMAL")
    ]
    if normal.empty:
        raise ValueError("no NORMAL LOAD rows to fit baseline")

    mu = normal.groupby("mill_id")[list(score_cols)].mean()
    sd = normal.groupby("mill_id")[list(score_cols)].std().clip(lower=1e-6)
    baselines: dict[str, MillBaseline] = {}
    for mill_id in mu.index:
        baselines[str(mill_id)] = MillBaseline(
            mu={c: float(mu.loc[mill_id, c]) for c in score_cols},
            sd={c: float(sd.loc[mill_id, c]) for c in score_cols},
        )
    return baselines


def load_training_frame() -> pd.DataFrame:
    """Full sensor_readings table for offline fit."""
    from db import read_readings

    log.info("Loading full training frame from Supabase")
    df = read_readings()
    if df.empty:
        log.error("sensor_readings is empty — cannot fit")
        raise ValueError(
            "No rows in sensor_readings. Run: "
            "uv run python -m data_simulation.generate_historical_data --hours 2"
        )
    log.info("Training frame ready rows=%s mills=%s", len(df), df["mill_id"].nunique())
    return df
