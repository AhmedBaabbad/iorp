"""PROD-QUALITY-FIX-001 item 5 (option B): an inspection records several defect types (each once, counted with
defect_count); a rejection names one or several of its inspection's defects; severity is the highest among them.

Defects overlap (one unit may carry several), so affected quantities are shown per defect and never added up.
"""
import importlib.util
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from tests.quality.test_quality_inspections import CHECKS, REJECTIONS, code, q, result_env  # noqa: F401  (fixtures)

spec = importlib.util.spec_from_file_location("rejection_defects_migration", Path(__file__).parents[2] / "alembic/versions/2026_11_07_1300_f6a1b2m5_rejection_defects.py")
m5 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m5)


def defect(category, severity="minor", count=1):
    return dict(defect_date="2026-10-03", defect_category=category, severity=severity, defect_count=count, description=f"{category} found")


def found(q, check, *defects):
    r = q.client.post(f"{CHECKS}/{check['id']}/defects/batch", json={"defects": list(defects)})
    assert r.status_code == 201, r.text
    return {d["defect_category"]: d["id"] for d in r.json()}


def rejected(q, po, *defects, rejected_qty="10"):
    c = q.opened(po)
    ids = found(q, c, *defects) if defects else {}
    closed = q.close_check(c, inspected="100", accepted=str(100 - int(rejected_qty)), rejected=rejected_qty, result="rejected")
    assert closed.status_code == 200, closed.text
    return c, ids, q.rejections(po)[0]


# ── defects on an inspection ───────────────────────────────────────────────────────────────────

def test_several_defect_types_are_recorded_together_and_each_once(q):
    po = q.bare("kg", status="in_progress")
    c = q.opened(po)
    ids = found(q, c, defect("thickness", "major", 3), defect("surface"))
    assert set(ids) == {"thickness", "surface"}
    # The same type again: counted with defect_count instead.
    r = q.client.post(f"{CHECKS}/{c['id']}/defects", json=defect("thickness"))
    assert r.status_code == 409 and code(r) == "DEFECT_ALREADY_RECORDED"
    r = q.client.post(f"{CHECKS}/{c['id']}/defects/batch", json={"defects": [defect("color"), defect("color")]})
    assert r.status_code == 409 and code(r) == "DEFECT_ALREADY_RECORDED"
    # All or none: the batch with a taken type records nothing.
    r = q.client.post(f"{CHECKS}/{c['id']}/defects/batch", json={"defects": [defect("weight"), defect("surface")]})
    assert r.status_code == 409
    assert len(q.client.get(f"{CHECKS}/{c['id']}/defects").json()) == 2
    # Changing a defect to a type already on the inspection is refused too.
    r = q.client.patch(f"/api/v1/quality/quality-defects/{ids['surface']}", json={"defect_category": "thickness"})
    assert r.status_code == 409 and code(r) == "DEFECT_ALREADY_RECORDED"


def test_inspection_list_shows_its_defects_highest_severity_and_filters_by_type(q):
    po = q.bare("kg", status="in_progress")
    mixed, plain = q.opened(po), q.opened(po)
    found(q, mixed, defect("surface", "minor", 4), defect("thickness", "critical"), defect("color", "major"))
    found(q, plain, defect("color", "minor"))
    rows = {c["id"]: c for c in q.client.get(CHECKS, params={"production_order_id": po["id"]}).json()["items"]}
    assert rows[mixed["id"]]["severity"] == "critical"
    assert [d["defect_category"] for d in rows[mixed["id"]]["defects"]] == ["thickness", "color", "surface"]
    assert rows[plain["id"]]["severity"] == "minor"
    by_type = lambda category: {c["id"] for c in q.client.get(CHECKS, params={"defect_category": category}).json()["items"]}  # noqa: E731
    assert by_type("color") == {mixed["id"], plain["id"]}
    assert by_type("surface") == {mixed["id"]}
    assert by_type("winding") == set()


# ── rejections and their defects ───────────────────────────────────────────────────────────────

