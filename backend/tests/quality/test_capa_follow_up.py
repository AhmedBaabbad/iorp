"""QUAL-CAPA-001: following up corrective actions — recurring problems, the later review of a closed report's effectiveness,
what needs each person's attention, the emails that tell them, and the corrective actions report."""
from datetime import timedelta
from uuid import UUID

import pytest

from app.core.security import hash_password
from app.core.utils import utc_now
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import User
from app.quality.application import capa_notices
from app.quality.domain import ncr as N
from app.quality.domain import permissions as Q
from app.quality.domain import report_permissions as R
from app.quality.infrastructure.models import NonConformanceReport
from tests.quality.test_ncr import ROOT, code, ncr  # noqa: F401 - the shared fixture

ALERTS = "/api/v1/quality/ncr-actions/alerts"


@pytest.fixture
def sent(monkeypatch):
    """Emails that would be sent: (to, subject, text)."""
    out = []
    monkeypatch.setattr(capa_notices.EmailService, "send_email", lambda self, to, subject, html, text=None: out.append((to, subject, text)) or True)
    return out


@pytest.fixture
def colleague(ncr):
    user = User(organization_id=ncr.org.id, full_name="Huda Saleh", email="huda@example.com", password_hash=hash_password("Test1234!"),
                status=UserStatus.ACTIVE, preferred_locale="ar")
    ncr.db.add(user)
    ncr.db.commit()
    return user


def through_investigation(ncr, report, category="material", **investigation):
    ncr.step(report, "contain", containment="Lot quarantined")
    return ncr.step(report, "investigate", root_cause_category=category, root_cause="Wet granules from the supplier's silo", **investigation)


def closed(ncr, report, review_days=0):
    r = through_investigation(ncr, report, action_required=True).json()
    r = ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", description="Dry the silo after maintenance", owner_name="Supplier")).json()
    ncr.client.post(f"{ROOT}/{r['id']}/actions/{r['corrective_actions'][0]['id']}/complete", json=dict(evidence="Drying log signed"))
    ncr.step(r, "submit")
    r = ncr.step(r, "verify", effective=True, review_days=review_days)
    assert r.status_code == 200, r.text
    return r.json()


def test_recurrence_rules():
    this = N.basis("s1", "material_non_conformance", "material", [" PP Granules "])
    assert N.matched_on(this, N.basis("s1", "other", None, [])) == ["supplier"]
    assert N.matched_on(this, N.basis(None, "other", None, ["pp granules"])) == ["item"]
    assert N.matched_on(this, N.basis(None, "material_non_conformance", "material", [])) == ["cause"]
    assert N.matched_on(this, N.basis(None, "product_non_conformance", "material", ["film"])) == []
    assert not N.is_recurring(1) and N.is_recurring(2)


def test_a_repeated_problem_is_recurring_and_needs_a_corrective_action(ncr):
    first, second = ncr.create(), ncr.create()
    third = ncr.create()
    r = ncr.client.get(f"{ROOT}/{third['id']}").json()["recurrence"]
    assert r["recurring"] is True and r["earlier"] == 2 and r["window_days"] == 180
    assert {x["report_number"] for x in r["related"]} == {first["report_number"], second["report_number"]}
    assert r["related"][0]["matched_on"] == ["item"]  # same affected item; the supplier is only named, not registered
    assert ncr.client.get(f"{ROOT}/{first['id']}").json()["recurrence"]["recurring"] is False  # the others came after it
    res = through_investigation(ncr, third, action_required=False, no_action_justification="Isolated case")
    assert code(res) == "RECURRING_NEEDS_ACTION"
    # the first one may still be closed as isolated; a cancelled report does not count
    assert through_investigation(ncr, first, action_required=False, no_action_justification="Isolated case").json()["status"] == "closed"
    ncr.step(second, "cancel", reason="Raised twice")
    assert ncr.client.get(f"{ROOT}/{third['id']}").json()["recurrence"]["earlier"] == 1
    other = ncr.create(items=[dict(item_name="Cartons", issue_description="Crushed")], supplier_name=None)
    assert ncr.client.get(f"{ROOT}/{other['id']}").json()["recurrence"]["related"] == []


def test_a_closed_report_is_reviewed_again_and_reopens_when_the_problem_came_back(ncr):
    r = closed(ncr, ncr.create(), review_days=90)
    assert r["status"] == "closed" and r["review_pending"] is True and r["review_due"] is False
    assert r["effectiveness_due_date"] == str(utc_now().date() + timedelta(days=90)) and r["actions"] == ["review_effectiveness"]
    assert code(ncr.step(r, "review-effectiveness", effective=False)) == "REVIEW_NOTES_REQUIRED"
    r = ncr.step(r, "review-effectiveness", effective=False, notes="Wet granules again on lot SUP-7802").json()
    assert r["status"] == "action" and r["effectiveness_result"] == "not_effective" and r["closed_at"] is None
    assert r["effectiveness_reviewed_by_name"] == "Test User" and r["history"][-1]["action"] == "effectiveness_review"
    assert code(ncr.step(r, "review-effectiveness", effective=True)) == "EFFECTIVENESS_REVIEW_NOT_PENDING"
    ncr.step(r, "submit")
    r = ncr.step(r, "verify", effective=True, review_days=30).json()
    assert r["effectiveness_result"] is None and r["review_pending"] is True
    r = ncr.step(r, "review-effectiveness", effective=True, notes="No repeat in 30 days").json()
    assert r["status"] == "closed" and r["effectiveness_result"] == "effective" and r["actions"] == []
    plain = closed(ncr, ncr.create())
    assert plain["effectiveness_due_date"] is None and plain["review_pending"] is False
    assert ncr.client.post(f"{ROOT}/{plain['id']}/verify", json=dict(effective=True, review_days=400)).status_code == 422
    ncr.grant(Q.NCR_READ, Q.NCR_UPDATE)
    assert ncr.step(r, "review-effectiveness", effective=True).status_code == 403


