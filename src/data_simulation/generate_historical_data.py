"""Offline: generate simulated mill data and save to Supabase.

  uv run python -m data_simulation.generate_historical_data --hours 2
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone

from data_simulation.core.transform import pivot_readings_to_wide
from data_simulation.simulator.engine import RollingMillSimulationEngine
from db import clear_readings, connect, count_readings, insert_readings
from logging_setup import setup_logging

log = setup_logging("monoegde.generate")


def generate_historical_dataset(hours: float = 2, batch_size: int = 5_000) -> None:
    ticks_per_second = 50
    total_ticks = int(hours * 3600 * ticks_per_second)
    expected_rows = total_ticks * 2  # RS-01 + FS-01

    log.info(
        "Generate start hours=%s ticks=%s expected_rows=%s",
        hours,
        total_ticks,
        expected_rows,
    )
    print(f"Generating {hours} simulated hour(s) → Supabase sensor_readings")
    print(f"Ticks: {total_ticks:,}  |  wide rows: {expected_rows:,}")
    print("Clearing existing sensor_readings…")
    clear_readings()

    engine = RollingMillSimulationEngine(
        distribution={
            "normal": 0.90,
            "false_issue": 0.05,
            "cobble": 0.05,
        }
    )
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    batch: list[dict] = []
    written = 0
    start_real = time.perf_counter()
    report_every = max(total_ticks // 10, 1)

    with connect() as conn:
        for tick in range(total_ticks):
            sim_time = start_time + timedelta(seconds=tick / ticks_per_second)
            iso_time = sim_time.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            )
            wide_rows = pivot_readings_to_wide(
                engine.get_tick(iso_time, include_labels=True)
            )
            batch.extend(wide_rows)

            if len(batch) >= batch_size:
                insert_readings(batch, conn=conn)
                conn.commit()
                written += len(batch)
                batch.clear()

            if tick > 0 and tick % report_every == 0:
                elapsed = time.perf_counter() - start_real
                pct = (tick / total_ticks) * 100
                msg = (
                    f"Progress: {pct:.0f}%  rows={written + len(batch):,}  "
                    f"({elapsed:.1f}s elapsed)"
                )
                print(msg)
                log.info(msg)

        if batch:
            insert_readings(batch, conn=conn)
            conn.commit()
            written += len(batch)

    elapsed = time.perf_counter() - start_real
    in_db = count_readings()
    print(f"\nDone in {elapsed:.1f}s. Wrote {written:,} rows.")
    print(f"Rows in sensor_readings: {in_db:,}")
    log.info("Generate done written=%s in_db=%s elapsed_s=%.1f", written, in_db, elapsed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mill data → Supabase")
    parser.add_argument(
        "--hours",
        type=float,
        default=2,
        help="Simulated hours of data (default: 2)",
    )
    args = parser.parse_args()
    generate_historical_dataset(hours=args.hours)
