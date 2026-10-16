"""The single list of what a backup contains.

Export and restore both read this file, so they can never drift apart again.
Adding a model to src/models.py without adding it here is a silent data-loss
bug: the UI happily collects the data and the backup quietly drops it. That is
exactly what happened to the Phase 5/6 models, so tests/test_backup.py fails
the build if any mapped table is ever missing from BACKUP_MODELS.
"""

from src.models import (
    BeneficiaryDesignation,
    Entity,
    Event,
    Holding,
    HoldingVendor,
    LocationPoint,
    Person,
    PersonRole,
    Playbook,
    PlaybookStep,
    PropertyStructure,
    RecurringBill,
    Valuation,
)

BACKUP_VERSION = "4.0"

# (key in the JSON file, model class)
# Parents first: restore inserts in this order and wipes in reverse, so a
# foreign key never points at a row that does not exist yet.
BACKUP_MODELS = [
    ("people", Person),
    ("person_roles", PersonRole),
    ("entities", Entity),
    ("holdings", Holding),
    ("valuations", Valuation),
    # Who inherits what share - the most load-bearing fact in the binder.
    ("beneficiary_designations", BeneficiaryDesignation),
    ("structures", PropertyStructure),
    ("location_points", LocationPoint),
    ("bills", RecurringBill),
    ("vendors", HoldingVendor),
    # The timeline: events point at people, entities and holdings, so they
    # come after all three.
    ("events", Event),
    ("playbooks", Playbook),
    ("playbook_steps", PlaybookStep),
]

# Association tables with no model class of their own. v4 has none: every
# link carries data of its own and is a model above.
BACKUP_TABLES = []

# Columns that point at a row of the same table. Restore inserts rows whose
# pointer is empty first, so the row they point at always exists by the time
# it is referenced (the root entity before its add-ons, an asset before the
# loan secured by it).
SELF_REFERENCES = {
    "entities": "parent_id",
    "holdings": "secured_by_id",
}