def test_alerts_show_what_needs_each_person(ncr, colleague):
    r = ncr.create(owner_user_id=str(ncr.user.id), due_date=str(utc_now().date() - timedelta(days=2)))
    ncr.step(r, "contain", containment="Quarantined")
    add = lambda **a: ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", **a))  # noqa: E731
    add(description="Late one", owner_user_id=str(ncr.user.id), due_date=str(utc_now().date() - timedelta(days=1)))
    add(description="Soon one", owner_user_id=str(ncr.user.id), due_date=str(utc_now().date() + timedelta(days=2)))
    add(description="Later one", owner_user_id=str(ncr.user.id), due_date=str(utc_now().date() + timedelta(days=20)))
    add(description="Someone else's", owner_user_id=str(colleague.id), due_date=str(utc_now().date() - timedelta(days=5)))
    review = closed(ncr, ncr.create(items=[dict(item_name="Cores", issue_description="Cracked")]), review_days=1)
    ncr.db.get(NonConformanceReport, UUID(review["id"])).effectiveness_due_date = utc_now().date()  # its day has come
    ncr.db.commit()
    a = ncr.client.get(ALERTS).json()
    assert (a["overdue"], a["due_soon"], a["report_overdue"], a["review_due"], a["open_actions"]) == (1, 1, 1, 1, 3)
    assert [i["kind"] for i in a["items"]] == ["overdue", "report_overdue", "review_due", "due_soon"] and a["total"] == 4
    ncr.grant(Q.NCR_ACTIONS_READ)  # reviews are for whoever verifies
    assert ncr.client.get(ALERTS).json()["review_due"] == 0
    ncr.grant(Q.CHECKS_READ)
    assert ncr.client.get(ALERTS).status_code == 403


def test_the_person_given_an_action_is_told_by_email(ncr, colleague, sent):
    r = ncr.create()
    ncr.step(r, "contain", containment="Quarantined")
    r = ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", description="Recalibrate the moisture meter",
                                                              owner_user_id=str(colleague.id), due_date="2026-11-01")).json()
    [(to, subject, text)] = sent
    assert to == "huda@example.com" and r["report_number"] in subject and "إجراء تصحيحي" in subject
    assert "Recalibrate the moisture meter" in text and "2026-11-01" in text and f"/non-conformance-reports/{r['id']}" in text
    ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="preventive", description="Mine", owner_user_id=str(ncr.user.id)))
    ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="preventive", description="Outside", owner_name="Supplier"))
    assert len(sent) == 1  # not for oneself, nor for someone without an account
    mine = r["corrective_actions"][0]["id"]
    ncr.client.patch(f"{ROOT}/{r['id']}/actions/{mine}", json=dict(due_date="2026-11-05"))
    assert len(sent) == 1  # the same owner


def test_an_email_that_fails_does_not_undo_the_action(ncr, colleague, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("SMTP down")
    monkeypatch.setattr(capa_notices, "action_assigned", boom)
    r = ncr.create()
    ncr.step(r, "contain", containment="Quarantined")
    res = ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", description="x", owner_user_id=str(colleague.id)))
    assert res.status_code == 201 and len(res.json()["corrective_actions"]) == 1


def test_the_daily_digest(ncr, colleague, sent):
    r = ncr.create()
    ncr.step(r, "contain", containment="Quarantined")
    for description, days in (("Late", -3), ("Soon", 1), ("Far", 30)):
        ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", description=description, owner_user_id=str(colleague.id),
                                                              due_date=str(utc_now().date() + timedelta(days=days))))
    sent.clear()
    assert capa_notices.send_digests(ncr.db, ncr.org.id, utc_now().date()) == 1
    [(to, subject, text)] = sent
    assert to == "huda@example.com" and subject == "متابعة الإجراءات التصحيحية"
    assert "إجراء متأخر" in text and "Late" in text and "Soon" in text and "Far" not in text


def test_the_corrective_actions_report(ncr):
    ncr.ctx.auth_user.permissions |= set(R.ALL)
    keys = {d["key"] for d in ncr.client.get("/api/v1/reports/definitions?module=quality").json()}
    assert "quality.corrective_actions" in keys
    for _ in range(2):
        r = ncr.create()
        ncr.step(r, "contain", containment="Quarantined")
        ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", description="Recalibrate", owner_name="Lab",
                                                              due_date=str(utc_now().date() - timedelta(days=4))))
    closed(ncr, ncr.create(), review_days=60)
    res = ncr.client.post("/api/v1/reports/quality.corrective_actions/preview", json=dict(lang="en"))
    assert res.status_code == 200, res.text
    html = res.text
    assert "Actions by owner" in html and "Overdue actions" in html and "Recurring problems" in html and "Effectiveness reviews after closing" in html
    assert "PP homopolymer granules" in html and "Scheduled" in html and "Recalibrate" in html
    ncr.ctx.auth_user.permissions -= {R.REPORT_CORRECTIVE_ACTIONS}
    assert ncr.client.post("/api/v1/reports/quality.corrective_actions/preview", json=dict(lang="en")).status_code == 403
