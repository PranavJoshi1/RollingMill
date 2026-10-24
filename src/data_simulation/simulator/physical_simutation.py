import random

import numpy as np

from data_simulation.core.schemas import SensorReading

SIGNAL_MAPPING = {
    "motor_current": ("current", "A"),
    "motor_speed": ("speed", "RPM"),
    "torque": ("torque", "Nm"),
    "vibration": ("vib", "mm/s"),
    "rolling_force": ("force", "kN"),
}

# Historical / production mix (rare incidents).
DEFAULT_DISTRIBUTION = {
    "normal": 0.90,
    "false_issue": 0.05,
    "cobble": 0.05,
}
# Live UI demo: frequent cobbles so precursor detection is easy to show.
LIVE_DEMO_DISTRIBUTION = {
    "normal": 0.50,
    "false_issue": 0.20,
    "cobble": 0.30,
}


class MillStand:
    def __init__(
        self,
        mill_id: str,
        specs: dict,
        distribution: dict = None,
        *,
        demo_pace: bool = False,
    ):
        self.mill_id = mill_id
        self.specs = specs
        self.state = "IDLE"
        self.ticks_in_state = 0
        self.pass_duration = 0
        self.state_duration = 0
        self.drift = 1.0
        self.current_billet_hardness = 1.0
        self.pass_profile = "NORMAL"
        # Faster IDLE→pass and shorter LOAD before precursor (live demos only).
        self.demo_pace = demo_pace

        self.distribution = distribution or DEFAULT_DISTRIBUTION

    def determine_pass_fate(self):
        roll = random.random()
        if roll < self.distribution["cobble"]:
            self.pass_profile = "COBBLE"
            self.current_billet_hardness = random.uniform(0.9, 1.1)
        elif roll < (self.distribution["cobble"] + self.distribution["false_issue"]):
            self.pass_profile = "FALSE_ISSUE"
            self.current_billet_hardness = random.uniform(1.5, 1.8)
        else:
            self.pass_profile = "NORMAL"
            self.current_billet_hardness = random.uniform(0.9, 1.1)

    def get_baseline_multipliers(self):
        self.drift = max(0.92, min(1.08, self.drift + random.uniform(-0.0005, 0.0005)))

        if self.state == "IDLE":
            return {
                "current": random.uniform(0.08, 0.12) * self.drift,
                "speed": random.uniform(0.995, 1.005),
                "torque": random.uniform(0.08, 0.12) * self.drift,
                "vib": random.uniform(0.4, 0.6) * self.drift,
                "force": random.uniform(0.005, 0.015),
            }
        elif self.state == "ENTRY":
            h = self.current_billet_hardness
            return {
                "current": random.uniform(1.3, 1.7) * h,
                "speed": random.uniform(0.92, 0.97),
                "torque": random.uniform(1.5, 2.0) * h,
                "vib": random.uniform(2.0, 3.2) * h,
                "force": random.uniform(1.05, 1.2) * h,
            }
        elif self.state == "LOAD":
            var = random.uniform(0.97, 1.03) * self.current_billet_hardness
            return {
                "current": 1.0 * var * self.drift,
                "speed": random.uniform(0.998, 1.002),
                "torque": 1.0 * var * self.drift,
                "vib": random.uniform(0.9, 1.1) * self.drift,
                "force": 1.0 * var,
            }
        elif self.state == "EXIT":
            return {
                "current": random.uniform(0.15, 0.25),
                "speed": random.uniform(1.02, 1.07),
                "torque": random.uniform(0.15, 0.25),
                "vib": random.uniform(1.5, 2.2),
                "force": random.uniform(0.02, 0.08),
            }
        elif self.state == "ANOMALY_PRECURSOR":
            progress = min(self.ticks_in_state / 200.0, 1.0)
            jitter = random.uniform(0.8, 1.2)
            return {
                "current": 1.0 + (progress * 0.6 * jitter),
                "speed": 1.0 - (progress * 0.15 * jitter),
                "torque": 1.0 + (progress * 0.8 * jitter),
                "vib": 1.0 + (progress * 4.0 * jitter) + random.uniform(0, 1.5),
                "force": 1.0 + (progress * 0.3 * random.uniform(0.9, 1.4)),
            }
        elif self.state == "COBBLE":
            return {
                "current": random.uniform(2.2, 2.8),
                "speed": random.uniform(0.1, 0.3),
                "torque": random.uniform(2.5, 3.5),
                "vib": random.uniform(6.0, 10.0),
                "force": random.uniform(1.5, 2.5),
            }

        return {"current": 1.0, "speed": 1.0, "torque": 1.0, "vib": 1.0, "force": 1.0}

    def _enter_state(self, state: str, duration: int | None = None):
        self.state = state
        self.ticks_in_state = 0
        if duration is not None:
            self.state_duration = duration

    def update_state(self):
        self.ticks_in_state += 1

        # Demo: start passes ~8× more often so cobbles show up within ~1–2 min wall time.
        idle_start_p = 0.04 if self.demo_pace else 0.005

        if self.state == "IDLE" and random.random() < idle_start_p:
            self.determine_pass_fate()
            if self.demo_pace:
                self.pass_duration = random.randint(120, 220)
                entry_dur = random.randint(6, 10)
            else:
                self.pass_duration = random.randint(400, 800)
                entry_dur = random.randint(8, 12)
            self._enter_state("ENTRY", duration=entry_dur)

        elif self.state == "ENTRY" and self.ticks_in_state > self.state_duration:
            self._enter_state("LOAD")

        elif self.state == "LOAD":
            # Demo: enter precursor earlier and with a shorter ramp.
            cobble_frac = 0.15 if self.demo_pace else 0.3
            if (
                self.pass_profile == "COBBLE"
                and self.ticks_in_state > (self.pass_duration * cobble_frac)
            ):
                prec_dur = (
                    random.randint(80, 120)
                    if self.demo_pace
                    else random.randint(180, 220)
                )
                self._enter_state("ANOMALY_PRECURSOR", duration=prec_dur)
            elif self.ticks_in_state > self.pass_duration:
                self._enter_state("EXIT", duration=random.randint(12, 18))

        elif self.state == "EXIT" and self.ticks_in_state > self.state_duration:
            self._enter_state("IDLE")

        elif self.state == "ANOMALY_PRECURSOR" and self.ticks_in_state > self.state_duration:
            cobble_dur = 120 if self.demo_pace else 250
            self._enter_state("COBBLE", duration=cobble_dur)

        elif self.state == "COBBLE" and self.ticks_in_state > self.state_duration:
            self._enter_state("IDLE")

    def generate_readings(
        self, timestamp: str, *, include_labels: bool = False
    ) -> list[SensorReading]:
        """Advance one tick and sample all signals (shared by offline and online)."""
        self.update_state()
        mults = self.get_baseline_multipliers()
        readings: list[SensorReading] = []

        label_kwargs = {}
        if include_labels:
            label_kwargs = {
                "ground_truth_state": self.state,
                "pass_profile": self.pass_profile,
            }

        for sig, (m_key, unit) in SIGNAL_MAPPING.items():
            mean_val = self.specs[sig]["mean"] * mults[m_key]
            std_val = self.specs[sig]["std"] * max(1.0, mults[m_key] * 0.5)
            val = np.random.normal(mean_val, std_val)
            readings.append(
                SensorReading(
                    mill_id=self.mill_id,
                    signal=sig,
                    timestamp=timestamp,
                    value=round(float(val), 2),
                    unit=unit,
                    **label_kwargs,
                )
            )

        temp = np.random.normal(
            self.specs["temperature"]["mean"], self.specs["temperature"]["std"]
        )
        if self.state in ("ANOMALY_PRECURSOR", "COBBLE"):
            temp += self.ticks_in_state * 0.01

        readings.append(
            SensorReading(
                mill_id=self.mill_id,
                signal="temperature",
                timestamp=timestamp,
                value=round(float(temp), 2),
                unit="°C",
                **label_kwargs,
            )
        )
        return readings

