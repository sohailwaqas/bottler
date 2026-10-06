"""modules/packaging_materials/manage_materials.py"""
import streamlit as st

from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error
from components.tables import styled_table


def render():
    with section_card("Add Packaging Material"):
        with st.form("add_material_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Material Name", placeholder="e.g. Crates")
            with c2:
                unit = st.text_input("Unit", value="pcs")
            ok = st.form_submit_button("OK — Add Material", type="primary", width='stretch')
        if ok:
            if not name.strip():
                toast_error("Material name is required.")
            else:
                try:
                    q.add_material(name.strip(), unit.strip() or "pcs")
                    toast_success(f"Material '{name}' added.")
                    st.rerun()
                except Exception as e:
                    toast_error(f"Could not add material (maybe it already exists): {e}")

    with section_card("Packaging Materials Master List"):
        df = q.get_materials_df()
        if df.empty:
            st.caption("No materials yet.")
            return
        styled_table(df[["name", "unit", "stock_qty"]].rename(
            columns={"name": "Material", "unit": "Unit", "stock_qty": "Stock"}))

        st.markdown("**Edit / Delete a Material**")
        chosen = st.selectbox("Select Material", df["name"].tolist(), key="manage_material_select")
        row = df[df["name"] == chosen].iloc[0]
        with st.expander(f"Edit '{chosen}'"):
            with st.form("edit_material_form"):
                e_name = st.text_input("Name", value=row["name"])
                e_unit = st.text_input("Unit", value=row["unit"])
                save = st.form_submit_button("Save Changes", type="primary")
            if save:
                q.update_material(int(row["id"]), name=e_name, unit=e_unit)
                toast_success("Material updated.")
                st.rerun()

        confirm = st.checkbox(f"I confirm I want to delete '{chosen}'", key="material_delete_confirm")
        if st.button("🗑️ Delete Material", disabled=not confirm):
            q.delete_material(int(row["id"]))
            toast_success("Material deleted.")
            st.rerun()
