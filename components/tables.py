"""
components/tables.py — a single styled_table() renderer used by every
"...History" / "...Status" page so filtering, empty states, and status
color-coding behave identically everywhere.
"""
import streamlit as st
import config
from components.kpi_card import empty_state


def status_from_stock(stock_qty: float, reorder_threshold: float) -> str:
    if stock_qty <= 0:
        return "critical"
    if stock_qty <= reorder_threshold:
        return "warning"
    return "ok"


def status_label_col(df, status_col="status"):
    """Prefix the status column with its semantic icon, e.g. 'Low Stock' -> '⚠️ Low Stock'."""
    # Same Unicode-compatibility reasoning as config.STATUS_ICONS - avoid
    # 🟠🟡🟢 (Unicode 12.0), which render as blank boxes on older font sets.
    icon_map = {"Out of Stock": "🔴", "Low Stock": "⚠️", "Near Expiry": "🔶", "OK": "✅",
                "critical": "🔴", "warning": "⚠️", "caution": "🔶", "ok": "✅"}
    df = df.copy()
    df[status_col] = df[status_col].map(lambda s: f"{icon_map.get(s, '')} {s}".strip())
    return df


def styled_table(df, empty_title="No records found", empty_subtitle="Try adjusting your filters or date range.",
                  height=None, width='stretch', column_config=None):
    if df is None or df.empty:
        empty_state(empty_title, empty_subtitle, icon="🗂️")
        return
    # NOTE: st.dataframe(height=None) raises "Invalid height value: None" on
    # current Streamlit — None is not treated as "auto" the way it used to
    # be. Only pass height through when a real value was requested; let
    # Streamlit's own default apply otherwise.
    kwargs = dict(width=width, hide_index=True, column_config=column_config)
    if height is not None:
        kwargs["height"] = height
    st.dataframe(df, **kwargs)
