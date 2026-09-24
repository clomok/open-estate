import os
import sys

import pytest

# Tests run from the repo root without installing the package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# config.Config refuses to start without these, which is the point of it.
os.environ.setdefault("ADMIN_PASSWORD", "test_password")
os.environ.setdefault("SECRET_KEY", "test_secret_key")
os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from src.extensions import db as _db  # noqa: E402


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db
