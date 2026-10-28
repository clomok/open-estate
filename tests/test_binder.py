"""The printed binder: the route end to end, and the pure service functions."""

import re
from datetime import date
from types import SimpleNamespace as NS

import pytest

from src.holding_types import mask
from src.models import BeneficiaryDesignation, Entity, Holding
from src.money import format_cents
from src.services import binder as svc
from tests.fixtures_estate import _populate

ARTICLE_IDS = ["art-i", "art-ii", "art-iii", "sched-a", "art-iv", "art-v", "art-vii",
               "art-viii", "art-ix", "art-x", "art-xi", "sched-b", "sched-c"]


@pytest.fixture
def client(app, db):
    c = app.test_client()
    with c.session_transaction() as s:
        s["is_admin"] = True
    return c


@pytest.fixture
def estate(db):
    _populate(db)
    return db


def page(client):
    r = client.get("/e/test/binder")
    assert r.status_code == 200, r.data[:500]
    return r.data.decode()


# --- the route -------------------------------------------------------------

def test_binder_renders_and_needs_login(app, client, estate):
    assert "Estate binder" in page(client)
    anon = app.test_client().get("/e/test/binder")
    assert anon.status_code == 302 and "login" in anon.headers["Location"]


def test_every_base_article_appears_once_in_order(client, estate):
    html = page(client)
    ids = re.findall(r'<section class="[^"]*" id="((?:art|sched)-[a-z]+)"', html)
    assert ids == ARTICLE_IDS


def test_stub_articles_say_nothing_recorded(client, estate):
    html = page(client)
    for art in ("art-v", "art-vii", "art-viii", "sched-c"):
        body = html.split(f'id="{art}"')[1].split("</section>")[0]
        assert "Nothing recorded yet" in body, art


def test_net_worth_matches_the_ledger_and_entities(client, estate):
    holdings = Holding.query.all()
    net = format_cents(svc.ledger_totals(holdings)["net"])
    html = page(client)
    assert f'id="net-worth">{net}<' in html
    for sheet in svc.entity_sheets(Entity.query.all(), holdings):
        own = [h for h in holdings if h.entity_id == sheet["entity"].id
               or (h.entity_id is None and sheet["entity"].is_root)]
        assert sheet["net_cents"] == svc.ledger_totals(own)["net"]
        block = html.split(f'id="entity-{sheet["entity"].id}"')[1].split("</section>")[0]
        assert f'Net: <strong>{format_cents(sheet["net_cents"])}</strong>' in block.split("entity-sheet")[0]


def test_beneficiary_matrix_flags_incomplete_rows(client, estate):
    html = page(client)
    assert 'class="complete"' in html and 'class="incomplete"' not in html
    # the house is 65 + 35: complete. Cut one share to 40 -> 75% total.
    d = estate.session.get(BeneficiaryDesignation, 1)
    d.percentage = 40.0
    estate.session.commit()
    html = page(client)
    house_row = [r for r in html.split("<tr ") if "Family Home" in r and "incomplete" in r]
    assert house_row and "75%" in house_row[0] and "not 100%" in house_row[0]
    undesig = html.split("No beneficiary recorded")[1].split("</section>")[0]
    assert "Rentals LLC units" in undesig            # no designation at all
    assert "Family Home" not in undesig


def test_sensitive_fields_print_masked(client, estate):
    html = page(client).split('id="sched-a"')[1].split('id="art-iv"')[0]
    assert mask("EXAMPLE123") in html
    assert "EXAMPLE123" not in html


def test_planning_content_is_absent(client, estate):
    html = page(client)
    assert 'id="art-vi"' not in html and 'id="appendix"' not in html
    for title in ("Retitle the coupe", "Annual trust review", "Get a pronouncement of death"):
        assert title not in html


def test_no_chart(client, estate):
    assert "chart" not in page(client).lower()


def test_binder_css_keeps_the_print_rules():
    css = open("src/static/css/binder.css").read()
    assert "@page" in css and "counter(pages)" in css


def test_footer_is_a_css_string(client, estate):
    html = page(client)
    assert '@bottom-left { content: "The Example Family Trust · estate binder · ' in html


# --- the service functions on hand-built objects ----------------------------

