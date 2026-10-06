"""modules/sales/history.py"""
import streamlit as st

from database import queries as q
from components.kpi_card import section_card, kpi_row
from components.tables import styled_table
from components.filters import date_range_picker, apply_filters_row


def render():
    with section_card("Sales History", "Every invoice line item, filterable by vehicle, route, brand, or type."):
        start, end = date_range_picker("sales_hist", default_days=30)
        df = q.get_sales_df(start, end)

        if not df.empty:
            total_cases = df["quantity"].sum()
            total_value = df["line_total"].sum()
            n_invoices = df["invoice_id"].nunique()
            retail_cases = df[df["type"] == "Retail"]["quantity"].sum()
            wholesale_cases = df[df["type"] == "Wholesale"]["quantity"].sum()
            kpi_row([
                {"icon": "📄", "label": "Invoices", "value": n_invoices, "status": "primary"},
                {"icon": "📦", "label": "Cases Sold", "value": f"{total_cases:,.0f}", "status": "primary"},
                {"icon": "💰", "label": "Sales Value", "value": f"Rs. {total_value:,.0f}", "status": "primary"},
                {"icon": "🏪", "label": "Retail Cases", "value": f"{retail_cases:,.0f}", "status": "ok"},
                {"icon": "🏬", "label": "Wholesale Cases", "value": f"{wholesale_cases:,.0f}", "status": "caution"},
            ])
            st.write("")

        display = df.rename(columns={"date": "Date", "type": "Type", "vehicle": "Vehicle", "route": "Route",
                                      "category": "Category", "brand": "Brand", "package": "Pack",
                                      "quantity": "Quantity", "selling_price": "Selling Price",
                                      "line_total": "Line Total"}) if not df.empty else df
        if not display.empty:
            display = display[["Date", "Type", "Vehicle", "Route", "Category", "Brand", "Pack",
                                "Quantity", "Selling Price", "Line Total"]]
            display = apply_filters_row(display, ["Type", "Vehicle", "Route", "Category", "Brand"], key_prefix="saleshist")
        styled_table(display, empty_title="No sales in this range")
