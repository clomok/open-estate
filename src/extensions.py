import sqlite3

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import event
from sqlalchemy.engine import Engine

# We define these here so other files can import them without creating loops
db = SQLAlchemy()
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