def H(id, side, value, name=None, entity_id=None, type_label="Thing", **kw):
    return NS(id=id, side=side, value_cents=value, name=name or f"H{id}", entity_id=entity_id,
              type_label=type_label, **kw)


def test_balance_sheet_groups_and_nets():
    hs = [H(1, "asset", 500, type_label="Bank"), H(2, "asset", 900, type_label="Home"),
          H(3, "asset", 100, type_label="Bank"), H(4, "liability", 300, type_label="Mortgage")]
    s = svc.balance_sheet(hs)
    assert [(t, sub) for t, _, sub in s["by_side"]["asset"]] == [("Home", 900), ("Bank", 600)]
    assert s["by_side"]["equity"] == []
    assert s["totals"] == {"asset": 1500, "liability": 300, "equity": 0, "net": 1200}


def test_entity_sheets_root_first_and_null_entity_is_root():
    root = NS(id=1, is_root=True, name="Zed Trust")
    a = NS(id=2, is_root=False, name="Beta LLC")
    b = NS(id=3, is_root=False, name="Alpha LLC")
    hs = [H(1, "asset", 1000), H(2, "asset", 400, entity_id=2), H(3, "liability", 100, entity_id=2),
          H(4, "equity", 50, entity_id=3)]
    sheets = svc.entity_sheets([a, b, root], hs)
    assert [s["entity"].name for s in sheets] == ["Zed Trust", "Alpha LLC", "Beta LLC"]
    assert [s["net_cents"] for s in sheets] == [1000, 0, 300]
    assert [h.id for h in sheets[2]["liabilities"]] == [3] and [h.id for h in sheets[1]["equity"]] == [4]


def D(person_id, pct, kind="trust_schedule"):
    return NS(person_id=person_id, percentage=pct, kind_label=kind)


def holding_with(id, shares, side="asset", entity_kind=None, value=100):
    totals = {}
    for d in shares:
        totals[d.kind_label] = round(totals.get(d.kind_label, 0) + d.percentage, 4)
    ent = NS(kind=entity_kind) if entity_kind else None
    return H(id, side, value, entity_id=1 if ent else None, entity=ent,
             beneficiary_designations=shares, share_totals=lambda t=totals: t)


def test_who_gets_what_scope_rows_and_gaps():
    ann, bob = NS(id=1, name="Ann"), NS(id=2, name="Bob")
    ok = holding_with(1, [D(1, 60), D(2, 40)], value=500)
    short = holding_with(2, [D(1, 40)], value=300)
    none = holding_with(3, [], value=200)
    inside_llc = holding_with(4, [], entity_kind="llc")
    debt = holding_with(5, [], side="liability")
    m = svc.who_gets_what([ok, short, none, inside_llc, debt], [bob, ann])
    assert [p.name for p in m["beneficiaries"]] == ["Ann", "Bob"]
    assert [r["holding"].id for r in m["rows"]] == [1, 2]
    assert m["rows"][0]["complete"] and m["rows"][0]["total_pct"] == 100.0
    assert not m["rows"][1]["complete"] and m["rows"][1]["total_pct"] == 40
    assert m["rows"][0]["cells"][2] == (40, "trust_schedule")
    assert [h.id for h in m["undesignated"]] == [3]


def test_people_by_role_family_first_and_recorded_order():
    def P(id, name, roles):
        return NS(id=id, name=name, roles=[NS(id=rid, role=r) for rid, r in roles])
    a = P(1, "Ann", [(5, "Trustee"), (1, "Attorney")])
    b = P(2, "Bob", [(2, "Trustee")])
    c = P(3, "Cy", [(3, "SuccessorTrustee"), (9, "Mystery")])
    out = svc.people_by_role([a, b, c])
    assert list(out) == ["Trustee", "SuccessorTrustee", "Attorney", "Mystery"]
    assert [p.name for p in out["Trustee"]] == ["Bob", "Ann"]     # role id 2 before 5


def test_colophon_and_helpers():
    hs = [NS(last_verified=date(2026, 6, 1)), NS(last_verified=date(2024, 1, 1)),
          NS(last_verified=None)]
    c = svc.colophon(hs, {"people": 3}, date(2026, 10, 27))
    assert c["verified_last_year"] == 1 and c["holdings"] == 3
    assert svc.long_date(date(2026, 10, 7)) == "October 7, 2026"
    assert svc.css_string('A "B" \\ <x>\n') == 'A \\"B\\" \\\\ \\3C x>'


