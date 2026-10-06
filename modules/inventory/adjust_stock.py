"""modules/inventory/adjust_stock.py"""
from datetime import date
import streamlit as st

import config
from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error
from components.tables import styled_table
from components.filters import date_range_picker, apply_filters_row

ADD_REASONS = ["Found", "Return"]
REMOVE_REASONS = ["Burst", "Loss"]


def render():
    skus = q.get_skus_df()
    if skus.empty:
        st.info("Add at least one SKU before adjusting stock.")
        return

    with section_card("Manually Adjust Stock"):
        with st.form("adjust_stock_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                adj_date = st.date_input("Date", value=date.today())
            with c2:
                adj_type = st.radio("Adjustment Type", ["Add Stock (Found/Return)", "Remove Stock (Burst/Loss)"],
                                     horizontal=True)
            adj_type_clean = "Add Stock" if adj_type.startswith("Add") else "Remove Stock"

            c3, c4, c5 = st.columns(3)
            with c3:
                category = st.selectbox("Category", sorted(skus["category"].unique()))
            with c4:
                brand_opts = sorted(skus[skus["category"] == category]["brand"].unique())
                brand = st.selectbox("Brand", brand_opts)
            with c5:
                pkg_opts = sorted(skus[(skus["category"] == category) & (skus["brand"] == brand)]["package"].unique())
                package = st.selectbox("Package", pkg_opts)

            sku_row = skus[(skus["category"] == category) & (skus["brand"] == brand) & (skus["package"] == package)]
            c6, c7 = st.columns(2)
            with c6:
                quantity = st.number_input("Quantity (cases)", min_value=1, value=1, step=1)
            with c7:
                reasons = ADD_REASONS if adj_type_clean == "Add Stock" else REMOVE_REASONS
                reason = st.selectbox("Reason", reasons)
            notes = st.text_area("Notes", placeholder="Optional context…", height=70)
            submitted = st.form_submit_button("Apply Adjustment", type="primary", width='stretch')

        if submitted:
            if sku_row.empty:
                toast_error("Could not resolve a matching SKU for that Category/Brand/Package.")
            else:
                try:
                    q.create_adjustment(adj_date.isoformat(), adj_type_clean, category, brand, package,
                                         int(sku_row.iloc[0]["id"]), quantity, reason, notes or None)
                    toast_success(f"{adj_type_clean} of {quantity} case(s) applied for {brand} {package}.")
                    st.rerun()
                except Exception as e:
                    toast_error(f"Could not apply adjustment: {e}")

    with section_card("Adjustments History"):
        start, end = date_range_picker("adj_hist", default_days=60)
        df = q.get_adjustments_df(start, end)
        if not df.empty:
            df = df.rename(columns={"date": "Date", "category": "Category", "brand": "Brand", "package": "Package",
                                     "adjustment_type": "Adjustment Type", "quantity": "Quantity", "reason": "Reason",
                                     "notes": "Notes"})
            df = apply_filters_row(df, ["Category", "Brand", "Package", "Adjustment Type"], key_prefix="adjhist")
        styled_table(df)
