"""QUAL-REPORT-001: the quality report center — one inspection, checks summary, rejections and defects — and quality in R1."""
import ast
from pathlib import Path
from uuid import uuid4

import pytest

from app.quality.domain import permissions as Q
from app.quality.domain import report_permissions as R
from tests.quality.test_quality_inspections import q, result_env  # noqa: F401  (fixtures)

REPORTS = "/api/v1/reports"
CHECKS = "/api/v1/quality/quality-checks"
REJECTIONS = "/api/v1/quality/quality-rejections"


@pytest.fixture
def rq(q):
    q.ctx.user.id = q.user.id
    q.ctx.user.full_name = q.user.full_name
    q.ctx.auth_user.permissions |= set(R.ALL) | {"reports:production:order_full"}

    def closed(po, inspected, accepted, rejected, result, line=0, **extra):
        c = q.opened(po, line=line, check_type="finished_product_inspection")
        r = q.close_check(c, inspected, accepted, rejected, result, **extra)
        assert r.status_code == 200, r.text
        return r.json()

    q.closed = closed
    return q


def preview(env, key, **params):
    return env.client.post(f"{REPORTS}/quality.{key}/preview", json=params)


def defect(env, check, category, severity, count=1, description="Found on inspection"):
    r = env.client.post(f"{CHECKS}/{check['id']}/defects", json=dict(defect_date="2026-10-03", defect_category=category, severity=severity,
                                                                    defect_count=count, description=description))
    assert r.status_code == 201, r.text
    return r.json()


def decide(env, rejection_id, disposition, **extra):
    r = env.client.post(f"{REJECTIONS}/{rejection_id}/decide", json=dict(disposition=disposition, **extra))
    assert r.status_code == 200, r.text


# ── the center lists what the user may run ──────────────────────────────────────────────────────

def test_center_lists_the_four_quality_reports_by_permission(rq):
    keys = {d["key"] for d in rq.client.get(f"{REPORTS}/definitions?module=quality").json()}
    assert keys == {"quality.check_full", "quality.checks_summary", "quality.rejections_analysis", "quality.defects_analysis"}
    rq.ctx.auth_user.permissions -= {Q.REJECTIONS_READ, R.REPORT_DEFECTS_ANALYSIS}
    keys = {d["key"] for d in rq.client.get(f"{REPORTS}/definitions?module=quality").json()}
    assert keys == {"quality.check_full", "quality.checks_summary"}  # rejections need their data; defects their report
    assert preview(rq, "rejections_analysis").status_code == 403


# ── Q1: one inspection ──────────────────────────────────────────────────────────────────────────

def test_check_report_is_interim_until_closed_then_complete(rq):
    po = rq.bare("kg", status="in_progress")
    c = rq.opened(po, check_type="finished_product_inspection")
    r = preview(rq, "check_full", check_id=c["id"])
    assert r.status_code == 200, r.text
    assert "تقرير مرحلي" in r.text and c["inspection_code"] in r.text and "معلومات الفحص" in r.text
    done = rq.close_check(c, "100", "92", "8", "rejected", rejection_reason="out_of_spec").json()
    defect(rq, done, "thickness", "major", 3)
    r = preview(rq, "check_full", check_id=c["id"])
    assert "تقرير مرحلي" not in r.text
    for text in ("العيوب المكتشفة", "السماكة / القياس", "حالات الرفض والقرارات", "خارج المواصفات", "بانتظار القرار", "إغلاق بالنتيجة", "92"):
        assert text in r.text, text
    english = preview(rq, "check_full", check_id=c["id"], lang="en").text
    assert "Inspection information" in english and "Awaiting decision" in english and "معلومات الفحص" not in english


def test_cancelled_check_is_marked_and_sections_follow_permissions(rq):
    c = rq.opened(rq.bare("kg", status="in_progress"))
    assert rq.client.post(f"{CHECKS}/{c['id']}/cancel", json=dict(reason="Lot moved")).status_code == 200
    r = preview(rq, "check_full", check_id=c["id"])
    assert "فحص ملغى" in r.text and "Lot moved" in r.text
    rq.ctx.auth_user.permissions.discard(Q.DEFECTS_READ)
    assert preview(rq, "check_full", check_id=c["id"], sections=["defects"]).status_code == 403
    assert preview(rq, "check_full", check_id=str(uuid4())).status_code == 404