# --- the toggles --------------------------------------------------------------

def opt_page(client, query):
    r = client.get(f"/e/test/binder?{query}")
    assert r.status_code == 200, r.data[:500]
    return r.data.decode()


def toc_of(html):
    return re.findall(r'<li><a href="#([a-z-]+)">', html.split('id="contents"')[1].split("</section>")[0])


def section(html, sid):
    return html.split(f'id="{sid}"')[1].split("</section>")[0]


@pytest.fixture
def soon(estate):
    """One open event inside the next year, one past it, one overdue."""
    from datetime import timedelta
    from src.models import Event
    t = date.today()
    estate.session.add_all([
        Event(kind="task", title="Renew the umbrella policy", date=t + timedelta(days=40), phase="now"),
        Event(kind="task", title="Far future errand", date=t + timedelta(days=500), phase="now"),
        Event(kind="task", title="Long overdue errand", date=t - timedelta(days=3), phase="now"),
        Event(kind="task", title="Someday filing", date=None, phase="now"),
    ])
    estate.session.commit()
    return estate


def test_planning_adds_article_vi_and_appendix_in_place(client, soon):
    html = opt_page(client, "planning=1")
    ids = re.findall(r'<section class="[^"]*" id="((?:art|sched)-[a-z]+|appendix)"', html)
    assert ids == ["art-i", "art-ii", "art-iii", "sched-a", "art-iv", "art-v", "art-vi", "art-vii",
                   "art-viii", "art-ix", "art-x", "art-xi", "sched-b", "sched-c", "appendix"]
    toc = toc_of(html)
    assert toc.index("art-vi") == toc.index("art-v") + 1 and toc[-2:] == ["appendix", "colophon"]
    assert "This copy" in html and "Includes</dd>" not in html and "Includes the planning" in html


def test_article_vi_bands_steps_and_unassigned(client, soon):
    body = section(opt_page(client, "planning=1"), "art-vi")
    assert "On the death of the trustor" in body
    assert "The first 72 hours" in body and "The first year" in body and "Days 4 to 30" not in body
    assert "Get a pronouncement of death" in body and "Estate tax return" in body
    assert body.count("unassigned") == 2
    assert "no one holds the" in body


def test_article_vi_names_the_contact_who_holds_the_role(client, soon):
    from src.models import PersonRole
    soon.session.add(PersonRole(person_id=2, role="SuccessorTrustee"))
    soon.session.commit()
    body = section(opt_page(client, "planning=1"), "art-vi")
    first = body.split("Get a pronouncement of death")[1].split("</li>")[0]
    assert "unassigned" not in first
    assert body.count("unassigned") == 1


def test_appendix_events_inside_a_year_only(client, soon):
    body = section(opt_page(client, "planning=1"), "appendix")
    assert "Renew the umbrella policy" in body
    assert "Far future errand" not in body and "Long overdue errand" not in body
    assert "Needs attention" in body and "Someday filing" in body


def test_planning_off_has_none_of_it(client, soon):
    html = opt_page(client, "reveal=1")
    assert 'id="art-vi"' not in html and 'id="appendix"' not in html
    assert "art-vi" not in toc_of(html) and "appendix" not in toc_of(html)
    assert "Renew the umbrella policy" not in html and "Get a pronouncement of death" not in html


def test_reveal_shows_raw_value_and_cover_line(client, estate):
    html = opt_page(client, "reveal=1")
    assert "EXAMPLE123" in html.split('id="sched-a"')[1].split('id="art-iv"')[0]
    assert "This copy contains account numbers and other sensitive details." in html
    masked = page(client)
    assert "EXAMPLE123" not in masked and "contains account numbers" not in masked


