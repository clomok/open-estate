"""The root of every dataset: exactly one trust.

v3 rule: each dataset has one root entity of kind `trust`. It is created on
first use (from the defaults below) when a database has none - a fresh
install, or a restore of an empty file - and every other entity is an add-on
attached to it. The database enforces "at most one"; this module supplies
"at least one".
"""

from flask import g, has_request_context

from src.extensions import db
from src.models import Entity

# The name a trust gets when nothing better is known - a migration or a restore
# runs outside any request, so it cannot see which estate it is building. It is
# a placeholder, never a name anyone chose.
PLACEHOLDER_NAME = "The Family Trust"


def estate_trust_name():
    """The trust's name taken from the estate on screen: 'Kyle' -> 'The Kyle
    Family Trust'. A label that already names a trust is used as it is. None
    outside a request, or when no estate is selected."""
    if not has_request_context():
        return None
    entry = g.get("estate_entry")
    label = (entry or {}).get("label", "").strip()
    if not label:
        return None
    if "trust" in label.lower():
        return label
    return f"The {label} Family Trust"


def get_root_entity(create=True):
    root = Entity.query.filter_by(is_root=True).first()
    if root is None and create:
        root = Entity(kind="trust", name=estate_trust_name() or PLACEHOLDER_NAME,
                      is_root=True, review_frequency="Annual")
        db.session.add(root)
        db.session.commit()
    elif root is not None and root.name == PLACEHOLDER_NAME:
        # Still the placeholder: name it for the estate it belongs to. A name
        # someone typed is never touched.
        name = estate_trust_name()
        if name:
            root.name = name
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
