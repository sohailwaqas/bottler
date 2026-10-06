"""modules/inventory/manage_sku.py"""
import streamlit as st

import config
from database import queries as q
from components.kpi_card import section_card, toast_success, toast_error
from components.tables import styled_table
from components.filters import apply_filters_row


def render():
    with section_card("Add SKU"):
        with st.form("add_sku_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                brand = st.text_input("Brand")
            with c2:
                package = st.text_input("Package", placeholder="e.g. 500 ML PET")
            with c3:
                category = st.text_input("Category", placeholder="e.g. CSD")
            c4, c5, c6 = st.columns(3)
            with c4:
                units_per_case = st.number_input("Units Per Case", min_value=1, value=24)
            with c5:
                reorder_threshold = st.number_input("Reorder Threshold", min_value=0, value=20)
            with c6:
                pack_type = st.selectbox("Pack Type", config.PACK_TYPES)
            c7, c8, c9 = st.columns(3)
            with c7:
                cost_price = st.number_input("Cost Price", min_value=0.0, value=50.0, step=1.0)
            with c8:
                selling_price = st.number_input("Selling Price", min_value=0.0, value=60.0, step=1.0)
            with c9:
                expiry_days = st.number_input("Expiry Threshold (days)", min_value=1, value=60)
            ok = st.form_submit_button("OK — Add SKU", type="primary", width='stretch')

        if ok:
            if not brand.strip() or not package.strip() or not category.strip():
                toast_error("Brand, Package, and Category are required.")
            else:
                q.add_sku(brand.strip(), package.strip(), category.strip(), units_per_case, reorder_threshold,
                           pack_type, cost_price, selling_price, expiry_days)
                toast_success(f"SKU '{brand} — {package}' added.")
                st.rerun()

    with section_card("SKU Master List", "Edit inline via the expander, or delete with confirmation."):
        df = q.get_skus_df()
        if df.empty:
            st.caption("No SKUs yet.")
            return

        display = df[["brand", "category", "package", "pack_type", "units_per_case", "reorder_threshold",
                       "cost_price", "selling_price", "stock_qty"]].rename(columns={
            "brand": "Brand", "category": "Category", "package": "Pack", "pack_type": "Pack Type",
            "units_per_case": "Units/Case", "reorder_threshold": "Reorder Level", "cost_price": "Cost Price",
            "selling_price": "Selling Price", "stock_qty": "Stock"})
        filtered = apply_filters_row(display, ["Category", "Brand", "Pack Type"], key_prefix="skumaster")
        styled_table(filtered)

        st.markdown("**Edit / Delete a SKU**")
        df["label"] = df["brand"] + " — " + df["package"]
        chosen_label = st.selectbox("Select SKU", df["label"].tolist(), key="manage_sku_select")
        row = df[df["label"] == chosen_label].iloc[0]

        with st.expander(f"Edit '{chosen_label}'", expanded=False):
            with st.form("edit_sku_form"):
                e1, e2, e3 = st.columns(3)
                with e1:
                    e_brand = st.text_input("Brand", value=row["brand"])
                with e2:
                    e_package = st.text_input("Package", value=row["package"])
                with e3:
                    e_category = st.text_input("Category", value=row["category"])
                e4, e5, e6 = st.columns(3)
                with e4:
                    e_units = st.number_input("Units Per Case", min_value=1, value=int(row["units_per_case"]))
                with e5:
                    e_reorder = st.number_input("Reorder Threshold", min_value=0, value=int(row["reorder_threshold"]))
                with e6:
                    e_pack_type = st.selectbox("Pack Type", config.PACK_TYPES,
                                                index=config.PACK_TYPES.index(row["pack_type"]) if row["pack_type"] in config.PACK_TYPES else 0)
                e7, e8 = st.columns(2)
                with e7:
                    e_cost = st.number_input("Cost Price", min_value=0.0, value=float(row["cost_price"]))
                with e8:
                    e_selling = st.number_input("Selling Price", min_value=0.0, value=float(row["selling_price"]))
                save = st.form_submit_button("Save Changes", type="primary")
            if save:
                q.update_sku(int(row["id"]), brand=e_brand, package=e_package, category=e_category,
                             units_per_case=e_units, reorder_threshold=e_reorder, pack_type=e_pack_type,
                             cost_price=e_cost, selling_price=e_selling)
                toast_success("SKU updated.")
                st.rerun()

        confirm = st.checkbox(f"I confirm I want to delete '{chosen_label}'", key="sku_delete_confirm")
        if st.button("🗑️ Delete SKU", disabled=not confirm):
            q.delete_sku(int(row["id"]))
            toast_success("SKU deleted.")
            st.rerun()
