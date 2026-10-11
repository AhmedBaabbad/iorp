"""QUAL-NCR-002: non-conformance reports — sources, items and dispositions, the stages of a corrective action
(containment, root cause, actions, verification), the CAPA list, costs and claim, files, permissions and the document."""
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import settings as app_settings
from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.dependencies import get_current_user
from app.main import app
from app.quality.domain import permissions as Q

ROOT = "/api/v1/quality/non-conformance-reports"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def ncr(client, db, test_org, test_user):
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False, id=test_user.id, full_name=test_user.full_name),
                          auth_user=SimpleNamespace(permissions=set(Q.ALL)),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=frozenset(Q.ALL)))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def grant(*codes):
        ctx.auth_user.permissions = set(codes)
        ctx.tenant = TenantContext(test_user.id, test_org.id, permissions=frozenset(codes))

    def body(**over):
        data = dict(report_date="2026-10-05", source_type="incoming_material", report_type="material_non_conformance", severity="major",
                    title="Wet PP granules — lot SUP-7781", description="Moisture 0.12 % against 0.05 % max; bubbles on the strap.",
                    supplier_name="Gulf Polymers", supplier_reference="DN-GP-4471 / lot SUP-7781", reference_code="SUP-7781",
                    items=[dict(item_name="PP homopolymer granules", item_reference="SUP-7781", quantity_affected="2", unit="ton",
                                issue_description="Moisture above specification", disposition="return_to_supplier")])
        data.update(over)
        return data

    def create(**over):
        r = client.post(ROOT, json=body(**over))
        assert r.status_code == 201, r.text
        return r.json()

    def step(report, name, **payload):
        return client.post(f"{ROOT}/{report['id']}/{name}", json=payload or None)

    yield SimpleNamespace(client=client, db=db, org=test_org, user=test_user, ctx=ctx, grant=grant, body=body, create=create, step=step)
    app.dependency_overrides.pop(get_current_user, None)


def code(r):
    return r.json()["detail"]["code"]


def test_a_report_names_its_source_and_what_is_affected(ncr):
    r = ncr.create()
    assert r["report_number"] == f"NCR-{date.today().year}-0001" and r["status"] == "open" and r["severity"] == "major"
    assert r["supplier_name"] == "Gulf Polymers" and r["supplier_action"] == "none" and r["claim_status"] == "none"
    [item] = r["items"]
    assert (item["quantity_affected"], item["unit"], item["disposition"]) == ("2.000", "ton", "return_to_supplier")
    assert set(r["actions"]) == {"edit", "contain", "cancel"}
    assert ncr.create()["report_number"].endswith("-0002")
    bad_unit = ncr.body(items=[dict(item_name="x", issue_description="y", unit="tons")])
    assert ncr.client.post(ROOT, json=bad_unit).status_code == 422
    assert ncr.client.post(ROOT, json=ncr.body(organization_id=str(uuid4()))).status_code == 422
    assert ncr.client.post(ROOT, json=ncr.body(severity="huge")).status_code == 422
    assert ncr.client.patch(f"{ROOT}/{r['id']}", json=dict(status="closed")).status_code == 422  # stages only


def test_the_stages_of_a_corrective_action(ncr):
    r = ncr.create()
    assert code(ncr.step(r, "investigate", root_cause_category="material", root_cause="x")) == "NCR_NOT_UNDER_INVESTIGATION"
    assert ncr.step(r, "contain").status_code == 422
    r = ncr.step(r, "contain", containment="Lot quarantined, line 2 switched to lot SUP-7790").json()
    assert r["status"] == "investigation" and r["contained_by_name"] == "Test User"
    action = lambda **a: ncr.client.post(f"{ROOT}/{r['id']}/actions", json=a)  # noqa: E731
    r = action(kind="correction", description="Return the lot to the supplier", owner_name="Gulf Polymers").json()
    r = ncr.step(r, "investigate", root_cause_category="material", root_cause_method="five_whys",
                 root_cause="The supplier's silo was not dried after maintenance").json()
    assert r["status"] == "action" and r["investigated_by_name"] == "Test User"
    r = action(kind="preventive", description="Moisture test on every incoming lot", owner_user_id=str(ncr.user.id),
               due_date=str(utc_now().date() + timedelta(days=7))).json()
    first, second = r["corrective_actions"]
    r2 = ncr.step(r, "submit")
    assert r2.status_code == 409 and code(r2) == "ACTIONS_STILL_OPEN" and r2.json()["detail"]["open"] == 2
    done = lambda a, evidence: ncr.client.post(f"{ROOT}/{r['id']}/actions/{a['id']}/complete", json=dict(evidence=evidence))  # noqa: E731
    assert done(first, "").status_code == 422
    done(first, "Returned under GP-RMA-12")
    ncr.client.post(f"{ROOT}/{r['id']}/actions/{second['id']}/cancel", json=dict(reason="Replaced by a supplier certificate check"))
    r = ncr.step(r, "submit").json()
    assert r["status"] == "verification"
    assert code(ncr.step(r, "verify", effective=False)) == "VERIFICATION_NOTES_REQUIRED"
    r = ncr.step(r, "verify", effective=False, notes="Next lot also wet").json()
    assert r["status"] == "action" and r["verification_attempts"] == 1
    r = action(kind="corrective", description="Supplier to add a dryer check to its release").json()
    third = r["corrective_actions"][2]
    done(third, "Supplier's release record now shows the dryer check")
    r = ncr.step(r, "submit").json()
    r = ncr.step(r, "verify", effective=True, notes="Three lots dry").json()
    assert r["status"] == "closed" and r["closed_at"] and r["verified_by_name"] == "Test User" and r["actions"] == []
    assert code(ncr.client.patch(f"{ROOT}/{r['id']}", json=dict(title="x"))) == "NCR_IS_FINAL"
    assert {"create", "contain", "investigate", "action_added", "action_done", "submit", "verify"} <= {h["action"] for h in r["history"]}


