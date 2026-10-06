"""modules/packaging_materials/purchase.py"""
from datetime import date
import streamlit as st

from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error


def render():
    materials = q.get_materials_df()
    if materials.empty:
        st.info("Add a packaging material first (Manage Materials tab).")
        return

    with section_card("Record Packaging Material Purchase"):
        with st.form("pm_purchase_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                p_date = st.date_input("Date", value=date.today())
            with c2:
                material_name = st.selectbox("Material", materials["name"].tolist())
            with c3:
                qty = st.number_input("Quantity", min_value=1, value=10)
            note = st.text_input("Note", placeholder="Optional")
            submitted = st.form_submit_button("Record Purchase", type="primary", width='stretch')

        if submitted:
            material_id = int(materials[materials["name"] == material_name].iloc[0]["id"])
            try:
                q.create_packaging_purchase(p_date.isoformat(), material_id, qty, note or None)
                toast_success(f"Recorded purchase of {qty} {material_name}.")
                st.rerun()
            except Exception as e:
                toast_error(f"Could not record purchase: {e}")

    with section_card("Recent Packaging Purchases"):
        df = q.get_packaging_purchases_df()
        if df.empty:
            st.caption("No packaging purchases recorded yet.")
        else:
            st.dataframe(df.head(50), width='stretch', hide_index=True)
