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
    ├── models.py           # DB Schema (Person, Asset, Appraisal, Milestone)
    ├── forms.py            # Polymorphic WTForms (RealEstateForm, VehicleForm, etc.)
    ├── services/           # Logic Layer (Export, Import)
    ├── routes/             # Web Handlers (Main, Manage, Settings)
    └── templates/          # HTML (Asset Details, Ledger, Dashboard)


```

## 4. Current Feature Status

### ✅ Completed Features

- **Infrastructure:**
- Secure Docker container (non-root user).
- `ops.ps1` for one-click maintenance (Wipe DB, Load Seed Data).
- Live code synchronization via Docker volumes.
- **Asset Management:**
- **Type-First Creation:** User selects category (Real Estate, Vehicle, etc.) before data entry.
- **Polymorphic Forms:** Specific fields for specific types (e.g., VIN for cars, APN for houses).
- **Dynamic Attributes:** Extra fields stored as JSON (`attributes` column).
- **Consolidated Ledger:** Unified "Assets & Liabilities" view with Card layout.
- **Valuation History:** `Appraisal` table tracks value over time.
- **Visualization:** Interactive Line Chart for asset value history.
- **UI/UX:**
- **Hybrid Layout:** Sidebar uses Flexbox on Desktop (no overlap) and Slide-out Drawer on Mobile.
- **Mobile Optimizations:** Touch-friendly targets, hamburger/arrow toggle.
- **Navigation:** Back buttons and active state tracking.
- **Durability:**
- **Backup:** JSON export + human-readable HTML summary.
- **Restore:** JSON ingestion (full overwrite).

### ⏳ Roadmap / Pending

1. **Document Storage:**

- [ ] Upload PDFs/Images for specific assets (stored in `instance/uploads`).
- [ ] "Gallery" view for asset receipts/titles.

2. **Logic Engine:**

- [ ] Automated Health Checks (e.g., "Warn if Asset has no Beneficiary").
- [ ] Auto-generate Tasks based on data.

3. **Transition Protocol:**

- [ ] "In Case of Emergency" view for Trustees (unlocked via specific protocol).

4. **Household Bills & Unified Timeline:**

- [ ] **Bills Module:** Associate recurring bills (Utilities, Insurance, Tax) specifically with Real Estate assets.
- [ ] **Unified Timeline:** Upgrade the "Planning" view to aggregate Dates from Milestones, Tasks, Bill Due Dates, and Appraisal Histories into a single "Master Timeline".

## 5. Database Schema Key Points

- **Asset:**
- `asset_type`: String (RealEstate, Vehicle, Liability, etc.).
- `value_estimated`: Float (Positive for Assets, Negative for Liabilities).
- `attributes`: JSON (Stores VIN, Address, Account #).
- `appraisals`: Relationship to `Appraisal` table (History).
- **Appraisal:**
- `date`, `value`, `source` (Zillow, Official, etc.).

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

# Run Seed
python scripts/seed.py


```

## 7. Development Guidelines

1. **Modifying Assets:**

- Add new types in `src/forms.py` (Form Class) AND `src/routes/manage.py` (`ASSET_TYPES_META`).
- Ensure `save_asset_from_form` maps specific fields to `attributes` JSON.

2. **Database Changes:**

- If modifying `models.py`, you MUST run a migration or Wipe/Reset the DB.
- **Never** enable WAL mode in `app.py` while using Docker on Windows (causes Disk I/O errors).

3. **UI Changes:**

- Modify `src/static/css/style.css`.
- Always test mobile view (resize browser) to ensure the Drawer works.

---

_Last Updated: Phase 4 Complete (Roadmap Updated with Bills & Unified Timeline)._

```

```
