# Open Estate Dashboard - AI Context & Instructions

## 1. Project Identity

- **Name:** Open Estate Dashboard (`open-estate-dashboard`)
- **Role:** Senior Software Architect & Developer.
- **Goal:** Build a durable, self-hosted, offline-capable web application for family estate planning and transition management.
- **Core Philosophy:**
  1.  **Simplicity First:** Standard HTML/CSS, Python, SQLite. Avoid complex JS frameworks.
  2.  **Durability:** The app must be runnable 10+ years from now. No external CDNs.
  3.  **Visual Clarity:** Differentiate "Technical Data" from "Family Summaries."
  4.  **Security:** Non-root Docker containers, local-only storage, CSRF protection.

## 2. Technical Stack

- **Language:** Python 3.11+
- **Web Framework:** Flask 3.x
- **Database:** SQLite (with `PRAGMA journal_mode=WAL` for concurrency).
- **ORM:** SQLAlchemy 2.x + Flask-Migrate (Alembic).
- **Frontend:** Jinja2 Templates + Server-Side Rendering.
- **Styling:** "Vendored" CSS (Tailwind-like utility classes stored in `src/static/css/style.css`).
- **Forms:** Flask-WTF (Server-side validation & CSRF tokens).
- **Infrastructure:** Docker Compose (Production-ready, restarts automatically).

## 3. Project Structure

```text
open-estate-dashboard/
├── ops.ps1                 # Operations script (Update, Logs, Shell)
├── .env                    # Secrets (Excluded from Git)
├── docker-compose.yml      # Orchestration
├── Dockerfile              # Build logic (Non-root user)
├── requirements.txt        # Python dependencies
├── app.py                  # Application Factory & Blueprints
├── config.py               # Configuration loader
├── instance/               # Persistent DB storage
├── scripts/                # Utility scripts
│   └── seed_example.py     # Public dummy data generator
└── src/
    ├── extensions.py       # Shared extensions (db, migrate)
    ├── models.py           # Database Schema
    ├── forms.py            # WTForms definitions
    ├── services/           # Logic Layer
    │   ├── auth_service.py # Session management
    │   ├── export_service.py # Backup logic (JSON+HTML Zip)
    │   └── import_service.py # Restore logic
    ├── routes/             # Web Handlers
    │   ├── auth.py         # Login
    │   ├── main.py         # Read-Only Views
    │   ├── manage.py       # Write/Edit Views
    │   └── settings.py     # Backup/Restore UI
    └── templates/          # HTML Files (Base, Dashboard, Assets, etc.)
```

## 4. Current Feature Status

### ✅ Completed Features

- **Infrastructure:** Secure Docker container with automated build script (`ops.ps1`).
- **Authentication:** Single-user password protection (via `.env`).
- **Dashboard:** Sticky sidebar layout with financial summaries (Net Worth, Totals).
- **Asset Management:**
- CRUD (Create, Read, Update, Delete) for Assets.
- **Dynamic Attributes:** "Idiot-proof" UI to add custom fields (VIN, Bank Name) stored as JSON.
- **Liabilities Logic:** Negative asset values are treated as debts.

- **Durability:**
- **Backup:** One-click export of `data.json` + `summary.html` (human readable).
- **Restore:** JSON ingestion to overwrite DB.

- **Visuals:** Dedicated views for Planning (Timeline), Details (People), and FAQ.

### ⏳ Pending / Roadmap

1. **Logic Engine (Milestone 4):**

- [ ] Automated "Health Check" on startup.
- [ ] Auto-generate Tasks (e.g., "Asset X has no beneficiary").
- [ ] Task Management UI (View/Complete tasks).

2. **Document Storage:**

- [ ] Upload PDF/Images for specific assets (stored in `instance/uploads`).

3. **Transition Protocol:**

- [ ] "Activate Protocol" button for Trustees (unlocks specific instructions upon death/incapacity).

4. **Security Hardening:**

- [ ] Add Rate Limiting for login attempts.

## 5. Database Schema (Key Highlights)

- **Person:** `id`, `name`, `role`, `attributes` (JSON).
- **Asset:** `id`, `name`, `type`, `value`, `is_in_trust`, `owner_id`, `attributes` (JSON).
- **Task:** `id`, `title`, `status`, `auto_generated` (Boolean).
- **Milestone:** `id`, `title`, `date_event`, `is_completed`.

_Note: The `attributes` JSON column is used extensively for flexible data to avoid schema migrations for minor details._

## 6. Operational Commands (Cheatsheet)

- **Update Code:** `.\ops.ps1` (Select 'Update') - Rebuilds container.
- **View Logs:** `.\ops.ps1` (Select 'Logs').
- **Database Migration:**

```powershell
.\ops.ps1 shell
flask db migrate -m "message"
flask db upgrade

```

- **Manual Backup:** Click "Download Backup" in Settings.

## 7. Development Guidelines

1. **Modifying UI:** Edit `src/templates/`. If styling changes, edit `src/static/css/style.css`.
2. **Modifying Logic:** Put heavy logic in `src/services/`. Keep routes thin.
3. **New Dependencies:** Add to `requirements.txt` -> Run `.\ops.ps1` (Update).
4. **Secrets:** NEVER commit `.env` or `scripts/seed.py`.

---

_Last Updated: Phase 3 Complete (Asset Management & Visuals)._
