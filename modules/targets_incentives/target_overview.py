"""modules/targets_incentives/target_overview.py"""
from datetime import date
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from database import queries as q
from utils.conversions import sku_row_to_8oz, incentive_for_achievement
from components.kpi_card import kpi_row, section_card, empty_state
from components.filters import month_picker, month_date_bounds


def _purchased_8oz(start_date: str, end_date: str) -> float:
    """
    8oz-equivalent volume PRIMARY-PURCHASED (from the company) within a date
    range. Targets and incentive slabs are earned against purchase volume,
    not sales volume - a distributor's incentive is for stocking up, not
    for what they've managed to sell on to retailers/wholesalers yet.
    """
    purchases = q.get_purchases_df(start_date=start_date, end_date=end_date)
    if purchases.empty:
        return 0.0
    skus = q.get_skus_df(include_inactive=True).set_index("id")
    total = 0.0
    for _, row in purchases.iterrows():
        if row["sku_id"] not in skus.index:
            continue
        sku_row = skus.loc[row["sku_id"]]
        total += sku_row_to_8oz(row["quantity"], sku_row)
    return total


def _achieved_8oz_for_month(month: str) -> float:
    start, end = month_date_bounds(month)
    return _purchased_8oz(start, end)


def _slab_date_range(t, i: int, month: str):
    """Resolve the actual (start, end) a slab's achievement should be
    measured over: the slab's own Start/End Date for "Date-Range" scope,
    or the whole calendar month otherwise."""
    scope = t.get(f"slab{i}_scope")
    start = t.get(f"slab{i}_start_date")
    end = t.get(f"slab{i}_end_date")
    if scope == "Date-Range" and start and end and not pd.isna(start) and not pd.isna(end):
        return start, end
    return month_date_bounds(month)


def render():
    targets = q.get_targets_df()
    if targets.empty:
        empty_state("No targets set yet", "Set a monthly target from the 'Set Targets / Caps' tab.", "🎯")
        return

    month = month_picker("target_overview_month")
    target_row = targets[targets["month"] == month]

    with section_card("Monthly Target Achievement", "Achievement is measured in 8oz-equivalent volume, from primary purchases (not sales)."):
        if target_row.empty:
            empty_state(f"No target set for {month}", "Set one from the 'Set Targets / Caps' tab.", "🎯")
            return

        t = target_row.iloc[0]
        achieved = _achieved_8oz_for_month(month)
        pct = (achieved / t["target_8oz"] * 100) if t["target_8oz"] else 0
        status = "ok" if pct >= 100 else ("caution" if pct >= 75 else ("warning" if pct >= 40 else "critical"))
        incentive_earned = incentive_for_achievement(achieved, t["target_8oz"], t["incentive_per_case"])

        kpi_row([
            {"icon": "🎯", "label": "Monthly Target", "value": f"{t['target_8oz']:,.0f} 8oz", "status": "primary"},
            {"icon": "📈", "label": "Purchased", "value": f"{achieved:,.0f} 8oz", "status": status},
            {"icon": "📊", "label": "% of Target", "value": f"{pct:,.1f}%", "status": status},
            {"icon": "💵", "label": "Incentive Earned", "value": f"Rs. {incentive_earned:,.0f}",
             "status": "ok" if incentive_earned > 0 else "warning"},
        ])

        fig = go.Figure(go.Bar(x=["Target", "Purchased"], y=[t["target_8oz"], achieved],
                                marker_color=[config.COLORS["text_muted"], config.COLORS[status]]))
        fig.update_layout(height=320, yaxis_title="8oz-equivalent volume")
        st.plotly_chart(fig, width='stretch')

    with section_card("Slab Incentives", "Two optional slabs on top of the base target, each earned against primary-purchase volume over its own scope."):
        any_slab = False
        for i in (1, 2):
            slab_target = t.get(f"slab{i}_target_8oz")
            if pd.isna(slab_target) or not slab_target:
                continue
            any_slab = True
            slab_incentive_rate = t.get(f"slab{i}_incentive_per_case")
            slab_scope = t.get(f"slab{i}_scope")
            slab_start, slab_end = _slab_date_range(t, i, month)
            slab_achieved = _purchased_8oz(slab_start, slab_end)
            slab_pct = (slab_achieved / slab_target * 100) if slab_target else 0
            slab_status = "ok" if slab_pct >= 100 else ("caution" if slab_pct >= 75 else "warning")
            slab_incentive = incentive_for_achievement(slab_achieved, slab_target, slab_incentive_rate)
            st.markdown(f"**Slab {i}** — scope: {slab_scope} · window: {slab_start} to {slab_end}")
            kpi_row([
                {"icon": "🏅", "label": f"Slab {i} Target", "value": f"{slab_target:,.0f} 8oz", "status": "primary"},
                {"icon": "📈", "label": "Purchased (window)", "value": f"{slab_achieved:,.0f} 8oz", "status": slab_status},
                {"icon": "📊", "label": "% Achieved", "value": f"{slab_pct:,.1f}%", "status": slab_status},
                {"icon": "💵", "label": "Slab Incentive", "value": f"Rs. {slab_incentive:,.0f}",
                 "status": "ok" if slab_incentive > 0 else "warning"},
            ])
            st.write("")
        if not any_slab:
            empty_state("No slabs configured for this month", "Add Slab 1 / Slab 2 from the 'Set Targets / Caps' tab.", "🏅")

    with section_card("Target Trend", "Each month's target is independent, not a running trend - shown as its own bar rather than a connected line across months."):
        available_months = sorted(targets["month"].unique().tolist())
        default_from = available_months[max(0, len(available_months) - 6)]
        default_to = available_months[-1]
        c1, c2 = st.columns(2)
        with c1:
            from_month = st.selectbox("From Month", available_months,
                                       index=available_months.index(default_from), key="trend_from_month")
        with c2:
            to_month = st.selectbox("To Month", available_months,
                                     index=available_months.index(default_to), key="trend_to_month")

        if from_month > to_month:
            st.warning("'From Month' is after 'To Month' — pick a 'From Month' that's earlier (or the same).")
            hist_months = []
        else:
            hist_months = [m for m in available_months if from_month <= m <= to_month]

        if not hist_months:
            empty_state("No months in this range", "Adjust the From/To month selection above.", "📅")
        else:
            hist_achieved = [_achieved_8oz_for_month(m) for m in hist_months]
            hist_targets = [targets[targets["month"] == m].iloc[0]["target_8oz"] for m in hist_months]
            fig2 = go.Figure()
            fig2.add_bar(x=hist_months, y=hist_targets, name="Target", marker_color=config.COLORS["text_muted"])
            fig2.add_bar(x=hist_months, y=hist_achieved, name="Purchased", marker_color=config.COLORS["primary"])
            fig2.update_layout(height=340, yaxis_title="8oz-equivalent volume", barmode="group")
            st.plotly_chart(fig2, width='stretch')
