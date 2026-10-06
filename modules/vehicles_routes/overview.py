"""modules/vehicles_routes/overview.py"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from database import queries as q
from components.kpi_card import kpi_row, section_card, empty_state
from components.filters import date_range_picker


def render():
    vehicles = q.get_vehicles_df()
    routes = q.get_routes_df()

    kpi_row([
        {"icon": "🚚", "label": "Active Vehicles", "value": len(vehicles), "status": "primary"},
        {"icon": "🛣️", "label": "Active Routes", "value": len(routes), "status": "primary"},
    ])
    st.write("")

    with section_card("Sales by Vehicle & Route", "Cases sold in the selected date range."):
        start, end = date_range_picker("vr_overview", default_days=30)
        sales = q.get_sales_df(start, end)
        if sales.empty:
            empty_state("No sales in this range", "Record sales from Sales > New Sale to see breakdowns here.", "🚚")
            return

        c1, c2 = st.columns(2)
        with c1:
            by_vehicle = sales.groupby("vehicle")["quantity"].sum().reset_index().sort_values("quantity", ascending=True)
            fig1 = go.Figure(go.Bar(x=by_vehicle["quantity"], y=by_vehicle["vehicle"], orientation="h",
                                     marker_color=config.COLORS["primary"]))
            fig1.update_layout(height=340, title="Cases Sold by Vehicle", xaxis_title="Cases")
            st.plotly_chart(fig1, width='stretch')
        with c2:
            by_route = sales.groupby("route")["quantity"].sum().reset_index().sort_values("quantity", ascending=True)
            fig2 = go.Figure(go.Bar(x=by_route["quantity"], y=by_route["route"], orientation="h",
                                     marker_color=config.COLORS["ok"]))
            fig2.update_layout(height=340, title="Cases Sold by Route", xaxis_title="Cases")
            st.plotly_chart(fig2, width='stretch')
