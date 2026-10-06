"""modules/sales/new_sale.py — sales recorded per vehicle load, not per shop."""
from datetime import date
import streamlit as st

import config
from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error, empty_state
from components.cart import get_cart, add_to_cart, render_cart_table, clear_cart

CART_KEY = "sale_cart"


def _cart_qty_for_sku(cart, sku_id: int) -> int:
    return sum(i["quantity"] for i in cart if i.get("sku_id") == sku_id)


def render():
    all_skus = q.get_sku_options()
    vehicles = q.get_vehicles_df()
    routes = q.get_routes_df()

    if all_skus.empty:
        st.info("Add at least one SKU before recording a sale.")
        return
    if vehicles.empty or routes.empty:
        st.info("Add at least one Vehicle and Route (Vehicles & Routes tab) before recording a sale.")
        return

    # Out-of-stock SKUs can't be sold at all - excluded from every
    # Category/Brand/Pack dropdown below rather than merely warned about,
    # so there's no way to build an invoice line for something with 0
    # stock in the first place.
    skus = all_skus[all_skus["stock_qty"] > 0]

    with section_card("New Sale", "Sales are recorded per vehicle load, not per shop."):
        if skus.empty:
            empty_state("Nothing in stock to sell", "Every SKU is currently out of stock - restock via Inventory > Purchase first.", "📭")
            return

        out_of_stock_count = len(all_skus) - len(skus)
        if out_of_stock_count:
            st.caption(f"⚠️ {out_of_stock_count} SKU(s) are out of stock and excluded from selection below.")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sale_date = st.date_input("Date", value=date.today(), key="sale_date")
        with c2:
            sale_type = st.radio("Type", config.SALE_TYPES, horizontal=True, key="sale_type")
        with c3:
            vehicle = st.selectbox("Vehicle", vehicles["name"].tolist(), key="sale_vehicle")
        with c4:
            route = st.selectbox("Route", routes["name"].tolist(), key="sale_route")

        # Category/Brand/Pack selectors live outside the form: the Quantity
        # input's max_value needs to react to the currently-selected SKU's
        # available stock immediately, which a form can't do until submit.
        c5, c6, c7 = st.columns(3)
        with c5:
            category = st.selectbox("Category", sorted(skus["category"].unique()), key="sale_category")
        with c6:
            brand_opts = sorted(skus[skus["category"] == category]["brand"].unique())
            brand = st.selectbox("Brand", brand_opts, key="sale_brand")
        with c7:
            pack_opts = sorted(skus[(skus["category"] == category) & (skus["brand"] == brand)]["package"].unique())
            pack = st.selectbox("Pack", pack_opts, key="sale_pack")

        row = skus[(skus["category"] == category) & (skus["brand"] == brand) & (skus["package"] == pack)]
        cart = get_cart(CART_KEY)

        with st.form("add_sale_item", clear_on_submit=True):
            if row.empty:
                st.number_input("Quantity (cases)", min_value=1, value=1, disabled=True, key="sale_qty_disabled")
                available = 0
            else:
                r = row.iloc[0]
                already_in_cart = _cart_qty_for_sku(cart, int(r["id"]))
                available = max(int(r["stock_qty"]) - already_in_cart, 0)
                help_text = (f"{r['stock_qty']:,.0f} in stock" +
                             (f", {already_in_cart:,.0f} already in this invoice" if already_in_cart else ""))
                qty = st.number_input("Quantity (cases)", min_value=1, max_value=max(available, 1),
                                       value=min(5, max(available, 1)), step=1, key="sale_qty", help=help_text)
            added = st.form_submit_button("➕ Add to Invoice", width='stretch')

        if added:
            if row.empty:
                toast_error("Could not resolve that SKU.")
            elif available <= 0:
                toast_error(f"No remaining stock for {brand} — {pack} (all of it is already in this invoice).")
            else:
                r = row.iloc[0]
                add_to_cart(CART_KEY, {
                    "sku_id": int(r["id"]), "SKU": f"{r['brand']} — {r['package']}", "Quantity": qty,
                    "quantity": qty, "Selling Price": r["selling_price"],
                })
                st.rerun()

        render_cart_table(CART_KEY, {"SKU": "SKU", "Quantity": "Quantity (cases)", "Selling Price": "Selling Price"},
                           title="Invoice Items")

        cart = get_cart(CART_KEY)
        if cart:
            total_cases = sum(i["quantity"] for i in cart)
            total_value = sum(i["quantity"] * i["Selling Price"] for i in cart)
            st.caption(f"**{len(cart)}** line item(s) · **{total_cases}** cases · est. value **Rs. {total_value:,.0f}**")
            if st.button("✅ Finalize & Save Invoice", type="primary", width='stretch'):
                # Final safety check in case stock changed (e.g. another
                # sale/adjustment) between adding to cart and finalizing.
                fresh_skus = q.get_skus_df().set_index("id")
                shortfalls = []
                for i in cart:
                    live_stock = fresh_skus.loc[i["sku_id"], "stock_qty"] if i["sku_id"] in fresh_skus.index else 0
                    if i["quantity"] > live_stock:
                        shortfalls.append(f"{i['SKU']} (only {live_stock:,.0f} left)")
                if shortfalls:
                    toast_error("Stock changed since these were added — reduce quantity or remove: " + "; ".join(shortfalls))
                else:
                    items = [{"sku_id": i["sku_id"], "quantity": i["quantity"]} for i in cart]
                    try:
                        inv_id = q.create_sales_invoice(sale_date.isoformat(), sale_type, vehicle, route, items)
                        clear_cart(CART_KEY)
                        toast_success(f"Invoice #{inv_id} saved — stock decremented.")
                        st.rerun()
                    except Exception as e:
                        toast_error(f"Could not save invoice: {e}")
