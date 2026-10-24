"""Mono Edge visual theme for Streamlit (aligned with the assessment brief)."""

from __future__ import annotations

import streamlit as st

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');

:root {
  --ink: #182a38;
  --slate: #526676;
  --muted: #778a96;
  --paper: #f4f7f7;
  --white: #fff;
  --line: #dce6e7;
  --navy: #102836;
  --deep: #081c28;
  --teal: #008c85;
  --mint: #a8f1dc;
  --ice: #ecf8f5;
}

html, body, [class*="css"] {
  font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--ink);
}

.stApp {
  background: var(--paper);
}

/* ---- Hide Streamlit developer chrome (keep sidebar reopen control) ---- */
#MainMenu,
footer,
.stDeployButton,
[data-testid="stStatusWidget"],
[data-testid="stDecoration"],
[data-testid="manage-app-button"],
div[data-testid="stToolbarActions"] {
  display: none !important;
  visibility: hidden !important;
}

/* “Press Enter / double-click” helper text under inputs & dataframes */
[data-testid="InputInstructions"],
[data-testid="stWidgetLabel"] ~ div [data-testid="InputInstructions"],
.stTextInput [data-testid="InputInstructions"],
.stNumberInput [data-testid="InputInstructions"],
.stSelectbox [data-testid="InputInstructions"],
.stMultiSelect [data-testid="InputInstructions"],
.stDateInput [data-testid="InputInstructions"],
.stTimeInput [data-testid="InputInstructions"],
.stTextArea [data-testid="InputInstructions"] {
  display: none !important;
  height: 0 !important;
  overflow: hidden !important;
}

/* Soft header — keep sidebar toggle visible */
[data-testid="stHeader"] {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

/*
 * When the sidebar is closed, Streamlit shows a reopen control.
 * Pin it so it never disappears behind hidden toolbar chrome.
 */
[data-testid="stSidebarCollapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  position: fixed !important;
  top: 0.85rem !important;
  left: 0.85rem !important;
  z-index: 1000000 !important;
}
[data-testid="stSidebarCollapsedControl"] button,
button[kind="headerNoPadding"] {
  width: 44px !important;
  height: 44px !important;
  min-width: 44px !important;
  background: #102836 !important;
  border: 1px solid #1f4a52 !important;
  border-radius: 12px !important;
  box-shadow: 0 8px 24px rgba(8, 28, 40, 0.28) !important;
  color: #a8f1dc !important;
}
[data-testid="stSidebarCollapsedControl"] button:hover,
button[kind="headerNoPadding"]:hover {
  background: #008c85 !important;
  border-color: #008c85 !important;
  color: #fff !important;
}
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] span {
  color: #a8f1dc !important;
  fill: #a8f1dc !important;
}

.me-topnav-rule {
  height: 1px;
  background: var(--line);
  margin: 0.35rem 0 1.1rem;
}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
  background: #fcfdfd !important;
  border-right: 1px solid var(--line) !important;
}
[data-testid="stSidebar"] > div:first-child {
  padding-top: 1.1rem;
}
[data-testid="stSidebar"] * {
  font-family: "IBM Plex Sans", sans-serif;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  margin-bottom: 0.2rem;
}

/* Nav links */
[data-testid="stSidebarNav"] {
  padding-top: 0.4rem !important;
}
[data-testid="stSidebarNav"] ul {
  gap: 4px;
}
[data-testid="stSidebarNav"] a,
[data-testid="stSidebarNav"] span {
  font-weight: 600 !important;
  letter-spacing: -0.01em;
  border-radius: 10px !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebarNav"] a[aria-selected="true"] {
  background: var(--ice) !important;
  color: var(--teal) !important;
}
/* Hide the default “App” section eyebrow if present */
[data-testid="stSidebarNav"] [data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarNav"] small,
[data-testid="stSidebarNav"] header {
  display: none !important;
}

.me-side-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 6px;
}
.me-side-brand .me-brand-symbol {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: #a9f0d6;
  flex: 0 0 30px;
}
.me-side-brand .me-side-name {
  font-weight: 750;
  letter-spacing: 0.12em;
  font-size: 13px;
  color: var(--ink);
}
.me-side-user {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 12px 40px;
  letter-spacing: 0.02em;
}

