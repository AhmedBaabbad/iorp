"""QUAL-SPEC-001: test parameters, controlled product specifications and inspection measurements."""
import pytest

from app.quality.domain import permissions as Q
from tests.quality.test_quality_inspections import q, result_env  # noqa: F401  (fixtures)

PARAMS = "/api/v1/quality/quality-test-parameters"
SPECS = "/api/v1/quality/quality-specifications"
CHECKS = "/api/v1/quality/quality-checks"


def code(r):
    return r.json()["detail"]["code"]


@pytest.fixture
def sq(q):
    params = {p["code"]: p["id"] for p in q.client.post(f"{PARAMS}/standard").json()}

    def spec(code_="ROF-TDS-PP-001", product="film", lines=None, activate=True, **extra):
        body = dict(code=code_, title="PP strap — full automatic", product_type=product, grade="Full Automatic",
                    lines=lines if lines is not None else standard_lines(params), **extra)
        r = q.client.post(SPECS, json=body)
        assert r.status_code == 201, r.text
        if activate:
            r = q.client.post(f"{SPECS}/{r.json()['id']}/activate")
            assert r.status_code == 200, r.text
        return r.json()

    def measure(check, parameter_code, readings=None, result=None, observation=None):
        m = next(m for m in check["measurements"] if m["parameter_code"] == parameter_code)
        r = q.client.put(f"{CHECKS}/{check['id']}/measurements/{m['id']}",
                         json=dict(readings=readings or [], attribute_result=result, observation=observation))
        assert r.status_code == 200, r.text
        return r.json()

    q.params, q.spec, q.measure = params, spec, measure
    return q


def standard_lines(params):
    return [
        dict(parameter_id=params["WIDTH"], target_source="order_line", order_spec_key="width_mm", tolerance_minus="0.2", tolerance_plus="0.2",
             readings_required=3),
        dict(parameter_id=params["THICKNESS"], target_source="order_line", order_spec_key="thickness_mm", tolerance_minus="0.01", tolerance_plus="0.02"),
        dict(parameter_id=params["ROLL_LENGTH"], min_value="6900"),
        dict(parameter_id=params["COLOR"], requirement="As approved sample", acceptance="Visual match required"),
    ]


def strap_order(sq, **spec):
    return sq.planned(spec or {"width_mm": 5, "thickness_mm": 0.35}, to="in_progress")


# ── parameters ──────────────────────────────────────────────────────────────────────────────────

def test_standard_parameters_are_added_once_and_codes_are_unique(sq):
    assert {"WIDTH", "THICKNESS", "BREAK_STRENGTH", "ELONGATION", "COLOR", "CORE_PACKAGING"} <= set(sq.params)
    again = sq.client.post(f"{PARAMS}/standard").json()
    assert len(again) == len(sq.params)
    r = sq.client.post(PARAMS, json=dict(code="width", name_ar="عرض", name_en="Width", kind="numeric", unit="mm"))
    assert r.status_code == 409 and code(r) == "PARAMETER_CODE_TAKEN"
    r = sq.client.post(PARAMS, json=dict(code="CAMBER", name_ar="الانحناء", name_en="Camber", kind="numeric", unit="mm"))
    assert r.status_code == 201 and r.json()["code"] == "CAMBER"


# ── specification documents ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("line,expected", [
    (dict(parameter="WIDTH"), "LIMITS_REQUIRED"),
    (dict(parameter="WIDTH", target_source="order_line", tolerance_plus="0.2"), "ORDER_SPEC_KEY_REQUIRED"),
    (dict(parameter="WIDTH", target_source="fixed", tolerance_plus="0.2"), "TARGET_REQUIRED"),
    (dict(parameter="WIDTH", min_value="6", max_value="5"), "LIMITS_INVALID"),
    (dict(parameter="COLOR"), "REQUIREMENT_REQUIRED"),
])
def test_specification_lines_are_validated(sq, line, expected):
    line = dict(line, parameter_id=sq.params[line.pop("parameter")])
    r = sq.client.post(SPECS, json=dict(code="X-1", title="x", product_type="film", lines=[line]))
    assert r.status_code == 400 and code(r) == expected
    assert sq.client.get(SPECS).json() == []  # nothing half-saved


def test_draft_activate_revise_supersede(sq):
    draft = sq.spec(activate=False)
    assert draft["status"] == "draft" and draft["revision"] == 1 and set(draft["actions"]) == {"edit", "activate"}
    assert sq.client.post(f"{SPECS}/{sq.spec(code_='EMPTY', lines=[], activate=False)['id']}/activate").json()["detail"]["code"] == "SPECIFICATION_EMPTY"
    active = sq.client.post(f"{SPECS}/{draft['id']}/activate").json()
    assert active["status"] == "active" and active["actions"] == ["revise"]
    r = sq.client.patch(f"{SPECS}/{active['id']}", json=dict(title="changed"))
    assert r.status_code == 409 and code(r) == "SPECIFICATION_NOT_DRAFT"
    revision = sq.client.post(f"{SPECS}/{active['id']}/revise").json()
    assert revision["revision"] == 2 and revision["status"] == "draft" and len(revision["lines"]) == 4
    assert code(sq.client.post(f"{SPECS}/{active['id']}/revise")) == "SPECIFICATION_DRAFT_EXISTS"
    sq.client.post(f"{SPECS}/{revision['id']}/activate")
    assert sq.client.get(f"{SPECS}/{active['id']}").json()["status"] == "superseded"
    assert [s["status"] for s in sq.client.get(SPECS, params=dict(status="active")).json()] == ["active"]


