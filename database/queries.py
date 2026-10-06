"""
database/queries.py — every parameterized read/write the app needs.

Convention: read functions return pandas DataFrames (ready for st.dataframe /
plotly); write functions return the new row id (or True/False) and always
run inside a single connection/transaction so partial writes can't happen.
"""
from datetime import datetime
import pandas as pd
import streamlit as st

from database.db import get_connection

NOW = lambda: datetime.now().isoformat(timespec="seconds")


def _df(sql, params=()):
    conn = get_connection()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SKUs
# ---------------------------------------------------------------------------
@st.cache_data(ttl=5, show_spinner=False)
def get_skus_df(include_inactive: bool = False) -> pd.DataFrame:
    sql = "SELECT * FROM skus"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY brand, package"
    return _df(sql)


def get_sku_options(include_inactive: bool = False) -> pd.DataFrame:
    df = get_skus_df(include_inactive)
    if df.empty:
        return df
    df = df.copy()
    df["label"] = df["brand"] + " — " + df["package"]
    return df


def add_sku(brand, package, category, units_per_case, reorder_threshold, pack_type,
            cost_price, selling_price, expiry_threshold_days=60):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute(
            """INSERT INTO skus (brand, package, category, units_per_case, reorder_threshold,
               expiry_threshold_days, pack_type, cost_price, selling_price, stock_qty,
               is_active, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,0,1,?,?)""",
            (brand, package, category, units_per_case, reorder_threshold, expiry_threshold_days,
             pack_type, cost_price, selling_price, now, now),
        )
        conn.commit()
        return True
    finally:
        conn.close()
        get_skus_df.clear()


def update_sku(sku_id, **fields):
    if not fields:
        return False
    fields["updated_at"] = NOW()
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    try:
        conn.execute(f"UPDATE skus SET {cols} WHERE id = ?", (*fields.values(), sku_id))
        conn.commit()
        return True
    finally:
        conn.close()
        get_skus_df.clear()


def delete_sku(sku_id):
    return update_sku(sku_id, is_active=0)


# ---------------------------------------------------------------------------
# Stock overview helpers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=5, show_spinner=False)
def get_near_expiry_df() -> pd.DataFrame:
    sql = """
    SELECT b.id, s.brand, s.package, s.category, s.pack_type,
           s.expiry_threshold_days, b.quantity, b.expiry_date
    FROM sku_expiry_batches b JOIN skus s ON s.id = b.sku_id
    WHERE s.is_active = 1 AND b.quantity > 0
      AND julianday(b.expiry_date) - julianday('now') <= s.expiry_threshold_days
    ORDER BY b.expiry_date ASC
    """
    return _df(sql)


@st.cache_data(ttl=5, show_spinner=False)
def get_stock_movements_df(start_date=None, end_date=None) -> pd.DataFrame:
    sql = """
    SELECT t.date, s.brand || ' — ' || s.package AS sku, t.type, t.reference_type AS reference,
           t.quantity, t.notes
    FROM stock_transactions t JOIN skus s ON s.id = t.sku_id
    WHERE 1=1
    """
    params = []
    if start_date:
        sql += " AND date(t.date) >= date(?)"
        params.append(start_date)
    if end_date:
        sql += " AND date(t.date) <= date(?)"
        params.append(end_date)
    sql += " ORDER BY t.date DESC, t.id DESC"
    return _df(sql, params)


# ---------------------------------------------------------------------------
# Purchases
# ---------------------------------------------------------------------------
def create_purchase(purchase_date, items: list[dict], notes=None):
    """items: [{sku_id, quantity, cost_price}]"""
    conn = get_connection()
    try:
        now = NOW()
        cur = conn.execute("INSERT INTO purchases (date, notes, created_at) VALUES (?,?,?)",
                            (purchase_date, notes, now))
        purchase_id = cur.lastrowid
        for it in items:
            conn.execute(
                "INSERT INTO purchase_items (purchase_id, sku_id, quantity, cost_price) VALUES (?,?,?,?)",
                (purchase_id, it["sku_id"], it["quantity"], it.get("cost_price", 0)),
            )
            conn.execute(
                """INSERT INTO stock_transactions (sku_id, type, reference_type, reference_id,
                   quantity, date, notes, created_at) VALUES (?, 'IN','Purchase', ?, ?, ?, ?, ?)""",
                (it["sku_id"], purchase_id, it["quantity"], purchase_date, f"PO #{purchase_id}", now),
            )
            conn.execute("UPDATE skus SET stock_qty = stock_qty + ?, updated_at=? WHERE id=?",
                         (it["quantity"], now, it["sku_id"]))
        conn.commit()
        return purchase_id
    finally:
        conn.close()
        get_skus_df.clear()
        get_stock_movements_df.clear()
        get_purchases_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_purchases_df(start_date=None, end_date=None) -> pd.DataFrame:
    sql = """
    SELECT p.id, p.date, s.id AS sku_id, s.category, s.brand, s.package, pi.quantity, pi.cost_price, p.notes
    FROM purchases p JOIN purchase_items pi ON pi.purchase_id = p.id
    JOIN skus s ON s.id = pi.sku_id WHERE 1=1
    """
    params = []
    if start_date:
        sql += " AND date(p.date) >= date(?)"; params.append(start_date)
    if end_date:
        sql += " AND date(p.date) <= date(?)"; params.append(end_date)
    sql += " ORDER BY p.date DESC, p.id DESC"
    return _df(sql, params)


