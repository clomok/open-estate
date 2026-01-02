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
- **Database:** SQLite (WAL Mode Disabled for Windows Docker compatibility).
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
├── app.py                  # Application Factory (WAL mode disabled)
├── instance/               # Persistent DB storage (estate.db)
├── scripts/
│   ├── seed.py             # Personalized data seed
│   └── seed_example.py     # Generic demo data seed
└── src/
    ├── models.py           # DB Schema (Person, Asset, Appraisal, Milestone, +Phase 5 models)
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
- `ops.ps1` for one-click maintenance (Wipe DB, Load Seed Data).
- Live code synchronization via Docker volumes.

- **Asset Management:**
- **Type-First Creation:** User selects category (Real Estate, Vehicle, etc.) before data entry.
- **Polymorphic Forms:** Specific fields for specific types.
- **Consolidated Ledger:** Unified view with Card layout.
- **Visual Polish:** Cards sorted by Value (High->Low) with Watermark background icons.

- **Real Estate Expansion (Phase 5):**
- **Tabbed Interface:** Organized into Overview, Accommodations, Systems, Financials, Team.
- **Coordinate Ledger:** GPS Pin Dropper ("Where is the Septic Tank?") using native HTML5 Geolocation.
- **Sub-Items:** Track Structures (Sheds/Pools), Recurring Bills (Taxes/Insurance), and specific Vendor assignments (Gardener/Pool Guy).

- **UI/UX:**
- **Hybrid Layout:** Sidebar uses Flexbox on Desktop and Slide-out Drawer on Mobile.
- **Mobile Optimizations:** Touch-friendly targets, hamburger/arrow toggle.

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
- `RecurringBill`: Holding costs (`payee`, `amount`, `frequency`).
- `AssetVendor`: Links `Person` to `Asset` with a Role (`Pool Cleaner`).

## 6. Operational Commands (Cheatsheet)

**Using the Ops Manager (Recommended):**

```powershell
.\ops.ps1
# Menu Options:
# 1. Update (Rebuild container)
# 5. Wipe DB (Resets DB & Restarts Server)
# 6. Seed (Loads data from scripts/)

```

**Manual Commands (Inside Container):**

```bash
# Enter Shell
.\ops.ps1 shell

# Reset Database Manually
rm instance/estate.db
rm -rf migrations
flask db init
flask db migrate -m "init"
flask db upgrade

```

## 7. Development Guidelines

1. **Modifying Assets:**

- Add new types in `src/forms.py` AND `src/routes/manage.py` (`ASSET_TYPES_META` + `ASSET_ICONS`).

2. **Database Changes:**

- If modifying `models.py`, you MUST run a migration or Wipe/Reset the DB.
- **Never** enable WAL mode in `app.py` while using Docker on Windows.

3. **UI Changes:**

- Modify `src/static/css/style.css`.
- Always test mobile view (resize browser) to ensure the Drawer works.

---

_Last Updated: Phase 5 Complete (Real Estate Expansion)._