def test_check_report_escapes_text(rq):
    c = rq.opened(rq.bare("kg", status="in_progress"), notes="<script>alert(1)</script>")
    r = preview(rq, "check_full", check_id=c["id"], sections=["notes"])
    assert "&lt;script&gt;" in r.text and "<script>alert" not in r.text


# ── Q2: checks summary ──────────────────────────────────────────────────────────────────────────

def test_summary_keeps_units_apart_and_counts_closed_checks_only(rq):
    po = rq.bare("kg", "roll", status="in_progress")
    rq.closed(po, "100", "92", "8", "rejected")
    rq.closed(po, "50", "50", "0", "accepted")
    rq.closed(po, "10", "10", "0", "accepted", line=1)
    rq.opened(po, check_type="in_process_inspection")
    r = preview(rq, "checks_summary")
    assert r.status_code == 200, r.text
    assert "الإجماليات حسب الوحدة" in r.text and "توزيع النتائج" in r.text
    assert "94.67" in r.text  # kg: 142 accepted of 150
    assert "5.33" in r.text   # kg rejection rate
    assert "100.00" in r.text  # roll
    assert preview(rq, "checks_summary", date_from="2026-12-01", date_to="2026-01-01").status_code == 422


def test_summary_filters_and_grouping(rq):
    po = rq.bare("kg", status="in_progress")
    rq.closed(po, "100", "92", "8", "rejected")
    rq.closed(po, "50", "50", "0", "accepted")
    r = preview(rq, "checks_summary", result=["rejected"], grouping="result", order_id=po["id"])
    assert "النتيجة: مرفوض" in r.text and "الفحوصات مرفوض" in r.text and "الفحوصات مقبول" not in r.text


# ── Q3: rejections and dispositions ─────────────────────────────────────────────────────────────

def test_rejections_analysis_shows_outcomes_and_unresolved_cases(rq):
    po = rq.bare("kg", status="in_progress")
    rq.closed(po, "100", "90", "10", "rejected", rejection_reason="out_of_spec")
    rq.closed(po, "100", "95", "5", "rejected", rejection_reason="surface_failure")
    rq.closed(po, "100", "98", "2", "rejected")
    first, second, _third = sorted(rq.rejections(po), key=lambda r: r["rejection_code"])
    decide(rq, first["id"], "scrap")
    decide(rq, second["id"], "hold")
    r = preview(rq, "rejections_analysis")
    assert r.status_code == 200, r.text
    for text in ("ملخص الرفض حسب الوحدة", "هالك (إتلاف)", "حجز (عزل)", "بانتظار القرار", "خارج المواصفات", "حالات بلا قرار نهائي"):
        assert text in r.text, text
    open_section = r.text.split("حالات بلا قرار نهائي")[-1]
    assert second["rejection_code"] in open_section and first["rejection_code"] not in open_section.split("اتجاه")[0]
    assert "58.82" in r.text  # out_of_spec: 10 of 17 kg


# ── Q4: defects ─────────────────────────────────────────────────────────────────────────────────

def test_defects_pareto_and_severity(rq):
    po = rq.bare("kg", status="in_progress")
    c = rq.closed(po, "100", "100", "0", "accepted")
    defect(rq, c, "thickness", "major", 6)
    defect(rq, c, "surface", "minor", 3)
    defect(rq, c, "winding", "critical", 1, description="Telescoped roll")
    r = preview(rq, "defects_analysis")
    assert r.status_code == 200, r.text
    body = r.text
    assert body.index("السماكة / القياس") < body.index("عيب سطحي") < body.index("عيب اللف")  # most units first
    assert "60.00" in body and "90.00" in body and "100.00" in body  # share and cumulative
    assert "Telescoped roll" in body and "العيوب الرئيسية والحرجة" in body


# ── lookups, tenancy and boundaries ─────────────────────────────────────────────────────────────

