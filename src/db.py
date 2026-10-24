"""Simple Supabase Postgres helpers: connect, insert, read."""

from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import psycopg
from dotenv import load_dotenv

from logging_setup import setup_logging

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
log = setup_logging("monoegde.db")

COLS = (
    "mill_id",
    "timestamp",
    "motor_current",
    "motor_speed",
    "torque",
    "vibration",
    "rolling_force",
    "temperature",
    "ground_truth_state",
    "pass_profile",
)


def connect():
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        log.error("DATABASE_URL is not set")
        raise RuntimeError("DATABASE_URL is not set")
    url = raw.strip().strip("'\"")
    # psycopg wants postgresql:// (not sqlalchemy's postgresql+psycopg://)
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    host = urlparse(url).hostname or "?"
    try:
        conn = psycopg.connect(url, sslmode="require")
        log.debug("Connected to Postgres host=%s", host)
        return conn
    except Exception:
        log.exception("Failed to connect to Postgres host=%s", host)
        raise


def clear_readings() -> None:
    """Delete all sensor rows (for a fresh offline generate)."""
    log.info("Truncating sensor_readings")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE sensor_readings RESTART IDENTITY")
        conn.commit()


def insert_readings(rows: list[dict], conn=None) -> int:
    """Insert wide sensor rows. Returns how many were written.

    Pass an open ``conn`` to reuse one connection across many batches.
    """
    if not rows:
        return 0
    own = conn is None
    if own:
        conn = connect()
    try:
        cols = ", ".join(COLS)
        with conn.cursor() as cur:
            with cur.copy(f"COPY sensor_readings ({cols}) FROM STDIN") as copy:
                for r in rows:
                    copy.write_row(tuple(r.get(c) for c in COLS))
        if own:
            conn.commit()
    except Exception:
        log.exception("insert_readings failed (n=%s)", len(rows))
        raise
    finally:
        if own:
            conn.close()
    log.debug("Inserted %s sensor rows", len(rows))
    return len(rows)


def count_readings(mill_id: str | None = None) -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            if mill_id:
                cur.execute(
                    "SELECT COUNT(*) FROM sensor_readings WHERE mill_id = %s",
                    (mill_id,),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM sensor_readings")
            return int(cur.fetchone()[0])


def list_mills() -> list[str]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT mill_id FROM sensor_readings ORDER BY mill_id"
            )
            return [r[0] for r in cur.fetchall()]


def read_readings(
    mill_id: str | None = None,
    limit: int | None = None,
    stride: int = 1,
) -> pd.DataFrame:
    """Read sensor rows as a DataFrame (same columns as the CSV).

    ``stride`` > 1 keeps every Nth row across the full time range (fast sample).
    """
    stride = max(1, int(stride))
    cols = ", ".join(COLS)
    params: list = []
    where = ""
    if mill_id:
        where = "WHERE mill_id = %s"
        params.append(mill_id)

    if stride == 1:
        sql = f"SELECT {cols} FROM sensor_readings {where} ORDER BY timestamp"
    else:
        # Sample evenly across time so cobble / false-issue episodes still appear.
        sql = f"""
            SELECT {cols} FROM (
              SELECT {cols},
                     ROW_NUMBER() OVER (ORDER BY timestamp) AS rn
              FROM sensor_readings
              {where}
            ) t
            WHERE MOD(rn, %s) = 1
            ORDER BY timestamp
        """
        params.append(stride)

    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))

    log.debug(
        "read_readings mill_id=%s stride=%s limit=%s", mill_id, stride, limit
    )
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or None)
                rows = cur.fetchall()
    except Exception:
        log.exception(
            "read_readings failed mill_id=%s stride=%s", mill_id, stride
        )
        raise
    df = pd.DataFrame(rows, columns=list(COLS))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    log.info(
        "read_readings ok rows=%s mill_id=%s stride=%s",
        len(df),
        mill_id,
        stride,
    )
    return df


def insert_user(username: str, salt: str, password_hash: str) -> None:
    log.info("Creating user username=%s", username)
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, salt, password_hash) "
                    "VALUES (%s, %s, %s)",
                    (username, salt, password_hash),
                )
            conn.commit()
    except Exception:
        log.exception("insert_user failed username=%s", username)
        raise


def get_user(username: str) -> dict | None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, salt, password_hash FROM users "
                "WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
    if not row:
        log.debug("get_user miss username=%s", username)
        return None
    log.debug("get_user hit username=%s", username)
    return {"username": row[0], "salt": row[1], "password_hash": row[2]}


def _ensure_saved_fits_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_fits (
              algorithm TEXT PRIMARY KEY,
              display_name TEXT NOT NULL,
              hparams JSONB NOT NULL,
              report JSONB NOT NULL,
              detector BYTEA NOT NULL,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


def save_best_fit(algorithm: str, report: dict[str, Any], detector: Any) -> None:
    """Persist approved fit (hparams + pickled detector) as the best for this algo."""
    log.info("Saving best fit algorithm=%s thr=%s", algorithm, report.get("threshold"))
    blob = pickle.dumps(detector, protocol=pickle.HIGHEST_PROTOCOL)
    try:
        with connect() as conn:
            _ensure_saved_fits_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO saved_fits
                      (algorithm, display_name, hparams, report, detector, updated_at)
                    VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, NOW())
                    ON CONFLICT (algorithm) DO UPDATE SET
                      display_name = EXCLUDED.display_name,
                      hparams = EXCLUDED.hparams,
                      report = EXCLUDED.report,
                      detector = EXCLUDED.detector,
                      updated_at = NOW()
                    """,
                    (
                        algorithm,
                        report.get("display_name", algorithm),
                        json.dumps(report.get("hparams", {})),
                        json.dumps(report),
                        blob,
                    ),
                )
            conn.commit()
    except Exception:
        log.exception("save_best_fit failed algorithm=%s", algorithm)
        raise
    log.info("Saved best fit algorithm=%s bytes=%s", algorithm, len(blob))


def get_best_fit_meta(algorithm: str) -> dict[str, Any] | None:
    """Return saved report/hparams (no detector) or None."""
    with connect() as conn:
        _ensure_saved_fits_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT display_name, hparams, report, updated_at
                FROM saved_fits WHERE algorithm = %s
                """,
                (algorithm,),
            )
            row = cur.fetchone()
    if not row:
        log.debug("No saved fit meta for algorithm=%s", algorithm)
        return None
    return {
        "display_name": row[0],
        "hparams": row[1],
        "report": row[2],
        "updated_at": row[3],
    }


def load_best_fit(algorithm: str) -> tuple[Any, dict[str, Any]] | None:
    """Load pickled detector + report dict. Resets buffers; detection off."""
    log.info("Loading best fit algorithm=%s", algorithm)
    with connect() as conn:
        _ensure_saved_fits_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT detector, report FROM saved_fits WHERE algorithm = %s",
                (algorithm,),
            )
            row = cur.fetchone()
    if not row:
        log.warning("No saved fit found algorithm=%s", algorithm)
        return None
    try:
        detector = pickle.loads(bytes(row[0]))
    except Exception:
        log.exception("Unpickle failed for algorithm=%s (re-save best fit)", algorithm)
        raise
    detector.stop()
    detector.reset_buffers()
    report = row[1] if isinstance(row[1], dict) else json.loads(row[1])
    log.info(
        "Loaded best fit algorithm=%s thr=%s",
        algorithm,
        report.get("threshold"),
    )
    return detector, report
