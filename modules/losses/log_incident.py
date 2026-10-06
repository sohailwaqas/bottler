"""modules/losses/log_incident.py"""
from datetime import date
import streamlit as st

import config
from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error


def render():
    skus = q.get_sku_options()
    materials = q.get_materials_df()

    with section_card("New Log Incident"):
        source = st.radio("Source", config.LOSS_SOURCES, horizontal=True, key="loss_source_radio")

        with st.form("log_incident_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                l_date = st.date_input("Date", value=date.today())
            with c2:
                loss_type = st.selectbox("Loss Type", config.LOSS_TYPES)

            sku_id, material_id = None, None
            if source == "Inventory Management":
                if skus.empty:
                    st.warning("No SKUs available — add one from Inventory first.")
                else:
                    label = st.selectbox("SKU", skus["label"].tolist())
                    sku_id = int(skus[skus["label"] == label].iloc[0]["id"])
            else:
                if materials.empty:
                    st.warning("No packaging materials available — add one first.")
                else:
                    mname = st.selectbox("Material", materials["name"].tolist())
                    material_id = int(materials[materials["name"] == mname].iloc[0]["id"])

            quantity = st.number_input("Quantity", min_value=1, value=1)
            note = st.text_area("Note", height=70, placeholder="Optional context…")
            submitted = st.form_submit_button("Log Incident", type="primary", width='stretch')

        if submitted:
            if source == "Inventory Management" and sku_id is None:
                toast_error("Select a SKU to log this incident.")
            elif source == "Packaging Material" and material_id is None:
                toast_error("Select a material to log this incident.")
            else:
                try:
                    q.create_loss_incident(l_date.isoformat(), source, loss_type, quantity,
                                            sku_id=sku_id, material_id=material_id, notes=note or None)
                    toast_success("Incident logged.")
                    st.rerun()
                except Exception as e:
                    toast_error(f"Could not log incident: {e}")
