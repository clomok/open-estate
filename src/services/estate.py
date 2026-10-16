"""The root of every dataset: exactly one trust.

v3 rule: each dataset has one root entity of kind `trust`. It is created on
first use (from the defaults below) when a database has none - a fresh
install, or a restore of an empty file - and every other entity is an add-on
attached to it. The database enforces "at most one"; this module supplies
"at least one".
"""

from src.extensions import db
from src.models import Entity


def get_root_entity(create=True):
    root = Entity.query.filter_by(is_root=True).first()
    if root is None and create:
        root = Entity(kind="trust", name="The Family Trust", is_root=True,
                      review_frequency="Annual")
        db.session.add(root)
        db.session.commit()
    return root


def check_single_root():
    """Raise if a restore would leave a dataset with no trust at its root."""
    count = Entity.query.filter_by(is_root=True).count()
    if count != 1:
        raise ValueError(f"A dataset needs exactly one root trust; this one would have {count}.")


def addon_entities():
    return (Entity.query.filter_by(is_root=False)
            .order_by(Entity.kind, Entity.name).all())
