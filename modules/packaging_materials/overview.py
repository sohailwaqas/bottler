"""modules/packaging_materials/overview.py"""
import plotly.graph_objects as go
import streamlit as st

import config
from database import queries as q
from components.kpi_card import kpi_row, section_card, empty_state

# 🪵 (Unicode 13.0, 2020) rendered as a blank "tofu" box on a user's Windows
# machine whose emoji font hadn't been updated that recently. Map known
# material names to older (Unicode ≤6.0), near-universally-supported icons,
# with a safe fallback for any custom material name added later.
MATERIAL_ICONS = {
    "Pallets": "📦",
    "Empties": "🍾",
    "Plastic Sheets": "📄",
}
DEFAULT_MATERIAL_ICON = "📦"


def render():
    df = q.get_materials_df()
    if df.empty:
        empty_state("No packaging materials yet", "Add Pallets, Plastic Sheets, or Empties from Manage Materials.", "📦")
        return

    kpi_row([
        {"icon": MATERIAL_ICONS.get(row["name"], DEFAULT_MATERIAL_ICON), "label": row["name"],
         "value": f"{row['stock_qty']:,.0f} {row['unit']}", "status": "primary"}
        for _, row in df.iterrows()
    ])

    st.write("")
    with section_card("Current Packaging Material Levels"):
        fig = go.Figure(go.Bar(x=df["name"], y=df["stock_qty"], marker_color=config.COLORS["primary"],
                                text=df["stock_qty"], textposition="outside"))
        fig.update_layout(height=360, yaxis_title="Quantity on hand")
        st.plotly_chart(fig, width='stretch')