/* ---- Expanders: quieter disclosure ---- */
[data-testid="stExpander"] {
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
  background: #fcfdfd !important;
  overflow: hidden;
}
[data-testid="stExpander"] details {
  border: none !important;
}
[data-testid="stExpander"] summary {
  padding: 0.65rem 0.9rem !important;
  font-weight: 650 !important;
  color: var(--ink) !important;
  letter-spacing: -0.01em;
}
[data-testid="stExpander"] summary:hover {
  color: var(--teal) !important;
}
[data-testid="stExpander"] summary svg,
[data-testid="stExpander"] summary span[data-testid="stExpanderToggleIcon"],
[data-testid="stExpanderToggleIcon"] {
  color: var(--teal) !important;
  opacity: 0.85;
}
/* Drop the loud Material “expand_more” glyph sizing */
[data-testid="stExpanderToggleIcon"] {
  transform: scale(0.85);
}

/* Captions / helper text */
[data-testid="stCaptionContainer"],
.stCaption {
  color: var(--muted) !important;
  font-size: 0.82rem !important;
}

/* Primary buttons → teal */
.stButton > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button {
  background: var(--teal) !important;
  border-color: var(--teal) !important;
  color: #fff !important;
  font-weight: 650 !important;
  border-radius: 10px !important;
}
.stButton > button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  border: 1px solid var(--line) !important;
  background: #fff !important;
  color: var(--ink) !important;
}
.stButton > button:hover {
  border-color: var(--teal) !important;
  color: var(--teal) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 8px;
  border-bottom: 1px solid var(--line);
}
.stTabs [data-baseweb="tab"] {
  font-weight: 650;
  color: var(--slate);
}
.stTabs [aria-selected="true"] {
  color: var(--teal) !important;
}

/* Dataframes: less “spreadsheet chrome” */
[data-testid="stDataFrame"] {
  border: 1px solid var(--line);
  border-radius: 12px;
  overflow: hidden;
}

/* ---- Shared landing fragments ---- */
.me-hero {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  background: linear-gradient(112deg, #081e2a 4%, #153e4c 63%, #075b59 120%);
  color: #fff;
  padding: 36px 40px 40px;
  border-radius: 16px;
  margin-bottom: 28px;
  box-shadow: 0 15px 55px rgba(24, 49, 62, 0.12);
}
.me-hero:before {
  content: "";
  position: absolute;
  inset: 0;
  opacity: 0.13;
  z-index: -1;
  background-image:
    linear-gradient(rgba(255,255,255,.33) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.33) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: linear-gradient(to right, transparent 0%, #000 70%);
}
.me-hero:after {
  content: "";
  position: absolute;
  right: -100px;
  top: -120px;
  width: 360px;
  height: 360px;
  background: #20ad9c;
  filter: blur(110px);
  opacity: 0.22;
  z-index: -1;
}
.me-topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 36px;
  flex-wrap: wrap;
}
.me-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 750;
  letter-spacing: 0.14em;
  font-size: 15px;
}
.me-brand-symbol {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  background: #a9f0d6;
  color: #123b42;
}
.me-top-kind {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #a8c7ca;
  font-weight: 700;
}
.me-eyebrow {
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 750;
  color: var(--mint);
  margin-bottom: 12px;
}
.me-hero h1 {
  max-width: 820px;
  font-size: clamp(28px, 4.2vw, 48px);
  letter-spacing: -0.045em;
  line-height: 1.1;
  font-weight: 750;
  margin: 0 0 14px;
  color: #fff !important;
}
.me-subtitle {
  max-width: 640px;
  color: #d0e0e3;
  font-size: 16px;
  line-height: 1.65;
  margin: 0;
}
.me-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 28px;
}
.me-tag {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #d9f5f0;
  background: rgba(173, 250, 231, 0.12);
  border: 1px solid rgba(196, 250, 239, 0.23);
  border-radius: 99px;
  padding: 7px 12px;
  font-weight: 750;
}
.me-signal {
  width: 100%;
  height: 48px;
  margin-top: 22px;
  opacity: 0.65;
}
.me-signal svg {
  width: 100%;
  height: 100%;
  display: block;
}

