"""modules/targets_incentives/wholesale_cap_monitor.py"""
from datetime import date
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from database import queries as q
from components.kpi_card import section_card, empty_state, status_badge
from components.tables import styled_table
from components.filters import month_picker, month_date_bounds


def render():
    caps = q.get_wholesale_caps_df()
    with section_card("Wholesale Cap Monitor", "Flags packs where wholesale sales exceed their allowed % of total sales for the month."):
        if caps.empty:
            empty_state("No wholesale caps configured", "Set caps from the 'Set Targets / Caps' tab.", "🏬")
            return

        month = month_picker("wcm_month")
        start, end = month_date_bounds(month)
        sales = q.get_sales_df(start_date=start, end_date=end)
        month_caps = caps[caps["month"] == month]

        if month_caps.empty:
            empty_state(f"No caps configured for {month}", "Set one from the 'Set Targets / Caps' tab.", "🏬")
            return

        rows = []
        for _, cap in month_caps.iterrows():
            pack_sales = sales[sales["package"] == cap["pack"]]
            if cap["brand"] != "All":
                pack_sales = pack_sales[pack_sales["brand"] == cap["brand"]]
            total_cases = pack_sales["quantity"].sum()
            wholesale_cases = pack_sales[pack_sales["type"] == "Wholesale"]["quantity"].sum()
            wholesale_pct = (wholesale_cases / total_cases * 100) if total_cases else 0.0
            exceeded = wholesale_pct > cap["cap_pct"]
            rows.append({
                "Pack": cap["pack"], "Brand": cap["brand"], "Cap %": cap["cap_pct"],
                "Wholesale %": round(wholesale_pct, 1), "Total Cases": int(total_cases),
                "Wholesale Cases": int(wholesale_cases),
                "Status": "🔴 Exceeded" if exceeded else "✅ Within Cap",
            })

        df = pd.DataFrame(rows)
        styled_table(df)

        fig = go.Figure()
        colors = [config.COLORS["critical"] if "Exceeded" in s else config.COLORS["ok"] for s in df["Status"]]
        fig.add_bar(x=df["Pack"], y=df["Wholesale %"], marker_color=colors, name="Wholesale %")
        fig.add_scatter(x=df["Pack"], y=df["Cap %"], mode="markers+lines",
                         line=dict(color=config.COLORS["text_muted"], dash="dash"), name="Cap %")
        fig.update_layout(height=360, yaxis_title="Wholesale % of total sales")
        st.plotly_chart(fig, width='stretch')
