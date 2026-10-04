"""QUAL-COA-001: certificates of analysis from closed, conforming inspections — draft, issue, revoke, replace — and the document."""
import pytest

from app.quality.domain import permissions as Q
from tests.quality.test_quality_inspections import q, result_env  # noqa: F401  (fixtures)
from tests.quality.test_quality_specifications import sq, strap_order  # noqa: F401  (fixtures)

COA = "/api/v1/quality/quality-certificates"
SETTINGS = "/api/v1/quality/quality-settings"


def code(r):
    return r.json()["detail"]["code"]


@pytest.fixture
def cq(sq):
    sq.ctx.user.id, sq.ctx.user.full_name = sq.user.id, sq.user.full_name
    sq.spec()

    def measured_check(width=("5.0", "5.1", "4.9"), result="accepted", accepted="120", rejected="0"):
        check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
        check = sq.measure(check, "WIDTH", list(width))
        check = sq.measure(check, "THICKNESS", ["0.35"])
        check = sq.measure(check, "ROLL_LENGTH", ["6950"])
        check = sq.measure(check, "COLOR", result="conforming", observation="Black")
        total = str(int(accepted) + int(rejected))
        r = sq.close_check(check, total, accepted, rejected, result)
        assert r.status_code == 200, r.text
        return r.json()

    def draft(check, **extra):
        r = sq.client.post(COA, json=dict(quality_check_id=check["id"], **extra))
        assert r.status_code == 201, r.text
        return r.json()

    sq.measured_check, sq.draft = measured_check, draft
    return sq


def test_only_closed_conforming_measured_inspections_are_certifiable(cq):
    open_check = cq.opened(strap_order(cq), check_type="finished_product_inspection")
    assert code(cq.client.post(COA, json=dict(quality_check_id=open_check["id"]))) == "CHECK_NOT_CLOSED"
    unplanned = cq.close_check(cq.opened(check_type="general"), "10", "10", "0", "accepted").json()
    assert code(cq.client.post(COA, json=dict(quality_check_id=unplanned["id"]))) == "CERTIFICATE_NEEDS_MEASUREMENTS"
    failed = cq.measured_check(width=("5.0", "5.5", "4.9"), result="conditional_accept")
    sources = cq.client.get(f"{COA}/sources", params=dict(check_id=failed["id"])).json()
    assert sources["certifiable"] is False and sources["blocker"] == "CERTIFICATE_HAS_FAILED_MEASUREMENT"
    rejected = cq.measured_check(result="rejected", accepted="100", rejected="20")
    assert code(cq.client.post(COA, json=dict(quality_check_id=rejected["id"]))) == "CHECK_NOT_CERTIFIABLE"


def test_draft_takes_the_inspection_facts_and_freezes_them(cq):
    check = cq.measured_check()
    sources = cq.client.get(f"{COA}/sources", params=dict(check_id=check["id"])).json()
    assert sources["certifiable"] and len(sources["customers"]) == 1
    draft = cq.draft(check, customer_po="PO-7788")
    assert draft["status"] == "draft" and draft["certificate_no"] is None and set(draft["actions"]) == {"edit", "issue"}
    assert draft["customer_name"] == sources["customers"][0]["name"] and draft["customer_po"] == "PO-7788"
    assert draft["batch_no"] == f"{check['order_number']}-L1" and draft["product_description"] == "PP strap — full automatic"
    assert draft["specification_code"] == "ROF-TDS-PP-001" and draft["inspection_code"] == check["inspection_code"]
    assert float(draft["quantity"]) == 120 and draft["inspector_name"]
    width = next(m for m in draft["measurements"] if m["code"] == "WIDTH")
    assert (width["lower"], width["upper"], width["mean"], width["status"]) == ("4.8", "5.2", "5", "pass")
    r = cq.client.patch(f"{COA}/{draft['id']}", json=dict(quantity="130"))
    assert r.status_code == 400 and code(r) == "QUANTITY_EXCEEDS_ACCEPTED"
    updated = cq.client.patch(f"{COA}/{draft['id']}", json=dict(quantity="100", package_count=10, delivery_ref="DN-55", retained_sample=True,
                                                                 retention_ref="RS-1")).json()
    assert float(updated["quantity"]) == 100 and updated["package_count"] == 10 and updated["retained_sample"]


def test_issue_numbers_from_the_settings_and_locks(cq):
    assert cq.client.patch(SETTINGS, json=dict(coa_prefix="ROF-COA-", coa_last_number=9)).status_code == 200
    assert code(cq.client.patch(SETTINGS, json=dict(coa_last_number=5))) == "CERTIFICATE_NUMBER_BACKWARDS"
    draft = cq.draft(cq.measured_check())
    issued = cq.client.post(f"{COA}/{draft['id']}/issue").json()
    assert issued["status"] == "issued" and issued["certificate_no"] == "ROF-COA-0010" and issued["issued_by_name"]
    assert set(issued["actions"]) == {"revoke", "replace"}
    r = cq.client.patch(f"{COA}/{draft['id']}", json=dict(remarks="late edit"))
    assert r.status_code == 409 and code(r) == "CERTIFICATE_NOT_DRAFT"
    assert cq.client.get(SETTINGS).json()["coa_last_number"] == 10