def test_a_minor_case_closes_from_the_investigation_with_a_reason(ncr):
    r = ncr.create(severity="minor")
    ncr.step(r, "contain", containment="One carton set aside")
    r2 = ncr.step(r, "investigate", root_cause_category="method", root_cause="Carton crushed by a forklift", action_required=False)
    assert r2.status_code == 400 and code(r2) == "NO_ACTION_JUSTIFICATION_REQUIRED"
    closed = ncr.step(r, "investigate", root_cause_category="method", root_cause="Carton crushed by a forklift", action_required=False,
                      no_action_justification="Isolated handling damage").json()
    assert closed["status"] == "closed" and closed["no_action_justification"] == "Isolated handling damage"
    cancelled = ncr.create()
    assert ncr.step(cancelled, "cancel", reason="Raised twice").json()["status"] == "cancelled"


def test_the_corrective_action_list_shows_whose_and_what_is_late(ncr):
    r = ncr.create()
    ncr.step(r, "contain", containment="Quarantined")
    late = ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", description="Recalibrate the moisture meter",
                                                                 owner_user_id=str(ncr.user.id), due_date=str(utc_now().date() - timedelta(days=1)))).json()
    both = ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="preventive", description="Monthly calibration", owner_name="Lab")).json()
    assert late["corrective_actions"][0]["overdue"] is True and both["overdue_actions"] == 1 and both["open_actions"] == 2
    rows = ncr.client.get("/api/v1/quality/ncr-actions", params=dict(overdue=True)).json()["items"]
    assert [a["description"] for a in rows] == ["Recalibrate the moisture meter"] and rows[0]["report_number"] == r["report_number"]
    assert [a["description"] for a in ncr.client.get("/api/v1/quality/ncr-actions", params=dict(mine=True)).json()["items"]] == ["Recalibrate the moisture meter"]
    assert len(ncr.client.get("/api/v1/quality/ncr-actions").json()["items"]) == 2
    assert [u["name"] for u in ncr.client.get(f"{ROOT}/lookups/users").json()] == ["Test User"]


def test_items_costs_and_the_claim(ncr):
    r = ncr.create(cost_material="9000", cost_labor="1200.50", claim_amount="10200.50", claim_status="claimed", supplier_action="scar")
    assert r["total_cost"] == "10200.50" and r["claim_status"] == "claimed" and r["supplier_action"] == "scar"
    r = ncr.client.post(f"{ROOT}/{r['id']}/items", json=dict(item_name="Strap made from the lot", quantity_affected="300", unit="kg",
                                                            issue_description="Bubbles", disposition="scrap")).json()
    second = r["items"][1]
    r = ncr.client.patch(f"{ROOT}/{r['id']}/items/{second['id']}", json=dict(disposition="return_to_process", disposition_notes="Ground")).json()
    assert r["items"][1]["disposition"] == "return_to_process"
    r = ncr.client.delete(f"{ROOT}/{r['id']}/items/{second['id']}").json()
    assert len(r["items"]) == 1
    r = ncr.client.patch(f"{ROOT}/{r['id']}", json=dict(supplier_response="Replacement lot sent", supplier_responded_at="2026-10-07",
                                                       claim_status="accepted")).json()
    assert r["supplier_response"] == "Replacement lot sent" and r["claim_status"] == "accepted"
    assert ncr.client.get(ROOT, params=dict(search="Gulf")).json()["items"][0]["id"] == r["id"]
    assert ncr.client.get(ROOT, params=dict(status="closed")).json()["items"] == []


