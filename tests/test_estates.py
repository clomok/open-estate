"""Several estates in one running app, each its own SQLite file.

The promise under test: a request can only ever read or write the estate its
URL names. Not the one used last, not the first one, not whichever engine a
neighbouring thread happened to open - and with no estate named at all,
nothing.
"""

import io
import os
import threading

import pytest
import sqlalchemy as sa
from flask import g

from src import estates
from src.extensions import NoEstateSelected, db as _db
from src.models import Person
from src.services.estate import get_root_entity
from tests.conftest import make_app


def _count(root, slug, table="person"):
    engine = sa.create_engine(f"sqlite:///{estates.db_path(str(root), slug)}")
    try:
        with engine.connect() as conn:
            return conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()
    finally:
        engine.dispose()


@pytest.fixture
def two(tmp_path):
    """Two estates, `alpha` (the default) and `beta`, each with its schema."""
    app = make_app(tmp_path, slugs=("alpha", "beta"))
    for slug in ("alpha", "beta"):
        with app.app_context():
            g.estate = slug
            _db.create_all()
            get_root_entity()
    yield app, tmp_path
    for engine in app.extensions.get("estate_engines", {}).values():
        engine.dispose()


@pytest.fixture
def client(two):
    app, _ = two
    c = app.test_client()
    with c.session_transaction() as s:
        s["is_admin"] = True
    return c


def _add_contact(client, slug, name):
    r = client.post(f"/e/{slug}/manage/contact/new",
                    data={"name": name, "kind": "individual", "roles": ["Trustee"]})
    assert r.status_code == 302, r.data[:300]


def test_a_write_lands_only_in_the_estate_its_url_names(two, client):
    _, root = two
    _add_contact(client, "beta", "Bea Beta")
    assert (_count(root, "alpha"), _count(root, "beta")) == (0, 1)
    _add_contact(client, "alpha", "Al Alpha")
    _add_contact(client, "alpha", "Alice Alpha")
    assert (_count(root, "alpha"), _count(root, "beta")) == (2, 1)
    assert "Bea Beta" in client.get("/e/beta/contacts").data.decode()
    assert "Bea Beta" not in client.get("/e/alpha/contacts").data.decode()


def test_a_form_left_open_on_one_estate_writes_there_after_a_switch(two, client):
    """Two tabs: alpha's form is still open when the other tab moves to beta.
    The cookie now remembers beta; the post still goes to alpha, because the
    form's own URL says so."""
    _, root = two
    client.get("/e/beta/")
    with client.session_transaction() as s:
        assert s["estate"] == "beta"
    _add_contact(client, "alpha", "Late Submit")
    assert (_count(root, "alpha"), _count(root, "beta")) == (1, 0)


def test_no_estate_selected_means_no_database(two):
    app, _ = two
    with app.app_context():
        with pytest.raises(NoEstateSelected):
            Person.query.count()
        with pytest.raises(NoEstateSelected):
            _db.session.add(Person(name="Nowhere"))
            _db.session.commit()
        _db.session.rollback()


