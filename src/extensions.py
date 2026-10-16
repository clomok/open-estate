import sqlite3
import threading

import sqlalchemy as sa
from flask import current_app, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine

from src import estates


class NoEstateSelected(RuntimeError):
    """Something touched the database with no estate chosen for it."""


class EstateSQLAlchemy(SQLAlchemy):
    """Flask-SQLAlchemy whose only engine is the selected estate's.

    Every path to the database - `db.session`, `db.engine`, `create_all`,
    the Alembic env - asks `engines` for its connection, so this property is
    the whole seam. The selection lives in `g.estate`, which belongs to one
    app context: one request, or one `with app.app_context()` in a script.
    It is set by the `/e/<slug>/` URL (app.py) or by a script naming its
    estate, and it is never defaulted here. With no selection there is no
    engine at all, so a write that forgot to say where it goes fails instead
    of landing in whichever estate happened to be first.
    """

    _estate_lock = threading.Lock()

    @property
    def engines(self):
        app = current_app._get_current_object()
        slug = g.get("estate")
        if slug is None:
            raise NoEstateSelected("No estate is selected for this request.")
        cache = app.extensions.setdefault("estate_engines", {})
        engine = cache.get(slug)
        if engine is None:
            with self._estate_lock:
                engine = cache.get(slug)
                if engine is None:
                    path = estates.db_path(app.config["ESTATES_ROOT"], slug)
                    engine = sa.create_engine(f"sqlite:///{path}")
                    cache[slug] = engine
        return {None: engine}


# We define these here so other files can import them without creating loops
db = EstateSQLAlchemy()
migrate = Migrate()


@event.listens_for(Engine, "connect")
def _enforce_foreign_keys(dbapi_connection, connection_record):
    """SQLite ignores every FOREIGN KEY clause unless this is set, and it has
    to be set again on each new connection. Without it an edit years from now
    can leave a valuation pointing at a holding that no longer exists."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