def test_a_rejection_from_an_inspection_names_its_defects_and_takes_the_highest_severity(q):
    po = q.bare("kg", status="in_progress")
    _, ids, rejection = rejected(q, po, defect("surface", "minor"), defect("thickness", "major"))
    detail = q.client.get(f"{REJECTIONS}/{rejection['id']}").json()
    assert {d["quality_defect_id"] for d in detail["defects"]} == set(ids.values())
    assert detail["severity"] == "major" and rejection["severity"] == "major"


def test_rejection_defects_one_or_several_each_once(q):
    po = q.bare("kg", status="in_progress")
    _, ids, rejection = rejected(q, po, defect("surface", "minor"), defect("thickness", "critical"), defect("color", "major"))
    url = f"{REJECTIONS}/{rejection['id']}"
    one = q.client.patch(url, json={"defects": [{"quality_defect_id": ids["surface"], "affected_quantity": "4"}]})
    assert one.status_code == 200, one.text
    assert [(d["defect_category"], Decimal(d["affected_quantity"])) for d in one.json()["defects"]] == [("surface", Decimal("4"))]
    assert one.json()["severity"] == "minor"
    # Overlapping defects: 8 and 6 of the 10 rejected units; each is shown, nothing adds them up.
    several = q.client.patch(url, json={"defects": [{"quality_defect_id": ids["thickness"], "affected_quantity": "8"},
                                                    {"quality_defect_id": ids["color"], "affected_quantity": "6"}]}).json()
    assert several["severity"] == "critical" and Decimal(several["quantity_rejected"]) == 10
    assert sorted(Decimal(d["affected_quantity"]) for d in several["defects"]) == [6, 8]
    assert not any(key.startswith("affected") for key in several if key != "defects")
    r = q.client.patch(url, json={"defects": [{"quality_defect_id": ids["color"]}, {"quality_defect_id": ids["color"]}]})
    assert r.status_code == 422 and code(r) == "REJECTION_DEFECT_DUPLICATE"
    r = q.client.patch(url, json={"defects": [{"quality_defect_id": ids["color"], "affected_quantity": "11"}]})
    assert r.status_code == 422 and code(r) == "AFFECTED_QUANTITY_EXCEEDS_REJECTED"
    # No defect at all is allowed: a rejection may stand on its reason and notes.
    assert q.client.patch(url, json={"defects": []}).json()["severity"] is None


def test_only_defects_of_the_rejections_inspection_and_organization(q, db):
    po = q.bare("kg", status="in_progress")
    _, _, rejection = rejected(q, po, defect("surface"))
    other_check = q.opened(po)
    other_ids = found(q, other_check, defect("winding", "critical"))
    url = f"{REJECTIONS}/{rejection['id']}"
    r = q.client.patch(url, json={"defects": [{"quality_defect_id": other_ids["winding"]}]})
    assert r.status_code == 404 and code(r) == "DEFECT_NOT_FOUND"
    r = q.client.patch(url, json={"defects": [{"quality_defect_id": str(uuid4())}]})
    assert r.status_code == 404 and code(r) == "DEFECT_NOT_FOUND"
    # A manual rejection without an inspection has no findings to name.
    body = dict(rejection_date="2026-10-03", rejection_reason="out_of_spec", rejection_notes="Customer complaint", production_order_id=po["id"],
                quantity_rejected="2", defects=[{"quality_defect_id": other_ids["winding"]}])
    r = q.client.post(REJECTIONS, json=body)
    assert r.status_code == 422 and code(r) == "DEFECTS_NEED_A_CHECK"


def test_another_organizations_defect_is_refused(q, db):
    from app.foundation.infrastructure.models import Organization, User
    from app.quality.infrastructure.models import QualityCheck, QualityDefect
    po = q.bare("kg", status="in_progress")
    _, _, rejection = rejected(q, po, defect("surface"))
    org = Organization(name="Other", code=f"other-{uuid4().hex[:6]}", timezone="UTC"); db.add(org); db.flush()
    user = User(organization_id=org.id, full_name="Other", email=f"{uuid4().hex}@example.invalid", password_hash="unused"); db.add(user); db.flush()
    check = QualityCheck(organization_id=org.id, inspection_code="QI-X", check_type="general", check_datetime=datetime.now(timezone.utc),
                         qty_inspected=1, qty_accepted=1, qty_rejected=0, checked_by_user_id=user.id)
    db.add(check); db.flush()
    foreign = QualityDefect(organization_id=org.id, quality_check_id=check.id, defect_date=date(2026, 10, 3), defect_category="surface",
                            severity="critical", description="x", detected_by_user_id=user.id)
    db.add(foreign); db.commit()
    r = q.client.patch(f"{REJECTIONS}/{rejection['id']}", json={"defects": [{"quality_defect_id": str(foreign.id)}]})
    assert r.status_code == 404 and code(r) == "DEFECT_NOT_FOUND"


