"""Monoegde Streamlit entrypoint: auth gate + protected navigation."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `uv run streamlit run src/frontend/app.py` without installing frontend.
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st

from frontend.auth import init_session, logout, render_auth_page
from frontend.nav import register_pages, render_top_nav
from frontend.pages import history, home, live
from frontend.theme import inject_theme
from logging_setup import setup_logging

log = setup_logging("monoegde.app")


def main() -> None:
    st.set_page_config(
        page_title="Mono Edge · Signal Analytics",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "Get Help": None,
            "Report a bug": None,
            "About": "Mono Edge · rolling mill signal analytics",
        },
    )
    inject_theme()
    init_session()

    if not st.session_state.authenticated:
        log.debug("Unauthenticated — showing sign-in")
        render_auth_page()
        return

    log.debug("Authenticated as %s", st.session_state.username)

    with st.sidebar:
        st.markdown(
            f"""
<div class="me-side-brand">
  <span class="me-brand-symbol">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M2 14h4l3-8 4 12 3-8 2 4h4" stroke="#0a4e4c" stroke-width="2.4"
            stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </span>
  <span class="me-side-name">MONO EDGE</span>
</div>
<div class="me-side-user">{st.session_state.username}</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("Sign out", use_container_width=True):
            log.info("User signed out: %s", st.session_state.username)
            logout()
            st.rerun()

    home_page = st.Page(home.render, title="Home", url_path="home", default=True)
    live_page = st.Page(live.render, title="Live monitoring", url_path="live")
    history_page = st.Page(
        history.render,
        title="Historical analytics",
        url_path="history",
    )
    register_pages(
        {
            "home": home_page,
            "live": live_page,
            "history": history_page,
        }
    )
    page = st.navigation([home_page, live_page, history_page])
    log.debug("Navigating to page title=%s", getattr(page, "title", page))
    # Pass the current Page so top tabs highlight like the sidebar.
    render_top_nav(page)
    page.run()


if __name__ == "__main__":
    main()