.me-intro {
  font-size: 17px;
  line-height: 1.75;
  color: #334b5a;
  margin: 0 0 28px;
  max-width: 900px;
}
.me-intro strong { color: #152f3b; }

.me-section-heading {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin: 8px 0 16px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
}
.me-section-index {
  font-size: 12px;
  color: var(--teal);
  font-weight: 800;
  letter-spacing: 0.06em;
}
.me-section-heading h2 {
  font-size: 24px;
  margin: 0;
  font-weight: 750;
  letter-spacing: -0.03em;
  color: var(--ink) !important;
}

.me-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 18px 0 24px;
}
.me-metric {
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fcfdfd;
}
.me-metric-label {
  display: block;
  color: #647d89;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 10px;
  font-weight: 800;
  margin-bottom: 4px;
}
.me-metric-value {
  font-size: 22px;
  font-weight: 780;
  letter-spacing: -0.03em;
  color: var(--ink);
}
.me-metric-desc {
  font-size: 12px;
  color: #748792;
  margin-top: 2px;
}

.me-req {
  border: 1px solid var(--line);
  border-radius: 13px;
  padding: 18px 18px 16px;
  background: #fff;
}
.me-req-num {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #e7f5f1;
  color: #087f78;
  font-weight: 800;
  font-size: 11px;
  margin-bottom: 10px;
}
.me-req h3 {
  margin: 0 0 6px;
  font-size: 15px;
  color: #1b3542;
}
.me-req p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #566d79;
}

.me-context {
  background: var(--ice);
  border: 1px solid #d3eae4;
  border-left: 4px solid #049e91;
  border-radius: 0 11px 11px 0;
  padding: 16px 18px;
  color: #284958;
  font-size: 14px;
  line-height: 1.7;
  margin-bottom: 18px;
}

.me-auth-header {
  text-align: center;
  margin: 0.5rem auto 1.4rem;
  max-width: 520px;
}
.me-auth-header .me-brand {
  justify-content: center;
  color: var(--ink);
  margin-bottom: 1.1rem;
}
.me-auth-header h1 {
  font-size: clamp(26px, 3.5vw, 34px);
  letter-spacing: -0.04em;
  line-height: 1.15;
  font-weight: 750;
  color: var(--ink) !important;
  margin: 0 0 10px;
}
.me-auth-header p {
  margin: 0;
  color: var(--slate);
  font-size: 15px;
  line-height: 1.55;
}

.me-footer {
  margin-top: 36px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  color: #82949d;
  font-size: 11px;
  letter-spacing: 0.05em;
}
.me-footer-brand {
  color: #3e626c;
  font-weight: 800;
  letter-spacing: 0.12em;
}

@media (max-width: 760px) {
  .me-hero { padding: 26px 22px 28px; }
  .me-metrics { grid-template-columns: 1fr; }
}
</style>
"""

BRAND_SVG = """
<svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
  <path d="M2 14h4l3-8 4 12 3-8 2 4h4" stroke="#0a4e4c" stroke-width="2.4"
        stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

SIGNAL_SVG = """
<svg viewBox="0 0 900 64" preserveAspectRatio="none" fill="none" aria-hidden="true">
  <path d="M0 35H900" stroke="#88d6c4" stroke-opacity=".3" stroke-dasharray="5 6"/>
  <path d="M0 38L42 39L66 36L88 39L110 37L130 39L149 35L172 37L192 36L217 40L239 36L265 38L283 34L303 39L322 36L347 38L368 36L383 18L397 48L410 12L425 56L440 21L455 42L477 36L497 38L520 35L540 39L563 36L588 38L611 35L627 42L642 26L657 41L674 28L695 38L718 37L740 36L758 39L778 36L802 38L822 35L847 40L869 36L900 38"
        stroke="#83e8ce" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def inject_theme() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_hero(
    *,
    eyebrow: str,
    title_html: str,
    subtitle: str,
    kind: str = "Signal Analytics Platform",
    tags: list[str] | None = None,
) -> None:
    tags = tags or ["Live monitoring", "Historical analytics", "Auth gated"]
    tags_html = "".join(f'<span class="me-tag">{t}</span>' for t in tags)
    st.markdown(
        f"""
<div class="me-hero">
  <div class="me-topline">
    <div class="me-brand">
      <span class="me-brand-symbol">{BRAND_SVG}</span>
      MONO EDGE
    </div>
    <div class="me-top-kind">{kind}</div>
  </div>
  <div class="me-eyebrow">{eyebrow}</div>
  <h1>{title_html}</h1>
  <p class="me-subtitle">{subtitle}</p>
  <div class="me-tags">{tags_html}</div>
  <div class="me-signal">{SIGNAL_SVG}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        """
<div class="me-footer">
  <span class="me-footer-brand">MONO EDGE</span>
  <span>Signal Analytics · Rolling mill monitoring</span>
  <span>20 ms · 50 Hz</span>
</div>
""",
        unsafe_allow_html=True,
    )
