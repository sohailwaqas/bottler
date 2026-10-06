"""
theme.py — inject the shared CSS once per session and register a single
Plotly template ("bottler") so every chart in the app looks consistent.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

import config


def inject_css():
    # IMPORTANT: do NOT guard this behind a "only once per session" flag.
    # Streamlit fully rebuilds the DOM from scratch on every script rerun
    # (every button click, every widget interaction), so a <style> tag
    # emitted only on the very first run disappears the moment anything
    # else happens - which meant NO page ever actually had this stylesheet
    # applied (every KPI card, section card, and badge rendered as plain
    # unstyled stacked text). Re-emitting identical CSS every run is cheap
    # and has no visible cost; skipping it silently broke the entire UI.
    css = config.STYLE_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def register_plotly_template():
    if "bottler" in pio.templates:
        pio.templates.default = "bottler"
        return
    c = config.COLORS
    palette = [c["primary"], "#7C3AED", c["ok"], c["warning"], c["caution"],
               "#0EA5E9", c["critical"], "#64748B"]
    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family="Inter, Segoe UI, sans-serif", color=c["text"], size=13),
            colorway=palette,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=48, r=24, t=48, b=40),
            title=dict(font=dict(size=15, color=c["text"]), x=0.01, xanchor="left"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                        font=dict(size=12)),
            xaxis=dict(gridcolor=c["border"], zerolinecolor=c["border"], linecolor=c["border"],
                       tickfont=dict(size=11.5, color=c["text_muted"])),
            yaxis=dict(gridcolor=c["border"], zerolinecolor=c["border"], linecolor=c["border"],
                       tickfont=dict(size=11.5, color=c["text_muted"])),
            hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=c["border"]),
        )
    )
    pio.templates["bottler"] = template
    pio.templates.default = "plotly_white+bottler"


def apply():
    if not st.session_state.get("_page_config_set"):
        st.set_page_config(
            page_title=f"{config.APP_NAME} — {config.APP_TAGLINE}",
            page_icon=str(config.LOGO_PATH) if config.LOGO_PATH.exists() else "🍾",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        st.session_state["_page_config_set"] = True
    inject_css()
    register_plotly_template()
