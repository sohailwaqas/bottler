"""
app.py — Bottler entrypoint.

Flow: Product Activation (first run) -> Login (every session) -> Router.
Navigation model (fixed per spec):
    Left sidebar   = Modules (top level) -> Sub-modules (nested)
    Top tabs        = Pages within the active sub-module
"""
import streamlit as st

import config
import theme
from database.db import init_db, seed_demo_data
from auth import activation, login
from utils.backup_utils import maybe_run_scheduled_backup

# --- module page renderers --------------------------------------------------
from modules.inventory import stock_overview, purchase as inv_purchase, adjust_stock, history as inv_history, manage_sku
from modules.packaging_materials import overview as pm_overview, purchase as pm_purchase, adjust as pm_adjust, manage_materials
from modules.losses import log_incident, market_lifting, quota_vs_actual, history as loss_history
from modules.sales import new_sale, history as sales_history
from modules.vehicles_routes import overview as vr_overview, manage as vr_manage
from modules.targets_incentives import target_overview, wholesale_cap_monitor, set_targets
from modules import settings as settings_module

theme.apply()
init_db()
seed_demo_data()
login.ensure_default_admin()
maybe_run_scheduled_backup()

# ---------------------------------------------------------------------------
# Navigation registry
# ---------------------------------------------------------------------------
NAV = {
    "Inventory Ops": {
        "icon": "📦",
        "submodules": {
            "Inventory": {
                "icon": "🍾",
                "pages": {
                    "Stock Overview": stock_overview.render,
                    "Purchase": inv_purchase.render,
                    "Adjust Stock": adjust_stock.render,
                    "History": inv_history.render,
                    "Manage SKUs": manage_sku.render,
                },
            },
            "Packaging Materials": {
                "icon": "📦",
                "pages": {
                    "Overview": pm_overview.render,
                    "Purchase": pm_purchase.render,
                    "Adjust": pm_adjust.render,
                    "Manage Materials": manage_materials.render,
                },
            },
            "Losses": {
                "icon": "⚠️",
                "pages": {
                    "Log Incident": log_incident.render,
                    "Market Lifting": market_lifting.render,
                    "Quota vs Actual": quota_vs_actual.render,
                    "History": loss_history.render,
                },
            },
        },
    },
    "Sales & Fleet": {
        "icon": "🚚",
        "submodules": {
            "Sales": {
                "icon": "📄",
                "pages": {
                    "New Sale": new_sale.render,
                    "History": sales_history.render,
                },
            },
            "Vehicles & Routes": {
                "icon": "🛣️",
                "pages": {
                    "Overview": vr_overview.render,
                    "Manage": vr_manage.render,
                },
            },
        },
    },
    "Targets & Incentives": {
        "icon": "🎯",
        "submodules": {
            "Target Tracking": {
                "icon": "🏆",
                "pages": {
                    "Target Overview": target_overview.render,
                    "Wholesale Cap Monitor": wholesale_cap_monitor.render,
                    "Set Targets / Caps": set_targets.render,
                },
            },
        },
    },
    "Settings": {
        "icon": "⚙️",
        "submodules": {
            "Settings": {
                "icon": "⚙️",
                "pages": {
                    "Backup & Restore": settings_module.render_backup_restore,
                    "Users": settings_module.render_users,
                },
            },
        },
    },
}


def render_sidebar():
    with st.sidebar:
        logo_col, name_col = st.columns([1, 3])
        st.markdown(
            f'<div class="b-brand"><img src="data:image/png;base64,{_logo_b64()}" />'
            f'<div><div class="b-brand-name">{config.APP_NAME}</div>'
            f'<div class="b-brand-sub">{config.APP_TAGLINE}</div></div></div>',
            unsafe_allow_html=True,
        )
        distro = activation.get_distribution_name()
        user = st.session_state.get("user", {})
        st.markdown(
            f'<div class="b-distro-badge"><b>{distro}</b>'
            f'Signed in as {user.get("username", "")} · {user.get("role", "")}</div>',
            unsafe_allow_html=True,
        )

        if "nav_module" not in st.session_state:
            st.session_state["nav_module"] = list(NAV.keys())[0]

        st.markdown("**MODULES**")
        for mod_name, mod in NAV.items():
            active = st.session_state["nav_module"] == mod_name
            if st.button(f"{mod['icon']}  {mod_name}", key=f"nav_mod_{mod_name}",
                         width='stretch', type="primary" if active else "secondary"):
                st.session_state["nav_module"] = mod_name
                st.session_state.pop("nav_submodule", None)
                st.rerun()

        mod = NAV[st.session_state["nav_module"]]
        submods = mod["submodules"]
        if "nav_submodule" not in st.session_state or st.session_state["nav_submodule"] not in submods:
            st.session_state["nav_submodule"] = list(submods.keys())[0]

        st.markdown("<hr style='border-color:#1F2937; margin:10px 0;'>", unsafe_allow_html=True)
        st.markdown("**SUB-MODULES**")
        for sub_name, sub in submods.items():
            active = st.session_state["nav_submodule"] == sub_name
            if st.button(f"{sub['icon']}  {sub_name}", key=f"nav_sub_{sub_name}",
                         width='stretch', type="primary" if active else "secondary"):
                st.session_state["nav_submodule"] = sub_name
                st.rerun()

        st.markdown("<hr style='border-color:#1F2937; margin:10px 0;'>", unsafe_allow_html=True)
        if st.button("🚪  Log out", width='stretch'):
            login.logout()

    return st.session_state["nav_module"], st.session_state["nav_submodule"]


@st.cache_data(show_spinner=False)
def _logo_b64():
    import base64
    return base64.b64encode(config.LOGO_PATH.read_bytes()).decode() if config.LOGO_PATH.exists() else ""


def render_main(module_name, submodule_name):
    sub = NAV[module_name]["submodules"][submodule_name]
    pages = sub["pages"]

    st.markdown(f"### {sub['icon']} {submodule_name}")
    tabs = st.tabs(list(pages.keys()))
    for tab, (page_name, render_fn) in zip(tabs, pages.items()):
        with tab:
            try:
                render_fn()
            except Exception as e:
                st.error(f"❌ Something went wrong loading **{page_name}**: {e}")


def main():
    if not activation.is_activated():
        activation.render_activation_screen()
        return

    if not login.is_logged_in():
        login.render_login_screen()
        return

    module_name, submodule_name = render_sidebar()
    render_main(module_name, submodule_name)


if __name__ == "__main__":
    main()