# ---------------------------------------------------------------------------
# Stock adjustments
# ---------------------------------------------------------------------------
def create_adjustment(adj_date, adjustment_type, category, brand, package, sku_id, quantity, reason, notes=None):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute(
            """INSERT INTO stock_adjustments (date, adjustment_type, category, brand, package, sku_id,
               quantity, reason, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (adj_date, adjustment_type, category, brand, package, sku_id, quantity, reason, notes, now),
        )
        delta = quantity if adjustment_type == "Add Stock" else -quantity
        conn.execute("UPDATE skus SET stock_qty = MAX(stock_qty + ?, 0), updated_at=? WHERE id=?",
                     (delta, now, sku_id))
        conn.execute(
            """INSERT INTO stock_transactions (sku_id, type, reference_type, quantity, date, notes, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (sku_id, "IN" if adjustment_type == "Add Stock" else "OUT", "Adjustment", quantity,
             adj_date, reason, now),
        )
        conn.commit()
        return True
    finally:
        conn.close()
        get_skus_df.clear()
        get_stock_movements_df.clear()
        get_adjustments_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_adjustments_df(start_date=None, end_date=None) -> pd.DataFrame:
    sql = "SELECT date, category, brand, package, adjustment_type, quantity, reason, notes FROM stock_adjustments WHERE 1=1"
    params = []
    if start_date:
        sql += " AND date(date) >= date(?)"; params.append(start_date)
    if end_date:
        sql += " AND date(date) <= date(?)"; params.append(end_date)
    sql += " ORDER BY date DESC, id DESC"
    return _df(sql, params)


# ---------------------------------------------------------------------------
# Packaging materials
# ---------------------------------------------------------------------------
@st.cache_data(ttl=5, show_spinner=False)
def get_materials_df(include_inactive=False) -> pd.DataFrame:
    sql = "SELECT * FROM packaging_materials"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    return _df(sql)


def add_material(name, unit="pcs"):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute(
            "INSERT INTO packaging_materials (name, unit, stock_qty, is_active, created_at, updated_at) VALUES (?,?,0,1,?,?)",
            (name, unit, now, now),
        )
        conn.commit()
        return True
    finally:
        conn.close(); get_materials_df.clear()


def update_material(material_id, **fields):
    if not fields:
        return False
    fields["updated_at"] = NOW()
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    try:
        conn.execute(f"UPDATE packaging_materials SET {cols} WHERE id=?", (*fields.values(), material_id))
        conn.commit()
        return True
    finally:
        conn.close(); get_materials_df.clear()


def delete_material(material_id):
    return update_material(material_id, is_active=0)


def create_packaging_purchase(p_date, material_id, quantity, note=None):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute("INSERT INTO packaging_purchases (date, material_id, quantity, note, created_at) VALUES (?,?,?,?,?)",
                     (p_date, material_id, quantity, note, now))
        conn.execute("UPDATE packaging_materials SET stock_qty = stock_qty + ?, updated_at=? WHERE id=?",
                     (quantity, now, material_id))
        conn.commit()
        return True
    finally:
        conn.close(); get_materials_df.clear(); get_packaging_purchases_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_packaging_purchases_df() -> pd.DataFrame:
    sql = """SELECT pp.date, m.name AS material, pp.quantity, pp.note
              FROM packaging_purchases pp JOIN packaging_materials m ON m.id = pp.material_id
              ORDER BY pp.date DESC, pp.id DESC"""
    return _df(sql)


def create_packaging_adjustment(a_date, material_id, adjustment_type, quantity, reason):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute(
            "INSERT INTO packaging_adjustments (date, material_id, adjustment_type, quantity, reason, created_at) VALUES (?,?,?,?,?,?)",
            (a_date, material_id, adjustment_type, quantity, reason, now),
        )
        delta = quantity if adjustment_type == "Increase" else -quantity
        conn.execute("UPDATE packaging_materials SET stock_qty = MAX(stock_qty + ?, 0), updated_at=? WHERE id=?",
                     (delta, now, material_id))
        conn.commit()
        return True
    finally:
        conn.close(); get_materials_df.clear(); get_packaging_adjustments_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_packaging_adjustments_df(start_date=None, end_date=None) -> pd.DataFrame:
    sql = """SELECT pa.date, m.name AS material, pa.adjustment_type, pa.quantity, pa.reason
              FROM packaging_adjustments pa JOIN packaging_materials m ON m.id = pa.material_id WHERE 1=1"""
    params = []
    if start_date:
        sql += " AND date(pa.date) >= date(?)"; params.append(start_date)
    if end_date:
        sql += " AND date(pa.date) <= date(?)"; params.append(end_date)
    sql += " ORDER BY pa.date DESC, pa.id DESC"
    return _df(sql, params)


# ---------------------------------------------------------------------------
# Losses
# ---------------------------------------------------------------------------
def create_loss_incident(l_date, source, loss_type, quantity, sku_id=None, material_id=None, notes=None):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute(
            """INSERT INTO loss_incidents (source, loss_type, sku_id, material_id, quantity, date, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (source, loss_type, sku_id, material_id, quantity, l_date, notes, now),
        )
        if source == "Inventory Management" and sku_id:
            conn.execute("UPDATE skus SET stock_qty = MAX(stock_qty - ?, 0), updated_at=? WHERE id=?",
                         (quantity, now, sku_id))
            conn.execute(
                "INSERT INTO stock_transactions (sku_id, type, reference_type, quantity, date, notes, created_at) VALUES (?, 'OUT','Loss', ?, ?, ?, ?)",
                (sku_id, quantity, l_date, f"Loss: {loss_type}", now),
            )
        elif source == "Packaging Material" and material_id:
            conn.execute("UPDATE packaging_materials SET stock_qty = MAX(stock_qty - ?, 0), updated_at=? WHERE id=?",
                         (quantity, now, material_id))
        conn.commit()
        return True
    finally:
        conn.close()
        get_skus_df.clear(); get_materials_df.clear(); get_losses_df.clear(); get_stock_movements_df.clear()


def create_market_lifting(l_date, sku_id, loss_type, quantity, notes=None):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute(
            "INSERT INTO market_liftings (date, sku_id, loss_type, quantity, notes, created_at) VALUES (?,?,?,?,?,?)",
            (l_date, sku_id, loss_type, quantity, notes, now),
        )
        conn.commit()
        return True
    finally:
        conn.close(); get_market_liftings_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_losses_df(start_date=None, end_date=None) -> pd.DataFrame:
    sql = """
    SELECT l.date, l.source, l.loss_type,
           COALESCE(s.brand || ' — ' || s.package, m.name) AS item,
           l.quantity, l.notes
    FROM loss_incidents l
    LEFT JOIN skus s ON s.id = l.sku_id
    LEFT JOIN packaging_materials m ON m.id = l.material_id
    WHERE 1=1
    """
    params = []
    if start_date:
        sql += " AND date(l.date) >= date(?)"; params.append(start_date)
    if end_date:
        sql += " AND date(l.date) <= date(?)"; params.append(end_date)
    sql += " ORDER BY l.date DESC, l.id DESC"
    return _df(sql, params)


@st.cache_data(ttl=5, show_spinner=False)
def get_market_liftings_df(start_date=None, end_date=None) -> pd.DataFrame:
    sql = """SELECT ml.date, s.brand || ' — ' || s.package AS sku, ml.loss_type, ml.quantity, ml.notes
              FROM market_liftings ml JOIN skus s ON s.id = ml.sku_id WHERE 1=1"""
    params = []
    if start_date:
        sql += " AND date(ml.date) >= date(?)"; params.append(start_date)
    if end_date:
        sql += " AND date(ml.date) <= date(?)"; params.append(end_date)
    sql += " ORDER BY ml.date DESC, ml.id DESC"
    return _df(sql, params)


@st.cache_data(ttl=5, show_spinner=False)
def get_combined_loss_history_df(start_date=None, end_date=None) -> pd.DataFrame:
    li = get_losses_df(start_date, end_date).rename(columns={"item": "sku_or_material"})
    li["log_type"] = "Log Incident"
    ml = get_market_liftings_df(start_date, end_date).rename(columns={"sku": "sku_or_material"})
    ml["source"] = "Inventory Management"
    ml["log_type"] = "Market Lifting"
    cols = ["date", "log_type", "source", "loss_type", "sku_or_material", "quantity", "notes"]
    li = li.reindex(columns=cols)
    ml = ml.reindex(columns=cols)
    out = pd.concat([li, ml], ignore_index=True)
    if not out.empty:
        out = out.sort_values("date", ascending=False)
    return out


def set_monthly_loss_quota(month, quota_cases, notes=None):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute(
            """INSERT INTO monthly_loss_quotas (month, quota_cases_1l_pet, notes, created_at)
               VALUES (?,?,?,?)
               ON CONFLICT(month) DO UPDATE SET quota_cases_1l_pet=excluded.quota_cases_1l_pet,
               notes=excluded.notes""",
            (month, quota_cases, notes, now),
        )
        conn.commit()
        return True
    finally:
        conn.close(); get_loss_quotas_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_loss_quotas_df() -> pd.DataFrame:
    return _df("SELECT * FROM monthly_loss_quotas ORDER BY month DESC")


# ---------------------------------------------------------------------------
# Vehicles & Routes
# ---------------------------------------------------------------------------
@st.cache_data(ttl=5, show_spinner=False)
def get_vehicles_df(include_inactive=False) -> pd.DataFrame:
    sql = "SELECT * FROM vehicles"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    return _df(sql)


@st.cache_data(ttl=5, show_spinner=False)
def get_routes_df(include_inactive=False) -> pd.DataFrame:
    sql = "SELECT * FROM routes"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name"
    return _df(sql)


def add_vehicle(name, plate_no=None):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO vehicles (name, plate_no, is_active, created_at) VALUES (?,?,1,?)",
                     (name, plate_no, NOW()))
        conn.commit(); return True
    finally:
        conn.close(); get_vehicles_df.clear()


def update_vehicle(vehicle_id, **fields):
    if not fields: return False
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    try:
        conn.execute(f"UPDATE vehicles SET {cols} WHERE id=?", (*fields.values(), vehicle_id))
        conn.commit(); return True
    finally:
        conn.close(); get_vehicles_df.clear()


def delete_vehicle(vehicle_id):
    return update_vehicle(vehicle_id, is_active=0)


def add_route(name):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO routes (name, is_active, created_at) VALUES (?,1,?)", (name, NOW()))
        conn.commit(); return True
    finally:
        conn.close(); get_routes_df.clear()


def update_route(route_id, **fields):
    if not fields: return False
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn = get_connection()
    try:
        conn.execute(f"UPDATE routes SET {cols} WHERE id=?", (*fields.values(), route_id))
        conn.commit(); return True
    finally:
        conn.close(); get_routes_df.clear()


def delete_route(route_id):
    return update_route(route_id, is_active=0)


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------
def create_sales_invoice(sale_date, sale_type, vehicle_name, route_name, items: list[dict], notes=None):
    """items: [{sku_id, quantity}]"""
    conn = get_connection()
    try:
        now = NOW()
        cur = conn.execute(
            "INSERT INTO sales_invoices (date, type, vehicle_name, route_name, notes, created_at) VALUES (?,?,?,?,?,?)",
            (sale_date, sale_type, vehicle_name, route_name, notes, now),
        )
        invoice_id = cur.lastrowid
        for it in items:
            sp_row = conn.execute("SELECT selling_price FROM skus WHERE id=?", (it["sku_id"],)).fetchone()
            sp = sp_row[0] if sp_row else 0
            conn.execute(
                "INSERT INTO sales_invoice_items (invoice_id, sku_id, quantity, selling_price) VALUES (?,?,?,?)",
                (invoice_id, it["sku_id"], it["quantity"], sp),
            )
            conn.execute(
                """INSERT INTO stock_transactions (sku_id, type, reference_type, reference_id, quantity, date, notes, created_at)
                   VALUES (?, 'OUT','Sale', ?, ?, ?, ?, ?)""",
                (it["sku_id"], invoice_id, it["quantity"], sale_date, f"Invoice #{invoice_id}", now),
            )
            conn.execute("UPDATE skus SET stock_qty = MAX(stock_qty - ?, 0), updated_at=? WHERE id=?",
                         (it["quantity"], now, it["sku_id"]))
        conn.commit()
        return invoice_id
    finally:
        conn.close()
        get_skus_df.clear(); get_stock_movements_df.clear(); get_sales_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_sales_df(start_date=None, end_date=None) -> pd.DataFrame:
    sql = """
    SELECT si.id AS invoice_id, si.date, si.type, si.vehicle_name AS vehicle, si.route_name AS route,
           s.category, s.brand, s.package, sii.quantity, sii.selling_price,
           (sii.quantity * sii.selling_price) AS line_total, s.id as sku_id
    FROM sales_invoices si
    JOIN sales_invoice_items sii ON sii.invoice_id = si.id
    JOIN skus s ON s.id = sii.sku_id
    WHERE 1=1
    """
    params = []
    if start_date:
        sql += " AND date(si.date) >= date(?)"; params.append(start_date)
    if end_date:
        sql += " AND date(si.date) <= date(?)"; params.append(end_date)
    sql += " ORDER BY si.date DESC, si.id DESC"
    return _df(sql, params)


# ---------------------------------------------------------------------------
# Targets & Incentives
# ---------------------------------------------------------------------------
def set_monthly_target(month, target_8oz, incentive_per_case,
                        slab1_target_8oz, slab1_incentive_per_case, slab1_scope, slab1_start_date, slab1_end_date,
                        slab2_target_8oz, slab2_incentive_per_case, slab2_scope, slab2_start_date, slab2_end_date,
                        notes=None):
    conn = get_connection()
    try:
        now = NOW()
        conn.execute(
            """INSERT INTO monthly_targets (month, target_8oz, incentive_per_case, slab1_target_8oz,
               slab1_incentive_per_case, slab1_scope, slab1_start_date, slab1_end_date, slab2_target_8oz,
               slab2_incentive_per_case, slab2_scope, slab2_start_date, slab2_end_date, notes, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(month) DO UPDATE SET
                 target_8oz=excluded.target_8oz, incentive_per_case=excluded.incentive_per_case,
                 slab1_target_8oz=excluded.slab1_target_8oz, slab1_incentive_per_case=excluded.slab1_incentive_per_case,
                 slab1_scope=excluded.slab1_scope, slab1_start_date=excluded.slab1_start_date,
                 slab1_end_date=excluded.slab1_end_date,
                 slab2_target_8oz=excluded.slab2_target_8oz, slab2_incentive_per_case=excluded.slab2_incentive_per_case,
                 slab2_scope=excluded.slab2_scope, slab2_start_date=excluded.slab2_start_date,
                 slab2_end_date=excluded.slab2_end_date, notes=excluded.notes""",
            (month, target_8oz, incentive_per_case, slab1_target_8oz, slab1_incentive_per_case,
             slab1_scope, slab1_start_date, slab1_end_date, slab2_target_8oz, slab2_incentive_per_case,
             slab2_scope, slab2_start_date, slab2_end_date, notes, now),
        )
        conn.commit()
        return True
    finally:
        conn.close(); get_targets_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_targets_df() -> pd.DataFrame:
    return _df("SELECT * FROM monthly_targets ORDER BY month DESC")


def get_target_for_month(month) -> dict | None:
    df = get_targets_df()
    row = df[df["month"] == month]
    return row.iloc[0].to_dict() if not row.empty else None


def set_wholesale_cap(month, pack, brand, cap_pct):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO wholesale_caps (month, pack, brand, cap_pct, created_at) VALUES (?,?,?,?,?)",
                     (month, pack, brand, cap_pct, NOW()))
        conn.commit(); return True
    finally:
        conn.close(); get_wholesale_caps_df.clear()


@st.cache_data(ttl=5, show_spinner=False)
def get_wholesale_caps_df() -> pd.DataFrame:
    return _df("SELECT * FROM wholesale_caps ORDER BY month DESC, id DESC")


def clear_all_caches():
    for fn in [get_skus_df, get_near_expiry_df, get_stock_movements_df, get_purchases_df,
               get_adjustments_df, get_materials_df, get_packaging_purchases_df,
               get_packaging_adjustments_df, get_losses_df, get_market_liftings_df,
               get_combined_loss_history_df, get_loss_quotas_df, get_vehicles_df, get_routes_df,
               get_sales_df, get_targets_df, get_wholesale_caps_df]:
        fn.clear()
