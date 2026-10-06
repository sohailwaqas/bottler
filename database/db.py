"""
database/db.py — connection management, schema creation, and demo seeding.

Design notes:
  * Single-file SQLite DB at config.DB_PATH.
  * All tables carry created_at / updated_at where mutation happens, and a
    soft-delete `is_active` flag on every master table that offers "Delete".
  * Schema init is idempotent (CREATE TABLE IF NOT EXISTS) so repeated
    `streamlit run` calls never clobber existing data.
"""
import sqlite3
import random
import calendar
from datetime import datetime, date, timedelta
from contextlib import contextmanager

import config


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor(commit: bool = False):
    """Context manager yielding a cursor on a fresh connection."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS license_activation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    distribution_name TEXT,
    license_key_hash TEXT NOT NULL,
    activation_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Operator',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL,
    package TEXT NOT NULL,
    category TEXT NOT NULL,
    units_per_case INTEGER NOT NULL DEFAULT 24,
    reorder_threshold INTEGER NOT NULL DEFAULT 20,
    expiry_threshold_days INTEGER NOT NULL DEFAULT 60,
    pack_type TEXT NOT NULL DEFAULT 'PET',
    cost_price REAL NOT NULL DEFAULT 0,
    selling_price REAL NOT NULL DEFAULT 0,
    stock_qty REAL NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sku_expiry_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    quantity REAL NOT NULL,
    expiry_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    type TEXT NOT NULL CHECK(type IN ('IN','OUT')),
    reference_type TEXT NOT NULL CHECK(reference_type IN ('Purchase','Sale','Adjustment','Loss')),
    reference_id INTEGER,
    quantity REAL NOT NULL,
    date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL REFERENCES purchases(id),
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    quantity REAL NOT NULL,
    cost_price REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    adjustment_type TEXT NOT NULL CHECK(adjustment_type IN ('Add Stock','Remove Stock')),
    category TEXT,
    brand TEXT,
    package TEXT,
    sku_id INTEGER REFERENCES skus(id),
    quantity REAL NOT NULL,
    reason TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS packaging_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    unit TEXT NOT NULL DEFAULT 'pcs',
    stock_qty REAL NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS packaging_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    material_id INTEGER NOT NULL REFERENCES packaging_materials(id),
    quantity REAL NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS packaging_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    material_id INTEGER NOT NULL REFERENCES packaging_materials(id),
    adjustment_type TEXT NOT NULL CHECK(adjustment_type IN ('Increase','Decrease')),
    quantity REAL NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loss_incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL CHECK(source IN ('Inventory Management','Packaging Material')),
    loss_type TEXT NOT NULL,
    sku_id INTEGER REFERENCES skus(id),
    material_id INTEGER REFERENCES packaging_materials(id),
    quantity REAL NOT NULL,
    date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_liftings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    loss_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_loss_quotas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT UNIQUE NOT NULL,
    quota_cases_1l_pet REAL NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    plate_no TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('Retail','Wholesale')),
    vehicle_name TEXT NOT NULL,
    route_name TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales_invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES sales_invoices(id),
    sku_id INTEGER NOT NULL REFERENCES skus(id),
    quantity REAL NOT NULL,
    selling_price REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS monthly_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT UNIQUE NOT NULL,
    target_8oz REAL NOT NULL,
    incentive_per_case REAL NOT NULL,
    slab1_target_8oz REAL,
    slab1_incentive_per_case REAL,
    slab1_scope TEXT,
    slab1_start_date TEXT,
    slab1_end_date TEXT,
    slab2_target_8oz REAL,
    slab2_incentive_per_case REAL,
    slab2_scope TEXT,
    slab2_start_date TEXT,
    slab2_end_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wholesale_caps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    pack TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT 'All',
    cap_pct REAL NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Columns added after the initial release. CREATE TABLE IF NOT EXISTS never
# alters a table that already exists, so a pre-existing monthly_targets
# table (from an earlier version of this app) would be missing these -
# each tuple is (table, column, sqlite type) and gets added via ALTER TABLE
# if not already present.
SCHEMA_MIGRATIONS = [
    ("monthly_targets", "slab1_start_date", "TEXT"),
    ("monthly_targets", "slab1_end_date", "TEXT"),
    ("monthly_targets", "slab2_start_date", "TEXT"),
    ("monthly_targets", "slab2_end_date", "TEXT"),
]


def _run_migrations(conn):
    for table, column, sqltype in SCHEMA_MIGRATIONS:
        existing_cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing_cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sqltype}")
    # Best-effort carry-over from the old single-deadline columns, if present,
    # so upgrading doesn't silently blank out previously-configured slabs.
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(monthly_targets)")}
    if "slab1_deadline" in existing_cols:
        conn.execute("UPDATE monthly_targets SET slab1_end_date = slab1_deadline WHERE slab1_end_date IS NULL")
    if "slab2_deadline" in existing_cols:
        conn.execute("UPDATE monthly_targets SET slab2_end_date = slab2_deadline WHERE slab2_end_date IS NULL")


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        _run_migrations(conn)
        conn.commit()
    finally:
        conn.close()


def is_seeded() -> bool:
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) as c FROM skus")
        return cur.fetchone()["c"] > 0


# ---------------------------------------------------------------------------
# Demo data seeding — uses the real SKU master list supplied by the client
# so reviewers see the actual product catalogue, not placeholder items.
# ---------------------------------------------------------------------------
RAW_SKUS = [
    ("7-UP", "1000 ML PET", "CSD"), ("7UP MINT", "1000 ML PET", "CSD"),
    ("7-UP ZERO", "1000 ML PET", "CSD"), ("M.DEW", "1000 ML PET", "CSD"),
    ("MIRINDA", "1000 ML PET", "CSD"), ("PEPSI", "1000 ML PET", "CSD"),
    ("LEMONADE TWIST", "1000 ML PET-Revive", "Energy Drink"),
    ("LYCHEE BURST", "1000 ML PET-Revive", "Energy Drink"),
    ("S-M-JUICE", "1000 ML Tetra Pack", "Juices"),
    ("Aquafina", "1500 ML PET AF", "Water"),
    ("7-UP", "1500 ML PET", "CSD"), ("M.DEW", "1500 ML PET", "CSD"),
    ("MIRINDA", "1500 ML PET", "CSD"), ("PEPSI", "1500 ML PET", "CSD"),
    ("7UP MINT", "1500 ML PET", "CSD"),
    ("S-M-JUICE", "200 ML T.Pack", "Juices"),
    ("7-UP", "2000 ML PET 6BT", "CSD"), ("M.DEW", "2000 ML PET 6BT", "CSD"),
    ("PEPSI", "2000 ML PET 6BT", "CSD"),
    ("S-M-JUICE", "240 ML RB SLICE", "Juices"),
    ("STING - BB", "240 ML RB STING", "CSD"), ("STING - GR", "240 ML RB STING", "CSD"),
    ("7-UP", "250 ML CAN", "CSD"), ("7UP MINT", "250 ML CAN", "CSD"),
    ("7-UP ZERO", "250 ML CAN", "CSD"), ("M.DEW", "250 ML CAN", "CSD"),
    ("MIRINDA", "250 ML CAN", "CSD"), ("PEPSI", "250 ML CAN", "CSD"),
    ("PEPSI Zero", "250 ML CAN", "CSD"),
    ("7-UP", "250 ML RB", "CSD"), ("7UP MINT", "250 ML RB", "CSD"),
    ("M.DEW", "250 ML RB", "CSD"), ("MIRINDA", "250 ML RB", "CSD"),
    ("PEPSI", "250 ML RB", "CSD"),
    ("STING - BB", "300 ML PET Sting", "CSD"),
    ("REVIVE LEMONADE TWIST", "300 ML PET-Revive", "Energy Drink"),
    ("REVIVE LYCHEE BURST", "300 ML PET-Revive", "Energy Drink"),
    ("7-UP", "345 ML PET", "CSD"), ("7UP MINT", "345 ML PET", "CSD"),
    ("7-UP ZERO", "345 ML PET", "CSD"), ("M.DEW", "345 ML PET", "CSD"),
    ("MIRINDA", "345 ML PET", "CSD"), ("PEPSI", "345 ML PET", "CSD"),
    ("Aquafina", "5.0L PET Bottle Bulk Water", "Water"),
    ("Aquafina", "500 ML PET AF", "Water"),
    ("BLUE BOLT", "500 ML PET GTR", "Water"),
    ("LEMON & LIME", "500 ML PET GTR", "Water"),
    ("TROPICAL FRUIT", "500 ML PET GTR", "Water"),
    ("STING - BB", "500 ML PET Sting", "Energy Drink"),
    ("7-UP", "500 ML PET", "CSD"), ("7UP MINT", "500 ML PET", "CSD"),
    ("7-UP ZERO", "500 ML PET", "CSD"), ("M.DEW", "500 ML PET", "CSD"),
    ("MIRINDA", "500 ML PET", "CSD"), ("PEPSI", "500 ML PET", "CSD"),
]


def _pack_type_for(package: str) -> str:
    p = package.lower()
    if "can" in p:
        return "Can"
    if "tetra" in p or "t.pack" in p:
        return "Tetra Pack"
    if "rb" in p.split():
        return "SSRB"
    if " rb" in p or p.startswith("rb") or "rb " in p:
        return "SSRB"
    if "pet" in p:
        return "PET"
    return "Other"


def _units_per_case_for(package: str) -> int:
    p = package.lower()
    if "5.0l" in p or "bulk" in p:
        return 2
    if p.startswith("2000") or "2000 ml" in p:
        return 6
    if p.startswith("1500") or "1500 ml" in p:
        return 12
    if p.startswith("1000") or "1000 ml" in p:
        return 12
    if p.startswith("500") or "500 ml" in p:
        return 24
    if p.startswith("345") or "345 ml" in p:
        return 24
    if p.startswith("300") or "300 ml" in p:
        return 24
    if p.startswith("250") or "250 ml" in p:
        return 30
    if p.startswith("240") or "240 ml" in p:
        return 30
    if p.startswith("200") or "200 ml" in p:
        return 27
    return 24


def _ml_from_package(package: str) -> float:
    import re
    m = re.search(r"([\d.]+)\s*(ml|l)\b", package.lower())
    if not m:
        return 500.0
    val, unit = float(m.group(1)), m.group(2)
    return val * 1000 if unit == "l" else val


def _price_for(category: str, ml: float) -> tuple:
    # Rough, realistic PKR pricing scaled by volume & category, for demo only.
    base = {"CSD": 0.055, "Water": 0.035, "Juices": 0.07, "Energy Drink": 0.09}.get(category, 0.05)
    selling = round(ml * base, -1) if ml >= 200 else round(ml * base)
    selling = max(selling, 30)
    cost = round(selling * 0.78)
    return float(cost), float(selling)


def seed_demo_data():
    """Populate a realistic demo dataset. Idempotent — only runs if empty."""
    if is_seeded():
        return
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    cur = conn.cursor()

    sku_ids = {}
    rng = random.Random(42)
    for brand, package, category in RAW_SKUS:
        pack_type = _pack_type_for(package)
        units_per_case = _units_per_case_for(package)
        ml = _ml_from_package(package)
        cost, selling = _price_for(category, ml)
        stock = rng.choice(
            [0, 0, rng.randint(1, 15), rng.randint(1, 15),
             rng.randint(20, 60), rng.randint(60, 160), rng.randint(160, 400)]
        )
        cur.execute(
            """INSERT INTO skus (brand, package, category, units_per_case, reorder_threshold,
               expiry_threshold_days, pack_type, cost_price, selling_price, stock_qty,
               is_active, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)""",
            (brand, package, category, units_per_case, 20, 60, pack_type, cost, selling,
             stock, now, now),
        )
        sku_id = cur.lastrowid
        sku_ids[(brand, package)] = sku_id
        if stock > 0:
            cur.execute(
                """INSERT INTO stock_transactions (sku_id, type, reference_type, quantity, date, notes, created_at)
                   VALUES (?, 'IN', 'Adjustment', ?, ?, 'Opening balance', ?)""",
                (sku_id, stock, (date.today() - timedelta(days=75)).isoformat(), now),
            )
        # A few SKUs get a near-expiry batch for the Near-Expiry table demo.
        if rng.random() < 0.22 and stock > 0:
            qty = min(stock, rng.randint(2, 12))
            exp = (date.today() + timedelta(days=rng.randint(3, 45))).isoformat()
            cur.execute(
                "INSERT INTO sku_expiry_batches (sku_id, quantity, expiry_date, created_at) VALUES (?,?,?,?)",
                (sku_id, qty, exp, now),
            )

    # Vehicles & routes
    vehicles = ["LEA-2211", "LEB-4470", "LEC-9081", "Counter Sale"]
    routes = ["Route North", "Route South", "Route East", "Route Cantt", "Counter Sale"]
    for v in vehicles:
        cur.execute("INSERT INTO vehicles (name, plate_no, is_active, created_at) VALUES (?,?,1,?)",
                    (v, v if v != "Counter Sale" else None, now))
    for r in routes:
        cur.execute("INSERT INTO routes (name, is_active, created_at) VALUES (?,1,?)", (r, now))

    # Packaging materials
    for m, unit, qty in [("Pallets", "pcs", 340), ("Plastic Sheets", "rolls", 128), ("Empties", "cases", 2100)]:
        cur.execute(
            "INSERT INTO packaging_materials (name, unit, stock_qty, is_active, created_at, updated_at) VALUES (?,?,?,1,?,?)",
            (m, unit, qty, now, now),
        )

    conn.commit()

    # --- Sales invoices over the last ~70 days across routes/vehicles -----
    all_skus = list(sku_ids.items())
    active_vehicles = [v for v in vehicles if v != "Counter Sale"]
    active_routes = [r for r in routes if r != "Counter Sale"]
    for d_off in range(70, 0, -1):
        d = date.today() - timedelta(days=d_off)
        n_invoices = rng.randint(1, 3)
        for _ in range(n_invoices):
            sale_type = rng.choices(["Retail", "Wholesale"], weights=[70, 30])[0]
            vehicle = rng.choice(active_vehicles)
            route = rng.choice(active_routes)
            cur.execute(
                "INSERT INTO sales_invoices (date, type, vehicle_name, route_name, notes, created_at) VALUES (?,?,?,?,?,?)",
                (d.isoformat(), sale_type, vehicle, route, None, now),
            )
            invoice_id = cur.lastrowid
            n_lines = rng.randint(2, 6)
            for _ in range(n_lines):
                (brand, package), sku_id = rng.choice(all_skus)
                qty = rng.randint(1, 8)
                cur.execute(
                    "SELECT selling_price FROM skus WHERE id=?", (sku_id,)
                )
                sp = cur.fetchone()["selling_price"]
                cur.execute(
                    "INSERT INTO sales_invoice_items (invoice_id, sku_id, quantity, selling_price) VALUES (?,?,?,?)",
                    (invoice_id, sku_id, qty, sp),
                )
                cur.execute(
                    "INSERT INTO stock_transactions (sku_id, type, reference_type, reference_id, quantity, date, notes, created_at) VALUES (?, 'OUT','Sale', ?, ?, ?, ?, ?)",
                    (sku_id, invoice_id, qty, d.isoformat(), f"Invoice #{invoice_id}", now),
                )
                cur.execute("UPDATE skus SET stock_qty = MAX(stock_qty - ?, 0) WHERE id=?", (qty, sku_id))

    # --- A handful of purchases (restocking) -------------------------------
    for d_off in [60, 45, 30, 15, 5]:
        d = date.today() - timedelta(days=d_off)
        cur.execute("INSERT INTO purchases (date, notes, created_at) VALUES (?,?,?)",
                    (d.isoformat(), "Primary purchase from company", now))
        purchase_id = cur.lastrowid
        for (brand, package), sku_id in rng.sample(all_skus, k=10):
            qty = rng.randint(20, 120)
            cur.execute("SELECT cost_price FROM skus WHERE id=?", (sku_id,))
            cp = cur.fetchone()["cost_price"]
            cur.execute(
                "INSERT INTO purchase_items (purchase_id, sku_id, quantity, cost_price) VALUES (?,?,?,?)",
                (purchase_id, sku_id, qty, cp),
            )
            cur.execute(
                "INSERT INTO stock_transactions (sku_id, type, reference_type, reference_id, quantity, date, notes, created_at) VALUES (?, 'IN','Purchase', ?, ?, ?, ?, ?)",
                (sku_id, purchase_id, qty, d.isoformat(), f"PO #{purchase_id}", now),
            )
            cur.execute("UPDATE skus SET stock_qty = stock_qty + ? WHERE id=?", (qty, sku_id))

    # --- Stock adjustments ---------------------------------------------------
    reasons_add = ["Found", "Return"]
    reasons_remove = ["Burst", "Loss"]
    for _ in range(14):
        d = date.today() - timedelta(days=rng.randint(1, 70))
        (brand, package), sku_id = rng.choice(all_skus)
        cur.execute("SELECT category FROM skus WHERE id=?", (sku_id,))
        cat = cur.fetchone()["category"]
        adj_type = rng.choice(["Add Stock", "Remove Stock"])
        qty = rng.randint(1, 10)
        reason = rng.choice(reasons_add if adj_type == "Add Stock" else reasons_remove)
        cur.execute(
            """INSERT INTO stock_adjustments (date, adjustment_type, category, brand, package, sku_id,
               quantity, reason, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (d.isoformat(), adj_type, cat, brand, package, sku_id, qty, reason, None, now),
        )
        delta = qty if adj_type == "Add Stock" else -qty
        cur.execute("UPDATE skus SET stock_qty = MAX(stock_qty + ?, 0) WHERE id=?", (delta, sku_id))
        cur.execute(
            "INSERT INTO stock_transactions (sku_id, type, reference_type, quantity, date, notes, created_at) VALUES (?,?,?,?,?,?,?)",
            (sku_id, "IN" if adj_type == "Add Stock" else "OUT", "Adjustment", qty, d.isoformat(), reason, now),
        )

    # --- Packaging purchases & adjustments -----------------------------------
    cur.execute("SELECT id, name FROM packaging_materials")
    materials = {r["name"]: r["id"] for r in cur.fetchall()}
    for d_off in [55, 40, 20, 8]:
        d = date.today() - timedelta(days=d_off)
        for name, mid in materials.items():
            qty = rng.randint(10, 60)
            cur.execute("INSERT INTO packaging_purchases (date, material_id, quantity, note, created_at) VALUES (?,?,?,?,?)",
                        (d.isoformat(), mid, qty, "Restock", now))
    for _ in range(6):
        d = date.today() - timedelta(days=rng.randint(1, 60))
        name, mid = rng.choice(list(materials.items()))
        atype = rng.choice(["Increase", "Decrease"])
        qty = rng.randint(2, 20)
        reason = rng.choice(config.PACKAGING_ADJUST_REASONS)
        cur.execute("INSERT INTO packaging_adjustments (date, material_id, adjustment_type, quantity, reason, created_at) VALUES (?,?,?,?,?,?)",
                    (d.isoformat(), mid, atype, qty, reason, now))

    # --- Losses & market liftings --------------------------------------------
    for _ in range(10):
        d = date.today() - timedelta(days=rng.randint(1, 70))
        source = rng.choices(config.LOSS_SOURCES, weights=[65, 35])[0]
        loss_type = rng.choice(config.LOSS_TYPES)
        qty = rng.randint(1, 6)
        if source == "Inventory Management":
            (brand, package), sku_id = rng.choice(all_skus)
            cur.execute(
                "INSERT INTO loss_incidents (source, loss_type, sku_id, quantity, date, notes, created_at) VALUES (?,?,?,?,?,?,?)",
                (source, loss_type, sku_id, qty, d.isoformat(), None, now),
            )
        else:
            name, mid = rng.choice(list(materials.items()))
            cur.execute(
                "INSERT INTO loss_incidents (source, loss_type, material_id, quantity, date, notes, created_at) VALUES (?,?,?,?,?,?,?)",
                (source, loss_type, mid, qty, d.isoformat(), None, now),
            )
    for _ in range(6):
        d = date.today() - timedelta(days=rng.randint(1, 70))
        (brand, package), sku_id = rng.choice(all_skus)
        qty = rng.randint(1, 5)
        loss_type = rng.choice(["Leakage", "Burst", "Expired"])
        cur.execute(
            "INSERT INTO market_liftings (date, sku_id, loss_type, quantity, notes, created_at) VALUES (?,?,?,?,?,?)",
            (d.isoformat(), sku_id, loss_type, qty, None, now),
        )

    # --- Monthly loss quotas (last 3 months incl. current) -------------------
    for m_off in range(2, -1, -1):
        m = (date.today().replace(day=1) - timedelta(days=1)) if m_off else date.today()
        month_key = (date.today().replace(day=1) - timedelta(days=30 * m_off)).strftime("%Y-%m")
        cur.execute(
            "INSERT OR IGNORE INTO monthly_loss_quotas (month, quota_cases_1l_pet, notes, created_at) VALUES (?,?,?,?)",
            (month_key, 25.0, "Standard monthly loss allowance", now),
        )

    # --- Monthly targets & slabs (last 3 months incl. current) --------------
    # Slab 1 demonstrates "Whole Month" scope; Slab 2 demonstrates
    # "Date-Range" scope (a specific window within the month) - both
    # incentive slabs are earned against primary-purchase volume, not sales.
    for m_off in range(2, -1, -1):
        month_start = date.today().replace(day=1) - timedelta(days=30 * m_off)
        month_key = month_start.strftime("%Y-%m")
        year, mon = int(month_key[:4]), int(month_key[5:7])
        last_day = calendar.monthrange(year, mon)[1]
        month_first = f"{month_key}-01"
        month_last = f"{month_key}-{last_day:02d}"
        slab2_start = f"{month_key}-10"
        slab2_end = f"{month_key}-25"
        cur.execute(
            """INSERT OR IGNORE INTO monthly_targets
               (month, target_8oz, incentive_per_case, slab1_target_8oz, slab1_incentive_per_case,
                slab1_scope, slab1_start_date, slab1_end_date, slab2_target_8oz, slab2_incentive_per_case,
                slab2_scope, slab2_start_date, slab2_end_date, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (month_key, 480000, 18, 220000, 20, "Whole Month", month_first, month_last,
             350000, 22, "Date-Range", slab2_start, slab2_end, "Auto-seeded demo target", now),
        )

    # --- Wholesale caps --------------------------------------------------------
    this_month = date.today().strftime("%Y-%m")
    for pack in ["500 ML PET", "1500 ML PET", "250 ML CAN"]:
        cur.execute(
            "INSERT INTO wholesale_caps (month, pack, brand, cap_pct, created_at) VALUES (?,?,?,?,?)",
            (this_month, pack, "All", 35.0, now),
        )

    conn.commit()
    conn.close()
