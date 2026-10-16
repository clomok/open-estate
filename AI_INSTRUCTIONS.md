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
├── ops.ps1                 # Master Operations script (Update, Wipe, Seed, Logs) - Wipe/Seed take -Estate
├── Makefile                # Linux/Mac equivalent - seed/wipe take ESTATE=<slug>
├── .gitattributes          # Enforces LF line endings (Critical for Docker/Windows)
├── compose.yaml            # Docker orchestration (Mounts .:/app, one container for every estate)
├── app.py                  # Application Factory + Custom Jinja Filters
├── datasets/
│   ├── README.md           # How estates work - read before touching deployment
│   ├── site.env.example    # Template for the site's settings (the only one committed)
│   └── site.env            # Port, bind, login for the whole site (GITIGNORED)
├── instance/               # (GITIGNORED)
│   ├── estates.json        # The estate registry: slug, label, protected
│   └── estates/<slug>/estate.db  # One SQLite file per estate
├── scripts/
│   ├── upgrade_db.py       # Migrates every estate at start; --estate for one
│   ├── estate_admin.py     # list / adopt / wipe
│   ├── seed.py             # Personalized data seed
│   └── seed_example.py     # Generic demo data seed (--estate required)
├── tests/                  # pytest, temp-dir estates, no container needed
└── src/
    ├── estates.py          # THE estate registry + the protected guard (stdlib only)
    ├── extensions.py       # db: its only engine is the estate the URL names
    ├── models.py           # DB Schema (Person, Asset, Appraisal, RecurringBill, etc.)
    ├── forms.py            # Polymorphic WTForms
    ├── services/
    │   ├── backup_schema.py # THE list of what a backup covers (export + import read it)
    │   ├── export_service.py
    │   ├── import_service.py
    │   ├── feeds.py         # THE registry of derived timeline items
    │   ├── events.py        # done / snooze / repeat, and the Row the pages show
    │   ├── playbooks.py     # running a playbook on a date
    │   ├── default_playbook.py  # the shipped death-of-trustor steps (data)
    │   └── timeline_service.py  # history rows: valuations, purchases, maintenance
    ├── routes/             # Web Handlers (Main, Manage, Settings)
    └── templates/          # HTML Templates
        ├── now.html        # Home page: what needs doing now
        ├── dashboard.html  # /overview: net worth
        ├── timeline.html   # Unified Timeline View
        ├── assets.html
        ├── asset_details.html
        └── ...



