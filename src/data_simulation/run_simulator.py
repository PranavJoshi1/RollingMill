import asyncio
import time

from data_simulation.core.transform import pivot_readings_to_wide
from data_simulation.simulator.engine import RollingMillSimulationEngine


async def stream_data():
    """Live demo: emit long assignment payloads; pivot only for detection features."""
    engine = RollingMillSimulationEngine()
    tick_count = 0

    print("Starting High-Fidelity Signal Generator at 50Hz...")
    print("Wire schema: long {mill_id, signal, timestamp, value, unit}")
    print("Detection view: pivoted wide row per mill\n")

    while True:
        start_time = time.perf_counter()

        # 1) Assignment / API wire format (12 long payloads: 2 mills × 6 signals)
        payloads = engine.get_tick()

        # 2) Same tick, flat feature rows for cobble / ML inference
        feature_rows = pivot_readings_to_wide(payloads)

        if tick_count % 100 == 0:
            sample = feature_rows[0]
            print(
                f"[{payloads[0]['timestamp']}] "
                f"wire={len(payloads)} long msgs → {len(feature_rows)} wide rows | "
                f"RS-01 I={sample['motor_current']:.1f}A "
                f"States -> RS-01: {engine.rs_01.state}, FS-01: {engine.fs_01.state}"
            )

        tick_count += 1

        # Maintain strict 50Hz (20ms) interval
        elapsed = time.perf_counter() - start_time
        sleep_time = max(0, 0.02 - elapsed)
        await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    try:
        asyncio.run(stream_data())
    except KeyboardInterrupt:
        print("\nSimulation stopped.")