def test_lookups_are_scoped_and_need_read_permissions(rq):
    po = rq.bare("kg", status="in_progress")
    c = rq.opened(po)
    checks = rq.client.get(f"{REPORTS}/quality/lookups/checks?q={c['inspection_code']}").json()
    assert [x["label"] for x in checks] == [c["inspection_code"]]
    assert rq.client.get(f"{REPORTS}/quality/lookups/orders").status_code == 200
    assert rq.client.get(f"{REPORTS}/quality/lookups/unknown").status_code == 404
    rq.ctx.auth_user.permissions.discard(Q.CHECKS_READ)
    assert rq.client.get(f"{REPORTS}/quality/lookups/checks").status_code == 403


def test_production_order_report_includes_quality_for_readers(rq):
    po = rq.bare("kg", status="in_progress")
    rq.closed(po, "100", "92", "8", "rejected")
    definition = next(d for d in rq.client.get(f"{REPORTS}/definitions?module=production&order_id={po['id']}").json() if d["key"] == "production.order_full")
    assert {"quality_checks", "quality_rejections"} <= {s["key"] for s in definition["sections"]}
    r = rq.client.post(f"{REPORTS}/production.order_full/preview", json=dict(order_id=po["id"]))
    assert "فحوصات الجودة" in r.text and "حالات رفض الجودة" in r.text and "بانتظار القرار" in r.text
    rq.ctx.auth_user.permissions -= {Q.CHECKS_READ, Q.REJECTIONS_READ}
    r = rq.client.post(f"{REPORTS}/production.order_full/preview", json=dict(order_id=po["id"]))
    assert r.status_code == 200 and "فحوصات الجودة" not in r.text


def test_row_limit_asks_to_narrow_filters(rq, monkeypatch):
    from app.quality.reporting import builders
    monkeypatch.setattr(builders, "LIMIT", 1)
    po = rq.bare("kg", status="in_progress")
    rq.opened(po); rq.opened(po)
    r = preview(rq, "checks_summary")
    assert r.status_code == 422 and "REPORT_ROW_LIMIT_NARROW_FILTERS" in r.text


def test_quality_reporting_imports_no_other_module():
    root = Path(__file__).resolve().parents[2] / "app" / "quality" / "reporting"
    imported = set()
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    assert not [m for m in imported if m.split(".")[:2] in (["app", "production"], ["app", "commercial"], ["app", "foundation"], ["app", "workforce"])]


@pytest.mark.skipif(not __import__("os").environ.get("REPORT_SAMPLES_DIR"), reason="Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running")
def test_write_review_samples(rq):
    """Q1 (Arabic and English), Q2, Q3 and Q4 through the real renderer, for visual review. Written outside the project."""
    import os
    out = Path(os.environ["REPORT_SAMPLES_DIR"]); out.mkdir(parents=True, exist_ok=True)

    def save(key, name, **params):
        r = rq.client.post(f"{REPORTS}/quality.{key}/pdf", json=params)
        assert r.status_code == 200, r.text
        (out / name).write_bytes(r.content)
    po = rq.planned({"width_mm": 5, "thickness_mm": 0.35, "weight_kg": 10, "color": "Black"}, {"width_mm": 15, "thickness_mm": 0.85}, to="in_progress")
    main = rq.closed(po, "120", "112", "8", "rejected", rejection_reason="dimension_failure", notes="Width below tolerance on 8 rolls")
    defect(rq, main, "dimension", "major", 8, "Width 4.5 mm on 8 rolls")
    defect(rq, main, "winding", "minor", 2, "Loose winding")
    rq.closed(po, "60", "60", "0", "accepted", line=1)
    rq.closed(po, "40", "38", "2", "conditional_accept")
    rejection = sorted(rq.rejections(po), key=lambda r: r["rejection_code"])[0]
    decide(rq, rejection["id"], "rework", decision_notes="Re-slit to 5 mm")
    save("check_full", "Q1-check.pdf", check_id=main["id"])
    save("check_full", "Q1-check-en.pdf", check_id=main["id"], lang="en")
    save("checks_summary", "Q2-summary.pdf")
    save("rejections_analysis", "Q3-rejections.pdf")
    save("defects_analysis", "Q4-defects.pdf")
    save("defects_analysis", "Q4-defects-en.pdf", lang="en")
