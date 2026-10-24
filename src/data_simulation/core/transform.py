"""Long wire payload ↔ wide feature row (CSV / ML / cobble detection)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

# Column order for wide CSV / feature vectors
WIDE_SIGNAL_COLS = [
    "motor_current",
    "motor_speed",
    "torque",
    "vibration",
    "rolling_force",
    "temperature",
]

def pivot_readings_to_wide(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pivot assignment long payloads into one wide row per (mill_id, timestamp).

    Input (wire / assignment schema), many rows::
        {mill_id, signal, timestamp, value, unit, ...}

    Output (ML / detection / wide CSV), one row per mill per tick::
        {mill_id, timestamp, motor_current, motor_speed, ..., labels?}
    """
    groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)

    for r in readings:
        key = (r["mill_id"], r["timestamp"])
        row = groups[key]
        if not row:
            row["mill_id"] = r["mill_id"]
            row["timestamp"] = r["timestamp"]
            if r.get("ground_truth_state") is not None:
                row["ground_truth_state"] = r["ground_truth_state"]
            if r.get("pass_profile") is not None:
                row["pass_profile"] = r["pass_profile"]
        row[r["signal"]] = r["value"]

    # Stable order: RS/FS as they appear in the tick list
    return list(groups.values())
