"""modules/vehicles_routes/manage.py"""
import streamlit as st

from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error
from components.tables import styled_table


def render():
    col1, col2 = st.columns(2)

    with col1, section_card("Vehicles"):
        with st.form("add_vehicle_form", clear_on_submit=True):
            name = st.text_input("Vehicle Name", placeholder="e.g. LED-1234")
            plate = st.text_input("Plate No. (optional)")
            ok = st.form_submit_button("OK — Add Vehicle", type="primary", width='stretch')
        if ok:
            if not name.strip():
                toast_error("Vehicle name is required.")
            else:
                try:
                    q.add_vehicle(name.strip(), plate.strip() or None)
                    toast_success(f"Vehicle '{name}' added.")
                    st.rerun()
                except Exception as e:
                    toast_error(f"Could not add vehicle: {e}")

        vdf = q.get_vehicles_df()
        styled_table(vdf[["name", "plate_no"]].rename(columns={"name": "Name", "plate_no": "Plate No."}) if not vdf.empty else vdf)
        if not vdf.empty:
            chosen = st.selectbox("Select Vehicle", vdf["name"].tolist(), key="manage_vehicle_select")
            row = vdf[vdf["name"] == chosen].iloc[0]
            with st.expander(f"Edit '{chosen}'"):
                with st.form("edit_vehicle_form"):
                    e_name = st.text_input("Name", value=row["name"])
                    e_plate = st.text_input("Plate No.", value=row["plate_no"] or "")
                    save = st.form_submit_button("Save Changes", type="primary")
                if save:
                    q.update_vehicle(int(row["id"]), name=e_name, plate_no=e_plate or None)
                    toast_success("Vehicle updated.")
                    st.rerun()
            confirm = st.checkbox(f"Confirm delete '{chosen}'", key="vehicle_delete_confirm")
            if st.button("🗑️ Delete Vehicle", disabled=not confirm, key="delete_vehicle_btn"):
                q.delete_vehicle(int(row["id"]))
                toast_success("Vehicle deleted.")
                st.rerun()

    with col2, section_card("Routes"):
        with st.form("add_route_form", clear_on_submit=True):
            rname = st.text_input("Route Name", placeholder="e.g. Route North")
            rok = st.form_submit_button("OK — Add Route", type="primary", width='stretch')
        if rok:
            if not rname.strip():
                toast_error("Route name is required.")
            else:
                try:
                    q.add_route(rname.strip())
                    toast_success(f"Route '{rname}' added.")
                    st.rerun()
                except Exception as e:
                    toast_error(f"Could not add route: {e}")

        rdf = q.get_routes_df()
        styled_table(rdf[["name"]].rename(columns={"name": "Name"}) if not rdf.empty else rdf)
        if not rdf.empty:
            rchosen = st.selectbox("Select Route", rdf["name"].tolist(), key="manage_route_select")
            rrow = rdf[rdf["name"] == rchosen].iloc[0]
            with st.expander(f"Edit '{rchosen}'"):
                with st.form("edit_route_form"):
                    e_rname = st.text_input("Name", value=rrow["name"])
                    rsave = st.form_submit_button("Save Changes", type="primary")
                if rsave:
                    q.update_route(int(rrow["id"]), name=e_rname)
                    toast_success("Route updated.")
                    st.rerun()
            rconfirm = st.checkbox(f"Confirm delete '{rchosen}'", key="route_delete_confirm")
            if st.button("🗑️ Delete Route", disabled=not rconfirm, key="delete_route_btn"):
                q.delete_route(int(rrow["id"]))
                toast_success("Route deleted.")
                st.rerun()
