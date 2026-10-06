"""
auth/activation.py — first-run product activation gate.

Uses `licensingpy` (ECDSA-signed, offline-verifiable licenses) to validate
a license key handed out to an authorized distributor. Only the PUBLIC
key + a preseed HASH are bundled in the app (assets/license_public.json);
the private signing key and raw preseed secret stay with the vendor and are
never shipped — see demo_license/ (git-ignored) for how the bundled demo
license was produced.

Activation state is persisted in SQLite (license_activation table) as a
hash of the validated key, not a plain "activated=True" flag, so it
survives restarts and can't be trivially toggled by editing a text file.
"""
import json
import hashlib
from datetime import datetime, date

import streamlit as st
from licensing import LicenseManager
from licensing.exceptions import LicenseError, LicenseExpiredError, LicenseInvalidError, HardwareMismatchError

import config
from database.db import get_connection

# NOTE on hardware binding: licensingpy licenses are hardware-fingerprint
# bound. For a demo distributed to run on arbitrary reviewer machines, we
# validate signature + preseed + expiry but skip the hardware-match check.
# In a real distributor rollout, set CHECK_HARDWARE = True and generate a
# license per target machine (licensingpy supports target-hardware
# generation for exactly this workflow) — flagged here explicitly.
CHECK_HARDWARE = False


def _load_public_artifacts():
    path = config.ASSETS_DIR / "license_public.json"
    if not path.exists():
        return None, None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("public_key"), data.get("preseed_hash")


def _hash_key(license_string: str) -> str:
    return hashlib.sha256(license_string.encode("utf-8")).hexdigest()


def get_activation_status() -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM license_activation ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def verify_license_string(license_string: str):
    """Returns (ok: bool, info_or_error: dict|str)."""
    public_key, preseed_hash = _load_public_artifacts()
    if not public_key or not preseed_hash:
        return False, "License verification artifacts are missing from this install."
    try:
        manager = LicenseManager(public_key, preseed_hash)
        data = manager.verify_license(license_string.strip(), check_hardware=CHECK_HARDWARE, check_expiry=True)
        return True, data
    except LicenseExpiredError:
        return False, "This license key has expired. Please contact your provider for a renewal."
    except HardwareMismatchError:
        return False, "This license key is bound to a different machine."
    except LicenseInvalidError:
        return False, "This license key is invalid or was not issued for Bottler."
    except LicenseError as e:
        return False, f"License error: {e}"
    except Exception:
        return False, "Could not parse this license key. Please check it was pasted in full."


def activate(license_string: str, distribution_name: str) -> tuple[bool, str]:
    ok, info = verify_license_string(license_string)
    if not ok:
        return False, info
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO license_activation (distribution_name, license_key_hash, activation_date, status) VALUES (?,?,?,?)",
            (distribution_name.strip(), _hash_key(license_string), datetime.now().isoformat(timespec="seconds"), "active"),
        )
        conn.commit()
    finally:
        conn.close()
    return True, "Activated"


def deactivate_note_expired():
    conn = get_connection()
    try:
        conn.execute("UPDATE license_activation SET status='expired' WHERE status='active'")
        conn.commit()
    finally:
        conn.close()


def is_activated() -> bool:
    status = get_activation_status()
    return bool(status and status.get("status") == "active" and status.get("distribution_name"))


def get_distribution_name() -> str:
    status = get_activation_status()
    return (status or {}).get("distribution_name", "")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def render_activation_screen():
    logo_path = config.LOGO_PATH
    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        with st.container(border=True):
            if logo_path.exists():
                st.image(str(logo_path), width=180)
            st.markdown(
                f'<div class="b-auth-title">Activate {config.APP_NAME}</div>'
                f'<div class="b-auth-sub">Enter the license key provided by your distributor account manager.</div>',
                unsafe_allow_html=True,
            )

            status = get_activation_status()
            if status and status.get("status") == "expired":
                st.markdown(
                    '<div class="b-badge b-badge-critical" style="margin-bottom:14px;">'
                    '🔴 Previous license expired / invalid</div>',
                    unsafe_allow_html=True,
                )

            with st.form("activation_form", clear_on_submit=False):
                distro_name = st.text_input("Distribution Name", placeholder="e.g. Al-Noor Beverages Distribution")
                license_key = st.text_area("License Key", height=110, placeholder="Paste the full license key JSON here…")
                submitted = st.form_submit_button("Activate", width='stretch')

            if submitted:
                if not distro_name.strip():
                    st.error("❌ Distribution Name is required.")
                elif not license_key.strip():
                    st.error("❌ Please paste your license key.")
                else:
                    ok, msg = activate(license_key, distro_name)
                    if ok:
                        st.success("✅ License activated successfully. Loading Bottler…")
                        st.session_state["_just_activated"] = True
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
                        st.markdown(
                            '<div class="b-badge b-badge-critical" style="margin-top:6px;">'
                            '🔴 Unauthorized / expired license — contact your provider</div>',
                            unsafe_allow_html=True,
                        )

            with st.expander("Don't have a license key?"):
                st.write(
                    "Contact your Bottler provider to receive an activation key for your distribution. "
                    "No modules are accessible until a valid key is entered."
                )
