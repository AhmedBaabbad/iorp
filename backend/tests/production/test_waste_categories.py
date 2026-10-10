"""PROD-QUALITY-FIX-001 item 4: a waste record may have several categories, each with its share of the quantity.

The shares add up to the record's quantity (one unit of waste is counted under one category only), so category totals
add shares and waste totals add records: nothing is counted twice.
"""
import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from tests.production.test_waste_records import WASTE, code, env  # noqa: F401  (env is a fixture)

spec = importlib.util.spec_from_file_location("waste_categories_migration", Path(__file__).parents[2] / "alembic/versions/2026_11_07_1200_f6a1b2m4_waste_record_categories.py")
m4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m4)


def post(env, po, quantity, *lines, **extra):
    return env.client.post(WASTE, json={"production_order_id": po["id"], "waste_date": "2026-10-01", "quantity_wasted": quantity, "unit": "kg",
                                        "categories": [dict(category=c, **({"quantity": q} if q is not None else {})) for c, q in lines], **extra})


def shares(record):
    return [(c["category"], Decimal(c["quantity"])) for c in record["categories"]]


def test_a_single_category_takes_the_whole_quantity(env):
    po = env.order()
    r = post(env, po, "12.5", ("process", None))
    assert r.status_code == 201, r.text
    assert shares(r.json()) == [("process", Decimal("12.5"))]
    # Its own quantity, when given, must be the record's.
    assert code(post(env, po, "12.5", ("process", "10"))) == "WASTE_CATEGORY_TOTAL_MISMATCH"


def test_several_categories_whose_shares_add_up_are_accepted(env):
    po = env.order()
    r = post(env, po, "10", ("process", "3"), ("changeover", "6.5"), ("contamination", "0.5"))
    assert r.status_code == 201, r.text
    # Largest share first.
    assert shares(r.json()) == [("changeover", Decimal("6.5")), ("process", Decimal("3")), ("contamination", Decimal("0.5"))]
    assert Decimal(r.json()["quantity_wasted"]) == 10


@pytest.mark.parametrize("lines,expected", [
    ([("process", "3"), ("changeover", "6")], "WASTE_CATEGORY_TOTAL_MISMATCH"),
    ([("process", "5"), ("process", "5")], "WASTE_CATEGORY_DUPLICATE"),
    ([("process", "10"), ("changeover", "0")], "WASTE_CATEGORY_QUANTITY_INVALID"),
    ([("process", "11"), ("changeover", "-1")], "WASTE_CATEGORY_QUANTITY_INVALID"),
    ([("process", "10"), ("changeover", None)], "WASTE_CATEGORY_QUANTITY_REQUIRED"),
])
def test_invalid_shares_are_refused(env, lines, expected):
    po = env.order()
    r = post(env, po, "10", *lines)
    assert r.status_code == 422 and code(r) == expected, r.text
    assert env.rows() == []


def test_no_category_or_unknown_category_is_refused(env):
    po = env.order()
    assert post(env, po, "1").status_code == 422
    assert post(env, po, "1", ("trim_loss", None)).status_code == 422


def test_editing_quantity_and_categories(env):
    po = env.order()
    single = post(env, po, "4", ("process", None)).json()
    # A single category follows a changed quantity.
    r = env.client.patch(f"{WASTE}/{single['id']}", json={"quantity_wasted": "6"})
    assert r.status_code == 200 and shares(r.json()) == [("process", Decimal("6"))]
    # Splitting it: the new shares replace the old ones.
    r = env.client.patch(f"{WASTE}/{single['id']}", json={"categories": [{"category": "process", "quantity": "2"}, {"category": "other", "quantity": "4"}]})
    assert r.status_code == 200, r.text
    assert shares(r.json()) == [("other", Decimal("4")), ("process", Decimal("2"))]
    # Several categories cannot silently follow a new quantity: the shares must be given again.
    r = env.client.patch(f"{WASTE}/{single['id']}", json={"quantity_wasted": "7"})
    assert r.status_code == 422 and code(r) == "WASTE_CATEGORY_TOTAL_MISMATCH"
    r = env.client.patch(f"{WASTE}/{single['id']}", json={"quantity_wasted": "7", "categories": [{"category": "process", "quantity": "7"}]})
    assert r.status_code == 200 and shares(r.json()) == [("process", Decimal("7"))]
    assert env.client.patch(f"{WASTE}/{single['id']}", json={"categories": []}).status_code == 422


def test_filter_matches_a_record_on_any_of_its_categories(env):
    po = env.order()
    mixed = post(env, po, "5", ("process", "3"), ("changeover", "2")).json()
    only = post(env, po, "1", ("changeover", None)).json()
    post(env, po, "1", ("other", None))
    found = lambda category: {r["id"] for r in env.client.get(WASTE, params={"waste_category": category}).json()}  # noqa: E731
    assert found("process") == {mixed["id"]}
    assert found("changeover") == {mixed["id"], only["id"]}
    assert found("machine_fault") == set()


