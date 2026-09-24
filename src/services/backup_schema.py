"""The single list of what a backup contains.

Export and restore both read this file, so they can never drift apart again.
Adding a model to src/models.py without adding it here is a silent data-loss
bug: the UI happily collects the data and the backup quietly drops it. That is
exactly what happened to the Phase 5/6 models, so tests/test_backup.py fails
the build if any mapped model is ever missing from BACKUP_MODELS.
"""

from src.models import (
    asset_beneficiaries,
    Appraisal,
    Asset,
    AssetVendor,
    LocationPoint,
    Milestone,
    Person,
    PropertyStructure,
    RecurringBill,
    Task,
    TrustProfile,
)

# (key in the JSON file, model class)
# Parents first: restore inserts in this order and wipes in reverse, so a
# foreign key never points at a row that does not exist yet.
BACKUP_MODELS = [
    ("people", Person),
    ("assets", Asset),
    ("appraisals", Appraisal),
    ("tasks", Task),
    ("milestones", Milestone),
    ("structures", PropertyStructure),
    ("location_points", LocationPoint),
    ("bills", RecurringBill),
    ("vendors", AssetVendor),
    ("trust_profile", TrustProfile),
]

# Association tables have no model class of their own, so they are listed
# separately. asset_beneficiaries carries the inheritance percentages - the
# most load-bearing fact in the whole binder.
BACKUP_TABLES = [
    ("asset_beneficiaries", asset_beneficiaries),
]