def test_highest_severity_rule():
    from app.quality.domain.rules import highest_severity
    assert highest_severity(["minor", "critical", "major"]) == "critical"
    assert highest_severity(["minor", "major"]) == "major"
    assert highest_severity([]) is None


# ── the migration ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def old_rejections():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(sa.text("CREATE TABLE foundation_organizations (id CHAR(32) PRIMARY KEY)"))
        c.execute(sa.text("CREATE TABLE quality_defects (id CHAR(32) PRIMARY KEY, quality_check_id CHAR(32), defect_category VARCHAR(20), "
                          "severity VARCHAR(10), created_at DATETIME)"))
        c.execute(sa.text("CREATE TABLE quality_rejections (id CHAR(32) PRIMARY KEY, organization_id CHAR(32), quality_defect_id CHAR(32) "
                          "REFERENCES quality_defects (id))"))
        c.execute(sa.text("CREATE INDEX ix_quality_rejections_quality_defect_id ON quality_rejections (quality_defect_id)"))
        org, check = uuid4().hex, uuid4().hex
        defects = {name: uuid4().hex for name in ("surface", "thickness")}
        c.execute(sa.text("INSERT INTO foundation_organizations (id) VALUES (:o)"), dict(o=org))
        for (name, severity), when in zip((("surface", "minor"), ("thickness", "critical")), ("2026-10-01", "2026-10-02")):
            c.execute(sa.text("INSERT INTO quality_defects VALUES (:i, :c, :n, :s, :w)"), dict(i=defects[name], c=check, n=name, s=severity, w=when))
        c.execute(sa.text("INSERT INTO quality_rejections VALUES (:i, :o, :d)"), dict(i=uuid4().hex, o=org, d=defects["surface"]))
        c.execute(sa.text("INSERT INTO quality_rejections VALUES (:i, :o, NULL)"), dict(i=uuid4().hex, o=org))
    yield engine, defects
    engine.dispose()


def test_migration_keeps_each_rejections_defect_and_restores_the_most_severe(old_rejections, capsys):
    engine, defects = old_rejections
    with engine.begin() as c, Operations.context(MigrationContext.configure(c)):
        m5.upgrade()
    with engine.connect() as c:
        links = [str(x) for x in c.execute(sa.text("SELECT quality_defect_id FROM quality_rejection_defects")).scalars()]
        assert "quality_defect_id" not in {col["name"] for col in sa.inspect(c).get_columns("quality_rejections")}
    assert links == [defects["surface"]]
    assert "1 rejection(s) with a defect -> 1 row(s)" in capsys.readouterr().out

    # Later the rejection names both defects; the downgrade keeps the most severe one.
    with engine.begin() as c:
        rejection, org = c.execute(sa.text("SELECT quality_rejection_id, organization_id FROM quality_rejection_defects")).one()
        c.execute(sa.text("INSERT INTO quality_rejection_defects (id, organization_id, quality_rejection_id, quality_defect_id, created_at, updated_at) "
                          "VALUES (:i, :o, :r, :d, '2026-10-05', '2026-10-05')"), dict(i=uuid4().hex, o=org, r=rejection, d=defects["thickness"]))
    with engine.begin() as c, Operations.context(MigrationContext.configure(c)):
        m5.downgrade()
    with engine.connect() as c:
        restored = sorted((x or "") for x in c.execute(sa.text("SELECT quality_defect_id FROM quality_rejections")).scalars())
        assert "quality_rejection_defects" not in sa.inspect(c).get_table_names()
    assert restored == sorted(["", defects["thickness"]])
