"""Structured result of an offline fit (shown in Live before starting the stream)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FitReport(BaseModel):
    """Human-readable summary after fitting on historical data."""

    algorithm: str
    display_name: str
    source: str = Field(description="Path or description of training data")
    hparams: dict[str, Any] = Field(default_factory=dict)
    threshold: float
    metrics: dict[str, float | int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
