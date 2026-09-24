# Open Estate Dashboard

**A durable, self-hosted, offline-first digital vault for family estate planning and transition management.**

![Status](https://img.shields.io/badge/Status-In%20Development-yellow)
![Stack](https://img.shields.io/badge/Stack-Python%20%7C%20Flask%20%7C%20SQLite%20%7C%20Docker-blue)

## 📋 The Goal

This project was born out of a need for a simple, resilient system to organize family trusts, assets, and emergency protocols. Unlike commercial SaaS products that might disappear or change pricing, this dashboard is designed to:

1.  **Last Decades:** Built on standard technologies (HTML, CSS, Python, SQLite) that will still be readable in 20+ years.
2.  **Run Offline:** Zero reliance on external CDNs or internet connectivity once deployed.
3.  **Ensure Privacy:** Self-hosted on your own hardware (Raspberry Pi, NAS, or Desktop). Your data never leaves your house.

## 🧠 Core Philosophy

1.  **Simplicity First:** We avoid complex JavaScript frameworks. Server-side rendering ensures the app is fast, lightweight, and easy to maintain.
2.  **Consent for Complexity:** Every feature must justify its existence. If it adds maintenance burden, it is rejected.
3.  **Visual Clarity:** Differentiates "Technical Details" (for execution) from "Layman Summaries" (for decision making).
4.  **Durability:** Data is portable. One-click backups provide both a machine-readable JSON file and a human-readable HTML summary, and they carry the _whole_ database — `src/services/backup_schema.py` is the single list that export and restore both read, with a test that fails the build if a new table is ever left out of it.

## 🛠️ Tech Stack

- **Backend:** Python 3.11 + Flask
- **Database:** SQLite (Single file, easy to backup)
- **Frontend:** Jinja2 Templates + Minimal CSS (No build steps required)
- **Deployment:** Docker Compose (Containerized & Isolated)

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose installed on your machine.

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/clomok/open-estate.git
    cd open-estate
    ```

2.  **Create a dataset:**

    Each estate runs as its own instance, defined by one file in `datasets/`.
    See [`datasets/README.md`](datasets/README.md) for the full picture.

    ```bash
    make new DATASET=demo        # copies the template, creates instance/demo/
    # Edit datasets/demo.env: set a unique PORT, SECRET_KEY and ADMIN_PASSWORD
    ```

3.  **Run the App (Windows):**
    Use the included operations script:

    ```powershell
    .\ops.ps1 -Dataset demo
    # Select Option 1 (Update) to build and start the container
    ```

    **Run the App (Linux/Mac):**

    ```bash
    make up DATASET=demo
    ```

4.  **Access:**
    Open your browser to the `PORT` set in `datasets/demo.env` (5000 by default).
    The sidebar shows which dataset you are looking at.

> Upgrading an install from before datasets existed? Run `make adopt DATASET=<name>`
> — the stack will refuse to start until the dataset file exists.

## ✅ Tests

No container needed — the suite runs against an in-memory database:

```bash
pip install -r requirements-dev.txt
make test
```

## 🗺️ Roadmap

- [x] **Secure Infrastructure:** Non-root Docker container with Authentication.
- [x] **Asset Management:** Add/Edit Assets, Liabilities, and Vehicles.
- [x] **Dynamic Details:** Flexible "Attribute" system for custom data (VIN, Safe Combos, etc).
- [x] **Durability Layer:** JSON/HTML Backup & Restore system, covering every table.
- [x] **Multiple Estates:** One container per dataset — separate database, port, password and badge.
- [ ] **Logic Engine:** Automated health checks (e.g., "Warn if Asset has no Beneficiary").
- [ ] **Document Storage:** Secure local upload for PDF trust documents.
- [ ] **Transition Protocol:** "In Case of Emergency" view for Trustees.

## ⚠️ Disclaimer

**This software is for organizational purposes only.** It is not a substitute for legal advice, a licensed attorney, or a financial advisor. Always consult with professionals regarding estate planning and trust administration.
