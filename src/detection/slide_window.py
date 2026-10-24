"""Statistical sliding-window cobble precursor detection.

Offline fit (NORMAL LOAD) → online score (ring buffer of |z| means).
"""

from __future__ import annotations

from collections import deque
from typing import Any, Mapping

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from detection.common import (
    DEFAULT_NORMAL_QUANTILE,
    DEFAULT_SCORE_COLS,
    DEFAULT_TICK_S,
    DEFAULT_W,
    MillBaseline,
    TickResult,
    fit_normal_baselines,
    load_training_frame,
    prepare_labeled_frame,
)
from detection.fit_report import FitReport
from logging_setup import setup_logging

log = setup_logging("monoegde.detection.slide_window")


class SlidingWindowDetector(BaseModel):
    """Per-mill ring-buffer detector; call :meth:`update` on every live tick."""

    model_config = ConfigDict(validate_assignment=True)

    baselines: dict[str, MillBaseline]
    score_cols: tuple[str, ...] = DEFAULT_SCORE_COLS
    window: int = Field(default=DEFAULT_W, gt=0)
    threshold: float = Field(default=1.0, ge=0.0)
    tick_s: float = Field(default=DEFAULT_TICK_S, gt=0.0)
    active: bool = False

    _buffers: dict[str, deque[float]] = PrivateAttr(default_factory=dict)
    _latest: dict[str, TickResult] = PrivateAttr(default_factory=dict)

    @property
    def window_seconds(self) -> float:
        return self.window * self.tick_s

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def reset_buffers(self) -> None:
        self._buffers.clear()
        self._latest.clear()

    def latest(self, mill_id: str) -> TickResult | None:
        return self._latest.get(mill_id)

    def update(self, row: Mapping[str, Any]) -> TickResult | None:
        if not self.active:
            return None

        mill_id = str(row["mill_id"])
        baseline = self.baselines.get(mill_id)
        if baseline is None:
            return None

        zs: list[float] = []
        for col in self.score_cols:
            if col not in row:
                continue
            zs.append(abs((float(row[col]) - baseline.mu[col]) / baseline.sd[col]))
        if not zs:
            return None

        z_score = float(np.mean(zs))
        buf = self._buffers.setdefault(mill_id, deque(maxlen=self.window))
        buf.append(z_score)

        ready = len(buf) >= max(1, self.window // 2)
        window_score = float(np.mean(buf)) if ready else None
        flag = bool(window_score is not None and window_score > self.threshold)

        result = TickResult(
            mill_id=mill_id,
            z_score=z_score,
            window_score=window_score,
            flag=flag,
            ready=ready,
        )
        self._latest[mill_id] = result
        return result


def fit_sliding_window(
    df: pd.DataFrame,
    *,
    score_cols: tuple[str, ...] = DEFAULT_SCORE_COLS,
    window: int = DEFAULT_W,
    normal_quantile: float = DEFAULT_NORMAL_QUANTILE,
    tick_s: float = DEFAULT_TICK_S,
    source: str = "historical dataframe",
) -> tuple[SlidingWindowDetector, FitReport]:
    """Fit per-mill μ/σ and a NORMAL-LOAD threshold from labeled historical data."""
    log.info(
        "fit_sliding_window rows=%s window=%s q=%.3f",
        len(df),
        window,
        normal_quantile,
    )
    ts = prepare_labeled_frame(df, score_cols)
    baselines = fit_normal_baselines(ts, score_cols)

    z_parts: list[pd.Series] = []
    for mill_id, base in baselines.items():
        mill = ts[ts["mill_id"] == mill_id]
        z = pd.concat(
            [
                ((mill[c] - base.mu[c]) / base.sd[c]).abs().rename(c)
                for c in score_cols
            ],
            axis=1,
        ).mean(axis=1)
        z_parts.append(z)

    ts = ts.copy()
    ts["z_score"] = pd.concat(z_parts).sort_index()
    ts["window_score"] = ts.groupby("mill_id")["z_score"].transform(
        lambda s: s.rolling(window, min_periods=max(1, window // 2)).mean()
    )
    normal_scores = ts.loc[
        (ts["ground_truth_state"] == "LOAD") & (ts["pass_profile"] == "NORMAL"),
        "window_score",
    ].dropna()
    if normal_scores.empty:
        raise ValueError("could not compute NORMAL window scores for threshold")

    threshold = float(normal_scores.quantile(normal_quantile))
    det = SlidingWindowDetector(
        baselines=baselines,
        score_cols=score_cols,
        window=window,
        threshold=threshold,
        tick_s=tick_s,
    )

    precursor_scores = ts.loc[
        ts["ground_truth_state"] == "ANOMALY_PRECURSOR", "window_score"
    ].dropna()
    false_scores = ts.loc[
        (ts["ground_truth_state"] == "LOAD") & (ts["pass_profile"] == "FALSE_ISSUE"),
        "window_score",
    ].dropna()

    def _rate(s: pd.Series) -> float:
        if s.empty:
            return 0.0
        return float((s > threshold).mean() * 100.0)

    report = FitReport(
        algorithm="statistical_window",
        display_name="Statistical window (|z|)",
        source=source,
        hparams={
            "window": window,
            "normal_quantile": normal_quantile,
            "score_cols": list(score_cols),
        },
        threshold=threshold,
        metrics={
            "n_normal_score_rows": int(len(normal_scores)),
            "train_score_mean": round(float(normal_scores.mean()), 4),
            "train_score_p50": round(float(normal_scores.median()), 4),
            "train_score_p99": round(float(normal_scores.quantile(0.99)), 4),
            "train_flag_rate_pct": round(_rate(normal_scores), 2),
            "n_precursor_score_rows": int(len(precursor_scores)),
            "precursor_score_mean": round(
                float(precursor_scores.mean()) if len(precursor_scores) else 0.0, 4
            ),
            "precursor_flag_rate_pct": round(_rate(precursor_scores), 2),
            "n_false_issue_score_rows": int(len(false_scores)),
            "false_issue_score_mean": round(
                float(false_scores.mean()) if len(false_scores) else 0.0, 4
            ),
            "false_issue_flag_rate_pct": round(_rate(false_scores), 2),
            "n_mills": len(baselines),
        },
        notes=[
            f"Threshold = {normal_quantile:.3f} quantile of NORMAL LOAD window scores.",
            "Review precursor_flag_rate_pct (want high) vs false_issue_flag_rate_pct "
            "(want low) before starting the live demo.",
        ],
    )
    log.info(
        "fit_sliding_window done thr=%.4f n_mills=%s",
        threshold,
        len(baselines),
    )
    return det, report


def fit_sliding_window_from_db(**kwargs: Any) -> tuple[SlidingWindowDetector, FitReport]:
    kwargs.pop("source", None)
    log.info("fit_sliding_window_from_db kwargs=%s", kwargs)
    return fit_sliding_window(
        load_training_frame(), source="supabase:sensor_readings", **kwargs
    )