def test_each_step_needs_its_permission(ncr):
    r = ncr.create()
    ncr.step(r, "contain", containment="Quarantined")
    r = ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", description="Fix the dryer", owner_user_id=str(ncr.user.id))).json()
    action = r["corrective_actions"][0]
    ncr.grant(Q.NCR_READ, Q.NCR_ACTIONS_READ, Q.NCR_ACTIONS_COMPLETE)  # e.g. the maintenance manager who owns the action
    seen = ncr.client.get(f"{ROOT}/{r['id']}").json()
    assert seen["actions"] == [] and seen["can_complete_actions"] is True
    assert ncr.client.patch(f"{ROOT}/{r['id']}", json=dict(title="x")).status_code == 403
    assert ncr.step(r, "cancel", reason="x").status_code == 403
    done = ncr.client.post(f"{ROOT}/{r['id']}/actions/{action['id']}/complete", json=dict(evidence="Dryer timer replaced"))
    assert done.status_code == 200 and done.json()["corrective_actions"][0]["status"] == "done"
    ncr.grant(Q.NCR_READ)
    assert ncr.client.get("/api/v1/quality/ncr-actions").status_code == 200
    assert ncr.client.post(ROOT, json=ncr.body()).status_code == 403


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(app_settings, "uploads_dir", str(tmp_path))
    return tmp_path


def test_photos_are_kept_with_the_report(ncr, uploads):
    r = ncr.create()
    [f] = ncr.client.post(f"{ROOT}/{r['id']}/attachments", files=dict(file=("bubbles.png", PNG))).json()
    assert f["content_type"] == "image/png" and f["uploaded_by_name"] == "Test User"
    assert ncr.client.get(f"{ROOT}/{r['id']}/attachments/{f['id']}").content == PNG
    assert code(ncr.client.post(f"{ROOT}/{r['id']}/attachments", files=dict(file=("x.png", b"MZ")))) == "FILE_UNSUPPORTED_TYPE"
    assert ncr.client.delete(f"{ROOT}/{r['id']}/attachments/{f['id']}").json() == []


def test_the_report_document_in_arabic_and_english(ncr):
    r = ncr.create(cost_material="9000", claim_amount="9000", claim_status="claimed", supplier_action="scar")
    ncr.step(r, "contain", containment="Lot quarantined")
    ncr.step(r, "investigate", root_cause_category="material", root_cause_method="fishbone", root_cause="Silo not dried")
    ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind="corrective", description="Dryer check before release", owner_name="Gulf Polymers"))
    preview = lambda lang: ncr.client.post("/api/v1/reports/quality.ncr/preview", json=dict(report_id=r["id"], lang=lang))  # noqa: E731
    ar = preview("ar")
    assert ar.status_code == 200, ar.text
    for text in ("تقرير عدم مطابقة", r["report_number"], "مواد واردة", "Gulf Polymers", "إرجاع للمورد", "الاحتواء الفوري", "المادة",
                 "مخطط عظم السمكة", "إجراء تصحيحي", "طلب إجراء تصحيحي من المورد (SCAR)", "9000", "مُطالَب بها", "طن"):
        assert text in ar.text, text
    en = preview("en").text
    assert "NON-CONFORMANCE REPORT" in en and "Return to supplier" in en and "Corrective action" in en and "Fishbone" in en


@pytest.mark.skipif(not __import__("os").environ.get("REPORT_SAMPLES_DIR"), reason="Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running")
def test_write_ncr_samples(ncr):
    """A supplier's material report through its stages, in Arabic and English, through the real renderer."""
    import os
    from pathlib import Path
    out = Path(os.environ["REPORT_SAMPLES_DIR"]); out.mkdir(parents=True, exist_ok=True)
    r = ncr.create(cost_material="9000", cost_labor="1200", claim_amount="10200", claim_status="claimed", supplier_action="scar",
                   owner_user_id=str(ncr.user.id), due_date="2026-10-20")
    ncr.step(r, "contain", containment="Lot SUP-7781 quarantined and tagged; line 2 switched to lot SUP-7790.")
    ncr.step(r, "investigate", root_cause_category="material", root_cause_method="five_whys",
             root_cause="The supplier's silo was not dried after maintenance; its release check does not measure moisture.")
    for kind, text in (("correction", "Return lot SUP-7781 to the supplier"), ("corrective", "Supplier adds a moisture test to its release"),
                       ("preventive", "Moisture test on every incoming lot at receipt")):
        ncr.client.post(f"{ROOT}/{r['id']}/actions", json=dict(kind=kind, description=text, owner_name="Gulf Polymers", due_date="2026-10-15"))
    for lang in ("ar", "en"):
        doc = ncr.client.get(f"{ROOT}/{r['id']}/document.pdf", params=dict(lang=lang))
        assert doc.status_code == 200, doc.text
        (out / f"NCR-{lang}.pdf").write_bytes(doc.content)
