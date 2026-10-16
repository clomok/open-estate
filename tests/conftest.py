import os
import sys

import pytest

# Tests run from the repo root without installing the package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# config.Config refuses to start without these, which is the point of it.
os.environ.setdefault("ADMIN_PASSWORD", "test_password")
os.environ.setdefault("SECRET_KEY", "test_secret_key")

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from config import Config  # noqa: E402
from src import estates  # noqa: E402
from src.extensions import db as _db  # noqa: E402


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


def make_app(root, slugs=("test",)):
    """An app whose estates live under `root`, with each of `slugs` registered
    and given its folder. The first one is the default estate."""
    class RootConfig(TestConfig):
        ESTATES_ROOT = str(root)
    for slug in slugs:
        os.makedirs(estates.estate_dir(str(root), slug), exist_ok=True)
        estates.add(str(root), slug, slug.title())
    return create_app(RootConfig)


@pytest.fixture
def app(tmp_path):
    """One estate, `test`, selected for the whole test. Requests go to
    /e/test/..., exactly as the browser does."""
    application = make_app(tmp_path)
    with application.app_context():
        g.estate = "test"
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()
        _db.engine.dispose()


@pytest.fixture
def db(app):
    return _db
