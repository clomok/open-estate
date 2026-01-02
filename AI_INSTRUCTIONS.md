# Open Estate Dashboard - AI Context & Instructions

## 1. Project Identity

- **Name:** Open Estate Dashboard (`open-estate-dashboard`)
- **Role:** Senior Software Architect & Developer.
- **Goal:** Build a durable, self-hosted, offline-capable web application for family estate planning and transition management.
- **Core Philosophy:**

1. **Simplicity First:** Standard HTML/CSS, Python, SQLite. Avoid complex JS frameworks.
2. **Durability:** The app must be runnable 10+ years from now. No external CDNs (Chart.js is the only exception).
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
├── app.py                  # Application Factory + Custom Jinja Filters
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
        ├── manage_asset.html   # Smart Edit Form with Validation
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
- **Polymorphic Ledger:** Real Estate, Vehicles, Financials, Art, Jewelry, etc.
- **Smart Edit Forms:**
- High-visibility "Valuation" cards for Homes/Vehicles/Art.
- Dirty form detection (confirms discard on exit).
- Top-left "Cancel/Back" navigation.

- **Phase 5 Expansion (Real Estate):**
- `PropertyStructure` (Sheds/Pools), `LocationPoint` (GPS Pins), `RecurringBill` (Taxes/Utilities).

- **Contacts Hub (Formerly Details):**
- **Relationship Tags:** Visual badges showing "Owns X", "Beneficiary of Y", "Service Provider for Z".
- **Professional Roles:** Slots for Attorneys, CPAs, etc.

- **UI/UX Refinements:**
- **Global Currency:** Standardized formatting (`$1,000` or `$1,000.50`) via `| currency` filter.
- **Wide Layout:** Asset Details view widened to 1200px for better data density.
- **Hybrid Navigation:** Sidebar uses Flexbox on Desktop and Slide-out Drawer on Mobile.

- **Durability:**
- **Backup:** JSON export + human-readable HTML summary.
- **Restore:** JSON ingestion (full overwrite).

### ⏳ Roadmap / Pending

1. **Document Storage (Phase 6) - [NEXT PRIORITY]:**

- [ ] Configure `UPLOAD_FOLDER` in backend.
- [ ] Create `AssetDocument` model (file path, description, upload date).
- [ ] UI for uploading PDFs/Images to specific assets.
- [ ] Gallery view for receipts/titles.

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

- **Person:**
- `role` (Trustor, Beneficiary, Vendor, etc).
- Linked to assets via `owner_id` (ownership), `asset_beneficiaries` (inheritance), or `asset_vendor` (service jobs).

- **Sub-Items (Phase 5):**
- `PropertyStructure`: Sheds, Decks, Pools (`date_last_maintained`).
- `LocationPoint`: Latitude/Longitude pins (`label`, `description`).
- `RecurringBill`: Holding costs (`payee`, `amount`, `frequency`, `account_number`).

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
- Use `Asset.attributes` (JSON) for flexible fields rather than new columns.

2. **Database Changes:**

- If modifying `models.py`, you MUST Wipe/Reset the DB (using Option 5).
- **CRITICAL:** Never enable `PRAGMA journal_mode=WAL` in `app.py`.

3. **UI Changes:**

- Modify `src/static/css/style.css`.
- Always test mobile view (resize browser) to ensure the Drawer works.

---

_Last Updated: Phase 5.5 Complete (UX Polish, Contacts Hub, Currency Standards)._
