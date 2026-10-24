"""Historical analytics: filter stored readings and compare normal vs abnormal."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db import count_readings, list_mills, read_readings
from frontend.charts import SIGNAL_COLS, UNITS, downsample, summarize_signal
from logging_setup import setup_logging

log = setup_logging("monoegde.history")

PROFILE_ORDER = ["NORMAL", "FALSE_ISSUE", "COBBLE"]
PROFILE_COLORS = {
    "NORMAL": "#2a9d8f",
    "FALSE_ISSUE": "#e9c46a",
    "COBBLE": "#e76f51",
}
ACTIVE_STATES = {"ENTRY", "LOAD", "EXIT", "ANOMALY_PRECURSOR", "COBBLE"}
_FAST_TARGET_ROWS = 25_000
LOAD_MODES = {
    "fast": "Fast sample (~25k rows)",
    "full": "Full mill data (slower)",
}


def _profile_color() -> alt.Color:
    return alt.Color(
        "profile:N",
        scale=alt.Scale(
            domain=PROFILE_ORDER,
            range=[PROFILE_COLORS[p] for p in PROFILE_ORDER],
        ),
        title="Pass profile",
    )


def _active(df: pd.DataFrame) -> pd.DataFrame:
    active = df[df["ground_truth_state"].isin(ACTIVE_STATES)]
    return active if not active.empty else df


@st.cache_data(show_spinner="Loading from Supabase…", ttl=300)
def load_history(mill_id: str, mode: str) -> pd.DataFrame:
    log.info("History load mill_id=%s mode=%s", mill_id, mode)
    if mode == "full":
        df = read_readings(mill_id=mill_id, stride=1)
    else:
        n = count_readings(mill_id=mill_id)
        stride = max(1, n // _FAST_TARGET_ROWS) if n else 1
        log.debug("History fast sample mill_n=%s stride=%s", n, stride)
        df = read_readings(mill_id=mill_id, stride=stride)
    log.info("History loaded mill_id=%s rows=%s", mill_id, len(df))
    return df


def _find_episodes(mill_df: pd.DataFrame) -> pd.DataFrame:
    active = mill_df[mill_df["ground_truth_state"].isin(ACTIVE_STATES)].copy()
    if active.empty:
        return pd.DataFrame()

    active = active.sort_values("timestamp")
    gap = active["timestamp"].diff().dt.total_seconds().fillna(0) > 1.0
    profile_chg = active["pass_profile"] != active["pass_profile"].shift()
    active["episode_id"] = (gap | profile_chg).cumsum()

    rows = []
    for ep_id, g in active.groupby("episode_id"):
        states = sorted(g["ground_truth_state"].unique())
        rows.append(
            {
                "episode_id": int(ep_id),
                "profile": g["pass_profile"].iloc[0],
                "start": g["timestamp"].iloc[0],
                "end": g["timestamp"].iloc[-1],
                "duration_s": (
                    g["timestamp"].iloc[-1] - g["timestamp"].iloc[0]
                ).total_seconds(),
                "samples": len(g),
                "has_cobble_state": "COBBLE" in states,
                "has_precursor": "ANOMALY_PRECURSOR" in states,
                "states": ", ".join(states),
            }
        )
    return pd.DataFrame(rows).sort_values("start").reset_index(drop=True)


def _profile_series_chart(
    window: pd.DataFrame, signal: str, unit: str, max_points: int
) -> alt.Chart:
    parts = []
    for profile in PROFILE_ORDER:
        mask = window["pass_profile"] == profile
        if not mask.any():
            continue
        chunk = downsample(
            window.loc[mask, ["timestamp", signal]].copy(),
            max_points=max(100, max_points // 3),
        )
        chunk["profile"] = profile
        parts.append(chunk.rename(columns={signal: "value"}))

    if not parts:
        return alt.Chart(pd.DataFrame({"timestamp": [], "value": []})).mark_line()

    return (
        alt.Chart(pd.concat(parts, ignore_index=True))
        .mark_line(opacity=0.9)
        .encode(
            x=alt.X("timestamp:T", title="Time"),
            y=alt.Y("value:Q", title=f"{signal} ({unit})"),
            color=_profile_color(),
            tooltip=["timestamp:T", "profile:N", "value:Q"],
        )
        .properties(height=340)
        .interactive()
    )


def _comparison_table(window: pd.DataFrame, signal: str) -> pd.DataFrame:
    stats = (
        _active(window)
        .groupby("pass_profile", dropna=False)[signal]
        .agg(mean="mean", std="std", min="min", max="max", count="count")
        .reindex(PROFILE_ORDER)
        .dropna(how="all")
        .round(2)
    )
    if "NORMAL" in stats.index:
        base = stats.loc["NORMAL", "mean"]
        if pd.notna(base) and base != 0:
            stats["vs_normal_%"] = ((stats["mean"] - base) / abs(base) * 100).round(1)
    return stats


def _signature_chart(window: pd.DataFrame) -> alt.Chart | None:
    active = _active(window)
    rows = []
    for profile in PROFILE_ORDER:
        sub = active[active["pass_profile"] == profile]
        if sub.empty:
            continue
        for sig in SIGNAL_COLS:
            rows.append(
                {"profile": profile, "signal": sig, "mean": float(sub[sig].mean())}
            )
    if not rows:
        return None

    sig_df = pd.DataFrame(rows)
    normals = sig_df[sig_df["profile"] == "NORMAL"].set_index("signal")["mean"]
    sig_df["relative"] = sig_df.apply(
        lambda r: (
            r["mean"] / normals[r["signal"]]
            if r["signal"] in normals.index and normals[r["signal"]]
            else float("nan")
        ),
        axis=1,
    )
    return (
        alt.Chart(sig_df.dropna(subset=["relative"]))
        .mark_bar()
        .encode(
            x=alt.X("signal:N", title=None, sort=SIGNAL_COLS),
            y=alt.Y(
                "relative:Q",
                title="Mean ÷ normal mean",
                scale=alt.Scale(zero=True),
            ),
            color=_profile_color(),
            xOffset="profile:N",
            tooltip=["profile", "signal", "mean", "relative"],
        )
        .properties(height=280)
    )


def render() -> None:
    st.title("Historical analytics")
    st.caption(
        "Compare **NORMAL** passes vs **FALSE_ISSUE** (hard billet / load change) "
        "vs **COBBLE** (true incident with precursor). Data from Supabase."
    )

    n_rows = count_readings()
    if n_rows == 0:
        st.warning(
            "No rows in `sensor_readings`. Generate offline with:\n\n"
            "`uv run python -m data_simulation.generate_historical_data --hours 2`"
        )
        return

    mills = list_mills()
    if not mills:
        st.warning("No mills found in Supabase.")
        return

    st.caption(f"{n_rows:,} rows in Supabase")

    c0, c1, c2, c3 = st.columns([1.4, 1, 1, 1.1])
    with c0:
        load_label = st.radio(
            "Data load",
            list(LOAD_MODES.values()),
            index=0,
            horizontal=True,
            key="hist_load_mode",
            help=(
                "Fast sample pulls ~25k evenly spaced rows across the full time "
                "range (much quicker). Full mill data loads every row."
            ),
        )
        load_mode = next(k for k, v in LOAD_MODES.items() if v == load_label)
    with c1:
        mill_id = st.selectbox("Mill / machine", mills, key="hist_mill")
    with c2:
        vib_i = SIGNAL_COLS.index("vibration") if "vibration" in SIGNAL_COLS else 0
        signal = st.selectbox(
            "Signal",
            SIGNAL_COLS,
            index=vib_i,
            key="hist_signal",
            help="Vibration / torque usually show cobble most clearly.",
        )
    with c3:
        max_points = st.slider("Chart points (downsample)", 200, 5000, 1500, 100)

    mill_df = load_history(mill_id, load_mode)
    if mill_df.empty:
        st.warning("No rows returned for this mill / load mode.")
        return

    mill_n = count_readings(mill_id=mill_id)
    if load_mode == "fast":
        st.caption(
            f"Loaded **{len(mill_df):,}** / {mill_n:,} rows for `{mill_id}` "
            "(fast sample). Switch to **Full mill data** for every tick."
        )
    else:
        st.caption(f"Loaded **{len(mill_df):,}** rows for `{mill_id}` (full).")

    unit = UNITS.get(signal, "")
    episodes = _find_episodes(mill_df)
    t_min, t_max = mill_df["timestamp"].min(), mill_df["timestamp"].max()
    start, end = t_min, t_max
    episode_focus = False

    st.subheader("Event browser")
    st.caption(
        "FALSE_ISSUE = elevated load without cobble state. "
        "COBBLE = pass that reaches ANOMALY_PRECURSOR → COBBLE."
    )

    if episodes.empty:
        st.info("No labeled active passes found for this mill.")
    else:
        show = st.multiselect(
            "Show profiles",
            PROFILE_ORDER,
            default=["COBBLE", "FALSE_ISSUE"],
            key="hist_profile_filter",
        )
        catalog = episodes[episodes["profile"].isin(show)].copy()
        if catalog.empty:
            st.info("No episodes for the selected profiles — include NORMAL or others.")
        else:
            catalog["label"] = catalog.apply(
                lambda r: (
                    f"{r['profile']} · {r['start'].strftime('%H:%M:%S')} "
                    f"({r['duration_s']:.1f}s)"
                    + (" · precursor" if r["has_precursor"] else "")
                    + (" · cobble state" if r["has_cobble_state"] else "")
                ),
                axis=1,
            )
            pick = st.selectbox(
                "Jump to episode",
                options=["(full range)"] + catalog["label"].tolist(),
                key="hist_episode_pick",
            )
            pad_s = st.slider("Context padding (seconds around episode)", 0, 30, 8)

            if pick != "(full range)":
                ep = catalog.loc[catalog["label"] == pick].iloc[0]
                start = max(ep["start"] - pd.Timedelta(seconds=pad_s), t_min)
                end = min(ep["end"] + pd.Timedelta(seconds=pad_s), t_max)
                episode_focus = True
                st.success(
                    f"Focused on **{ep['profile']}** · states: `{ep['states']}` · "
                    f"{ep['samples']} samples"
                )

            st.dataframe(
                catalog[
                    [
                        "profile",
                        "start",
                        "end",
                        "duration_s",
                        "samples",
                        "has_precursor",
                        "has_cobble_state",
                        "states",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                height=220,
            )

    if not episode_focus:
        start, end = st.slider(
            "Time range",
            min_value=t_min.to_pydatetime(),
            max_value=t_max.to_pydatetime(),
            value=(t_min.to_pydatetime(), t_max.to_pydatetime()),
            format="YYYY-MM-DD HH:mm:ss",
            key="hist_time_slider",
        )
    else:
        st.caption(
            f"Window: `{pd.Timestamp(start).strftime('%H:%M:%S')}` → "
            f"`{pd.Timestamp(end).strftime('%H:%M:%S')}` "
            "(choose “(full range)” to use the manual slider)"
        )

    window = mill_df[
        (mill_df["timestamp"] >= pd.Timestamp(start))
        & (mill_df["timestamp"] <= pd.Timestamp(end))
    ].copy()
    if window.empty:
        st.warning("No rows in the selected range.")
        return

    st.subheader("Normal vs false-issue vs cobble")
    stats = _comparison_table(window, signal)
    st.markdown(f"**{signal}** during active pass states (ENTRY / LOAD / …)")
    st.dataframe(stats, use_container_width=True)

    if len(stats) >= 2:
        mean_chart = (
            alt.Chart(stats.reset_index().rename(columns={"pass_profile": "profile"}))
            .mark_bar()
            .encode(
                x=alt.X("profile:N", sort=PROFILE_ORDER, title="Pass profile"),
                y=alt.Y("mean:Q", title=f"Mean {signal} ({unit})"),
                color=alt.Color(
                    "profile:N",
                    scale=alt.Scale(
                        domain=PROFILE_ORDER,
                        range=[PROFILE_COLORS[p] for p in PROFILE_ORDER],
                    ),
                    legend=None,
                ),
                tooltip=["profile", "mean", "std", "min", "max", "count"],
            )
            .properties(height=240)
        )
        st.altair_chart(mean_chart, use_container_width=True)

    st.markdown("**Multi-signal signature** (mean during active states)")
    radar = _signature_chart(window)
    if radar is not None:
        st.altair_chart(radar, use_container_width=True)
        st.caption(
            "Relative to NORMAL: FALSE_ISSUE lifts force/current/torque together; "
            "COBBLE spikes vibration and collapses speed."
        )

    st.subheader("Timeline by pass profile")
    st.altair_chart(
        _profile_series_chart(window, signal, unit, max_points),
        use_container_width=True,
    )

    if "ground_truth_state" in window.columns:
        st.markdown("**FSM state time** in this window (row counts ≈ 20 ms ticks)")
        st.bar_chart(window["ground_truth_state"].value_counts())

    with st.expander("Window summary", expanded=False):
        overall = summarize_signal(window[signal])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Mean", f"{overall['mean']:.2f} {unit}")
        m2.metric("Range", f"{overall['range']:.2f} {unit}")
        m3.metric("Min", f"{overall['min']:.2f} {unit}")
        m4.metric("Max", f"{overall['max']:.2f} {unit}")
