"""Column value <-> JSON value, driven off the SQLAlchemy column type.

Shared by the exporter, the importer and the v3 migration, so a date is
written and read back the same way on every path.
"""

from datetime import datetime, date

from sqlalchemy import Date as SADate, DateTime as SADateTime


def encode(value):
    """Make a column value JSON-safe."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def decode(column, value):
    """Turn a JSON value back into what the column expects."""
    if value is None or value == "":
        return None

    if isinstance(column.type, SADateTime):
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            # A v1.x backup may have written a bare date here.
            return datetime.combine(date.fromisoformat(value), datetime.min.time())

    if isinstance(column.type, SADate):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            return datetime.fromisoformat(value).date()

    return value


def row_kwargs(table, row_data):
    """Map one JSON record onto real columns.

    Unknown keys are ignored (a backup from a newer version still restores what
    this version understands) and absent keys are left out entirely, so the
    column's own default applies instead of being overwritten with None.
    """
    kwargs = {}
    for column in table.columns:
        if column.name in row_data:
            kwargs[column.name] = decode(column, row_data[column.name])
    return kwargs


def parent_first(rows, pointer):
    """Order rows so a row that points at another row of the same table comes
    after the row it points at. Raises on a cycle rather than looping."""
    ordered, placed, pending = [], set(), list(rows)
    while pending:
        ready = [r for r in pending if r.get(pointer) in (None, *placed)]
        if not ready:
            raise ValueError(f"rows reference each other in a loop through {pointer}")
        for r in ready:
            ordered.append(r)
            placed.add(r.get("id"))
        pending = [r for r in pending if r not in ready]
    return ordered
