"""modules/packaging_materials/adjust.py"""
from datetime import date
import streamlit as st

import config
from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error
from components.tables import styled_table
from components.filters import date_range_picker, apply_filters_row


def render():
    materials = q.get_materials_df()
    if materials.empty:
        st.info("Add a packaging material first (Manage Materials tab).")
        return

    with section_card("Adjust Packaging Material Stock"):
        with st.form("pm_adjust_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                a_date = st.date_input("Date", value=date.today())
            with c2:
                material_name = st.selectbox("Material", materials["name"].tolist())
            c3, c4 = st.columns(2)
            with c3:
                adj_type = st.radio("Type", ["Increase", "Decrease"], horizontal=True)
            with c4:
                qty = st.number_input("Quantity", min_value=1, value=5)
            reason = st.selectbox("Reason", config.PACKAGING_ADJUST_REASONS)
            submitted = st.form_submit_button("Apply Adjustment", type="primary", width='stretch')

        if submitted:
            material_id = int(materials[materials["name"] == material_name].iloc[0]["id"])
            try:
                q.create_packaging_adjustment(a_date.isoformat(), material_id, adj_type, qty, reason)
                toast_success(f"{adj_type} of {qty} {material_name} applied.")
                st.rerun()
            except Exception as e:
                toast_error(f"Could not apply adjustment: {e}")

    with section_card("Adjustments History"):
        start, end = date_range_picker("pm_adj_hist", default_days=60)
        df = q.get_packaging_adjustments_df(start, end)
        if not df.empty:
            df = df.rename(columns={"date": "Date", "material": "Material", "adjustment_type": "Type",
                                     "quantity": "Quantity", "reason": "Reason"})
            df = apply_filters_row(df, ["Material", "Type", "Reason"], key_prefix="pmadjhist")
        styled_table(df)
