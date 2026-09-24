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
├── ops.ps1                 # Master Operations script (Update, Wipe, Seed, Logs) - takes -Dataset
├── Makefile                # Linux/Mac equivalent - every target takes DATASET=<name>
├── .gitattributes          # Enforces LF line endings (Critical for Docker/Windows)
├── compose.yaml            # Docker orchestration (Mounts .:/app, one container per dataset)
├── app.py                  # Application Factory + Custom Jinja Filters
├── datasets/
│   ├── README.md           # How datasets work - read before touching deployment
│   ├── demo.env.example    # Template for a dataset (the only one committed)
│   └── <name>.env          # One per instance: port, secrets, label (GITIGNORED)
├── instance/
│   └── <name>/estate.db    # Per-dataset DB storage (GITIGNORED)
├── scripts/
│   ├── seed.py             # Personalized data seed
│   └── seed_example.py     # Generic demo data seed
├── tests/                  # pytest, in-memory DB, no container needed
└── src/
    ├── models.py           # DB Schema (Person, Asset, Appraisal, RecurringBill, etc.)
    ├── forms.py            # Polymorphic WTForms
    ├── services/
    │   ├── backup_schema.py # THE list of what a backup covers (export + import read it)
    │   ├── export_service.py
    │   ├── import_service.py
    │   └── timeline_service.py
    ├── routes/             # Web Handlers (Main, Manage, Settings)
    └── templates/          # HTML Templates
        ├── dashboard.html
        ├── timeline.html   # Unified Timeline View
        ├── assets.html
        ├── asset_details.html
        └── ...



```

## 3.5 Multi-Dataset Layout

The app is single-tenant by design - a singleton `TrustProfile`, one
`ADMIN_PASSWORD`, one `DATABASE_URL`. Several estates (demo, family, client)
are therefore kept apart by running **separate containers**, not by adding
tenant columns. No application code knows about datasets; it is a file per
instance (`datasets/<name>.env`) and a mount per instance
(`instance/<name>/` -> `/app/instance`).

Consequences to respect:

- `DATASET` has **no default**. Compose fails loudly if it is unset.
- `DATABASE_URL` is identical in every dataset. Do not make it dataset-specific -
  the mount is the one thing that chooses an estate, and one place to get right
  beats two.
- `DATASET_PROTECTED=1` marks real data. `wipe` and `seed` refuse on it outright.
- Never put real data in a seed script. Real data moves between instances
  through **Settings -> Download Backup** and **Settings -> Restore**.
- The sidebar badge (`DATASET_LABEL`) must stay visible on every page. It is the
  thing that stops someone editing a real estate believing it is the demo.

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
- Renamed from "Details" to "Contacts" for clarity.
- Relationship Tags and Professional Roles.
- **Unified Timeline (Polished):**
- **Split-View Layout:** Upcoming vs. History with collapsible headers.
- **Dynamic Resizing:** "Upcoming" section shrinks to fit content (max 50%) when dual-view is active.
- **Visual Consistency:** Asset-specific icons (e.g., 🏠 for House History) used in timeline events.
- **Horizontal Cards:** High-density layout minimizing vertical scrolling.
- Filters and Saved Views (LocalStorage).
- **Durability:**
- Backup (JSON/HTML) & Restore, covering **every** table including association rows.
- Single source of truth: `src/services/backup_schema.py`.
- **Multi-Dataset:**
- One container per estate; own DB, port, password and sidebar badge.
- Destructive ops refuse on a dataset marked `DATASET_PROTECTED=1`.
- **Trust Profile (Phase 6):**
- **New "Details" Page:** High-level trust configuration.
- **Sensitivity Controls:** "Estimated Death Date" is hidden by default (toggleable).
- **Review Schedule:** Configuration for annual reviews.

### ⏳ Roadmap / Pending

1. **Document Storage (Phase 6) - [NEXT PRIORITY]:**

- [ ] Configure `UPLOAD_FOLDER` in backend.
- [ ] Create `AssetDocument` model (file path, description, upload date).
- [ ] UI for uploading PDFs/Images to specific assets.
- [ ] Gallery view for receipts/titles.

2. **Logic Engine & Notifications:**

- [ ] Automated Health Checks (e.g., "Warn if Asset has no Beneficiary").
- [ ] **Notification System:** Handle email/local alerts for Annual Reviews (as configured in Details).

3. **Transition Protocol:**

- [ ] "In Case of Emergency" view for Trustees (unlocked via specific protocol).

## 4.5 Non-Negotiables When Changing the Schema

**Adding a model or an association table means adding it to
`src/services/backup_schema.py` in the same commit.** Export and restore both
read that one list; a table missing from it is data the UI collects and the
backup silently drops. That is not hypothetical - Task, PropertyStructure,
LocationPoint, RecurringBill, AssetVendor, TrustProfile and every beneficiary
share were all lost on a round trip while the app flashed "restored
successfully". `tests/test_backup.py` now fails the build if it happens again,
so run the tests before calling a schema change done:

```bash
pip install -r requirements-dev.txt
make test
```

Serialization is driven off the SQLAlchemy column types, so a new **column** on
an existing model is covered automatically. Only new **tables** need the edit.

## 5. Database Schema Key Points

- **Asset:**
- `asset_type`, `value_estimated`, `attributes` (JSON).
- **Relationships:** `appraisals`, `structures`, `location_points`, `bills`, `vendors`.
- **TrustProfile (Singleton):**
- `name`, `date_established`, `date_death_estimated`, `date_death_actual`, `review_frequency`, `next_review_date`.
- **Person:**
- `role` (Trustor, Beneficiary, Vendor, etc).
- **Sub-Items:**
- `PropertyStructure`, `LocationPoint`, `RecurringBill`.

## 6. Operational Commands (Cheatsheet)

Every command names its dataset. There is no default.

**Using the Ops Manager (Windows, Recommended):**

```powershell
.\ops.ps1 -Dataset demo
# Menu Options:
# 1. Update (Rebuild container)
# 5. Wipe DB (Resets DB & Restarts Server - REQUIRED if schema changes)
# 6. Seed (Loads data from scripts/)
#
# 5 and 6 refuse outright on a dataset with DATASET_PROTECTED=1.



```

**Using the Makefile (Linux/Mac):**

```bash
make list                    # what datasets exist here
make new DATASET=demo        # create one from the template
make up DATASET=demo         # start it
make logs DATASET=demo
make shell DATASET=demo
make wipe DATASET=demo       # confirms by typing the dataset name
make test                    # no container, no dataset



```

**Recovering a broken container:**

```bash
# Rebuild the schema from the tracked migration history. Do NOT delete
# migrations/ and regenerate it - 'flask db upgrade' is what depends on it,
# and throwing it away is what the old wipe routine used to do.
make shell DATASET=demo
flask db upgrade



```

---

_Last Updated: multi-dataset packaging + full-coverage backup/restore._
