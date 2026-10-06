"""modules/losses/history.py"""
import streamlit as st

from database import queries as q
from components.kpi_card import section_card
from components.tables import styled_table
from components.filters import date_range_picker, apply_filters_row


def render():
    with section_card("Loss & Market Lifting History", "Combined view of Log Incident and Market Lifting entries."):
        start, end = date_range_picker("loss_hist", default_days=60)
        df = q.get_combined_loss_history_df(start, end)
        if not df.empty:
            df = df.rename(columns={"date": "Date", "log_type": "Log Type", "source": "Source",
                                     "loss_type": "Loss Type", "sku_or_material": "SKU / Material",
                                     "quantity": "Quantity", "notes": "Notes"})
            df = apply_filters_row(df, ["Log Type", "Source", "Loss Type"], key_prefix="losshist")
        styled_table(df, empty_title="No losses recorded in this range")
