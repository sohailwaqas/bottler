"""
auth/login.py — per-session username/password login.

Passwords are hashed with SHA-256 + a random per-user salt (hashlib) and
never stored in plaintext. `st.session_state` gates all module access;
logging out / session expiry always routes back through this screen.
"""
import hashlib
import secrets
from datetime import datetime

import streamlit as st
import config
from database.db import get_connection


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def ensure_default_admin():
    """Seed a single default Admin user on first run so the demo is usable
    out of the box. The password should be rotated on real deployments."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) c FROM users").fetchone()
        if row["c"] > 0:
            return
        salt = secrets.token_hex(16)
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, is_active, created_at) VALUES (?,?,?,?,1,?)",
            ("admin", _hash("bottler123", salt), salt, "Admin", datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def verify_login(username: str, password: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1", (username.strip(),)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    if _hash(password, row["salt"]) == row["password_hash"]:
        return dict(row)
    return None


def create_user(username: str, password: str, role: str = "Operator") -> tuple[bool, str]:
    salt = secrets.token_hex(16)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, is_active, created_at) VALUES (?,?,?,?,1,?)",
            (username.strip(), _hash(password, salt), salt, role, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return True, "User created."
    except Exception as e:
        if "UNIQUE" in str(e):
            return False, "That username already exists."
        return False, str(e)
    finally:
        conn.close()


def change_password(user_id: int, new_password: str):
    salt = secrets.token_hex(16)
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET password_hash=?, salt=? WHERE id=?", (_hash(new_password, salt), salt, user_id))
        conn.commit()
    finally:
        conn.close()


def logout():
    for k in ["user", "auth_ok"]:
        st.session_state.pop(k, None)
    st.rerun()


def is_logged_in() -> bool:
    return bool(st.session_state.get("auth_ok") and st.session_state.get("user"))


def render_login_screen():
    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        with st.container(border=True):
            if config.LOGO_PATH.exists():
                st.image(str(config.LOGO_PATH), width=180)
            from auth.activation import get_distribution_name
            distro = get_distribution_name()
            st.markdown(
                f'<div class="b-auth-title">Sign in</div>'
                f'<div class="b-auth-sub">{distro or config.APP_NAME}</div>',
                unsafe_allow_html=True,
            )

            with st.form("login_form"):
                username = st.text_input("Username", placeholder="admin")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Sign in", width='stretch')

            st.caption("Default demo login — username: `admin`, password: `bottler123`")

    if submitted:
        user = verify_login(username, password)
        if user:
            st.session_state["auth_ok"] = True
            st.session_state["user"] = {"id": user["id"], "username": user["username"], "role": user["role"]}
            st.success(f"✅ Welcome back, {user['username']}.")
            st.rerun()
        else:
            st.error("❌ Incorrect username or password.")
