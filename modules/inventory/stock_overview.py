"""modules/inventory/stock_overview.py"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from database import queries as q
from components.kpi_card import kpi_row, section_card, empty_state
from components.tables import status_from_stock, styled_table
from components.filters import apply_filters_row, date_range_picker
from components.charts import colors_for_statuses


def _status_label(row):
    if row["stock_qty"] <= 0:
        return "Out of Stock"
    if row["stock_qty"] <= row["reorder_threshold"]:
        return "Low Stock"
    return "OK"


def render():
    df = q.get_skus_df()
    if df.empty:
        empty_state("No SKUs yet", "Add your first SKU from the Manage SKUs tab to get started.", "🍾")
        return

    df = df.copy()
    df["margin"] = (df["selling_price"] - df["cost_price"]).round(1)
    df["stock_value_cost"] = df["stock_qty"] * df["cost_price"]
    df["status"] = df.apply(_status_label, axis=1)

    near_expiry = q.get_near_expiry_df()

    total_skus = len(df)
    total_cases = int(df["stock_qty"].sum())
    total_value = df["stock_value_cost"].sum()
    low_stock = int((df["status"] == "Low Stock").sum())
    out_of_stock = int((df["status"] == "Out of Stock").sum())
    near_expiry_cases = int(near_expiry["quantity"].sum()) if not near_expiry.empty else 0

    kpi_row([
        {"icon": "📦", "label": "Total SKUs", "value": total_skus, "status": "primary"},
        {"icon": "🔢", "label": "Total Cases", "value": f"{total_cases:,}", "status": "primary"},
        {"icon": "💰", "label": "Stock Value (Cost)", "value": f"Rs. {total_value:,.0f}", "status": "primary"},
        {"icon": "⚠️", "label": "Low Stock SKUs", "value": low_stock, "status": "warning" if low_stock else "ok"},
        {"icon": "🔴", "label": "Out of Stock SKUs", "value": out_of_stock, "status": "critical" if out_of_stock else "ok"},
        {"icon": "🔶", "label": "Near-Expiry Cases", "value": near_expiry_cases, "status": "caution" if near_expiry_cases else "ok"},
    ])

    st.write("")
    with section_card("Stock Levels", "All SKUs, sorted lowest stock first; bars colored by status, dashed line marks each SKU's reorder threshold."):
        # Show every SKU (not just a subset) - height scales with the SKU
        # count so labels stay legible instead of being crushed into a
        # fixed-size chart.
        plot_df = df.sort_values("stock_qty", ascending=True).copy()
        status_map = {"OK": "ok", "Low Stock": "warning", "Out of Stock": "critical"}
        colors = colors_for_statuses([status_map[s] for s in plot_df["status"]])
        plot_df["label"] = plot_df["brand"] + " " + plot_df["package"]
        # A SKU at 0 (or very low) stock draws a bar so short it's visually
        # indistinguishable from "missing entirely" - which is exactly
        # backwards for a chart whose job is to surface stock problems. Give
        # every bar a small minimum visible height purely for rendering;
        # the text label and hover always show the real value, so nothing
        # is misrepresented, it's just never invisible.
        max_stock = plot_df["stock_qty"].max() if not plot_df.empty else 0
        floor = max(max_stock * 0.015, 2)
        display_heights = plot_df["stock_qty"].clip(lower=floor)
        fig = go.Figure()
        fig.add_bar(x=plot_df["label"], y=display_heights, marker_color=colors, name="Stock (cases)",
                    text=plot_df["stock_qty"].map(lambda v: f"{v:,.0f}"), textposition="outside",
                    textfont=dict(size=10), cliponaxis=False,
                    hovertemplate="%{x}<br>Stock: %{text} cases<extra></extra>")
        fig.add_scatter(x=plot_df["label"], y=plot_df["reorder_threshold"], mode="lines+markers",
                         line=dict(color=config.COLORS["text_muted"], dash="dash", width=1.5),
                         marker=dict(size=4), name="Reorder threshold")
        fig.update_layout(height=max(460, len(plot_df) * 16), xaxis_tickangle=-40, yaxis_title="Cases in stock",
                           legend=dict(orientation="h", y=1.02), margin=dict(t=60))
        st.plotly_chart(fig, width='stretch')

    with section_card("Fast vs. Slow Movers", "Every SKU sold in the selected range, ranked by units sold."):
        start, end = date_range_picker("movers", default_days=30)
        sales = q.get_sales_df(start_date=start, end_date=end)
        if sales.empty:
            empty_state("No sales in this range", "Movement ranking will appear once sales are recorded.", "📉")
        else:
            movers = sales.groupby(["brand", "package"])["quantity"].sum().reset_index()
            movers["label"] = movers["brand"] + " " + movers["package"]
            movers = movers.sort_values("quantity", ascending=True)
            fig2 = go.Figure(go.Bar(x=movers["quantity"], y=movers["label"], orientation="h",
                                     marker_color=config.COLORS["primary"]))
            fig2.update_layout(height=max(380, len(movers) * 20), xaxis_title="Cases sold (selected range)",
                                margin=dict(l=10))
            st.plotly_chart(fig2, width='stretch')

    with section_card("Stock Status", "Filter by category, brand, pack, or status."):
        display_df = df[["brand", "category", "package", "pack_type", "units_per_case", "cost_price",
                          "selling_price", "margin", "stock_qty", "reorder_threshold", "status"]].rename(
            columns={"brand": "Brand", "category": "Category", "package": "Pack", "pack_type": "Pack Type",
                     "units_per_case": "Units/Case", "cost_price": "Cost Price", "selling_price": "Selling Price",
                     "margin": "Margin (Rs.)", "stock_qty": "Stock", "reorder_threshold": "Reorder Level",
                     "status": "Status"})
        filtered = apply_filters_row(display_df, ["Category", "Brand", "Pack", "Status"], key_prefix="stockstatus")
        styled_table(filtered)

    with section_card("Near-Expiry Stock", "Batches falling inside each SKU's expiry threshold window."):
        if near_expiry.empty:
            empty_state("Nothing near expiry", "No batches are currently inside their expiry threshold window.", "✅")
        else:
            ne = near_expiry.rename(columns={"brand": "Brand", "category": "Category", "package": "Pack",
                                              "expiry_threshold_days": "Expiry Threshold (days)",
                                              "quantity": "Quantity", "expiry_date": "Expiry Date"})
            ne = ne[["Brand", "Category", "Pack", "Expiry Threshold (days)", "Quantity", "Expiry Date"]]
            filtered_ne = apply_filters_row(ne, ["Category", "Brand", "Pack"], key_prefix="nearexpiry")
            styled_table(filtered_ne)
