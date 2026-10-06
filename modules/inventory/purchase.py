"""modules/inventory/purchase.py — Primary Purchase (From Company)."""
from datetime import date
import streamlit as st

from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error
from components.cart import get_cart, add_to_cart, render_cart_table, clear_cart
from components.tables import styled_table
from components.filters import date_range_picker, apply_filters_row

CART_KEY = "purchase_cart"


def render():
    skus = q.get_sku_options()
    if skus.empty:
        st.info("Add at least one SKU (Manage SKUs tab) before recording a purchase.")
        return

    with section_card("Primary Purchase (From Company)", "Pick a date, add line items, then finalize the order."):
        purchase_date = st.date_input("Purchase Date", value=date.today(), key="purchase_date")

        with st.form("add_purchase_item", clear_on_submit=True):
            c1, c2, c3 = st.columns([3, 1.2, 1.2])
            with c1:
                label = st.selectbox("SKU", skus["label"].tolist(), key="purchase_sku_select")
            with c2:
                qty = st.number_input("Quantity (cases)", min_value=1, value=10, step=1, key="purchase_qty")
            with c3:
                sku_row = skus[skus["label"] == label].iloc[0]
                cost_price = st.number_input("Cost Price / Case", min_value=0.0, value=float(sku_row["cost_price"]),
                                              step=1.0, key="purchase_cost")
            added = st.form_submit_button("➕ Add To Purchase Order", width='stretch')

        if added:
            add_to_cart(CART_KEY, {
                "sku_id": int(sku_row["id"]), "SKU": label, "Quantity": qty,
                "quantity": qty, "Cost Price": cost_price, "cost_price": cost_price,
            })
            st.rerun()

        render_cart_table(CART_KEY, {"SKU": "SKU", "Quantity": "Quantity (cases)", "Cost Price": "Cost Price / Case"},
                           title="Purchase Order Items")

        cart = get_cart(CART_KEY)
        if cart:
            total_cases = sum(i["quantity"] for i in cart)
            total_cost = sum(i["quantity"] * i["cost_price"] for i in cart)
            st.caption(f"**{len(cart)}** line item(s) · **{total_cases}** cases · est. cost **Rs. {total_cost:,.0f}**")
            if st.button("✅ Finalize & Save Purchase", type="primary", width='stretch'):
                items = [{"sku_id": i["sku_id"], "quantity": i["quantity"], "cost_price": i["cost_price"]} for i in cart]
                try:
                    pid = q.create_purchase(purchase_date.isoformat(), items, notes=None)
                    clear_cart(CART_KEY)
                    toast_success(f"Purchase #{pid} saved — stock levels updated.")
                    st.rerun()
                except Exception as e:
                    toast_error(f"Could not save purchase: {e}")

    with section_card("Recent Purchases"):
        start, end = date_range_picker("purchases_hist", default_days=60)
        df = q.get_purchases_df(start, end)
        if df.empty:
            st.caption("No purchases recorded in this range.")
        else:
            display = df.rename(columns={"id": "Purchase #", "date": "Date", "category": "Category",
                                          "brand": "Brand", "package": "Pack", "quantity": "Quantity",
                                          "cost_price": "Cost Price", "notes": "Notes"})
            display = display[["Purchase #", "Date", "Category", "Brand", "Pack", "Quantity", "Cost Price", "Notes"]]
            display = apply_filters_row(display, ["Category", "Brand", "Pack"], key_prefix="purchaseshist")
            styled_table(display)
