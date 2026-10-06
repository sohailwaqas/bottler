"""modules/targets_incentives/set_targets.py"""
from datetime import date
import streamlit as st

from database import queries as q
import config
from components.kpi_card import section_card, toast_success, toast_error
from components.tables import styled_table
from components.filters import valid_month_format

TARGET_SCOPES = config.TARGET_SLAB_SCOPES


def render():
    this_month = date.today().strftime("%Y-%m")

    with section_card("Set Monthly Target & Slabs"):
        st.caption("Base target and slab incentives are earned against primary-purchase volume from the company, not sales.")

        # Scope selectors live OUTSIDE the form: form widgets don't rerun
        # the app until the whole form is submitted, so a "Scope" selector
        # placed inside the form couldn't dynamically reveal the date-range
        # fields below it the moment "Date-Range" is picked. Living outside
        # lets the rest of the form react to the current scope immediately.
        sc1, sc2 = st.columns(2)
        with sc1:
            slab1_scope = st.selectbox("Slab 1 Scope", TARGET_SCOPES, key="s1s")
        with sc2:
            slab2_scope = st.selectbox("Slab 2 Scope", TARGET_SCOPES, key="s2s")

        with st.form("set_target_form"):
            month = st.text_input("Month (YYYY-MM)", value=this_month)
            c1, c2 = st.columns(2)
            with c1:
                target_8oz = st.number_input("Base Target (8oz-equivalent)", min_value=0.0, value=480000.0, step=1000.0)
            with c2:
                incentive_rate = st.number_input("Incentive per Raw Case (Rs.)", min_value=0.0, value=18.0)

            st.markdown(f"**Slab 1** — scope: {slab1_scope}")
            s1c1, s1c2 = st.columns(2)
            with s1c1:
                slab1_target = st.number_input("Slab 1 Target (8oz)", min_value=0.0, value=220000.0, key="s1t")
            with s1c2:
                slab1_rate = st.number_input("Slab 1 Incentive/Case", min_value=0.0, value=20.0, key="s1r")
            if slab1_scope == "Date-Range":
                s1d1, s1d2 = st.columns(2)
                with s1d1:
                    slab1_start = st.date_input("Slab 1 Start Date", value=date.today().replace(day=1), key="s1sd")
                with s1d2:
                    slab1_end = st.date_input("Slab 1 End Date", value=date.today(), key="s1ed")
            else:
                slab1_start, slab1_end = None, None

            st.markdown(f"**Slab 2** — scope: {slab2_scope}")
            s2c1, s2c2 = st.columns(2)
            with s2c1:
                slab2_target = st.number_input("Slab 2 Target (8oz)", min_value=0.0, value=350000.0, key="s2t")
            with s2c2:
                slab2_rate = st.number_input("Slab 2 Incentive/Case", min_value=0.0, value=22.0, key="s2r")
            if slab2_scope == "Date-Range":
                s2d1, s2d2 = st.columns(2)
                with s2d1:
                    slab2_start = st.date_input("Slab 2 Start Date", value=date.today().replace(day=1), key="s2sd")
                with s2d2:
                    slab2_end = st.date_input("Slab 2 End Date", value=date.today(), key="s2ed")
            else:
                slab2_start, slab2_end = None, None

            notes = st.text_area("Notes", height=60, placeholder="Optional")
            save = st.form_submit_button("Save Target", type="primary", width='stretch')

        if save:
            if not valid_month_format(month):
                toast_error("Month must be in YYYY-MM format, e.g. 2026-09.")
            elif slab1_scope == "Date-Range" and slab1_start > slab1_end:
                toast_error("Slab 1 Start Date must be on or before its End Date.")
            elif slab2_scope == "Date-Range" and slab2_start > slab2_end:
                toast_error("Slab 2 Start Date must be on or before its End Date.")
            else:
                try:
                    q.set_monthly_target(
                        month, target_8oz, incentive_rate,
                        slab1_target or None, slab1_rate or None, slab1_scope,
                        slab1_start.isoformat() if slab1_start else None,
                        slab1_end.isoformat() if slab1_end else None,
                        slab2_target or None, slab2_rate or None, slab2_scope,
                        slab2_start.isoformat() if slab2_start else None,
                        slab2_end.isoformat() if slab2_end else None,
                        notes or None,
                    )
                    toast_success(f"Target for {month} saved.")
                    st.rerun()
                except Exception as e:
                    toast_error(f"Could not save target: {e}")

    with section_card("Existing Targets"):
        tdf = q.get_targets_df()
        if not tdf.empty:
            display_cols = ["month", "target_8oz", "incentive_per_case",
                             "slab1_target_8oz", "slab1_incentive_per_case",
                             "slab2_target_8oz", "slab2_incentive_per_case"]
            styled_table(tdf[display_cols].rename(columns={
                "month": "Month", "target_8oz": "Target (8oz)", "incentive_per_case": "Incentive/Case",
                "slab1_target_8oz": "Slab 1 Target", "slab1_incentive_per_case": "Slab 1 Incentive/Case",
                "slab2_target_8oz": "Slab 2 Target", "slab2_incentive_per_case": "Slab 2 Incentive/Case",
            }))
        else:
            st.caption("No targets set yet.")

    with section_card("Set Wholesale Cap"):
        skus = q.get_skus_df()
        if skus.empty:
            st.info("Add at least one SKU (Inventory > Manage SKUs) before configuring a wholesale cap.")
            return
        with st.form("set_cap_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                cap_month = st.text_input("Month (YYYY-MM)", value=this_month, key="cap_month")
            with c2:
                pack = st.selectbox("Pack", sorted(skus["package"].unique()), key="cap_pack")
            with c3:
                brand = st.selectbox("Brand", ["All"] + sorted(skus["brand"].unique().tolist()), key="cap_brand")
            cap_pct = st.number_input("Cap % (max wholesale share)", min_value=0.0, max_value=100.0, value=35.0)
            cap_save = st.form_submit_button("Save Cap", type="primary", width='stretch')
        if cap_save:
            if not valid_month_format(cap_month):
                toast_error("Month must be in YYYY-MM format, e.g. 2026-09.")
            else:
                q.set_wholesale_cap(cap_month, pack, brand, cap_pct)
                toast_success(f"Wholesale cap for {pack} ({brand}) in {cap_month} set to {cap_pct}%.")
                st.rerun()

        cdf = q.get_wholesale_caps_df()
        if not cdf.empty:
            styled_table(cdf[["month", "pack", "brand", "cap_pct"]].rename(
                columns={"month": "Month", "pack": "Pack", "brand": "Brand", "cap_pct": "Cap %"}))
        else:
            st.caption("No wholesale caps configured yet.")