def test_replacement_supersedes_and_revoke_needs_a_reason(cq):
    issued = cq.client.post(f"{COA}/{cq.draft(cq.measured_check())['id']}/issue").json()
    replacement = cq.client.post(f"{COA}/{issued['id']}/replace").json()
    assert replacement["status"] == "draft" and replacement["supersedes_no"] == issued["certificate_no"]
    assert code(cq.client.post(f"{COA}/{issued['id']}/replace")) == "REPLACEMENT_DRAFT_EXISTS"
    cq.client.patch(f"{COA}/{replacement['id']}", json=dict(customer_po="PO-CORRECTED"))
    second = cq.client.post(f"{COA}/{replacement['id']}/issue").json()
    old = cq.client.get(f"{COA}/{issued['id']}").json()
    assert old["status"] == "revoked" and old["revoke_reason"] == f"Superseded by {second['certificate_no']}"
    assert old["superseded_by_no"] == second["certificate_no"]
    assert cq.client.post(f"{COA}/{second['id']}/revoke", json=dict(reason=" ")).status_code == 422
    revoked = cq.client.post(f"{COA}/{second['id']}/revoke", json=dict(reason="Wrong customer")).json()
    assert revoked["status"] == "revoked" and revoked["actions"] == []


def test_conditional_acceptance_states_its_deviation(cq):
    draft = cq.draft(cq.measured_check(result="conditional_accept"))
    r = cq.client.post(f"{COA}/{draft['id']}/issue")
    assert r.status_code == 400 and code(r) == "DEVIATION_NOTE_REQUIRED"
    cq.client.patch(f"{COA}/{draft['id']}", json=dict(deviation_note="Core 150 mm accepted by the customer"))
    assert cq.client.post(f"{COA}/{draft['id']}/issue").json()["status"] == "issued"


def test_document_in_english_and_arabic(cq):
    cq.ctx.auth_user.permissions.add(Q.COA_READ)
    draft = cq.draft(cq.measured_check(), customer_po="PO-7788")
    page = lambda lang: cq.client.post("/api/v1/reports/quality.certificate/preview", json=dict(certificate_id=draft["id"], lang=lang))  # noqa: E731
    r = page("en")
    assert r.status_code == 200, r.text
    for text in ("CERTIFICATE OF ANALYSIS (COA)", "DRAFT — NOT VALID", "PO-7788", "ROF-TDS-PP-001 — rev 1", "4.8 – 5.2", "PASS",
                 "Conforming — Black", "PENDING RELEASE APPROVAL", "valid without a signature"):
        assert text in r.text, text
    cq.client.post(f"{COA}/{draft['id']}/issue")
    issued = page("en").text
    assert "DRAFT — NOT VALID" not in issued and "COA-0001" in issued and "RELEASED / CONFORMING" in issued
    arabic = page("ar").text
    for text in ("شهادة تحليل (COA)", "بيانات الشهادة والدفعة", "مطابق — Black", "مُفرَج عنه — مطابق", "العرض"):
        assert text in arabic, text


def test_permissions_per_action(cq):
    draft = cq.draft(cq.measured_check())
    cq.ctx.auth_user.permissions.discard(Q.COA_ISSUE)
    assert cq.client.post(f"{COA}/{draft['id']}/issue").status_code == 403
    assert "issue" not in cq.client.get(f"{COA}/{draft['id']}").json()["actions"]
    cq.ctx.auth_user.permissions.discard(Q.COA_READ)
    assert cq.client.get(COA).status_code == 403


@pytest.mark.skipif(not __import__("os").environ.get("REPORT_SAMPLES_DIR"), reason="Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running")
def test_write_certificate_samples(cq):
    """The COA in English and Arabic (issued) and a draft, through the real renderer. Written outside the project."""
    import os
    from pathlib import Path
    from app.foundation.api.branding_schemas import BrandingUpdate
    from app.foundation.application.branding_service import BrandingService
    out = Path(os.environ["REPORT_SAMPLES_DIR"]); out.mkdir(parents=True, exist_ok=True)
    BrandingService(cq.db).update(cq.org.id, BrandingUpdate(legal_name_ar="مصنع ريحانة الأفق للصناعة", legal_name_en="REHANAH AL-OFUQ FACTORY FOR INDUSTRY",
                                                           commercial_registration_no="1010000000", vat_number="300000000000003"), cq.user.id)
    cq.client.patch(SETTINGS, json=dict(coa_prefix="ROF-COA-", coa_last_number=12))
    draft = cq.draft(cq.measured_check(), customer_po="UCIC-PO-4471")
    cq.client.patch(f"{COA}/{draft['id']}", json=dict(customer_name="UCIC Company", package_count=12, delivery_ref="DN-2026-0091",
                                                     sampling_reference="QC-PLAN-01", retained_sample=True, retention_ref="RS-0310"))
    save = lambda name, lang: (out / name).write_bytes(cq.client.get(f"{COA}/{draft['id']}/document.pdf", params=dict(lang=lang)).content)  # noqa: E731
    save("COA-draft-en.pdf", "en")
    cq.client.post(f"{COA}/{draft['id']}/issue")
    save("COA-issued-en.pdf", "en")
    save("COA-issued-ar.pdf", "ar")
