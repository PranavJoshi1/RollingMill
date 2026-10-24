"""Live monitoring: fit → accept → stream → detect."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from data_simulation.core.transform import WIDE_SIGNAL_COLS, pivot_readings_to_wide
from data_simulation.simulator.engine import RollingMillSimulationEngine
from db import get_best_fit_meta, load_best_fit, save_best_fit
from detection import (
    DEFAULT_NORMAL_QUANTILE,
    DEFAULT_W,
    FitReport,
    IsolationForestDetector,
    SlidingWindowDetector,
    fit_isolation_forest_from_db,
    fit_sliding_window_from_db,
)
from frontend.charts import UNITS
from logging_setup import setup_logging

log = setup_logging("monoegde.live")

MILLS = ("RS-01", "FS-01")
ALGORITHMS = {
    "statistical_window": "Statistical window (|z|)",
    "isolation_forest": "Isolation Forest",
}
TICKS_PER_REFRESH = 10
MAX_CHART_POINTS = 200
MAX_SCORE_POINTS = 200
REFRESH_SECONDS = 0.4

Detector = SlidingWindowDetector | IsolationForestDetector

METRIC_LABELS = {
    "n_train_windows_normal": "NORMAL train windows",
    "n_normal_score_rows": "NORMAL score rows",
    "train_score_mean": "NORMAL score mean",
    "train_score_p50": "NORMAL score median",
    "train_score_p99": "NORMAL score p99",
    "train_flag_rate_pct": "NORMAL flag rate (%)",
    "n_precursor_windows": "Precursor windows",
    "n_precursor_score_rows": "Precursor score rows",
    "precursor_score_mean": "Precursor score mean",
    "precursor_flag_rate_pct": "Precursor flag rate (%)",
    "n_false_issue_windows": "False-issue windows",
    "n_false_issue_score_rows": "False-issue score rows",
    "false_issue_score_mean": "False-issue score mean",
    "false_issue_flag_rate_pct": "False-issue flag rate (%)",
    "n_mills": "Mills in baseline",
}


def _deques(maxlen: int) -> dict[str, deque]:
    return {m: deque(maxlen=maxlen) for m in MILLS}


def _new_engine() -> RollingMillSimulationEngine:
    return RollingMillSimulationEngine(
        demo_mode=bool(st.session_state.get("live_demo_mode", True))
    )


def _ensure_state() -> None:
    defaults: dict[str, Any] = {
        "live_demo_mode": True,
        "live_engine": None,
        "live_buffers": None,
        "live_latest": None,
        "live_detector": None,
        "live_detection_on": False,
        "live_score_buffers": None,
        "live_algo": "statistical_window",
        "live_algo_applied": None,
        "live_stream_on": False,
        "live_fit_report": None,
        "live_fit_approved": False,
        "live_fit_status": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

    if st.session_state.live_engine is None:
        st.session_state.live_engine = _new_engine()
    if st.session_state.live_buffers is None:
        st.session_state.live_buffers = _deques(MAX_CHART_POINTS)
    if st.session_state.live_latest is None:
        st.session_state.live_latest = {m: None for m in MILLS}
    if st.session_state.live_score_buffers is None:
        st.session_state.live_score_buffers = _deques(MAX_SCORE_POINTS)


def _clear_scores() -> None:
    st.session_state.live_score_buffers = _deques(MAX_SCORE_POINTS)


def _clear_charts() -> None:
    st.session_state.live_buffers = _deques(MAX_CHART_POINTS)
    st.session_state.live_latest = {m: None for m in MILLS}
    _clear_scores()


def _stop_detection() -> None:
    det = st.session_state.live_detector
    if det is not None:
        det.stop()
        det.reset_buffers()
    st.session_state.live_detection_on = False
    _clear_scores()


def _reset_stream() -> None:
    st.session_state.live_engine = _new_engine()
    _clear_charts()
    det: Detector | None = st.session_state.live_detector
    if det is None:
        return
    det.reset_buffers()
    if st.session_state.live_detection_on:
        det.start()


def _advance() -> None:
    engine = st.session_state.live_engine
    buffers = st.session_state.live_buffers
    latest = st.session_state.live_latest
    detector: Detector | None = st.session_state.live_detector
    scores = st.session_state.live_score_buffers

    for i in range(TICKS_PER_REFRESH):
        for row in pivot_readings_to_wide(engine.get_tick()):
            mill = row["mill_id"]
            latest[mill] = row
            if detector is not None and detector.active:
                result = detector.update(row)
                if result is not None and result.window_score is not None:
                    scores[mill].append(
                        {
                            "timestamp": row["timestamp"],
                            "window_score": result.window_score,
                            "flag": result.flag,
                        }
                    )
            if i == TICKS_PER_REFRESH - 1:
                buffers[mill].append(row)


def _fit(algo: str, hparams: dict[str, Any]) -> tuple[Detector, FitReport]:
    log.info("Fitting algo=%s hparams=%s", algo, hparams)
    try:
        if algo == "isolation_forest":
            det, report = fit_isolation_forest_from_db(**hparams)
        else:
            det, report = fit_sliding_window_from_db(
                window=int(hparams["window"]),
                normal_quantile=float(hparams["normal_quantile"]),
            )
    except Exception:
        log.exception("Fit failed algo=%s", algo)
        raise
    log.info(
        "Fit ok algo=%s thr=%.4f metrics_keys=%s",
        algo,
        report.threshold,
        list(report.metrics),
    )
    return det, report


def _apply_fit(
    algo: str, det: Detector, report: FitReport | dict[str, Any], msg: str
) -> None:
    if not isinstance(report, FitReport):
        report = FitReport.model_validate(report)
    det.stop()
    det.reset_buffers()
    st.session_state.live_detector = det
    st.session_state.live_algo_applied = algo
    st.session_state.live_fit_report = report.model_dump()
    st.session_state.live_fit_status = msg
    st.session_state.live_fit_approved = False
    st.session_state.live_approve_checkbox = False
    st.session_state.live_stream_on = False
    st.session_state.live_detection_on = False
    _clear_scores()
    log.info("Applied fit algo=%s thr=%.4f", algo, report.threshold)


def _show_fit_report(report: FitReport) -> None:
    st.subheader("Fit results (historical)")
    st.success(
        f"**{report.display_name}** fitted on historical data.\n\n"
        f"- Source: `{report.source}`\n"
        f"- Threshold: **{report.threshold:.4f}** "
        f"(flag when live score > threshold)"
    )
    st.markdown("**Hyperparameters used**")
    st.json(report.hparams)
    st.markdown("**Training / evaluation metrics**")
    rows = [{"metric": METRIC_LABELS.get(k, k), "value": v} for k, v in report.metrics.items()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    for note in report.notes:
        st.caption(f"• {note}")


def _hparams_ui(algo: str) -> dict[str, Any]:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        window = st.number_input(
            "Window (ticks)", 50, 500, DEFAULT_W, 10, key=f"live_hp_window_{algo}"
        )
    with c2:
        q = st.number_input(
            "NORMAL score quantile",
            0.90,
            0.999,
            DEFAULT_NORMAL_QUANTILE,
            0.001,
            format="%.3f",
            key=f"live_hp_q_{algo}",
            help="Threshold = this quantile of NORMAL training scores.",
        )
    hparams: dict[str, Any] = {"window": int(window), "normal_quantile": float(q)}
    if algo != "isolation_forest":
        return hparams
    with c3:
        n_est = st.number_input(
            "Trees (n_estimators)", 50, 300, 100, 10, key="live_hp_n_estimators"
        )
    with c4:
        cont = st.number_input(
            "Contamination",
            0.001,
            0.1,
            0.02,
            0.001,
            format="%.3f",
            key="live_hp_contamination",
        )
    hparams["n_estimators"] = int(n_est)
    hparams["contamination"] = float(cont)
    return hparams


def _step_fit() -> None:
    with st.expander("Step 1 — Fit algorithm on historical data", expanded=True):
        algo = st.selectbox(
            "Algorithm",
            list(ALGORITHMS.keys()),
            format_func=ALGORITHMS.get,
            key="live_algo",
        )
        mode = st.radio(
            "How to prepare the detector",
            ["Use saved best", "Run new fit"],
            horizontal=True,
            key="live_fit_mode",
            help=(
                "Saved best = last fit you marked as best for this algorithm "
                "(instant load, no retrain). New fit = train again on Supabase data."
            ),
        )
        saved = get_best_fit_meta(algo)

        if mode == "Use saved best":
            if saved is None:
                st.warning(
                    f"No saved best for **{ALGORITHMS[algo]}** yet. "
                    "Run a new fit, accept it, then click **Save as best**."
                )
                return
            st.info(
                f"Saved **{saved['display_name']}** · updated `{saved['updated_at']}`"
            )
            st.json(saved["hparams"])
            if st.button("Load saved best", type="primary", use_container_width=True):
                log.info("User requested load saved best algo=%s", algo)
                try:
                    loaded = load_best_fit(algo)
                except Exception:
                    log.exception("Load saved best failed algo=%s", algo)
                    st.error("Could not load saved fit (see logs).")
                    return
                if loaded is None:
                    st.error("Could not load saved fit.")
                    return
                det, report_dict = loaded
                report = FitReport.model_validate(report_dict)
                _apply_fit(
                    algo,
                    det,
                    report,
                    f"Loaded saved best **{report.display_name}**. "
                    f"Threshold = **{report.threshold:.4f}**.",
                )
                st.rerun()
            return

        hparams = _hparams_ui(algo)
        if saved is not None:
            st.caption(
                f"Tip: a saved best exists for this algo (hparams: `{saved['hparams']}`). "
                "Switch to **Use saved best** to skip retraining."
            )
        st.caption("Training source: Supabase `sensor_readings`")

        if not st.button(
            "Fit on historical data", type="primary", use_container_width=True
        ):
            return

        old: Detector | None = st.session_state.live_detector
        if old is not None:
            old.stop()
            old.reset_buffers()

        status = st.status(
            f"Applying {ALGORITHMS[algo]} on Supabase data…", expanded=True
        )
        status.write(
            f"Loading historical data from Supabase and fitting "
            f"**{ALGORITHMS[algo]}** with window={hparams['window']}."
        )
        try:
            with st.spinner(f"Fitting {ALGORITHMS[algo]}…"):
                det, report = _fit(algo, hparams)
            _apply_fit(
                algo,
                det,
                report,
                f"Fitted **{report.display_name}**. "
                f"Threshold = **{report.threshold:.4f}** "
                f"(from NORMAL score quantile "
                f"{report.hparams.get('normal_quantile', '—')}).",
            )
            status.update(
                label=f"Fitted {report.display_name} · thr={report.threshold:.4f}",
                state="complete",
            )
            st.rerun()
        except (FileNotFoundError, ValueError) as exc:
            log.error("Fit UI error algo=%s: %s", algo, exc)
            st.session_state.live_detector = None
            st.session_state.live_algo_applied = None
            st.session_state.live_fit_report = None
            st.session_state.live_fit_status = None
            status.update(label="Fit failed", state="error")
            st.error(str(exc))


def _step_review() -> None:
    data = st.session_state.live_fit_report
    if data is None:
        st.info(
            "You can **start the live stream** anytime. "
            "Load a **saved best** or run a **new fit** to unlock detection."
        )
        return

    report = FitReport.model_validate(data)
    if st.session_state.live_fit_status:
        st.success(st.session_state.live_fit_status)
    _show_fit_report(report)

    st.session_state.setdefault("live_approve_checkbox", False)
    approved = st.checkbox(
        "I reviewed the metrics and accept this fit — unlock detection",
        key="live_approve_checkbox",
    )
    was = bool(st.session_state.live_fit_approved)
    st.session_state.live_fit_approved = bool(approved)

    if was and not approved:
        log.info("Fit acceptance revoked")
        if st.session_state.live_detection_on:
            _stop_detection()
    elif not was and approved:
        log.info("Fit accepted algo=%s", st.session_state.live_algo_applied)

    if not approved:
        st.warning(
            "Detection stays locked until you accept the fit. "
            "The live stream can still run without it."
        )
        return

    algo = st.session_state.live_algo_applied
    det = st.session_state.live_detector
    if not algo or det is None:
        return
    if st.button(
        "Save as best (reuse next time without refitting)", use_container_width=True
    ):
        try:
            save_best_fit(algo, st.session_state.live_fit_report, det)
            st.success(f"Saved best fit for **{ALGORITHMS[algo]}** in Supabase.")
        except Exception as exc:  # noqa: BLE001
            log.exception("Save as best failed algo=%s", algo)
            st.error(f"Could not save fit: {exc}")


def _step_stream(*, detection_locked: bool) -> None:
    with st.expander("Step 2 — Live stream & detection", expanded=True):
        if detection_locked:
            st.caption(
                "Stream is available now. Accept a fit in Step 1 to unlock detection."
            )

        demo = st.toggle(
            "Frequent cobbles (demo)",
            help=(
                "On: ~50% of passes are cobbles, with faster pass pacing so "
                "precursor detection shows up quickly. Off: rare production mix."
            ),
            key="live_demo_mode",
        )
        engine_demo = bool(getattr(st.session_state.live_engine, "demo_mode", False))
        if demo != engine_demo:
            was_on = bool(st.session_state.live_stream_on)
            _reset_stream()
            st.session_state.live_stream_on = was_on
            st.rerun()

        stream_on = bool(st.session_state.live_stream_on)
        detection_on = bool(st.session_state.live_detection_on)
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            label = "Stop live stream" if stream_on else "Start live stream"
            if st.button(
                label,
                use_container_width=True,
                type="primary" if not stream_on else "secondary",
            ):
                if stream_on:
                    log.info("Live stream stopped")
                    st.session_state.live_stream_on = False
                    if detection_on:
                        _stop_detection()
                else:
                    log.info("Live stream started")
                    _clear_charts()
                    det = st.session_state.live_detector
                    if det is not None:
                        det.reset_buffers()
                    st.session_state.live_stream_on = True
                st.rerun()

        with c2:
            label = "Stop detection" if detection_on else "Start detection"
            if st.button(
                label,
                use_container_width=True,
                disabled=detection_locked
                or st.session_state.live_detector is None
                or not stream_on,
            ):
                det = st.session_state.live_detector
                if detection_on:
                    log.info("Detection stopped")
                    _stop_detection()
                elif det is not None:
                    log.info(
                        "Detection started algo=%s",
                        st.session_state.live_algo_applied,
                    )
                    det.reset_buffers()
                    det.start()
                    _clear_scores()
                    st.session_state.live_detection_on = True
                st.rerun()

        with c3:
            if st.button("Reset stream buffers", use_container_width=True):
                _reset_stream()
                st.rerun()

        with c4:
            st.metric("Stream", "RUNNING" if stream_on else "STOPPED")

        if stream_on and detection_locked:
            st.caption(
                "Stream is running. Fit and accept an algorithm to enable detection."
            )
        elif stream_on and not detection_on:
            st.caption("Stream is running. Start detection to score ticks.")
        elif not stream_on:
            st.caption("Stream is stopped — charts will not update until you start it.")


def _live_panel(mill_id: str, signal: str) -> None:
    stream_on = bool(st.session_state.live_stream_on)
    if stream_on:
        _advance()

    engine = st.session_state.live_engine
    stand = engine.rs_01 if mill_id == "RS-01" else engine.fs_01
    row = st.session_state.live_latest.get(mill_id)
    detector: Detector | None = st.session_state.live_detector
    detection_on = bool(
        st.session_state.live_detection_on
        and detector is not None
        and detector.active
    )
    algo = st.session_state.live_algo_applied

    if not stream_on:
        st.info(
            "Live stream is **stopped**. Click **Start live stream** to begin "
            "the simulator (detection needs an accepted fit)."
        )

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("State", stand.state if stream_on or row else "—")
    s2.metric("Pass profile", stand.pass_profile if stream_on or row else "—")
    if row:
        unit = UNITS.get(signal, "")
        s3.metric(signal.replace("_", " ").title(), f"{row[signal]:.2f} {unit}")
        s4.metric("Timestamp", row["timestamp"][-12:])
    else:
        s3.metric(signal, "—")
        s4.metric("Timestamp", "—")

    if detection_on and detector is not None:
        result = detector.latest(mill_id)
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Detection", ALGORITHMS.get(algo, "ON") if algo else "ON")
        d2.metric("Window", f"{detector.window} ticks ({detector.window_seconds:.1f}s)")
        if result is None or not result.ready:
            d3.metric("Score", "warming up…")
            d4.metric("Flag", "—")
        else:
            d3.metric(
                "Score",
                f"{result.window_score:.3f}",
                delta=f"thr {detector.threshold:.3f}",
                delta_color="off",
            )
            d4.metric("Flag", "POSSIBLE COBBLE" if result.flag else "ok")
            if result.flag:
                st.error(
                    f"**Possible cobble** on {mill_id} — "
                    f"score {result.window_score:.3f} > {detector.threshold:.3f}"
                )

    buf = list(st.session_state.live_buffers[mill_id])
    if not buf:
        if stream_on:
            st.info("Waiting for samples…")
        return

    df = pd.DataFrame(buf)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    st.line_chart(
        df.set_index("timestamp")[[signal]].rename(
            columns={signal: f"{signal} ({UNITS.get(signal, '')})"}
        ),
        height=320,
    )

    if detection_on and detector is not None:
        score_buf = list(st.session_state.live_score_buffers[mill_id])
        if score_buf:
            sdf = pd.DataFrame(score_buf)
            sdf["timestamp"] = pd.to_datetime(sdf["timestamp"], utc=True)
            label = (
                "anomaly score" if algo == "isolation_forest" else "window score"
            )
            st.caption(
                f"{ALGORITHMS.get(algo, 'Detector')} · "
                f"{label} vs threshold ({detector.threshold:.3f})"
            )
            st.line_chart(
                sdf.set_index("timestamp")[["window_score"]].rename(
                    columns={"window_score": label}
                ),
                height=220,
            )

    with st.expander("Latest values · all signals", expanded=False):
        if row:
            latest = {s: row[s] for s in WIDE_SIGNAL_COLS if s in row}
            st.dataframe(
                pd.DataFrame([latest]).T.rename(columns={0: "value"}),
                use_container_width=True,
            )

    extra = (
        f" · detection every {TICKS_PER_REFRESH}×20 ms tick batch"
        if detection_on
        else ""
    )
    st.caption(
        f"{'Streaming' if stream_on else 'Stopped'} · "
        f"Updated {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC · "
        f"{len(buf)} points in chart{extra}"
    )


def render() -> None:
    st.title("Live monitoring")
    st.caption(
        "Workflow: **1)** Start live stream anytime → "
        "**2)** Fit / load best + accept → **3)** Start detection."
    )
    _ensure_state()
    _step_fit()
    _step_review()

    st.divider()
    detection_locked = not bool(st.session_state.live_fit_approved)
    _step_stream(detection_locked=detection_locked)

    col_a, col_b = st.columns(2)
    with col_a:
        mill_id = st.selectbox("Mill / machine", MILLS, key="live_mill")
    with col_b:
        signal = st.selectbox("Signal", WIDE_SIGNAL_COLS, key="live_signal")

    @st.fragment(run_every=REFRESH_SECONDS if st.session_state.live_stream_on else None)
    def panel() -> None:
        _live_panel(mill_id, signal)

    panel()
