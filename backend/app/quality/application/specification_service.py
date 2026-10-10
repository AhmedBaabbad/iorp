"""Test parameters and product specifications (QUAL-SPEC-001): the single writer of both.

A specification revision is edited only while a draft; activating it supersedes the revision in force with the
same code. Changing a specification in force means revising it: a new draft copying its lines, revision + 1.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.utils import utc_now
from app.core.interfaces.product_catalog import unknown_product_types
from app.quality.domain import specifications as rules
from app.quality.domain.rules import QualityError
from app.quality.infrastructure.models import QualitySpecification, QualitySpecificationLine, QualityTestParameter
from .support import log_activity, user_names

LINE_FIELDS = ("target_source", "order_spec_key", "target_value", "tolerance_minus", "tolerance_plus", "min_value", "max_value",
               "requirement", "acceptance", "method", "readings_required")


class SpecificationService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    # ── test parameters ─────────────────────────────────────────────────────────────────────────
    def parameters(self, active_only=False):
        query = select(QualityTestParameter).where(QualityTestParameter.organization_id == self.org)
        if active_only:
            query = query.where(QualityTestParameter.is_active.is_(True))
        return list(self.db.scalars(query.order_by(QualityTestParameter.sort_order, QualityTestParameter.code)))

    def _parameter(self, parameter_id) -> QualityTestParameter:
        parameter = self.db.scalar(select(QualityTestParameter).where(QualityTestParameter.id == parameter_id,
                                                                      QualityTestParameter.organization_id == self.org))
        if parameter is None:
            raise QualityError("PARAMETER_NOT_FOUND", 404)
        return parameter

    def create_parameter(self, data) -> QualityTestParameter:
        code = data.code.strip().upper()
        if self.db.scalar(select(QualityTestParameter.id).where(QualityTestParameter.organization_id == self.org, QualityTestParameter.code == code)):
            raise QualityError("PARAMETER_CODE_TAKEN", parameter_code=code)
        parameter = QualityTestParameter(organization_id=self.org, code=code, name_ar=data.name_ar, name_en=data.name_en, kind=data.kind,
                                         unit=data.unit if data.kind == rules.NUMERIC else None, method=data.method,
                                         sort_order=data.sort_order, is_active=True)
        self.db.add(parameter)
        self.db.commit()
        return parameter

    def update_parameter(self, parameter_id, data) -> QualityTestParameter:
        parameter = self._parameter(parameter_id)
        values = data.model_dump(exclude_unset=True)
        # The kind decides how a parameter is measured; specifications and inspections already rely on it.
        for field in ("name_ar", "name_en", "unit", "method", "is_active", "sort_order"):
            if field in values:
                setattr(parameter, field, values[field] if not (field == "unit" and parameter.kind != rules.NUMERIC) else None)
        self.db.commit()
        return parameter

    def add_standard_parameters(self) -> list[QualityTestParameter]:
        """The strapping-band parameters, added once; existing codes are left as the organization edited them."""
        existing = set(self.db.scalars(select(QualityTestParameter.code).where(QualityTestParameter.organization_id == self.org)))
        for order, (code, name_ar, name_en, kind, unit, method) in enumerate(rules.STANDARD_PARAMETERS, 1):
            if code not in existing:
                self.db.add(QualityTestParameter(organization_id=self.org, code=code, name_ar=name_ar, name_en=name_en, kind=kind,
                                                 unit=unit, method=method, sort_order=order * 10, is_active=True))
        self.db.commit()
        return self.parameters()

    # ── specifications ──────────────────────────────────────────────────────────────────────────
    def _get(self, spec_id, lock=False) -> QualitySpecification:
        query = select(QualitySpecification).where(QualitySpecification.id == spec_id, QualitySpecification.organization_id == self.org)
        spec = self.db.scalar(query.with_for_update() if lock else query)
        if spec is None:
            raise QualityError("SPECIFICATION_NOT_FOUND", 404)
        return spec

    def get(self, spec_id) -> QualitySpecification:
        return self._get(spec_id)

    def list(self, status=None, product_type=None, search=None):
        query = select(QualitySpecification).where(QualitySpecification.organization_id == self.org)
        if status:
            query = query.where(QualitySpecification.status == status)
        if product_type:
            query = query.where(QualitySpecification.product_type == product_type)
        if search:
            query = query.where(QualitySpecification.code.icontains(search, autoescape=True) | QualitySpecification.title.icontains(search, autoescape=True))
        return list(self.db.scalars(query.order_by(QualitySpecification.code, QualitySpecification.revision.desc()).limit(500)))

    def active_for(self, product_type) -> list[QualitySpecification]:
        return list(self.db.scalars(select(QualitySpecification).where(
            QualitySpecification.organization_id == self.org, QualitySpecification.status == rules.ACTIVE,
            func.lower(QualitySpecification.product_type) == (product_type or "").lower()).order_by(QualitySpecification.code)))

    def lines(self, spec_id) -> list[tuple[QualitySpecificationLine, QualityTestParameter]]:
        return list(self.db.execute(select(QualitySpecificationLine, QualityTestParameter)
                                    .join(QualityTestParameter, QualityTestParameter.id == QualitySpecificationLine.parameter_id)
                                    .where(QualitySpecificationLine.specification_id == spec_id)
                                    .order_by(QualitySpecificationLine.position, QualityTestParameter.sort_order)).all())

    def view(self, spec, detail=False, can=lambda _code: False) -> dict:
        names = user_names(self.db, self.org, [spec.created_by_user_id, spec.activated_by_user_id])
        actions = [a for a, ok in (("edit", spec.status == rules.DRAFT and can("update")), ("activate", spec.status == rules.DRAFT and can("activate")),
                                   ("revise", spec.status != rules.DRAFT and can("create"))) if ok]
        view = dict(created_by_name=names.get(spec.created_by_user_id), activated_by_name=names.get(spec.activated_by_user_id), actions=actions)
        if detail:
            view["lines"] = [dict({f: getattr(line, f) for f in LINE_FIELDS}, id=line.id, position=line.position, parameter_id=p.id,
                                  parameter_code=p.code, name_ar=p.name_ar, name_en=p.name_en, kind=p.kind, unit=p.unit,
                                  parameter_method=p.method) for line, p in self.lines(spec.id)]
        return view

    def _write_lines(self, spec, lines):
        parameters = {p.id: p for p in self.parameters()}
        seen = set()
        self.db.query(QualitySpecificationLine).filter(QualitySpecificationLine.specification_id == spec.id).delete()
        for position, line in enumerate(lines, 1):
            parameter = parameters.get(line.parameter_id)
            if parameter is None:
                raise QualityError("PARAMETER_NOT_FOUND", 404)
            if parameter.id in seen:
                raise QualityError("PARAMETER_REPEATED", 400, parameter=parameter.code)
            seen.add(parameter.id)
            values = {f: getattr(line, f) for f in LINE_FIELDS}
            if parameter.kind == rules.ATTRIBUTE:
                values.update(target_source=rules.NO_TARGET, order_spec_key=None, target_value=None, tolerance_minus=None, tolerance_plus=None,
                              min_value=None, max_value=None, readings_required=1)
            rules.assert_line(parameter.kind, dict(values, parameter_code=parameter.code))
            self.db.add(QualitySpecificationLine(specification_id=spec.id, parameter_id=parameter.id, position=position, **values))

    def _assert_product(self, product_type, keep=None):
        """MD-001: the product comes from the organization's products (asked through core); the one already stored may stay."""
        if unknown_product_types(self.db, self.org, [product_type], [keep] if keep else ()):
            raise QualityError("PRODUCT_TYPE_UNKNOWN", 400, product_type=product_type)

    def create(self, data) -> QualitySpecification:
        code = data.code.strip().upper()
        self._assert_product(data.product_type)
        if self.db.scalar(select(QualitySpecification.id).where(QualitySpecification.organization_id == self.org, QualitySpecification.code == code)):
            raise QualityError("SPECIFICATION_CODE_TAKEN", spec_code=code)
        spec = QualitySpecification(organization_id=self.org, code=code, revision=1, title=data.title, product_type=data.product_type,
                                    grade=data.grade, notes=data.notes, status=rules.DRAFT, created_by_user_id=self.tenant.user_id)
        self.db.add(spec)
        self.db.flush()
        self._write_lines(spec, data.lines)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_specification.created", "quality_specification", spec.id, f"{code} rev {spec.revision}")
        return spec

    def update(self, spec_id, data) -> QualitySpecification:
        spec = self._get(spec_id, lock=True)
        rules.assert_draft(spec.status)
        values = data.model_dump(exclude_unset=True)
        if values.get("product_type"):
            self._assert_product(values["product_type"], keep=spec.product_type)
        for field in ("title", "product_type", "grade", "notes"):
            if field in values:
                setattr(spec, field, values[field])
        if data.lines is not None:
            self._write_lines(spec, data.lines)
        self.db.commit()
        return spec

    def activate(self, spec_id) -> QualitySpecification:
        spec = self._get(spec_id, lock=True)
        count = self.db.scalar(select(func.count()).select_from(QualitySpecificationLine).where(QualitySpecificationLine.specification_id == spec.id))
        rules.assert_can_activate(spec.status, count)
        for current in self.db.scalars(select(QualitySpecification).where(
                QualitySpecification.organization_id == self.org, QualitySpecification.code == spec.code,
                QualitySpecification.status == rules.ACTIVE).with_for_update()):
            current.status = rules.SUPERSEDED
        self.db.flush()  # the revision in force steps aside before this one takes its place (one active per code)
        spec.status, spec.activated_at, spec.activated_by_user_id = rules.ACTIVE, utc_now(), self.tenant.user_id
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_specification.activated", "quality_specification", spec.id, f"{spec.code} rev {spec.revision}")
        return spec

    def revise(self, spec_id) -> QualitySpecification:
        source = self._get(spec_id, lock=True)
        if source.status == rules.DRAFT:
            raise QualityError("SPECIFICATION_IS_DRAFT")
        if self.db.scalar(select(QualitySpecification.id).where(QualitySpecification.organization_id == self.org, QualitySpecification.code == source.code,
                                                                QualitySpecification.status == rules.DRAFT)):
            raise QualityError("SPECIFICATION_DRAFT_EXISTS", spec_code=source.code)
        latest = self.db.scalar(select(func.max(QualitySpecification.revision)).where(QualitySpecification.organization_id == self.org,
                                                                                      QualitySpecification.code == source.code))
        draft = QualitySpecification(organization_id=self.org, code=source.code, revision=latest + 1, title=source.title, product_type=source.product_type,
                                     grade=source.grade, notes=source.notes, status=rules.DRAFT, created_by_user_id=self.tenant.user_id)
        self.db.add(draft)
        self.db.flush()
        for line, _parameter in self.lines(source.id):
            self.db.add(QualitySpecificationLine(specification_id=draft.id, parameter_id=line.parameter_id, position=line.position,
                                                 **{f: getattr(line, f) for f in LINE_FIELDS}))
        self.db.commit()
        return draft
