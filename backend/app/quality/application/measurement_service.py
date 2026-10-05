"""Inspection measurements (QUAL-SPEC-001): the single writer of a check's measurement plan and readings.

Applying a specification copies its lines into the check with the limits resolved for the inspected lot (the order
line's specification values, or the sample's), so the plan never changes when the specification is later revised.
Any specification in force can be applied (those for the order's product are offered first). A value the specification
takes from the order line but the line lacks (e.g. an order written before its sizes were recorded) is entered by the
inspector when applying the plan; it is kept on the check as the lot's value. A value the order line has always wins.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.core.utils import utc_now
from app.quality.domain import rules as check_rules
from app.quality.domain import specifications as rules
from app.quality.domain.rules import QualityError
from app.quality.infrastructure.models import QualityCheck, QualityCheckMeasurement
from .specification_service import SpecificationService
from .support import CommercialReads, ProductionReads, record


class MeasurementService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.specs = SpecificationService(db, tenant)

    def measurements(self, check_id) -> list[QualityCheckMeasurement]:
        return list(self.db.scalars(select(QualityCheckMeasurement).where(
            QualityCheckMeasurement.organization_id == self.org, QualityCheckMeasurement.quality_check_id == check_id)
            .order_by(QualityCheckMeasurement.position)))

    def lot(self, check) -> tuple[str | None, dict]:
        """(product type, specification values) of what the check inspects."""
        if check.sample_id:
            return CommercialReads(self.db, self.org).sample_spec(check.sample_id)
        if check.production_order_id:
            return ProductionReads(self.db, self.org).lot_spec(check.production_order_id, check.production_order_item_id)
        return None, {}

    def candidates(self, check) -> list[tuple]:
        """Every specification in force as (specification, matches the product, lot values it still needs), matching ones first."""
        product, lot_spec = self.lot(check)
        effective = self._effective(check, lot_spec)
        matching = {s.id for s in self.specs.active_for(product)} if product else set()
        specs = self.specs.list(status=rules.ACTIVE)
        out = [(s, s.id in matching, self.missing_keys(s.id, effective)) for s in specs]
        return sorted(out, key=lambda row: (not row[1], row[0].code))

    def missing_keys(self, spec_id, effective) -> list[str]:
        keys = {line.order_spec_key for line, parameter in self.specs.lines(spec_id)
                if parameter.kind == rules.NUMERIC and line.target_source == rules.ORDER_LINE and line.order_spec_key}
        return sorted(k for k in keys if rules.decimal(effective.get(k)) is None)

    @staticmethod
    def _effective(check, lot_spec, extra=None) -> dict:
        """The lot's values: the order line's (or sample's), completed by what the inspector entered for the missing ones."""
        entered = {**(check.lot_values or {}), **(extra or {})}
        effective = dict(lot_spec)
        for key, value in entered.items():
            if rules.decimal(lot_spec.get(key)) is None:
                effective[key] = value
        return effective

    def apply(self, check: QualityCheck, spec_id, *, lot_values=None, commit=True):
        """Copies the specification's lines into the check; replaces a plan nothing has been measured against yet."""
        check_rules.assert_editable(check.status)
        spec = self.specs.get(spec_id)
        if spec.status != rules.ACTIVE:
            raise QualityError("SPECIFICATION_NOT_ACTIVE", spec_status=spec.status)
        existing = self.measurements(check.id)
        if any(m.status != rules.PENDING or m.readings or m.attribute_result for m in existing):
            raise QualityError("MEASUREMENTS_STARTED")
        _product, lot_spec = self.lot(check)
        for key, value in (lot_values or {}).items():
            if rules.decimal(value) is None:
                raise QualityError("LOT_VALUE_INVALID", 400, key=key, value=str(value))
        effective = self._effective(check, lot_spec, lot_values)
        lines = self.specs.lines(spec.id)
        planned = []
        for line, parameter in lines:
            if parameter.kind == rules.NUMERIC:
                target, lower, upper = rules.resolve_limits({**{f: getattr(line, f) for f in ("target_source", "order_spec_key", "target_value",
                                                             "tolerance_minus", "tolerance_plus", "min_value", "max_value")},
                                                             "parameter_code": parameter.code}, effective)
            else:
                target = lower = upper = None
            planned.append(QualityCheckMeasurement(
                organization_id=self.org, quality_check_id=check.id, parameter_id=parameter.id, position=line.position,
                parameter_code=parameter.code, name_ar=parameter.name_ar, name_en=parameter.name_en, kind=parameter.kind, unit=parameter.unit,
                method=line.method or parameter.method, requirement=line.requirement, acceptance=line.acceptance,
                target=target, lower_limit=lower, upper_limit=upper, readings_required=line.readings_required or 1, status=rules.PENDING))
        for m in existing:
            self.db.delete(m)
        self.db.flush()
        self.db.add_all(planned)
        check.specification_id, check.specification_code, check.specification_revision = spec.id, spec.code, spec.revision
        # Keep only what the inspector supplied for values the lot lacks, as the lot's recorded values.
        used = {line.order_spec_key for line, _p in lines if line.target_source == rules.ORDER_LINE}
        supplied = {k: str(v) for k, v in effective.items() if k in used and rules.decimal(lot_spec.get(k)) is None}
        check.lot_values = supplied or None
        record(self.db, self.org, "check", check.id, "plan", check.status.value, check.status.value, self.tenant.user_id,
               detail=dict(specification=f"{spec.code} rev {spec.revision}"))
        if commit:
            self.db.commit()
        return planned

    def auto_apply(self, check: QualityCheck) -> None:
        """A new inspection takes its product's specification when exactly one is in force; otherwise the inspector chooses."""
        product, _spec = self.lot(check)
        candidates = self.specs.active_for(product) if product else []
        if len(candidates) == 1:
            try:
                self.apply(check, candidates[0].id, commit=False)
            except QualityError as exc:
                if exc.code != "LOT_SPEC_VALUE_MISSING":
                    raise
                # The lot lacks a value the specification takes from it: the inspector applies it and enters that value.

    def record(self, check: QualityCheck, measurement_id, data) -> QualityCheckMeasurement:
        check_rules.assert_editable(check.status)
        m = self.db.scalar(select(QualityCheckMeasurement).where(QualityCheckMeasurement.id == measurement_id,
                                                                 QualityCheckMeasurement.quality_check_id == check.id,
                                                                 QualityCheckMeasurement.organization_id == self.org).with_for_update())
        if m is None:
            raise QualityError("MEASUREMENT_NOT_FOUND", 404)
        if m.kind == rules.NUMERIC:
            readings = rules.parse_readings(data.readings)
            m.readings, m.attribute_result = [format(r, "f") for r in readings], None
        else:
            if data.attribute_result not in (rules.CONFORMING, rules.NONCONFORMING, None):
                raise QualityError("ATTRIBUTE_RESULT_INVALID", 400)
            readings, m.readings, m.attribute_result = [], None, data.attribute_result
        m.observation = (data.observation or "").strip() or None
        m.reading_count, m.minimum, m.maximum, m.mean, m.status = rules.evaluate(m.kind, readings, m.attribute_result, m.lower_limit,
                                                                                 m.upper_limit, m.readings_required)
        m.measured_at, m.measured_by_user_id = utc_now(), self.tenant.user_id
        self.db.commit()
        return m

    def assert_complete(self, check: QualityCheck, result) -> None:
        statuses = [m.status for m in self.measurements(check.id)]
        if statuses:
            rules.assert_plan_complete(statuses, result)


def as_text(value: Decimal | None):
    return None if value is None else format(value.normalize(), "f")
