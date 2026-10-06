"""modules/losses/market_lifting.py — leaked/burst/expired stock lifted back from the market."""
from datetime import date
import streamlit as st

from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error

LIFTING_TYPES = ["Leakage", "Burst", "Expired"]


def render():
    skus = q.get_sku_options()
    with section_card("New Market Lifting", "Record inventory-only stock lifted back from the market."):
        if skus.empty:
            st.warning("No SKUs available — add one from Inventory first.")
            return

        with st.form("market_lifting_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                l_date = st.date_input("Date", value=date.today())
            with c2:
                loss_type = st.selectbox("Loss Type", LIFTING_TYPES)
            label = st.selectbox("SKU", skus["label"].tolist())
            quantity = st.number_input("Quantity", min_value=1, value=1)
            note = st.text_area("Note", height=70, placeholder="Optional context…")
            submitted = st.form_submit_button("Log Market Lifting", type="primary", width='stretch')

        if submitted:
            sku_id = int(skus[skus["label"] == label].iloc[0]["id"])
            try:
                q.create_market_lifting(l_date.isoformat(), sku_id, loss_type, quantity, note or None)
                toast_success("Market lifting logged.")
                st.rerun()
            except Exception as e:
                toast_error(f"Could not log market lifting: {e}")
