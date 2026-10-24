"""Always-visible page navigation (works even when the sidebar is closed)."""

from __future__ import annotations

from typing import Any

import streamlit as st

# Filled by app.main() after Pages are constructed.
PAGES: dict[str, Any] = {}

# st.Page.title → nav key
_TITLE_TO_KEY = {
    "Home": "home",
    "Live monitoring": "live",
    "Historical analytics": "history",
}


def register_pages(pages: dict[str, Any]) -> None:
    PAGES.clear()
    PAGES.update(pages)


def go(key: str) -> None:
    page = PAGES.get(key)
    if page is None:
        st.error(f"Unknown page: {key}")
        return
    st.session_state["nav_page"] = key
    st.switch_page(page)


def active_key_from_page(page: Any) -> str:
    """Resolve current nav key from the Page returned by st.navigation()."""
    for key, pg in PAGES.items():
        if pg is page:
            return key

    title = getattr(page, "title", None)
    if title in _TITLE_TO_KEY:
        return _TITLE_TO_KEY[title]

    url = (getattr(page, "url_path", None) or "").strip("/")
    if url in PAGES:
        return url

    stored = st.session_state.get("nav_page")
    if stored in PAGES:
        return stored
    return "home"


def render_top_nav(current_page: Any | None = None) -> None:
    """Compact top tabs — highlight matches the page Streamlit is running."""
    if current_page is not None:
        current = active_key_from_page(current_page)
    else:
        current = st.session_state.get("nav_page", "home")
    st.session_state["nav_page"] = current

    items = [
        ("home", "Home"),
        ("live", "Live monitoring"),
        ("history", "Historical analytics"),
    ]
    cols = st.columns([1.15, 1.55, 1.85, 4])
    for col, (key, label) in zip(cols, items):
        with col:
            is_active = current == key
            if st.button(
                label,
                key=f"topnav_{key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                go(key)

    st.markdown('<div class="me-topnav-rule"></div>', unsafe_allow_html=True)