```

## 3.5 Several Estates, One App

One running app holds several estates (demo, plus one per real trust),
switched from the dropdown at the top of the sidebar. Each estate is its own
SQLite file, `instance/estates/<slug>/estate.db`, listed in
`instance/estates.json`. There are **no tenant columns**: within a request the
app has exactly one database, so no query can see two estates. Full picture:
`datasets/README.md`.

Consequences to respect:

- **Estate pages live under `/e/<slug>/`.** The `main`, `manage` and
  `settings` blueprints are registered with that prefix; `url_for` fills the
  slug in from `g.estate` (`app.py`), so templates and routes never pass it by
  hand. Do not move estate selection into the session: the URL is what keeps
  two tabs on two estates from writing into each other.
- **`db.engines` returns only `g.estate`'s engine** (`src/extensions.py`), and
  raises `NoEstateSelected` when nothing is selected. A script that touches
  data sets `g.estate = <slug>` inside its own `app.app_context()`, one
  context per estate. Never default it.
- **`protected` lives in `estates.json`.** Seed, wipe and restore call
  `estates.require_unprotected` themselves; the Makefile and `ops.ps1` only
  make you name the estate. Protect is one-way from the UI.
- **Migrations run per estate.** `scripts/upgrade_db.py` migrates every
  registered estate at container start; creating an estate runs it with
  `--estate` in a subprocess (Alembic's logging config must not run inside a
  gunicorn worker).
- Never put real data in a seed script. Real data moves between estates and
  installs through **Settings → Download Backup** and **Settings → Restore**.
- The dropdown must stay visible on every page and name the estate on screen.
  It is the thing that stops someone editing a real estate believing it is
  the demo. A protected estate renders it in the warm `dataset-badge-live`
  style.
- One login opens every estate on a site.

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
- **Timeline engine (Phase B):**
- **Now page is home (`/`):** Overdue · This week · Next 30 days · Needs
  attention · Recently done; filters by assignee, phase, entity; one-tap done,
  snooze a week, open. The net-worth dashboard is `/overview`.
- **Derived feeds** (bills due, trust review, not verified lately, stale
  values, unreachable contacts, beneficiary gaps) computed at read time.
- **Playbooks**, with the editable default death-of-trustor playbook.
- **Durability:**
- Backup (JSON/HTML) & Restore, covering **every** table including association rows.
- Single source of truth: `src/services/backup_schema.py`.
- **Several estates:**
- One app, one SQLite file per estate, switched from the sidebar dropdown; new estates created there.
- Seed, wipe and restore refuse an estate marked protected in `instance/estates.json`.
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

2. **Notifications:**

- [ ] Email / push digest of the Now page. Not decided. What it would need:
  a cron entry calling a script that builds `events.now_sections()` for
  today, an SMTP setting per site, and a "sent" record so a digest is not
  repeated. The feeds already compute everything a digest would say.

3. **Transition Protocol:**

- [x] Death-of-trustor playbook (runs on the date of passing; Phase B).
- [ ] "In Case of Emergency" printable view for Trustees (Phase D).

## 4.5 Non-Negotiables When Changing the Schema

**1. Every schema change is an Alembic migration. Never wipe and recreate.**
A protected estate holds a family's real data; it can only ever move forward
by migration. The container runs `scripts/upgrade_db.py` before gunicorn on
every start: for each estate it copies the database to that estate's
`backups/` folder and then runs `flask db upgrade`, so deploying a change *is*
applying its migration to every estate.

```bash
# after editing src/models.py, inside the container or a dev venv:
flask db migrate -m "what changed"     # autogenerate a draft
# READ the draft. Autogenerate cannot see renames or data moves - write those
# by hand (see migrations/versions/b7e2c41f9a03_ledger_v3.py for a data move).
flask db upgrade
make test                              # test_migrations proves models == migrations
```

`tests/test_migrations.py::test_migrations_build_exactly_the_model_schema`
fails the build when `src/models.py` and the migrations disagree, so a model
change without its migration cannot pass.

**2. Adding a model means adding it to `src/services/backup_schema.py` in the
same commit.** Export and restore both read that one list; a table missing
from it is data the UI collects and the backup silently drops. That is not
hypothetical - Task, PropertyStructure, LocationPoint, RecurringBill,
AssetVendor, TrustProfile and every beneficiary share were all lost on a round
trip while the app flashed "restored successfully". `tests/test_backup.py`
fails the build if it happens again. Serialization is driven off the column
types, so a new **column** on an existing model is covered automatically.

**3. Changing the backup layout bumps `BACKUP_VERSION` and keeps old files
restorable.** Old files are converted one frozen step at a time, each step
the same code its migration runs on an old database:
`src/services/v2_upgrade.py` (v1/v2 -> v3) then `src/services/v3_upgrade.py`
(v3 -> v4: task + milestone -> event, plus the default playbook). A v5 gets
its own step.

```bash
pip install -r requirements-dev.txt
make test
```

## 5. Database Schema Key Points (v4)

- **Entity:** exactly one root per estate, `kind = trust`, `is_root = 1`
  (enforced in the database). It carries the trust's name, dates, review
  schedule and transition dates; the Trust page edits it. Other kinds
  (`corporation`, `llc`, `retirement_account`, `individual`) are optional
  add-ons with `parent_id` = the root.
- **Holding:** the ledger. `side` ∈ `asset` · `liability` · `equity`,
  `type_code`, `value_cents` (always positive - the side gives the sign),
  `attributes` (JSON, validated against the registry), `entity_id` (NULL = in
  the trust), `owner_id`, `ownership_pct` (equity), `secured_by_id`
  (liability -> an asset). Net worth = Σ assets − Σ liabilities; equity is
  reported beside it, not inside it.
- **`src/holding_types.py`:** the one list of types, per side, with each
  field's `type` and `sensitivity`. Every side has `custom`, whose fields the
  user names. Add a type there and nowhere else.
- **Person:** `kind` (individual / organisation) and any number of
  **PersonRole** rows.
- **BeneficiaryDesignation:** holding, person, `percentage`, `kind`
  (`trust_schedule` · `account_tod` · `will`). Deleting a person with shares
  is refused.
- **Valuation:** dated history per holding (`value_cents`); the newest sets the
  holding's value.
- **Sub-items on every holding:** `PropertyStructure`, `LocationPoint`,
  `RecurringBill` (`amount_cents`), `HoldingVendor`.
- **Event:** the timeline. `kind` (task · deadline · renewal · review ·
  milestone · memory), `date` (nullable = undated), `done_at`, `assignee_id`,
  `phase` (now · planning · transition · administration), optional links to a
  holding / entity / person, `source`, and `repeat_every` + `repeat_unit`
  (done spawns the next one, counted from the event's own date).
- **Derived items are not rows.** `src/services/feeds.py` computes them on
  every read. Each has a `source` key with its cycle after the `@`
  (`bill:42@2026-11-01`, `verify:holding:7@never`). Touching one (done,
  snooze, note) writes ONE event with that source; `uq_event_source` makes a
  second impossible and the feed skips any source that has a row. Done runs
  the feed's `on_done`, which moves the record to its next cycle (a bill's
  next due date, a verified stamp), so the next cycle is a new key.
  **Never delete a derived event's row** - the item would come straight
  back; the delete route marks it done instead.
- **Adding a feed** = one `Feed(...)` in `FEEDS` with a unique `prefix`.
  Per-type thresholds (`verify_days`, `revalue_days`) live on each type in
  `src/holding_types.py`.
- **Playbook / PlaybookStep:** steps are `offset_days` after a trigger date,
  with a `who_role` (a PERSON_ROLES code) and a document to find. A run
  writes one event per step, `phase=transition`, source
  `playbook:<id>@<date>:step:<step id>` (so running twice adds nothing).
  Setting the trust's `date_death_actual` offers the `death_of_trustor` one.
- **Every table:** `created_at`, `updated_at`, `last_verified` (set only by
  "mark verified").
- **Money is Integer cents; dates are `Date`.** `src/money.py` and the
  `currency` filter are the only places cents become dollars.
- **Foreign keys are enforced** (`PRAGMA foreign_keys=ON`, `src/extensions.py`).

## 6. Operational Commands (Cheatsheet)

One stack serves every estate. Only seed and wipe act on one estate's data,
and they must name it - there is no default.

**Using the Ops Manager (Windows, Recommended):**

```powershell
.\ops.ps1
# Menu Options:
# 1. Update (Rebuild container)
# 5. Wipe (empties ONE demo estate - never needed for a schema change;
#    restarting the container applies new migrations to every estate)
# 6. Seed (Loads data from scripts/ into ONE estate)
#
# 5 and 6 ask which estate, and refuse outright on a protected one.
.\ops.ps1 -Run adopt -Estate demo   # once, to move an old dataset folder in
```

**Using the Makefile (Linux/Mac):**

```bash
make up                      # start the stack (needs datasets/site.env)
make logs
make shell
make estates                 # list the estates here
make seed ESTATE=demo        # refused on a protected estate
make wipe ESTATE=demo        # confirms by typing the estate name
make adopt DATASET=<old>     # once per old instance/<old>/ folder, stack stopped
make test                    # no container, no estate
```

**Recovering a broken container:**

```bash
# Rebuild the schema from the tracked migration history. Do NOT delete
# migrations/ and regenerate it - 'flask db upgrade' is what depends on it,
# and throwing it away is what the old wipe routine used to do.
make shell
python scripts/upgrade_db.py            # every estate
python scripts/upgrade_db.py --estate demo



```

---

_Last Updated: several estates in one app (estate dropdown, /e/<slug>/ URLs, estates.json)._