def test_totals_add_records_and_category_totals_add_shares(env):
    po = env.order(to="completed")
    post(env, po, "5", ("process", "3"), ("changeover", "2"))
    post(env, po, "4", ("process", None))
    summary = env.client.get(f"{WASTE}/summary", params={"production_order_id": po["id"]}).json()
    assert [(t["unit"], Decimal(t["quantity"]), t["count"]) for t in summary["totals"]] == [("kg", Decimal("9"), 2)]
    assert [(c["category"], Decimal(c["quantity"]), c["count"]) for c in summary["by_category"]] == [
        ("process", Decimal("7"), 2), ("changeover", Decimal("2"), 1)]
    # The shares never exceed the waste: categories add up to the total exactly.
    assert sum(Decimal(c["quantity"]) for c in summary["by_category"]) == Decimal("9")


def test_order_report_prints_each_category_with_its_share():
    from types import SimpleNamespace
    from app.production.reporting.builders import waste_categories
    line = lambda category, quantity: SimpleNamespace(category=category, quantity=Decimal(quantity))  # noqa: E731
    assert waste_categories(SimpleNamespace(categories=[line("process", "5.000")]), "en") == "Process waste"
    split = SimpleNamespace(categories=[line("process", "3.000"), line("changeover", "2.500")])
    assert waste_categories(split, "en") == "Process waste 3 · Changeover waste 2.5"
    assert waste_categories(split, "ar").startswith("هالك العملية 3")


# ---- the migration -----------------------------------------------------------------------------

@pytest.fixture
def old_records():
    engine = sa.create_engine("sqlite://")
    categories = ",".join(f"'{c}'" for c in m4.CATEGORIES)
    with engine.begin() as c:
        c.execute(sa.text("CREATE TABLE foundation_organizations (id CHAR(32) PRIMARY KEY)"))
        c.execute(sa.text("CREATE TABLE production_waste_records (id CHAR(32) PRIMARY KEY, organization_id CHAR(32) NOT NULL, "
                          "quantity_wasted NUMERIC(15, 3) NOT NULL, waste_category VARCHAR(32) NOT NULL, "
                          f"CONSTRAINT ck_waste_category CHECK (waste_category IN ({categories})))"))
        c.execute(sa.text("CREATE INDEX ix_production_waste_records_waste_category ON production_waste_records (waste_category)"))
        org = uuid4().hex
        c.execute(sa.text("INSERT INTO foundation_organizations (id) VALUES (:o)"), dict(o=org))
        for category, quantity in (("process", "4.5"), ("startup_setup", "2"), ("other", "1")):
            c.execute(sa.text("INSERT INTO production_waste_records (id, organization_id, quantity_wasted, waste_category) VALUES (:i, :o, :q, :c)"),
                      dict(i=uuid4().hex, o=org, q=quantity, c=category))
    yield engine
    engine.dispose()


def test_migration_turns_each_record_into_one_full_line_and_back(old_records, capsys):
    with old_records.begin() as c, Operations.context(MigrationContext.configure(c)):
        m4.upgrade()
    with old_records.connect() as c:
        lines = sorted(c.execute(sa.text("SELECT l.category, l.quantity, r.quantity_wasted FROM production_waste_record_categories l "
                                         "JOIN production_waste_records r ON r.id = l.waste_record_id")).all())
        columns = {col["name"] for col in sa.inspect(c).get_columns("production_waste_records")}
    assert [(cat, Decimal(str(q))) for cat, q, _ in lines] == [("other", Decimal("1")), ("process", Decimal("4.5")), ("startup_setup", Decimal("2"))]
    assert all(Decimal(str(q)) == Decimal(str(total)) for _, q, total in lines)
    assert "waste_category" not in columns
    assert "3 record(s) -> 3 line(s)" in capsys.readouterr().out

    # A record later split in two keeps its largest category on downgrade.
    with old_records.begin() as c:
        record = c.execute(sa.text("SELECT waste_record_id FROM production_waste_record_categories WHERE category = 'process'")).scalar()
        org = c.execute(sa.text("SELECT organization_id FROM production_waste_records")).scalar()
        c.execute(sa.text("UPDATE production_waste_record_categories SET quantity = 1.5 WHERE category = 'process'"))
        c.execute(sa.text("INSERT INTO production_waste_record_categories (id, organization_id, waste_record_id, category, quantity, created_at, updated_at) "
                          "VALUES (:i, :o, :r, 'changeover', 3, :now, :now)"), dict(i=uuid4().hex, o=org, r=record, now=date(2026, 10, 1)))
    with old_records.begin() as c, Operations.context(MigrationContext.configure(c)):
        m4.downgrade()
    with old_records.connect() as c:
        restored = sorted(c.execute(sa.text("SELECT waste_category FROM production_waste_records")).scalars())
        assert "production_waste_record_categories" not in sa.inspect(c).get_table_names()
    assert restored == ["changeover", "other", "startup_setup"]
