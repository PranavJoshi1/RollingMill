"""Sign-up / sign-in (hashed passwords stored in Supabase)."""

from __future__ import annotations

import hashlib
import hmac
import secrets

import psycopg
import streamlit as st

from db import get_user, insert_user
from frontend.theme import render_footer, render_hero
from logging_setup import setup_logging

log = setup_logging("monoegde.auth")
_PBKDF2_ITERS = 120_000


def _hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS
    )
    return salt.hex(), digest.hex()


def register_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if get_user(username):
        log.info("Register rejected — username taken: %s", username)
        return False, "That username is already taken."

    salt, pw_hash = _hash_password(password)
    try:
        insert_user(username, salt, pw_hash)
    except psycopg.errors.UniqueViolation:
        log.info("Register rejected — unique violation: %s", username)
        return False, "That username is already taken."
    log.info("Registered user: %s", username)
    return True, "Account created. You can sign in."


def authenticate(username: str, password: str) -> bool:
    user = username.strip().lower()
    record = get_user(user)
    if not record:
        log.info("Login failed — unknown user: %s", user)
        return False
    _, candidate = _hash_password(password, record["salt"])
    ok = hmac.compare_digest(candidate, record["password_hash"])
    if ok:
        log.info("Login ok: %s", user)
    else:
        log.info("Login failed — bad password: %s", user)
    return ok


def init_session() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("username", None)


def logout() -> None:
    st.session_state.authenticated = False
    st.session_state.username = None


def render_auth_page() -> None:
    # Hide empty sidebar chrome on the login screen.
    st.markdown(
        """
<style>
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarNav"],
button[kind="headerNoPadding"] {
  display: none !important;
  visibility: hidden !important;
}
[data-testid="stAppViewContainer"] > .main {
  margin-left: 0 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    render_hero(
        eyebrow="Access required",
        title_html="Sign in to the<br/>signal console.",
        subtitle=(
            "Monitor rolling-mill streams, explore historical passes, and "
            "compare normal operation with cobble-like incidents."
        ),
        kind="Authenticated access",
        tags=["Sign in", "Sign up"],
    )

    st.markdown(
        """
<p class="me-intro">
  <strong>Create an account</strong> or sign in below. Monitoring and analytics
  routes stay locked until authentication succeeds.
</p>
""",
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        tab_in, tab_up = st.tabs(["Sign in", "Sign up"])

        with tab_in:
            with st.form("sign_in"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", type="primary")
                if submitted:
                    if authenticate(username, password):
                        st.session_state.authenticated = True
                        st.session_state.username = username.strip().lower()
                        st.rerun()
                    st.error("Invalid username or password.")

        with tab_up:
            with st.form("sign_up"):
                username = st.text_input("Choose a username", key="su_user")
                password = st.text_input(
                    "Choose a password", type="password", key="su_pw"
                )
                password2 = st.text_input(
                    "Confirm password", type="password", key="su_pw2"
                )
                submitted = st.form_submit_button("Create account", type="primary")
                if submitted:
                    if password != password2:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = register_user(username, password)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

    render_footer()
