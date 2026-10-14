"""Certificates of Analysis (QUAL-COA-001): the single writer of certificates and of their numbering.

A draft copies the inspection's established facts (result, specification, measurements) so the certificate never
changes with later edits elsewhere. Issuing numbers it from the organization's locked counter. A replacement is a
new draft that, once issued, revokes the certificate it supersedes.
"""
from __future__ import annotations

from datetime import timezone

from sqlalchemy import select

from app.core.interfaces import approvals
from app.core.pagination import paginate
from app.core.utils import utc_now
from app.quality.domain import certificates as rules
from app.quality.domain.rules import QualityError
from app.quality.infrastructure.models import QualityCertificate, QualityCheck, QualitySettings, QualitySpecification
from .measurement_service import MeasurementService
from .support import ProductionReads, as_decimal, history, log_activity, record, user_names

EDITABLE = ("customer_id", "customer_name", "customer_po", "delivery_ref", "batch_no", "product_description", "grade", "production_date",
            "inspection_date", "quantity", "unit_label", "package_count", "sample_size", "sampling_reference", "retained_sample",
            "retention_ref", "deviation_note", "remarks")


def text(value):
    return None if value is None else format(value.normalize(), "f")


class CertificateService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.production = ProductionReads(db, self.org)

    # ── settings ────────────────────────────────────────────────────────────────────────────────
    def settings(self, lock=False) -> QualitySettings:
        query = select(QualitySettings).where(QualitySettings.organization_id == self.org)
        settings = self.db.scalar(query.with_for_update() if lock else query)
        if settings is None:
            settings = QualitySettings(organization_id=self.org, coa_prefix=rules.DEFAULT_PREFIX, coa_last_number=0)
            self.db.add(settings)
            self.db.flush()
        return settings

    def update_settings(self, data) -> QualitySettings:
        settings = self.settings(lock=True)
        if data.coa_prefix is not None:
            settings.coa_prefix = data.coa_prefix
        if data.coa_last_number is not None:
            rules.assert_next_number(settings.coa_last_number, data.coa_last_number)
            settings.coa_last_number = data.coa_last_number
        self.db.commit()
        return settings

    # ── reads ───────────────────────────────────────────────────────────────────────────────────
    def _get(self, certificate_id, lock=False) -> QualityCertificate:
        query = select(QualityCertificate).where(QualityCertificate.id == certificate_id, QualityCertificate.organization_id == self.org)
        certificate = self.db.scalar(query.with_for_update() if lock else query)
        if certificate is None:
            raise QualityError("CERTIFICATE_NOT_FOUND", 404)
        return certificate

    def get(self, certificate_id) -> QualityCertificate:
        return self._get(certificate_id)

    def list(self, params, status=None, quality_check_id=None, production_order_id=None, search=None):
        """One page of certificates, newest first, and the total matching the filters (ARCH-PAGE-001)."""
        query = select(QualityCertificate).where(QualityCertificate.organization_id == self.org)
        for column, value in ((QualityCertificate.status, status), (QualityCertificate.quality_check_id, quality_check_id),
                              (QualityCertificate.production_order_id, production_order_id)):
            if value:
                query = query.where(column == value)
        if search:
            query = query.where(QualityCertificate.certificate_no.icontains(search, autoescape=True)
                                | QualityCertificate.customer_name.icontains(search, autoescape=True)
                                | QualityCertificate.batch_no.icontains(search, autoescape=True))
        return paginate(self.db, query.order_by(QualityCertificate.created_at.desc(), QualityCertificate.id.desc()), params)

    def views(self, certificates, can, detail=False) -> list[dict]:
        names = user_names(self.db, self.org, [u for c in certificates for u in (c.prepared_by_user_id, c.issued_by_user_id, c.revoked_by_user_id)])
        linked = {c.supersedes_id for c in certificates if c.supersedes_id} | {c.id for c in certificates}
        numbers = dict(self.db.execute(select(QualityCertificate.id, QualityCertificate.certificate_no).where(
            QualityCertificate.organization_id == self.org, QualityCertificate.id.in_(linked))).all()) if linked else {}
        replaced_by = dict(self.db.execute(select(QualityCertificate.supersedes_id, QualityCertificate.certificate_no).where(
            QualityCertificate.organization_id == self.org, QualityCertificate.supersedes_id.in_([c.id for c in certificates]),
            QualityCertificate.status == rules.ISSUED)).all()) if certificates else {}
        out = []
        for c in certificates:
            view = dict(prepared_by_name=names.get(c.prepared_by_user_id), issued_by_name=names.get(c.issued_by_user_id),
                        revoked_by_name=names.get(c.revoked_by_user_id), supersedes_no=numbers.get(c.supersedes_id),
                        superseded_by_no=replaced_by.get(c.id),
                        # A replacement's issue also revokes the original (RBAC-002).
                        actions=rules.actions(c.status, (lambda a, c=c: can(a) and (a != "issue" or not c.supersedes_id or can("revoke")))))
            if detail:
                view["history"] = history(self.db, self.org, "certificate", c.id)
            out.append(view)
        return out

    def sources(self, check_id) -> dict:
        """Whether a closed inspection can be certified, and the customers its lot was made for."""
        check = self._check(check_id)
        statuses = [m.status for m in MeasurementService(self.db, self.tenant).measurements(check.id)]
        try:
            rules.assert_certifiable(check.status.value, check.result.value if check.result else None, statuses)
            blocker = None
        except QualityError as exc:
            blocker = exc.code
        customers = self.production.customers(check.production_order_id, check.production_order_item_id) if check.production_order_id else []
        return dict(certifiable=blocker is None, blocker=blocker, customers=customers)

    def _check(self, check_id) -> QualityCheck:
        check = self.db.scalar(select(QualityCheck).where(QualityCheck.id == check_id, QualityCheck.organization_id == self.org))
        if check is None:
            raise QualityError("QUALITY_CHECK_NOT_FOUND", 404)
        return check

    # ── writes ──────────────────────────────────────────────────────────────────────────────────
    def create(self, data) -> QualityCertificate:
        check = self._check(data.quality_check_id)
        measurements = MeasurementService(self.db, self.tenant).measurements(check.id)
        rules.assert_certifiable(check.status.value, check.result.value if check.result else None, [m.status for m in measurements])
        customers = {c["id"]: c["name"] for c in self.production.customers(check.production_order_id, check.production_order_item_id)} if check.production_order_id else {}
        if data.customer_id and data.customer_id not in customers:
            raise QualityError("CUSTOMER_NOT_ON_LOT", 400)
        lot = self.production.lot_facts(check.production_order_id, check.production_order_item_id) if check.production_order_id else {}
        spec = self.db.get(QualitySpecification, check.specification_id) if check.specification_id else None
        batch = f"{lot['number']}-L{lot['line_no']}" if lot.get("line_no") else lot.get("number") or check.inspection_code
        completed = lot.get("completed_at")
        inspected = (check.closed_at or check.check_datetime)
        inspector = user_names(self.db, self.org, [check.checked_by_user_id]).get(check.checked_by_user_id)
        certificate = QualityCertificate(
            organization_id=self.org, status=rules.DRAFT, quality_check_id=check.id, production_order_id=check.production_order_id,
            production_order_item_id=check.production_order_item_id, customer_id=data.customer_id,
            customer_name=(customers.get(data.customer_id) if data.customer_id else None) or (next(iter(customers.values())) if len(customers) == 1 else ""),
            customer_po=data.customer_po, batch_no=batch,
            product_description=(spec.title if spec else None) or lot.get("product_type") or check.check_type.value,
            grade=spec.grade if spec else None,
            production_date=_day(completed) if completed else _day(check.check_datetime), inspection_date=_day(inspected),
            quantity=check.qty_accepted, unit_label=check.unit or "",
            sample_size=f"{text(check.qty_inspected)} {check.unit or ''}".strip(),
            inspection_code=check.inspection_code, inspection_result=check.result.value,
            specification_code=check.specification_code, specification_revision=check.specification_revision,
            measurements=[_frozen(m) for m in measurements], inspector_name=inspector, prepared_by_user_id=self.tenant.user_id)
        if certificate.customer_id is None and len(customers) == 1:
            certificate.customer_id = next(iter(customers))
        self.db.add(certificate)
        self.db.flush()
        record(self.db, self.org, "certificate", certificate.id, "create", None, rules.DRAFT, self.tenant.user_id, detail=dict(source=check.inspection_code))
        self.db.commit()
        return certificate

    def update(self, certificate_id, data) -> QualityCertificate:
        certificate = self._get(certificate_id, lock=True)
        rules.assert_draft(certificate.status)
        values = data.model_dump(exclude_unset=True)
        if "customer_id" in values and values["customer_id"]:
            check = self._check(certificate.quality_check_id)
            customers = {c["id"]: c["name"] for c in self.production.customers(check.production_order_id, check.production_order_item_id)} if check.production_order_id else {}
            if values["customer_id"] not in customers:
                raise QualityError("CUSTOMER_NOT_ON_LOT", 400)
            values.setdefault("customer_name", customers[values["customer_id"]])
        if "quantity" in values:
            check = self._check(certificate.quality_check_id)
            rules.assert_quantity(as_decimal(values["quantity"]), check.qty_accepted)
        for field in EDITABLE:
            if field in values:
                setattr(certificate, field, values[field])
        self.db.commit()
        return certificate

    def issue(self, certificate_id) -> QualityCertificate:
        certificate = self._get(certificate_id, lock=True)
        rules.assert_can_issue(certificate.status, certificate.customer_name, certificate.batch_no, certificate.inspection_result, certificate.deviation_note)
        settings = self.settings(lock=True)
        settings.coa_last_number += 1
        certificate.certificate_no = rules.number(settings.coa_prefix, settings.coa_last_number)
        certificate.status, certificate.issued_at, certificate.issued_by_user_id = rules.ISSUED, utc_now(), self.tenant.user_id
        approvals.sign(self.db, self.tenant, "quality_certificate", certificate.id, "issue", "quality:certificates:issue")
        record(self.db, self.org, "certificate", certificate.id, "issue", rules.DRAFT, rules.ISSUED, self.tenant.user_id,
               detail=dict(number=certificate.certificate_no))
        if certificate.supersedes_id:
            old = self._get(certificate.supersedes_id, lock=True)
            if old.status == rules.ISSUED:
                self._revoke(old, f"Superseded by {certificate.certificate_no}")
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_certificate.issued", "quality_certificate", certificate.id, certificate.certificate_no)
        return certificate

    def _revoke(self, certificate, reason):
        certificate.status, certificate.revoked_at, certificate.revoked_by_user_id, certificate.revoke_reason = rules.REVOKED, utc_now(), self.tenant.user_id, reason
        record(self.db, self.org, "certificate", certificate.id, "revoke", rules.ISSUED, rules.REVOKED, self.tenant.user_id, reason=reason)

    def revoke(self, certificate_id, reason) -> QualityCertificate:
        certificate = self._get(certificate_id, lock=True)
        rules.assert_can_revoke(certificate.status, reason)
        self._revoke(certificate, reason.strip())
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_certificate.revoked", "quality_certificate", certificate.id, certificate.certificate_no)
        return certificate

    def replace(self, certificate_id) -> QualityCertificate:
        """A new draft with the same content, to correct an issued certificate; issuing it revokes the old one."""
        old = self._get(certificate_id, lock=True)
        if old.status != rules.ISSUED:
            raise QualityError("CERTIFICATE_NOT_ISSUED", certificate_status=old.status)
        if self.db.scalar(select(QualityCertificate.id).where(QualityCertificate.organization_id == self.org, QualityCertificate.supersedes_id == old.id,
                                                              QualityCertificate.status == rules.DRAFT)):
            raise QualityError("REPLACEMENT_DRAFT_EXISTS")
        copy = QualityCertificate(organization_id=self.org, status=rules.DRAFT, supersedes_id=old.id, prepared_by_user_id=self.tenant.user_id,
                                  **{f: getattr(old, f) for f in (*EDITABLE, "quality_check_id", "production_order_id", "production_order_item_id",
                                                                  "inspection_code", "inspection_result", "specification_code",
                                                                  "specification_revision", "measurements", "inspector_name")})
        self.db.add(copy)
        self.db.flush()
        record(self.db, self.org, "certificate", copy.id, "create", None, rules.DRAFT, self.tenant.user_id, detail=dict(supersedes=old.certificate_no))
        self.db.commit()
        return copy


def _day(value):
    value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return value.date()


def _frozen(m) -> dict:
    return dict(code=m.parameter_code, name_ar=m.name_ar, name_en=m.name_en, kind=m.kind, unit=m.unit, method=m.method,
                requirement=m.requirement, acceptance=m.acceptance, target=text(m.target), lower=text(m.lower_limit), upper=text(m.upper_limit),
                count=m.reading_count, minimum=text(m.minimum), maximum=text(m.maximum), mean=text(m.mean),
                attribute_result=m.attribute_result, observation=m.observation, status=m.status)
