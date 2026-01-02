# Open Estate Dashboard - AI Context & Instructions

## 1. Project Identity

- **Name:** Open Estate Dashboard (`open-estate-dashboard`)
- **Role:** Senior Software Architect & Developer.
- **Goal:** Build a durable, self-hosted, offline-capable web application for family estate planning and transition management.
- **Core Philosophy:**

1. **Simplicity First:** Standard HTML/CSS, Python, SQLite. Avoid complex JS frameworks.
2. **Durability:** The app must be runnable 10+ years from now. No external CDNs (Chart.js is currently CDN but flagged for local vendor).
3. **Visual Clarity:** Differentiate "Technical Data" from "Family Summaries."
4. **Mobile First:** Responsive design with a hybrid sidebar (Fixed on Desktop, Drawer on Mobile).

## 2. Technical Stack

- **Language:** Python 3.11+
- **Web Framework:** Flask 3.x
- **Database:** SQLite (WAL Mode **STRICTLY DISABLED** for Windows Docker compatibility).
- **ORM:** SQLAlchemy 2.x + Flask-Migrate (Alembic).
- **Frontend:** Jinja2 Templates + Vanilla CSS (No build steps).
- **Charting:** Chart.js (via CDN).
- **Infrastructure:** Docker Compose (Volume sync enabled for live development).
- **OS Compatibility:** Optimized for Windows Host (LF line endings forced via `.gitattributes`).

## 3. Project Structure

```text
open-estate-dashboard/
├── ops.ps1                 # Master Operations script (Update, Wipe, Seed, Logs)
├── .gitattributes          # Enforces LF line endings (Critical for Docker/Windows)
├── .env                    # Secrets (Excluded from Git)
├── compose.yaml            # Docker orchestration (Mounts .:/app)
├── app.py                  # Application Factory (WAL mode explicitly disabled)
├── instance/               # Persistent DB storage (estate.db)
├── scripts/
│   ├── seed.py             # Personalized data seed
│   └── seed_example.py     # Generic demo data seed
└── src/
    ├── models.py           # DB Schema (Person, Asset, Appraisal, RecurringBill, etc.)
    ├── forms.py            # Polymorphic WTForms
    ├── services/           # Logic Layer (Export, Import)
    ├── routes/             # Web Handlers (Main, Manage, Settings)
    └── templates/          # HTML Templates
        ├── dashboard.html
        ├── assets.html
        ├── asset_details.html  # Tabbed Interface
        ├── manage_asset.html
        ├── manage_subitem.html # Generic form for Pins/Bills/Structures
        └── ...


```

## 4. Current Feature Status

### ✅ Completed Features

- **Infrastructure:**
- Secure Docker container (non-root user).
- `ops.ps1` for one-click maintenance.
- **WAL Mode Disabled:** Fixed `disk I/O error` on Windows/Docker mounts.
- **Asset Management:**
- **Type-First Creation:** Real Estate, Vehicles, Financials, etc.
- **Refactoring:** "Utility" top-level asset **removed**. Utilities are now tracked as `RecurringBill` items attached to a Property.
- **Consolidated Ledger:** Unified view with Card layout.
- **Real Estate Expansion (Phase 5):**
- **Tabbed Interface:** Overview, Accommodations, Systems, Financials, Team.
- **Coordinate Ledger:** GPS Pin Dropper for physical locations.
- **Sub-Items:**
- `PropertyStructure`: Sheds, Pools.
- `RecurringBill`: Holding costs (Taxes, Water, HOA) with `account_number`.
- `AssetVendor`: Service providers specific to an asset.

- **UI/UX:**
- **Hybrid Layout:** Sidebar uses Flexbox on Desktop and Slide-out Drawer on Mobile.
- **Mobile Optimizations:** Touch-friendly targets.
- **Durability:**
- **Backup:** JSON export + human-readable HTML summary.
- **Restore:** JSON ingestion (full overwrite).

### ⏳ Roadmap / Pending

1. **Document Storage (Phase 6):**

- [ ] Upload PDFs/Images for specific assets (stored in `instance/uploads`).
- [ ] "Gallery" view for asset receipts/titles.

2. **Logic Engine:**

- [ ] Automated Health Checks (e.g., "Warn if Asset has no Beneficiary").
- [ ] Auto-generate Tasks based on data (e.g., "Pay Property Tax" based on Bill due date).

3. **Transition Protocol:**

- [ ] "In Case of Emergency" view for Trustees (unlocked via specific protocol).

4. **Unified Timeline:**

- [ ] Upgrade "Planning" view to aggregate Dates from Milestones, Tasks, Bill Due Dates, and Appraisal Histories.

## 5. Database Schema Key Points

- **Asset:**
- `asset_type`, `value_estimated`, `attributes` (JSON).
- **Relationships:** `appraisals`, `structures`, `location_points`, `bills`, `vendors`.
- **Phase 5 Extensions:**
- `PropertyStructure`: Sheds, Decks, Pools (`date_last_maintained`).
- `LocationPoint`: Latitude/Longitude pins (`label`, `description`).
- `RecurringBill`: Holding costs (`payee`, `amount`, `frequency`, `account_number`).
- `AssetVendor`: Links `Person` to `Asset` with a Role (`Pool Cleaner`).

## 6. Operational Commands (Cheatsheet)

**Using the Ops Manager (Recommended):**

```powershell
.\ops.ps1
# Menu Options:
# 1. Update (Rebuild container)
# 5. Wipe DB (Resets DB & Restarts Server - REQUIRED if schema changes)
# 6. Seed (Loads data from scripts/)


```

**Manual Commands (Inside Container):**

```bash
# Enter Shell
.\ops.ps1 shell

# Reset Database Manually (If container crashes loop)
# Run these on HOST machine if using Windows:
Remove-Item instance/estate.db
Remove-Item -Recurse migrations


```

## 7. Development Guidelines

1. **Modifying Assets:**

- Add new types in `src/forms.py` AND `src/routes/manage.py`.
- **Do not** add high-maintenance types; prefer sub-items (like `RecurringBill`).

2. **Database Changes:**

- If modifying `models.py`, you MUST Wipe/Reset the DB (using Option 5).
- **CRITICAL:** Never enable `PRAGMA journal_mode=WAL` in `app.py`. It causes file locking issues on Windows Docker mounts.

3. **UI Changes:**

- Modify `src/static/css/style.css`.
- Always test mobile view (resize browser) to ensure the Drawer works.

---

_Last Updated: Utility Deprecation Complete & WAL Fix Applied._