def test_hide_empty_drops_stub_articles_and_their_contents_lines(client, estate):
    html = opt_page(client, "hide_empty=1")
    for sid in ("art-vii", "art-viii", "sched-c", "art-v"):
        assert f'id="{sid}"' not in html and sid not in toc_of(html), sid
    for sid in ("art-i", "art-iii", "sched-a", "art-iv", "art-xi", "colophon"):
        assert f'id="{sid}"' in html and sid in toc_of(html), sid
    full = page(client)
    for sid in ("art-vii", "art-viii", "sched-c", "art-v"):
        assert f'id="{sid}"' in full and sid in toc_of(full)


def test_hide_empty_keeps_article_v_when_a_helper_exists(client, estate):
    from src.models import PersonRole
    estate.session.add(PersonRole(person_id=2, role="Attorney"))
    estate.session.commit()
    assert 'id="art-v"' in opt_page(client, "hide_empty=1")


def test_hide_empty_keeps_appendix_while_something_needs_attention(client, estate):
    html = opt_page(client, "planning=1&hide_empty=1")      # fixture flags gaps
    assert 'id="art-vi"' in html and 'id="appendix"' in html
    assert "Needs attention" in section(html, "appendix")


def test_setup_form_and_its_submit(client, estate):
    r = client.get("/e/test/binder/setup")
    assert r.status_code == 200
    html = r.data.decode()
    for name in ("planning", "reveal", "hide_empty"):
        assert f'name="{name}"' in html
    assert 'action="/e/test/binder"' in html and 'method="get"' in html
    assert "Firefox and Safari" in html and "Open binder" in html
    sent = client.get("/e/test/binder?planning=1&hide_empty=1")      # what the browser sends
    body = sent.data.decode()
    assert 'id="art-vi"' in body and 'id="art-vii"' not in body and "contains account numbers" not in body


def test_top_bar_links_flip_one_toggle(client, estate):
    html = opt_page(client, "planning=1")
    assert 'href="/e/test/binder"' in html                       # planning off -> back to base
    assert 'href="/e/test/binder?planning=1&amp;reveal=1"' in html


def test_setup_needs_login(app, estate):
    r = app.test_client().get("/e/test/binder/setup")
    assert r.status_code == 302 and "login" in r.headers["Location"]


# --- step 2 service functions -------------------------------------------------

def S(id, offset, pos=0, role=None, title=None):
    return NS(id=id, offset_days=offset, position=pos, who_role=role, title=title or f"S{id}")


def test_playbook_bands_edges_and_role_resolution():
    ann, bob = NS(name="Ann"), NS(name="Bob")
    steps = [S(1, 3, role="Trustee"), S(2, 4), S(3, 30, role="Mystery"), S(4, 31), S(5, 90),
             S(6, 91), S(7, 365), S(8, 366), S(9, 0, pos=1), S(10, 0, pos=0, role="Trustee")]
    bands = svc.playbook_bands(steps, {"Trustee": [ann, bob]})
    got = [(h, [r["step"].id for r in rows]) for h, rows in bands]
    assert got == [("The first 72 hours", [10, 9, 1]), ("Days 4 to 30", [2, 3]),
                   ("Days 31 to 90", [4, 5]), ("The first year", [6, 7]), ("Later", [8])]
    people = {r["step"].id: r["person"] for _, rows in bands for r in rows}
    assert people[10] is ann and people[1] is ann
    assert people[9] is None and people[3] is None          # no role / nobody holds it


def test_playbook_bands_drops_empty_bands():
    assert svc.playbook_bands([], {}) == []
    assert [h for h, _ in svc.playbook_bands([S(1, 40)], {})] == ["Days 31 to 90"]


def test_year_ahead_window_and_order():
    today = date(2026, 10, 27)
    R = lambda t, d, done=None: NS(title=t, date=d, done_at=done)
    rows = [R("b", date(2027, 10, 27)), R("a", today), R("late", date(2027, 10, 28)),
            R("past", date(2026, 10, 26)), R("undated", None),
            R("done", date(2026, 12, 1), done=date(2026, 11, 1)), R("A2", today)]
    assert [r.title for r in svc.year_ahead(rows, today)] == ["a", "A2", "b"]


def test_a_holding_in_the_trust_is_held_by_the_trust_by_name(client, estate):
    html = page(client)
    assert "<dt>Held by</dt><dd>The Example Family Trust</dd>" in html
    assert "<dt>Held by</dt><dd>The trust</dd>" not in html
