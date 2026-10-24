"""Isolation Forest cobble-precursor detector.

Offline: fit on NORMAL LOAD window features from historical data.
Online: ring-buffer features → anomaly score → flag.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Mapping

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from sklearn.ensemble import IsolationForest

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

log = setup_logging("monoegde.detection.iforest")
_TRAIN_STRIDE = 50


def _window_features_by_mask(
    ts: pd.DataFrame,
    baselines: dict[str, MillBaseline],
    score_cols: tuple[str, ...],
    window: int,
    mask_col: str,
) -> np.ndarray:
    """Mean |z| per signal over windows whose end tick has ``mask_col`` True."""
    features: list[np.ndarray] = []
    min_periods = max(1, window // 2)
    for mill_id, mill in ts.groupby("mill_id", sort=False):
        base = baselines.get(str(mill_id))
        if base is None:
            continue
        mill = mill.reset_index(drop=True)
        mask = mill[mask_col].to_numpy()
        z = np.column_stack(
            [
                ((mill[c] - base.mu[c]) / base.sd[c]).abs().to_numpy(dtype=np.float64)
                for c in score_cols
            ]
        )
        for end in range(min_periods - 1, len(mill), _TRAIN_STRIDE):
            if not mask[end]:
                continue
            start = max(0, end - window + 1)
            features.append(z[start : end + 1].mean(axis=0))
    if not features:
        return np.empty((0, len(score_cols)), dtype=np.float64)
    return np.vstack(features)


def _score_rate(
    model: IsolationForest, X: np.ndarray, threshold: float
) -> tuple[float, float, int]:
    if len(X) == 0:
        return 0.0, 0.0, 0
    scores = -model.decision_function(X)
    return float(scores.mean()), float(np.mean(scores > threshold)), int(len(X))


class IsolationForestDetector(BaseModel):
    """Per-mill ring buffer + sklearn IsolationForest."""

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)

    baselines: dict[str, MillBaseline]
    score_cols: tuple[str, ...] = DEFAULT_SCORE_COLS
    window: int = Field(default=DEFAULT_W, gt=0)
    threshold: float = 0.0
    tick_s: float = Field(default=DEFAULT_TICK_S, gt=0.0)
    n_estimators: int = 100
    contamination: float = 0.02
    active: bool = False

    _model: IsolationForest | None = PrivateAttr(default=None)
    _buffers: dict[str, deque[np.ndarray]] = PrivateAttr(default_factory=dict)
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
        if not self.active or self._model is None:
            return None

        mill_id = str(row["mill_id"])
        baseline = self.baselines.get(mill_id)
        if baseline is None:
            return None

        zs: list[float] = []
        for col in self.score_cols:
            if col not in row:
                return None
            zs.append(abs((float(row[col]) - baseline.mu[col]) / baseline.sd[col]))

        z_vec = np.asarray(zs, dtype=np.float64)
        z_score = float(z_vec.mean())
        buf = self._buffers.setdefault(mill_id, deque(maxlen=self.window))
        buf.append(z_vec)

        ready = len(buf) >= max(1, self.window // 2)
        window_score: float | None = None
        flag = False
        if ready:
            feat = np.stack(list(buf), axis=0).mean(axis=0)
            window_score = float(-self._model.decision_function(feat.reshape(1, -1))[0])
            flag = window_score > self.threshold

        result = TickResult(
            mill_id=mill_id,
            z_score=z_score,
            window_score=window_score,
            flag=flag,
            ready=ready,
        )
        self._latest[mill_id] = result
        return result


def fit_isolation_forest(
    df: pd.DataFrame,
    *,
    window: int = DEFAULT_W,
    n_estimators: int = 100,
    contamination: float = 0.02,
    normal_quantile: float = DEFAULT_NORMAL_QUANTILE,
    score_cols: tuple[str, ...] = DEFAULT_SCORE_COLS,
    tick_s: float = DEFAULT_TICK_S,
    random_state: int = 42,
    source: str = "historical dataframe",
) -> tuple[IsolationForestDetector, FitReport]:
    """Fit baselines + IsolationForest; return detector and training report."""
    log.info(
        "fit_isolation_forest rows=%s window=%s trees=%s",
        len(df),
        window,
        n_estimators,
    )
    ts = prepare_labeled_frame(df, score_cols)
    baselines = fit_normal_baselines(ts, score_cols)

    ts = ts.copy()
    ts["_m_normal"] = (ts["ground_truth_state"] == "LOAD") & (
        ts["pass_profile"] == "NORMAL"
    )
    ts["_m_precursor"] = ts["ground_truth_state"] == "ANOMALY_PRECURSOR"
    ts["_m_false"] = (ts["ground_truth_state"] == "LOAD") & (
        ts["pass_profile"] == "FALSE_ISSUE"
    )

    X = _window_features_by_mask(ts, baselines, score_cols, window, "_m_normal")
    if len(X) == 0:
        raise ValueError("no NORMAL LOAD windows to train Isolation Forest")
    log.info("Training IsolationForest on %s NORMAL windows", len(X))

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X)

    scores = -model.decision_function(X)
    threshold = float(np.quantile(scores, normal_quantile))

    X_prec = _window_features_by_mask(ts, baselines, score_cols, window, "_m_precursor")
    X_false = _window_features_by_mask(ts, baselines, score_cols, window, "_m_false")
    train_mean, train_flag_rate, n_train = _score_rate(model, X, threshold)
    prec_mean, prec_flag_rate, n_prec = _score_rate(model, X_prec, threshold)
    false_mean, false_flag_rate, n_false = _score_rate(model, X_false, threshold)

    det = IsolationForestDetector(
        baselines=baselines,
        score_cols=score_cols,
        window=window,
        threshold=threshold,
        tick_s=tick_s,
        n_estimators=n_estimators,
        contamination=contamination,
    )
    det._model = model

    report = FitReport(
        algorithm="isolation_forest",
        display_name="Isolation Forest",
        source=source,
        hparams={
            "window": window,
            "n_estimators": n_estimators,
            "contamination": contamination,
            "normal_quantile": normal_quantile,
            "score_cols": list(score_cols),
        },
        threshold=threshold,
        metrics={
            "n_train_windows_normal": n_train,
            "train_score_mean": round(train_mean, 4),
            "train_score_p50": round(float(np.median(scores)), 4),
            "train_score_p99": round(float(np.quantile(scores, 0.99)), 4),
            "train_flag_rate_pct": round(100.0 * train_flag_rate, 2),
            "n_precursor_windows": n_prec,
            "precursor_score_mean": round(prec_mean, 4),
            "precursor_flag_rate_pct": round(100.0 * prec_flag_rate, 2),
            "n_false_issue_windows": n_false,
            "false_issue_score_mean": round(false_mean, 4),
            "false_issue_flag_rate_pct": round(100.0 * false_flag_rate, 2),
            "n_mills": len(baselines),
        },
        notes=[
            f"Trained only on NORMAL LOAD windows (stride={_TRAIN_STRIDE}).",
            f"Threshold = {normal_quantile:.3f} quantile of NORMAL training scores "
            f"(higher score = more anomalous).",
            "Review precursor_flag_rate_pct (want high) vs false_issue_flag_rate_pct "
            "(want low) before starting the live demo.",
        ],
    )
    log.info(
        "fit_isolation_forest done thr=%.4f train_n=%s prec_n=%s",
        threshold,
        n_train,
        n_prec,
    )
    return det, report


def fit_isolation_forest_from_db(**kwargs: Any) -> tuple[IsolationForestDetector, FitReport]:
    kwargs.pop("source", None)
    log.info("fit_isolation_forest_from_db kwargs=%s", kwargs)
    return fit_isolation_forest(
        load_training_frame(), source="supabase:sensor_readings", **kwargs
    )
