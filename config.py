"""
config.py — Central configuration for Bottler.
Brand tokens, palette, file paths, and shared constants live here so
every module (and theme.py / plotly template) reads from one source
of truth instead of re-declaring magic values inline.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------
APP_NAME = "Bottler"
APP_TAGLINE = "Inventory, Sales & Incentive Management"
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "bottler.db"
LOGO_PATH = ASSETS_DIR / "logo.png"
STYLE_PATH = ASSETS_DIR / "style.css"

# License / activation artifacts (git-ignored — regenerated per deployment)
LICENSE_DIR = BASE_DIR / "demo_license"
LICENSE_DIR.mkdir(exist_ok=True)
LICENSE_KEYS_PATH = LICENSE_DIR / "keys.json"
LICENSE_PRESEED_PATH = LICENSE_DIR / "preseed.json"
LICENSE_FILE_PATH = LICENSE_DIR / "license.txt"

# ---------------------------------------------------------------------------
# Brand palette — derived from primary Royal Blue #2563EB
# ---------------------------------------------------------------------------
COLORS = {
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "primary_active": "#1E40AF",
    "primary_muted": "#EFF6FF",       # very light tint for backgrounds
    "primary_border": "#BFDBFE",
    "primary_soft": "#DBEAFE",

    "secondary": "#0F172A",           # near-black slate for headings
    "text": "#0F172A",
    "text_muted": "#64748B",
    "text_faint": "#94A3B8",

    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",
    "border": "#E2E8F0",

    # Status semantics — used consistently across KPI cards, tables,
    # badges, chart thresholds and alerts.
    "critical": "#DC2626",       # red    — Out of stock / severely missed / invalid
    "critical_bg": "#FEF2F2",
    "critical_border": "#FECACA",

    "warning": "#EA580C",        # orange — Low stock / slab at risk
    "warning_bg": "#FFF7ED",
    "warning_border": "#FED7AA",

    "caution": "#CA8A04",        # yellow — Near expiry / approaching cap
    "caution_bg": "#FEFCE8",
    "caution_border": "#FDE68A",

    "ok": "#16A34A",             # green  — OK / on track / achieved
    "ok_bg": "#F0FDF4",
    "ok_border": "#BBF7D0",

    "info": "#2563EB",
    "info_bg": "#EFF6FF",
}

STATUS_ORDER = ["critical", "warning", "caution", "ok"]
STATUS_LABELS = {
    "critical": "Critical",
    "warning": "Warning",
    "caution": "Caution",
    "ok": "OK",
}
STATUS_ICONS = {
    # Chosen for maximum cross-platform/font compatibility: 🟠🟡🟢 (Unicode
    # 12.0, 2019) render as blank "tofu" boxes on systems whose emoji font
    # hasn't been updated since ~2019 (confirmed on a user's Windows
    # machine). ⚠️/🔶/✅/🔴 are all Unicode 6.0 (2010) or older and render
    # reliably everywhere, including older Windows installs.
    "critical": "🔴",
    "warning": "⚠️",
    "caution": "🔶",
    "ok": "✅",
}

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
# Shared conversion constant — ALL 8oz-equivalent math must route through
# utils.conversions, never re-implemented inline.
ML_TO_8OZ = 0.00017612  # 1 ml = 0.00017612 8oz

PACK_TYPES = ["SSRB", "PET", "Can", "Tetra Pack", "Other"]

SALE_TYPES = ["Retail", "Wholesale"]

ADJUSTMENT_REASONS_STOCK = ["Found", "Return", "Burst", "Loss", "Recount", "Other"]

PACKAGING_MATERIALS_DEFAULT = ["Pallets", "Plastic Sheets", "Empties"]

PACKAGING_ADJUST_REASONS = [
    "Recount", "Breakage", "Missing", "Not Returned", "Data Entry Correction", "Other",
]

LOSS_SOURCES = ["Inventory Management", "Packaging Material"]
LOSS_TYPES = ["Leakage", "Burst", "Expired", "Damaged in Transit", "Theft", "Other"]

TARGET_SLAB_SCOPES = ["Whole Month", "Date-Range"]

DEFAULT_REORDER_THRESHOLD = 20
DEFAULT_EXPIRY_THRESHOLD_DAYS = 60

ROLES = ["Admin", "Operator"]