# ── measurement plan on an inspection ───────────────────────────────────────────────────────────

def test_new_inspection_takes_the_specification_with_limits_for_its_lot(sq):
    spec = sq.spec()
    check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    assert check["specification_code"] == spec["code"] and check["specification_revision"] == 1
    by_code = {m["parameter_code"]: m for m in check["measurements"]}
    assert list(by_code) == ["WIDTH", "THICKNESS", "ROLL_LENGTH", "COLOR"]
    width, thickness, length = by_code["WIDTH"], by_code["THICKNESS"], by_code["ROLL_LENGTH"]
    assert (float(width["target"]), float(width["lower_limit"]), float(width["upper_limit"])) == (5, 4.8, 5.2)
    assert (float(thickness["lower_limit"]), float(thickness["upper_limit"])) == (0.34, 0.37)
    assert length["target"] is None and float(length["lower_limit"]) == 6900 and length["upper_limit"] is None
    assert by_code["COLOR"]["requirement"] == "As approved sample" and all(m["status"] == "pending" for m in check["measurements"])
    assert "measure" in check["actions"]


def test_readings_decide_pass_or_fail_and_gate_the_close(sq):
    sq.spec()
    check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    check = sq.measure(check, "WIDTH", ["5.0", "5.1"])
    assert next(m for m in check["measurements"] if m["parameter_code"] == "WIDTH")["status"] == "pending"  # 3 readings required
    check = sq.measure(check, "WIDTH", ["5.0", "5.1", "4.9"])
    check = sq.measure(check, "THICKNESS", ["0.36", "0.38"])
    check = sq.measure(check, "COLOR", result="conforming")
    by_code = {m["parameter_code"]: m for m in check["measurements"]}
    assert by_code["WIDTH"]["status"] == "pass" and float(by_code["WIDTH"]["mean"]) == 5
    assert by_code["THICKNESS"]["status"] == "fail" and float(by_code["THICKNESS"]["maximum"]) == 0.38
    r = sq.close_check(check, "10", "10", "0", "accepted")
    assert r.status_code == 409 and code(r) == "MEASUREMENTS_INCOMPLETE" and r.json()["detail"]["count"] == 1
    check = sq.measure(check, "ROLL_LENGTH", ["6950"])
    r = sq.close_check(check, "10", "10", "0", "accepted")
    assert r.status_code == 400 and code(r) == "ACCEPTED_WITH_FAILED_MEASUREMENT"
    assert sq.close_check(check, "10", "10", "0", "conditional_accept").status_code == 200
    r = sq.client.put(f"{CHECKS}/{check['id']}/measurements/{by_code['WIDTH']['id']}", json=dict(readings=["5"]))
    assert r.status_code == 409 and code(r) == "CHECK_IS_FINAL"


def test_choice_between_specifications_and_no_replan_after_measuring(sq):
    sq.spec()
    second = sq.spec(code_="ROF-TDS-PP-002")
    check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    assert check["measurements"] == [] and check["specification_code"] is None  # two in force: the inspector chooses
    candidates = sq.client.get(f"{CHECKS}/{check['id']}/specifications").json()
    assert {c["code"] for c in candidates} == {"ROF-TDS-PP-001", "ROF-TDS-PP-002"}
    check = sq.client.post(f"{CHECKS}/{check['id']}/plan", json=dict(specification_id=second["id"])).json()
    assert check["specification_code"] == "ROF-TDS-PP-002"
    sq.measure(check, "COLOR", result="conforming")
    r = sq.client.post(f"{CHECKS}/{check['id']}/plan", json=dict(specification_id=second["id"]))
    assert r.status_code == 409 and code(r) == "MEASUREMENTS_STARTED"


def test_lot_without_the_specified_value_waits_for_a_manual_plan(sq):
    spec = sq.spec()
    check = sq.opened(strap_order(sq, color="Black"), check_type="finished_product_inspection")
    assert check["measurements"] == []
    r = sq.client.post(f"{CHECKS}/{check['id']}/plan", json=dict(specification_id=spec["id"]))
    assert r.status_code == 409 and code(r) == "LOT_SPEC_VALUE_MISSING" and r.json()["detail"]["key"] == "width_mm"


