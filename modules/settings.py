"""modules/settings.py — Backup & Restore, and User administration."""
import streamlit as st

from database import queries as q
from database.db import get_connection
from auth import login
from utils import backup_utils
from components.kpi_card import section_card, toast_success, toast_error, empty_state
from components.tables import styled_table


def render_backup_restore():
    with section_card("Backup & Restore", "Manual backups, plus an automatic daily backup on app start."):
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("📦 Backup Now", type="primary", width='stretch'):
                path = backup_utils.run_backup(reason="manual")
                if path:
                    toast_success(f"Backup created: {path.name}")
                    st.rerun()
                else:
                    toast_error("Backup failed — check the database file exists.")

        backups = backup_utils.list_backups()
        if not backups:
            empty_state("No backups yet", "Click 'Backup Now' to create your first backup.", "📦")
        else:
            import pandas as pd
            df = pd.DataFrame(backups)[["file", "size_kb", "created"]].rename(
                columns={"file": "File", "size_kb": "Size (KB)", "created": "Created"})
            styled_table(df)

            st.markdown("**Restore from Backup**")
            chosen = st.selectbox("Select a backup to restore", [b["file"] for b in backups])
            confirm = st.checkbox("I understand this will overwrite the current database (a safety snapshot will be taken first).")
            if st.button("♻️ Restore Selected Backup", disabled=not confirm):
                chosen_path = next(b["path"] for b in backups if b["file"] == chosen)
                ok = backup_utils.restore_backup(chosen_path)
                if ok:
                    q.clear_all_caches()
                    toast_success("Database restored. Please refresh the app.")
                else:
                    toast_error("Restore failed — the backup file may be corrupted.")


def render_users():
    user = st.session_state.get("user", {})
    with section_card("Users", "Admin-only: manage who can log in to Bottler."):
        if user.get("role") != "Admin":
            st.info("Only Admin users can manage other accounts. You can still change your own password below.")
        else:
            with st.form("add_user_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    username = st.text_input("Username")
                with c2:
                    password = st.text_input("Password", type="password")
                with c3:
                    role = st.selectbox("Role", ["Operator", "Admin"])
                ok = st.form_submit_button("OK — Create User", type="primary", width='stretch')
            if ok:
                if not username.strip() or not password:
                    toast_error("Username and password are required.")
                else:
                    success, msg = login.create_user(username, password, role)
                    if success:
                        toast_success(msg)
                        st.rerun()
                    else:
                        toast_error(msg)

            with get_connection() as conn:
                import pandas as pd
                users_df = pd.read_sql_query("SELECT username, role, is_active, created_at FROM users", conn)
            styled_table(users_df.rename(columns={"username": "Username", "role": "Role", "is_active": "Active",
                                                   "created_at": "Created"}))

        st.markdown("**Change My Password**")
        with st.form("change_pw_form", clear_on_submit=True):
            new_pw = st.text_input("New Password", type="password")
            change = st.form_submit_button("Update Password", type="primary")
        if change:
            if not new_pw:
                toast_error("Enter a new password.")
            else:
                login.change_password(user["id"], new_pw)
                toast_success("Password updated.")
