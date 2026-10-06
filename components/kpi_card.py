"""
components/kpi_card.py — styled KPI cards, status badges, empty/toast states.
Used everywhere instead of raw st.metric so icon + status color + delta are
always presented consistently.
"""
import html
import streamlit as st
import config

ACCENT = {
    "primary": (config.COLORS["primary"], config.COLORS["primary_muted"]),
    "critical": (config.COLORS["critical"], config.COLORS["critical_bg"]),
    "warning": (config.COLORS["warning"], config.COLORS["warning_bg"]),
    "caution": (config.COLORS["caution"], config.COLORS["caution_bg"]),
    "ok": (config.COLORS["ok"], config.COLORS["ok_bg"]),
}


def kpi_row(cards: list[dict]):
    """
    cards: [{icon, label, value, status ('primary'|'critical'|'warning'|'caution'|'ok'),
              delta (optional str), delta_status (optional)}]

    IMPORTANT: this builds ONE single-line HTML string with no embedded
    newlines anywhere. Markdown's CommonMark HTML-block rules terminate a
    raw <div> block at the first blank OR whitespace-only line — a previous
    multi-line version left a bare "{delta_html}" on its own line, which
    was blank whenever delta wasn't passed (i.e. on every call site in this
    app), so only the *first* card rendered as real HTML and everything
    after it printed as literal, unrendered markup. Keeping this on one
    line side-steps that class of bug entirely — don't reintroduce
    multi-line f-strings here without checking for blank/whitespace lines.
    """
    card_htmls = []
    for c in cards:
        accent, accent_bg = ACCENT.get(c.get("status", "primary"), ACCENT["primary"])
        delta_html = ""
        if c.get("delta"):
            d_status = c.get("delta_status", "ok")
            d_color, d_bg = ACCENT.get(d_status, ACCENT["ok"])
            delta_html = (
                f'<div class="b-kpi-delta" style="color:{d_color}; --accent-bg:{d_bg}">'
                f'{html.escape(c["delta"])}</div>'
            )
        card_htmls.append(
            f'<div class="b-kpi" style="--accent:{accent}; --accent-bg:{accent_bg}">'
            f'<div class="b-kpi-icon-wrap"><span class="b-kpi-icon">{c.get("icon", "📊")}</span></div>'
            f'<div class="b-kpi-label">{html.escape(c.get("label", ""))}</div>'
            f'<div class="b-kpi-value">{html.escape(str(c.get("value", "—")))}</div>'
            f'{delta_html}'
            f'</div>'
        )
    st.markdown('<div class="b-kpi-row">' + "".join(card_htmls) + "</div>", unsafe_allow_html=True)


def status_badge(status: str) -> str:
    label = config.STATUS_LABELS.get(status, status)
    icon = config.STATUS_ICONS.get(status, "")
    return f'<span class="b-badge b-badge-{status}">{icon} {label}</span>'


def empty_state(title: str, subtitle: str = "", icon: str = "📭"):
    # Single-line HTML deliberately — see kpi_row() docstring for why any
    # blank/whitespace-only line inside an unsafe_allow_html block breaks
    # markdown's HTML-block parsing partway through.
    st.markdown(
        f'<div class="b-empty"><div class="b-empty-icon">{icon}</div>'
        f'<div style="font-weight:700; color:{config.COLORS["text"]};">{html.escape(title)}</div>'
        f'<div style="font-size:0.85rem; margin-top:4px;">{html.escape(subtitle)}</div></div>',
        unsafe_allow_html=True,
    )


def section_card(title: str = "", subtitle: str = ""):
    """
    The ONE correct way to visually wrap multiple different Streamlit
    elements (charts, tables, forms, filters, text) inside a single
    bordered card. Use as: `with section_card("Title", "Subtitle"):  ...`

    The previous section_card_open()/section_card_close() pair opened and
    closed raw HTML <div> tags across TWO SEPARATE st.markdown() calls —
    but every Streamlit element renders as its own isolated DOM subtree, so
    the browser silently auto-closed those dangling tags right where they
    were written. The result: an empty decorative box containing only the
    title/subtitle (which were in the same initial call), while every
    chart/table/form in between rendered as plain, unstyled page content
    with no visible card around it at all. st.container(border=True) is
    the only construct that actually gives multiple child elements a real,
    shared DOM parent to render inside.
    """
    container = st.container(border=True)
    with container:
        if title:
            sub_html = f'<div class="b-card-sub">{html.escape(subtitle)}</div>' if subtitle else ""
            st.markdown(f'<div class="b-card-title">{html.escape(title)}</div>{sub_html}',
                        unsafe_allow_html=True)
    return container


def toast_success(message: str):
    st.success(f"✅ {message}")


def toast_error(message: str):
    st.error(f"❌ {message}")


def toast_warning(message: str):
    st.warning(f"⚠️ {message}")
