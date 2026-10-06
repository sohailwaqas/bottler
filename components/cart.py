"""
components/cart.py — the single "Add item -> cart table with inline
edit/remove -> Clear -> Finalize" interaction pattern, shared verbatim by
Inventory > Purchase and Sales > New Sale so behavior never drifts between
the two.
"""
import pandas as pd
import streamlit as st
from components.kpi_card import empty_state


def get_cart(cart_key: str) -> list:
    return st.session_state.setdefault(cart_key, [])


def add_to_cart(cart_key: str, item: dict):
    cart = get_cart(cart_key)
    # merge quantities if the same sku already sits in the cart
    for existing in cart:
        if existing.get("sku_id") == item.get("sku_id"):
            existing["quantity"] += item["quantity"]
            return
    cart.append(item)


def clear_cart(cart_key: str):
    st.session_state[cart_key] = []


def remove_from_cart(cart_key: str, index: int):
    cart = get_cart(cart_key)
    if 0 <= index < len(cart):
        cart.pop(index)


def render_cart_table(cart_key: str, display_cols: dict, title="Cart Items", empty_msg="Nothing added yet."):
    """
    display_cols: ordered dict {item_key: display_label} to show as columns.
    Renders each row with a Remove button; returns nothing (mutates session_state).
    """
    cart = get_cart(cart_key)
    st.markdown(f"**{title}**")
    if not cart:
        empty_state(empty_msg, "Use the form above to add items.", "🛒")
        return

    header_cols = st.columns(list(len(display_cols) * [2]) + [1])
    for hc, (key, label) in zip(header_cols[:-1], display_cols.items()):
        hc.markdown(f"<span style='font-size:0.78rem;color:#64748B;font-weight:700;'>{label}</span>",
                     unsafe_allow_html=True)
    header_cols[-1].markdown("<span style='font-size:0.78rem;color:#64748B;font-weight:700;'>—</span>",
                              unsafe_allow_html=True)

    for i, item in enumerate(cart):
        row_cols = st.columns(list(len(display_cols) * [2]) + [1])
        for rc, key in zip(row_cols[:-1], display_cols.keys()):
            val = item.get(key, "")
            rc.write(val)
        if row_cols[-1].button("🗑️", key=f"{cart_key}_remove_{i}", help="Remove this line"):
            remove_from_cart(cart_key, i)
            st.rerun()

    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("Clear All", key=f"{cart_key}_clear"):
            clear_cart(cart_key)
            st.rerun()