def test_concurrent_requests_on_two_estates_stay_apart(two):
    """g is per app context, and app contexts are per thread, so even a
    threaded server keeps each request on its own estate."""
    app, root = two
    barrier = threading.Barrier(2)
    errors = []

    def work(slug):
        try:
            for i in range(20):
                with app.app_context():
                    g.estate = slug
                    _db.session.add(Person(name=f"{slug}-{i}"))
                    if i == 0:
                        barrier.wait(timeout=5)
                    _db.session.commit()
                    assert {p.name.split("-")[0] for p in Person.query.all()} == {slug}
        except Exception as e:      # surfaced on the main thread below
            errors.append(e)

    threads = [threading.Thread(target=work, args=(s,)) for s in ("alpha", "beta")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert (_count(root, "alpha"), _count(root, "beta")) == (20, 20)


@pytest.mark.parametrize("path", ["/e/gamma/", "/e/Alpha/", "/e/..%2falpha/", "/e/a_b/contacts"])
def test_an_unknown_or_malformed_estate_is_not_found(client, path):
    assert client.get(path).status_code == 404


def test_the_bare_address_opens_the_estate_used_last(client):
    assert client.get("/").headers["Location"].endswith("/e/alpha/")
    client.get("/e/beta/contacts")
    assert client.get("/").headers["Location"].endswith("/e/beta/")


def test_the_badge_is_a_dropdown_naming_the_estate_on_screen(client):
    page = client.get("/e/beta/").data.decode()
    assert 'id="estateSelect"' in page
    assert 'value="beta" selected' in page
    assert 'value="alpha" ' in page and 'value="alpha" selected' not in page
    assert client.get("/estates/go?slug=alpha").headers["Location"].endswith("/e/alpha/")
    assert client.get("/estates/go?slug=__new__").headers["Location"].endswith("/estates/new")
    assert client.get("/estates/go?slug=nope").headers["Location"].endswith("/")


def test_links_on_a_page_stay_inside_its_estate(client):
    page = client.get("/e/beta/").data.decode()
    assert 'href="/e/beta/contacts"' in page
    assert 'href="/e/alpha/contacts"' not in page


def test_creating_an_estate_builds_and_migrates_its_database(two, client):
    _, root = two
    r = client.post("/estates/new", data={"slug": "wheeler", "label": "The Wheeler Trust"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/e/wheeler/")
    assert estates.get(str(root), "wheeler")["label"] == "The Wheeler Trust"
    # Built by the migrations, so it carries the default playbook they insert.
    assert _count(root, "wheeler", "playbook") >= 1
    assert client.get("/e/wheeler/").status_code == 200
    assert (_count(root, "alpha"), _count(root, "beta")) == (0, 0)


@pytest.mark.parametrize("slug", ["", "Bad Name", "../up", "alpha", "-lead"])
def test_a_bad_or_taken_estate_name_is_refused(two, client, slug):
    _, root = two
    before = estates.load(str(root))
    r = client.post("/estates/new", data={"slug": slug, "label": "X"})
    assert r.status_code == 200
    assert estates.load(str(root)) == before


def test_backup_and_restore_act_on_one_estate(two, client):
    _, root = two
    _add_contact(client, "alpha", "Kept")
    _add_contact(client, "beta", "Beta Only")
    r = client.get("/e/alpha/settings/download")
    assert r.status_code == 200
    assert "estate_alpha_backup.zip" in r.headers["Content-Disposition"]
    _add_contact(client, "alpha", "After Backup")
    r = client.post("/e/alpha/settings/upload",
                    data={"backup_file": (io.BytesIO(r.data), "estate_alpha_backup.zip")},
                    content_type="multipart/form-data", follow_redirects=True)
    assert "restored successfully" in r.data.decode()
    assert (_count(root, "alpha"), _count(root, "beta")) == (1, 1)


def test_a_protected_estate_refuses_restore(two, client):
    _, root = two
    _add_contact(client, "beta", "Real Person")
    backup = client.get("/e/alpha/settings/download").data
    assert client.post("/e/beta/settings/protect").status_code == 302
    assert estates.get(str(root), "beta")["protected"] is True
    r = client.post("/e/beta/settings/upload",
                    data={"backup_file": (io.BytesIO(backup), "x.zip")},
                    content_type="multipart/form-data", follow_redirects=True)
    assert "REFUSED" in r.data.decode()
    assert _count(root, "beta") == 1
    page = client.get("/e/beta/settings/").data.decode()
    assert "Protected: real data" in page and "Overwrite &amp; Restore" not in page
    assert "dataset-badge-live" in page


def test_the_registry_rejects_slugs_that_could_leave_the_folder(tmp_path):
    for bad in ("..", "a/b", "A", "", "x" * 41, "ünï"):
        with pytest.raises(estates.EstateError):
            estates.db_path(str(tmp_path), bad)
    assert not os.listdir(tmp_path)
