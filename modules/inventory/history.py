"""modules/inventory/history.py — Stock Movements."""
import streamlit as st

from database import queries as q
from components.kpi_card import section_card
from components.tables import styled_table
from components.filters import date_range_picker, apply_filters_row


def render():
    with section_card("Stock Movements", "Every IN/OUT transaction, sourced from purchases, sales, adjustments and losses."):
        start, end = date_range_picker("inv_hist", default_days=30)
        df = q.get_stock_movements_df(start, end)
        if not df.empty:
            df = df.rename(columns={"date": "Date", "sku": "SKU", "type": "Type", "reference": "Reference",
                                     "quantity": "Quantity", "notes": "Notes"})
            df = apply_filters_row(df, ["SKU", "Type", "Reference"], key_prefix="stockmove")
        styled_table(df, empty_title="No stock movements in this range")
