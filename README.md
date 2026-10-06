# Bottler
Inventory, Sales & Incentive Management for beverage distributors.

## Quick start

**Windows:** just double-click **`Start Bottler.bat`**. It creates a virtual
environment, installs dependencies, and launches the app in your browser —
no command line needed. Run it again any time to relaunch (it skips
reinstalling once set up).

**macOS / Linux:**
```bash
pip install -r requirements.txt
streamlit run app.py
```

> **Windows note:** `requirements.txt` deliberately does **not** install
> `netifaces` or `psutil`. They're optional `[hardware]` extras of
> `licensingpy` used only to sharpen hardware-fingerprint uniqueness, and
> `netifaces` in particular has no pre-built wheel for many Windows/Python
> combinations — pip would otherwise try to compile it from source and fail
> with `Microsoft Visual C++ 14.0 or greater is required`. `licensingpy`
> already falls back to `uuid.getnode()` / `os.cpu_count()` when they're
> absent, and this app disables hardware-fingerprint checking entirely
> (`CHECK_HARDWARE = False` in `auth/activation.py`), so nothing is lost by
> leaving them out. Verified: the full app (activation, login, every
> module) runs and passes end-to-end tests without either package
> installed.

> **Already ran an earlier copy of this app?** `Streamlit` is pinned to an
> exact version (`streamlit==1.63.0`) because this app uses the newer
> `width='stretch'` API, which older Streamlit releases either don't have
> or interpret differently (some accept only an integer pixel width there,
> which raised a `TypeError` specifically on the pages with the most
> tables/charts — Stock Overview, Sales History, Target Overview). If your
> `venv` folder was created by an earlier version of this app, just run
> **`Start Bottler.bat`** again — it now re-syncs dependencies against
> `requirements.txt` on every launch, so it will pick up the correct
> version automatically. (On macOS/Linux: re-run `pip install -r
> requirements.txt` in your existing environment.)

The first launch creates `data/bottler.db`, applies the schema, and seeds a
demo dataset built from the real 55-SKU catalogue you provided (7-Up,
Pepsi, Mirinda, Mountain Dew, Sting, Aquafina, Revive, etc.) with ~70 days
of purchases, sales, adjustments, and losses so every chart and table has
data to show on first run.

### Activation (first run only)

Bottler is gated behind a one-time **product activation** screen (built on
`licensingpy`, offline ECDSA-signed license verification) followed by a
per-session **login**.

- **Distribution Name:** anything, e.g. `Demo Beverages Distribution`
- **License Key:** paste the contents of `demo_license/license.txt`
  (generated specifically for this build — a lifetime license, valid through year 9999)

> The shipped app only bundles the *public* key + a preseed hash
> (`assets/license_public.json`) needed to *verify* a license. The private
> signing key and raw preseed secret live only in `demo_license/keys.json`
> and `demo_license/preseed.json` (both git-ignored) — that's how a real
> distributor rollout would generate additional keys without exposing the
> signing material inside the app itself.
>
> Hardware-fingerprint binding is supported by `licensingpy` but is
> **disabled** in `auth/activation.py` (`CHECK_HARDWARE = False`) so the
> demo license works on any reviewer's machine. For a real multi-machine
> rollout, flip that flag and generate one license per target machine.

### Login

- **Username:** `admin`
- **Password:** `bottler123`

Change this immediately after activation from **Settings → Users → Change
My Password**, and create named accounts for real operators from the same
screen (Admin role required to add/manage other users).

## Architecture

```
app.py                     Entrypoint: activation -> login -> sidebar/tab router
config.py                  Brand palette, status colors, domain constants
theme.py                   Injects assets/style.css once; registers the shared Plotly template
database/
  db.py                    Schema (CREATE TABLE IF NOT EXISTS) + demo data seeding
  queries.py               Every parameterized read (cached DataFrame) / write in the app
auth/
  activation.py            licensingpy-based product activation gate
  login.py                 hashlib (SHA-256 + per-user salt) username/password login
utils/
  conversions.py           THE single source of truth for ml -> 8oz-equivalent math
  backup_utils.py          Manual + scheduled SQLite backup/restore (built on `backup`)
components/                Shared UI: KPI cards, status badges, filters, tables, cart pattern
modules/
  inventory/                Stock Overview, Purchase, Adjust Stock, History, Manage SKUs
  packaging_materials/      Overview, Purchase, Adjust, Manage Materials
  losses/                   Log Incident, Market Lifting, Quota vs Actual, History
  sales/                    New Sale, History
  vehicles_routes/          Overview, Manage
  targets_incentives/       Target Overview, Wholesale Cap Monitor, Set Targets / Caps
  settings.py                Backup & Restore, Users
assets/
  logo.png, style.css, license_public.json
demo_license/                Vendor-only keys/preseed/license (git-ignored, shipped in this
                              delivery so the activation screen has something to paste)
```

## Design notes worth knowing

- **One conversion utility.** Every 8oz-equivalent figure (targets, slabs,
  incentives, monthly loss quotas) is computed via `utils/conversions.py`.
  Nothing re-implements the `1 ml = 0.00017612 8oz` constant inline.
- **One cart pattern.** Inventory ▸ Purchase and Sales ▸ New Sale share the
  exact same "add line → editable cart table → clear → finalize"
  component (`components/cart.py`) so the interaction never drifts between
  the two.
- **Cache invalidation.** Every list/table read is `st.cache_data`-cached
  (`ttl=5s`); every write function explicitly `.clear()`s the caches it
  affects so the UI reflects new data immediately rather than waiting on
  the TTL.
- **Status color semantics are fixed app-wide:** 🔴 critical / 🟠 warning /
  🟡 caution / 🟢 ok — the same four colors mean the same four things on
  every KPI card, badge, and chart.
- **Backups.** A scheduled backup runs automatically once every 24h on app
  start (`utils/backup_utils.maybe_run_scheduled_backup`); manual backups
  and restores are available from **Settings → Backup & Restore**. Restore
  always takes a safety snapshot of the current DB first.

## Regenerating demo data / license

Delete `data/bottler.db` and restart the app to reseed from scratch. To
mint a fresh demo license (e.g. after rotating keys), see the vendor-side
generation script pattern used to produce `demo_license/license.txt` — it
calls `licensing.LicenseGenerator.generate_license(...)` with the private
key + preseed hash in `demo_license/keys.json` / `preseed.json`.
