"""
components/filters.py — reusable, real (non-decorative) filter controls used
across every history/report page, plus a single consistent date-range picker.
"""
from datetime import date, timedelta
import streamlit as st


def date_range_picker(key_prefix: str, default_days: int = 30, label: str = "Date range"):
    col1, col2 = st.columns(2)
    default_start = date.today() - timedelta(days=default_days)
    with col1:
        start = st.date_input(f"{label} — from", value=default_start, key=f"{key_prefix}_start")
    with col2:
        end = st.date_input(f"{label} — to", value=date.today(), key=f"{key_prefix}_end")
    if start > end:
        st.warning("Start date is after end date — showing no results until corrected.")
    return start.isoformat(), end.isoformat()


def month_picker(key_prefix: str, label: str = "Month"):
    today = date.today()
    years = list(range(today.year - 2, today.year + 2))
    months = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
    c1, c2 = st.columns(2)
    with c1:
        y = st.selectbox(f"{label} — Year", years, index=years.index(today.year), key=f"{key_prefix}_y")
    with c2:
        m = st.selectbox(f"{label} — Month", months, index=today.month - 1, key=f"{key_prefix}_m")
    return f"{y}-{m}"


def month_date_bounds(month_str: str):
    """
    Given 'YYYY-MM', return (first_day_iso, last_day_iso) for that month.
    Deliberately NOT built as f"{month}-31" — SQLite's date() function
    rolls an out-of-range day like '2026-04-31' forward into '2026-05-01'
    instead of rejecting it, which silently leaked one day from the next
    month into every month-scoped query (targets, wholesale caps).

    Defensive: month values can originate from a free-text field elsewhere
    in the app (Set Targets / Caps), so a malformed string must never crash
    a page that later iterates over stored months — fall back to a safe
    28-day window instead of raising.
    """
    import calendar
    import re
    if not re.match(r"^\d{4}-\d{2}$", str(month_str)):
        return f"{month_str}-01", f"{month_str}-28"
    year, mon = int(month_str[:4]), int(month_str[5:7])
    if not (1 <= mon <= 12):
        return f"{month_str}-01", f"{month_str}-28"
    last_day = calendar.monthrange(year, mon)[1]
    return f"{month_str}-01", f"{month_str}-{last_day:02d}"


def valid_month_format(month_str: str) -> bool:
    import re
    if not re.match(r"^\d{4}-\d{2}$", str(month_str)):
        return False
    mon = int(month_str[5:7])
    return 1 <= mon <= 12


def multiselect_filter(df, column: str, label: str = None, key: str = None):
    """Renders a multiselect for `column` and returns the filtered dataframe."""
    if df.empty or column not in df.columns:
        return df
    options = sorted([o for o in df[column].dropna().unique().tolist()])
    label = label or column.replace("_", " ").title()
    chosen = st.multiselect(label, options, default=[], key=key or f"filter_{column}")
    if chosen:
        return df[df[column].isin(chosen)]
    return df


def apply_filters_row(df, columns: list[str], key_prefix: str = "f"):
    """Renders one multiselect per column side-by-side and returns the filtered df."""
    if df.empty:
        return df
    cols = st.columns(len(columns))
    out = df
    for c, colname in zip(cols, columns):
        with c:
            out = multiselect_filter(out, colname, key=f"{key_prefix}_{colname}")
    return out
