"""PROD-QUALITY-FIX-001 item 2: production and quality lists are server pages, as in the commercial module (ARCH-PAGE-001).

{items, total, page, page_size, pages}; page_size 1-100 (default 50); filters and sort run in the query before the page is
cut; the order ends with a unique column, so equal sort values never make a row repeat or vanish between pages.
"""
import pytest

from tests.production.test_waste_records import WASTE, env  # noqa: F401  (env is a fixture)
from tests.quality.test_quality_inspections import CHECKS, REJECTIONS, q, result_env  # noqa: F401  (fixtures)

ORDERS = "/api/v1/production/production-orders"
ENVELOPE = {"items", "total", "page", "page_size", "pages"}
PAGED = ["/api/v1/production/production-orders", "/api/v1/production/waste-records", "/api/v1/production/downtime-events",
         "/api/v1/production/shift-rosters", "/api/v1/quality/quality-checks", "/api/v1/quality/quality-rejections",
         "/api/v1/quality/quality-defects", "/api/v1/quality/non-conformance-reports", "/api/v1/quality/ncr-actions",
         "/api/v1/quality/quality-certificates"]


def waste(env, po, day, quantity="1", category="process"):
    r = env.client.post(WASTE, json={"production_order_id": po["id"], "waste_date": day, "quantity_wasted": quantity, "unit": "kg",
                                     "categories": [{"category": category}]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def everything(q):
    q.ctx.auth_user.permissions |= {"production:shift_rosters:read", "production:downtime_events:read", "production:waste_records:read",
                                    "quality:ncr:read", "quality:ncr_actions:read", "quality:coa:read"}
    return q


@pytest.mark.parametrize("path", PAGED)
def test_every_changed_list_answers_the_commercial_envelope_and_caps_page_size(everything, path):
    r = everything.client.get(path)
    assert r.status_code == 200, r.text
    assert set(r.json()) >= ENVELOPE and r.json()["page"] == 1 and r.json()["page_size"] == 50
    assert everything.client.get(path, params={"page_size": 101}).status_code == 422
    assert everything.client.get(path, params={"page": 0}).status_code == 422
    assert everything.client.get(path, params={"page_size": 100}).status_code == 200


def test_pages_split_rows_with_equal_dates_without_repeats_or_gaps(env):
    po = env.order()
    ids = {waste(env, po, "2026-10-01") for _ in range(7)}  # same date: the id decides the order
    pages = [env.client.get(WASTE, params={"page": n, "page_size": 3}).json() for n in (1, 2, 3)]
    assert [p["total"] for p in pages] == [7, 7, 7] and [p["pages"] for p in pages] == [3, 3, 3]
    seen = [r["id"] for p in pages for r in p["items"]]
    assert len(seen) == 7 and set(seen) == ids
    again = [r["id"] for n in (1, 2, 3) for r in env.client.get(WASTE, params={"page": n, "page_size": 3}).json()["items"]]
    assert again == seen  # deterministic
    assert env.client.get(WASTE, params={"page": 4, "page_size": 3}).json()["items"] == []


def test_filters_sort_and_pages_together(env):
    po, other = env.order(), env.order()
    for day in ("2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05"):
        waste(env, po, day, category="changeover")
    waste(env, po, "2026-10-06", category="other")
    waste(env, other, "2026-10-07", category="changeover")
    first = env.client.get(WASTE, params={"production_order_id": po["id"], "waste_category": "changeover", "page_size": 2}).json()
    second = env.client.get(WASTE, params={"production_order_id": po["id"], "waste_category": "changeover", "page_size": 2, "page": 2}).json()
    assert first["total"] == 5 and first["pages"] == 3
    # Newest first, filtered before the page is cut.
    assert [r["waste_date"] for r in first["items"] + second["items"]] == ["2026-10-05", "2026-10-04", "2026-10-03", "2026-10-02"]


def test_production_order_pages_search_and_picker_lookup(env):
    orders = [env.order() for _ in range(3)]
    page = env.client.get(ORDERS, params={"page_size": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and page["pages"] == 2
    number = orders[1]["production_order_number"]
    assert [o["id"] for o in env.client.get(ORDERS, params={"search": number}).json()["items"]] == [orders[1]["id"]]
    # The picker searches on the server, with a limit, and names chosen ids; it is never a page-1 list.
    found = env.client.get(f"{ORDERS}/lookup", params={"search": number}).json()
    assert [o["id"] for o in found] == [orders[1]["id"]]
    assert len(env.client.get(f"{ORDERS}/lookup", params={"limit": 2}).json()) == 2
    assert env.client.get(f"{ORDERS}/lookup", params={"limit": 51}).status_code == 422
    named = env.client.get(f"{ORDERS}/lookup", params=[("ids", orders[0]["id"]), ("ids", orders[2]["id"])]).json()
    assert {o["id"] for o in named} == {orders[0]["id"], orders[2]["id"]}
    running = env.client.get(f"{ORDERS}/lookup", params=[("statuses", "in_progress"), ("statuses", "on_hold")]).json()
    assert {o["status"] for o in running} <= {"in_progress", "on_hold"} and len(running) == 3


def test_quality_lists_have_no_hidden_cap(q):
    po = q.bare("kg", status="in_progress")
    for _ in range(3):
        q.opened(po)
    page = q.client.get(CHECKS, params={"production_order_id": po["id"], "page_size": 2}).json()
    assert page["total"] == 3 and page["pages"] == 2 and len(page["items"]) == 2
    rest = q.client.get(CHECKS, params={"production_order_id": po["id"], "page_size": 2, "page": 2}).json()
    assert len(rest["items"]) == 1 and {c["id"] for c in page["items"] + rest["items"]} == {c["id"] for c in
                                                                                             q.client.get(CHECKS, params={"page_size": 100}).json()["items"]}
    assert q.client.get(REJECTIONS, params={"production_order_id": po["id"]}).json()["total"] == 0


def test_the_run_team_picker_reads_the_rosters_in_effect_not_a_page(everything):
    r = everything.client.get("/api/v1/production/shift-rosters/active", params={"on": "2026-10-03"})
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_unresolved_rejections_are_counted_on_the_server(q):
    po = q.bare("kg", status="in_progress")
    for _ in range(2):
        q.close_check(q.opened(po), inspected="10", accepted="8", rejected="2", result="rejected")
    rid = q.rejections(po)[0]["id"]
    q.client.post(f"{REJECTIONS}/{rid}/decide", json=dict(disposition="scrap"))
    count = lambda **f: q.client.get(REJECTIONS, params=dict(production_order_id=po["id"], page_size=1, **f)).json()["total"]  # noqa: E731
    assert count() == 2 and count(unresolved=True) == 1
