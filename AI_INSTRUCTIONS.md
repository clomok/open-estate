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
    ├── services/           # Logic Layer (Export, Import, Timeline)
    ├── routes/             # Web Handlers (Main, Manage, Settings)
    └── templates/          # HTML Templates
        ├── dashboard.html
        ├── timeline.html   # Unified Timeline View
        ├── assets.html
        ├── asset_details.html
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
- **Smart Edit Forms:** High-visibility "Valuation" cards.

- **Phase 5 Expansion:**
- `PropertyStructure` (Sheds/Pools), `LocationPoint` (GPS Pins), `RecurringBill` (Taxes/Utilities).

- **Contacts Hub:**
- Relationship Tags and Professional Roles.

- **Unified Timeline (Polished):**
- **Split-View Layout:** Upcoming vs. History with collapsible headers.
- **Dynamic Resizing:** "Upcoming" section shrinks to fit content (max 50%) when dual-view is active.
- **Visual Consistency:** Asset-specific icons (e.g., 🏠 for House History) used in timeline events.
- **Horizontal Cards:** High-density layout minimizing vertical scrolling.
- Filters and Saved Views (LocalStorage).

- **Durability:**
- Backup (JSON/HTML) & Restore.

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

## 5. Database Schema Key Points

- **Asset:**
- `asset_type`, `value_estimated`, `attributes` (JSON).
- **Relationships:** `appraisals`, `structures`, `location_points`, `bills`, `vendors`.

- **Person:**
- `role` (Trustor, Beneficiary, Vendor, etc).

- **Sub-Items:**
- `PropertyStructure`, `LocationPoint`, `RecurringBill`.

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
Remove-Item instance/estate.db
Remove-Item -Recurse migrations


```

---

_Last Updated: Timeline Visual Polish (Icons & Split View)._