def test_a_new_revision_never_changes_an_inspection_already_planned(sq):
    spec = sq.spec()
    check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    revision = sq.client.post(f"{SPECS}/{spec['id']}/revise").json()
    lines = [dict({k: v for k, v in line.items() if k in ("parameter_id", "target_source", "order_spec_key", "target_value", "tolerance_minus",
                                                            "tolerance_plus", "min_value", "max_value", "requirement", "acceptance", "method",
                                                            "readings_required")}) for line in revision["lines"]]
    lines[0]["tolerance_plus"] = "0.5"
    assert sq.client.patch(f"{SPECS}/{revision['id']}", json=dict(lines=lines)).status_code == 200
    sq.client.post(f"{SPECS}/{revision['id']}/activate")
    width = next(m for m in sq.client.get(f"{CHECKS}/{check['id']}").json()["measurements"] if m["parameter_code"] == "WIDTH")
    assert float(width["upper_limit"]) == 5.2
    newer = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    assert newer["specification_revision"] == 2 and float(newer["measurements"][0]["upper_limit"]) == 5.5


def test_permissions_per_action(sq):
    spec = sq.spec(activate=False)
    sq.ctx.auth_user.permissions.discard(Q.SPECS_ACTIVATE)
    assert sq.client.post(f"{SPECS}/{spec['id']}/activate").status_code == 403
    sq.ctx.auth_user.permissions.add(Q.SPECS_ACTIVATE)
    sq.client.post(f"{SPECS}/{spec['id']}/activate")
    check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    sq.ctx.auth_user.permissions.discard(Q.CHECKS_MEASURE)
    m = check["measurements"][0]
    assert sq.client.put(f"{CHECKS}/{check['id']}/measurements/{m['id']}", json=dict(readings=["5"])).status_code == 403
    assert "measure" not in sq.client.get(f"{CHECKS}/{check['id']}").json()["actions"]


def test_inspection_report_shows_the_plan_and_verdicts(sq):
    sq.ctx.user.id, sq.ctx.user.full_name = sq.user.id, sq.user.full_name
    sq.ctx.auth_user.permissions.add("reports:quality:check_full")
    sq.spec()
    check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    check = sq.measure(check, "WIDTH", ["5.0", "5.1", "4.9"])
    check = sq.measure(check, "COLOR", result="conforming", observation="Black")
    r = sq.client.post("/api/v1/reports/quality.check_full/preview", json=dict(check_id=check["id"]))
    assert r.status_code == 200, r.text
    for text in ("نتائج القياس", "ROF-TDS-PP-001 — rev 1", "4.8 – 5.2", "≥ 6900", "As approved sample", "مطابق — Black", "لم يُقَس", "Calibrated vernier caliper"):
        assert text in r.text, text
    english = sq.client.post("/api/v1/reports/quality.check_full/preview", json=dict(check_id=check["id"], lang="en")).text
    assert "Measurement results" in english and "Width" in english and "Not measured" in english


@pytest.mark.skipif(not __import__("os").environ.get("REPORT_SAMPLES_DIR"), reason="Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running")
def test_write_measured_inspection_sample(sq):
    """Q1 with a measurement plan (Arabic and English), through the real renderer. Written outside the project."""
    import os
    from pathlib import Path
    out = Path(os.environ["REPORT_SAMPLES_DIR"]); out.mkdir(parents=True, exist_ok=True)
    sq.ctx.user.id, sq.ctx.user.full_name = sq.user.id, sq.user.full_name
    sq.ctx.auth_user.permissions.add("reports:quality:check_full")
    p = sq.params
    sq.spec(lines=[
        dict(parameter_id=p["WIDTH"], target_source="order_line", order_spec_key="width_mm", tolerance_minus="0.2", tolerance_plus="0.2", readings_required=3),
        dict(parameter_id=p["THICKNESS"], target_source="order_line", order_spec_key="thickness_mm", tolerance_minus="0.01", tolerance_plus="0.03", readings_required=3),
        dict(parameter_id=p["ROLL_WEIGHT"], target_source="fixed", target_value="10", tolerance_minus="0.1", tolerance_plus="0.2"),
        dict(parameter_id=p["ROLL_LENGTH"], min_value="6900"),
        dict(parameter_id=p["BREAK_STRENGTH"], min_value="1200"),
        dict(parameter_id=p["COLOR"], requirement="As approved sample (Black)", acceptance="Visual match required"),
        dict(parameter_id=p["WINDING"], requirement="Firm, even and aligned", acceptance="No loose, telescoped or damaged roll"),
    ])
    check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    for code_, values in (("WIDTH", ["5.02", "4.97", "5.01"]), ("THICKNESS", ["0.35", "0.36", "0.37"]), ("ROLL_WEIGHT", ["10.05"]),
                          ("ROLL_LENGTH", ["6980"]), ("BREAK_STRENGTH", ["1350", "1380"])):
        check = sq.measure(check, code_, values)
    check = sq.measure(check, "COLOR", result="conforming", observation="Black")
    check = sq.measure(check, "WINDING", result="conforming")
    assert sq.close_check(check, "120", "120", "0", "accepted").status_code == 200
    for lang in ("ar", "en"):
        r = sq.client.post("/api/v1/reports/quality.check_full/pdf", json=dict(check_id=check["id"], lang=lang))
        assert r.status_code == 200, r.text
        (out / f"Q1-measured-{lang}.pdf").write_bytes(r.content)
