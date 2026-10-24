"""App home — Mono Edge styled landing after sign-in."""

from __future__ import annotations

import streamlit as st

from frontend.nav import go
from frontend.theme import render_footer, render_hero


def render() -> None:
    user = st.session_state.get("username", "operator")

    render_hero(
        eyebrow=f"Signed in · {user}",
        title_html="Rolling mill<br/>signal analytics.",
        subtitle=(
            "Monitor live PLC-like streams, explore historical passes, and "
            "compare normal operation with false-issue load changes and cobble events."
        ),
        kind="Operator console",
        tags=["RS-01 / FS-01", "6 signals", "Auth gated"],
    )

    st.markdown(
        """
<p class="me-intro">
  <strong>Welcome back.</strong> Open a workspace below, or use the top tabs /
  sidebar. Charts downsample the 20&nbsp;ms source stream so the UI stays
  responsive while preserving the shape of each pass.
</p>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="me-section-heading">
  <span class="me-section-index">01 /</span>
  <h2>At a glance</h2>
</div>
<div class="me-metrics">
  <div class="me-metric">
    <span class="me-metric-label">PLC sampling interval</span>
    <div class="me-metric-value">20 ms</div>
    <div class="me-metric-desc">50 samples/second per signal</div>
  </div>
  <div class="me-metric">
    <span class="me-metric-label">Machines</span>
    <div class="me-metric-value">RS-01 · FS-01</div>
    <div class="me-metric-desc">Roughing &amp; finishing stands</div>
  </div>
  <div class="me-metric">
    <span class="me-metric-label">Operator experience</span>
    <div class="me-metric-value">Live + History</div>
    <div class="me-metric-desc">Monitoring and incident context</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="me-section-heading">
  <span class="me-section-index">02 /</span>
  <h2>Where to go</h2>
</div>
<div class="me-context">
  A steel rolling mill collects high-frequency operating signals. Events such as a
  <strong>cobble</strong> can interrupt production. This console helps you spot
  abnormal patterns and compare them against legitimate load changes
  (<strong>false issue</strong>) that should not be treated as incidents.
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
<div class="me-req">
  <div class="me-req-num">01</div>
  <h3>Live monitoring</h3>
  <p>Online synthetic stream from the mill simulator. Select a stand and signal;
  charts update continuously with intentional downsampling.</p>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button(
            "Open live monitoring →",
            key="home_go_live",
            type="primary",
            use_container_width=True,
        ):
            go("live")

    with c2:
        st.markdown(
            """
<div class="me-req">
  <div class="me-req-num">02</div>
  <h3>Historical analytics</h3>
  <p>Jump to cobble or false-issue episodes, compare means across profiles, and
  inspect multi-signal signatures against normal operation.</p>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button(
            "Open historical analytics →",
            key="home_go_history",
            type="primary",
            use_container_width=True,
        ):
            go("history")

    render_footer()
