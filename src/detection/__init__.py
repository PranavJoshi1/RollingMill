"""Detection algorithms: statistical window + Isolation Forest."""

from detection.common import (
    DEFAULT_NORMAL_QUANTILE,
    DEFAULT_SCORE_COLS,
    DEFAULT_TICK_S,
    DEFAULT_W,
    MillBaseline,
    TickResult,
)
from detection.fit_report import FitReport
from detection.isolation_forest import (
    IsolationForestDetector,
    fit_isolation_forest,
    fit_isolation_forest_from_db,
)
from detection.slide_window import (
    SlidingWindowDetector,
    fit_sliding_window,
    fit_sliding_window_from_db,
)

__all__ = [
    "DEFAULT_NORMAL_QUANTILE",
    "DEFAULT_SCORE_COLS",
    "DEFAULT_TICK_S",
    "DEFAULT_W",
    "FitReport",
    "IsolationForestDetector",
    "MillBaseline",
    "SlidingWindowDetector",
    "TickResult",
    "fit_isolation_forest",
    "fit_isolation_forest_from_db",
    "fit_sliding_window",
    "fit_sliding_window_from_db",
]
