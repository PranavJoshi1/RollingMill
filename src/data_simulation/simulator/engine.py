from datetime import datetime, timezone

from data_simulation.simulator.physical_simutation import (
    DEFAULT_DISTRIBUTION,
    LIVE_DEMO_DISTRIBUTION,
    MillStand,
)


class RollingMillSimulationEngine:
    def __init__(self, distribution: dict = None, *, demo_mode: bool = False):
        """Create both stands.

        ``demo_mode=True`` uses a high cobble rate and faster pass pacing for live
        demos. Historical generation should leave this False (default mix).
        """
        self.demo_mode = demo_mode
        if distribution is not None:
            dist = distribution
        elif demo_mode:
            dist = LIVE_DEMO_DISTRIBUTION
        else:
            dist = DEFAULT_DISTRIBUTION

        self.rs_01 = MillStand(
            "RS-01",
            {
                "motor_current": {"mean": 800.0, "std": 15.0},
                "motor_speed": {"mean": 40.0, "std": 0.5},
                "torque": {"mean": 4500.0, "std": 50.0},
                "vibration": {"mean": 3.0, "std": 0.2},
                "rolling_force": {"mean": 3500.0, "std": 40.0},
                "temperature": {"mean": 85.0, "std": 0.1},
            },
            distribution=dist,
            demo_pace=demo_mode,
        )

        self.fs_01 = MillStand(
            "FS-01",
            {
                "motor_current": {"mean": 350.0, "std": 5.0},
                "motor_speed": {"mean": 1200.0, "std": 8.0},
                "torque": {"mean": 900.0, "std": 12.0},
                "vibration": {"mean": 1.5, "std": 0.1},
                "rolling_force": {"mean": 1100.0, "std": 15.0},
                "temperature": {"mean": 60.0, "std": 0.1},
            },
            distribution=dist,
            demo_pace=demo_mode,
        )

    def get_tick(
        self,
        timestamp: str | None = None,
        *,
        include_labels: bool = False,
    ) -> list[dict]:
        """One 20ms tick from both stands. Pass timestamp for offline fast-forward."""
        if timestamp is None:
            timestamp = (
                datetime.now(timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            )

        readings = self.rs_01.generate_readings(
            timestamp, include_labels=include_labels
        ) + self.fs_01.generate_readings(timestamp, include_labels=include_labels)

        if include_labels:
            return [r.model_dump() for r in readings]
        return [r.model_dump(exclude_none=True) for r in readings]
