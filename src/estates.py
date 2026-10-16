"""Which estates this install holds, and where each one's data lives.

One running app serves several estates (a demo set and one per real trust).
Each estate is its own SQLite file, so nothing in the schema knows about
estates - there are no tenant columns, and a query can only ever see the one
database it was given:

    instance/
      estates.json                 the registry: slug, label, protected
      estates/<slug>/estate.db     that estate's whole database
      estates/<slug>/backups/      copies taken before a migration or a wipe

This module is deliberately standard-library only: `scripts/estate_admin.py
adopt` runs it on the host, before the container (and Flask) exist.
"""

import json
import os
import re
import tempfile

REGISTRY = "estates.json"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class EstateError(Exception):
    """A request the estate layout refuses: a bad slug, a duplicate, a guard."""


class EstateProtected(EstateError):
    """A destructive action was asked of an estate that holds real data."""


def check_slug(slug):
    """Slugs become folder names and URL segments, so the pattern is strict:
    lowercase letters, digits and dashes - nothing that can climb a path."""
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        raise EstateError(f"'{slug}' is not a valid estate name: use lowercase letters, "
                          "digits and dashes, starting with a letter or digit.")
    return slug


def estate_dir(root, slug):
    return os.path.join(root, "estates", check_slug(slug))


def db_path(root, slug):
    return os.path.join(estate_dir(root, slug), "estate.db")


def _registry_path(root):
    return os.path.join(root, REGISTRY)


def load(root):
    """The registry as a list of {slug, label, protected}, in display order.
    The first entry is the default estate. Missing file -> empty list."""
    path = _registry_path(root)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for row in data.get("estates", []):
        out.append({"slug": check_slug(row["slug"]),
                    "label": row.get("label") or row["slug"],
                    "protected": bool(row.get("protected", False))})
    return out


def save(root, estates):
    """Write the registry atomically: a reader in the other worker sees the
    old file or the new one, never half of either."""
    os.makedirs(root, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".estates-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"estates": estates}, f, indent=2)
        f.write("\n")
    os.replace(tmp, _registry_path(root))


def get(root, slug):
    for e in load(root):
        if e["slug"] == slug:
            return e
    return None


def default(root):
    estates = load(root)
    return estates[0] if estates else None


def add(root, slug, label, protected=False):
    check_slug(slug)
    estates = load(root)
    if any(e["slug"] == slug for e in estates):
        raise EstateError(f"An estate named '{slug}' already exists.")
    estates.append({"slug": slug, "label": (label or slug).strip(), "protected": bool(protected)})
    save(root, estates)
    return estates[-1]


def protect(root, slug):
    """Mark an estate as holding real data. One way on purpose: clearing the
    flag is a hand edit of estates.json, never a button."""
    estates = load(root)
    for e in estates:
        if e["slug"] == slug:
            e["protected"] = True
            save(root, estates)
            return e
    raise EstateError(f"No estate named '{slug}'.")


def require_unprotected(estate, action):
    """The one guard every destructive path calls - seed, wipe, restore -
    whether it runs from a script or from a button."""
    if estate is None:
        raise EstateError("No estate selected.")
    if estate["protected"]:
        raise EstateProtected(
            f"REFUSED: '{estate['slug']}' is protected - it holds real data, so it cannot be "
            f"{action}. Take a backup first; to lift the guard, set \"protected\": false for "
            f"it in instance/{REGISTRY} by hand.")
