"""modules/losses/quota_vs_actual.py"""
from datetime import date, timedelta
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from database import queries as q
from utils.conversions import raw_case_1l_pet_equivalent, package_to_ml
from components.kpi_card import section_card, kpi_row, toast_success, empty_state


def _actual_loss_cases_by_month(months: list[str]) -> dict:
    skus = q.get_skus_df(include_inactive=True).set_index("id")
    losses = q.get_losses_df()
    liftings = q.get_market_liftings_df()

    result = {m: 0.0 for m in months}

    # Re-query with sku_id (raw tables) for accurate per-SKU normalization.
    from database.db import get_connection
    conn = get_connection()
    li_df = pd.read_sql_query(
        "SELECT date, sku_id, quantity FROM loss_incidents WHERE source='Inventory Management' AND sku_id IS NOT NULL",
        conn)
    ml_df = pd.read_sql_query("SELECT date, sku_id, quantity FROM market_liftings", conn)
    conn.close()

    combined = pd.concat([li_df, ml_df], ignore_index=True) if not (li_df.empty and ml_df.empty) else pd.DataFrame(columns=["date", "sku_id", "quantity"])
    if combined.empty:
        return result

    combined["month"] = combined["date"].str.slice(0, 7)
    for _, row in combined.iterrows():
        m = row["month"]
        if m not in result or row["sku_id"] not in skus.index:
            continue
        sku_row = skus.loc[row["sku_id"]]
        ml = package_to_ml(sku_row["package"])
        cases_1l = raw_case_1l_pet_equivalent(row["quantity"], int(sku_row["units_per_case"]), ml)
        result[m] += cases_1l
    return result


def render():
    quotas = q.get_loss_quotas_df()

    with section_card("Quota vs. Actual", "1L-PET-equivalent monthly loss allowance vs. actual Log Incident + Market Lifting losses."):
        months_back = st.slider("Months to compare", min_value=3, max_value=12, value=6, key="quota_months")
        month_list = [(date.today().replace(day=1) - timedelta(days=30 * i)).strftime("%Y-%m") for i in range(months_back)][::-1]

        actual = _actual_loss_cases_by_month(month_list)
        quota_map = dict(zip(quotas["month"], quotas["quota_cases_1l_pet"])) if not quotas.empty else {}

        quota_vals = [quota_map.get(m, 0.0) for m in month_list]
        actual_vals = [actual.get(m, 0.0) for m in month_list]
        overage = [a > q_ and q_ > 0 for a, q_ in zip(actual_vals, quota_vals)]
        colors = [config.COLORS["critical"] if ov else config.COLORS["ok"] for ov in overage]

        fig = go.Figure()
        fig.add_bar(x=month_list, y=actual_vals, name="Actual Loss (1L-PET cases)", marker_color=colors)
        fig.add_scatter(x=month_list, y=quota_vals, name="Quota", mode="lines+markers",
                         line=dict(color=config.COLORS["text_muted"], dash="dash"))
        fig.update_layout(height=380, yaxis_title="1L-PET-equivalent cases")
        st.plotly_chart(fig, width='stretch')

        this_month = date.today().strftime("%Y-%m")
        this_quota = quota_map.get(this_month, 0.0)
        this_actual = actual.get(this_month, 0.0)
        status = "critical" if this_quota and this_actual > this_quota else "ok"
        kpi_row([
            {"icon": "🎯", "label": f"Quota — {this_month}", "value": f"{this_quota:,.1f} cases", "status": "primary"},
            {"icon": "📉", "label": f"Actual Loss — {this_month}", "value": f"{this_actual:,.1f} cases", "status": status},
        ])

    with section_card("Set Loss Quota For A Month"):
        with st.form("set_quota_form"):
            c1, c2 = st.columns(2)
            with c1:
                month = st.text_input("Month (YYYY-MM)", value=this_month)
            with c2:
                quota_val = st.number_input("Quota (1L-PET-equivalent cases)", min_value=0.0, value=25.0, step=1.0)
            notes = st.text_input("Notes", placeholder="Optional")
            save = st.form_submit_button("Save Quota", type="primary", width='stretch')
        if save:
            q.set_monthly_loss_quota(month, quota_val, notes or None)
            toast_success(f"Quota for {month} set to {quota_val:.1f} cases.")
            st.rerun()
