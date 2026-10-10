"""Non-conformance reports (QUAL-NCR-002): the single writer of a report, its items, corrective actions and files.

open ─contain→ investigation ─investigate→ action ─submit→ verification ─verify→ closed (or back to action), a minor
case closed from the investigation with a justification, any stage cancelled with a reason (domain/ncr.py). Every step
writes the quality history and the activity log. Sources and names in other modules are read through the shared tables.

Follow-up (QUAL-CAPA-001): the earlier reports a report repeats, the later review of a closed one's effectiveness, what
needs each person's attention, and an email to whoever is given an action.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import func, or_, select

from app.core.storage import InvalidAttachmentError, LocalFileStorage, save_attachment, compensate_new_file
from app.core.utils import utc_now
from app.quality.domain import ncr as N
from app.quality.domain.permissions import NCR_ACTIONS, NCR_ACTIONS_COMPLETE, NCR_VERIFY
from app.quality.domain.rules import QualityError
from app.quality.infrastructure.models import NCRAction, NCRAttachment, NonConformanceItem, NonConformanceReport, QualityCheck, QualityRejection
from . import capa_notices
from .support import ProcurementReads, ProductionReads, ShippingReads, _t, history, log_activity, next_code, record, user_names

logger = logging.getLogger(__name__)

HEADER = ("report_date", "source_type", "report_type", "severity", "title", "description", "reference_code", "quality_check_id",
          "quality_rejection_id", "production_order_id", "customer_name", "supplier_id", "supplier_name", "supplier_reference", "owner_user_id",
          "due_date", "supplier_action", "supplier_response", "supplier_responded_at", *N.COSTS, "claim_amount", "claim_status")
ITEM = ("item_reference", "item_name", "quantity_affected", "unit", "issue_description", "disposition", "disposition_notes", "notes")
MAX_FILES = 20


class NCRService:
    def __init__(self, db, tenant, storage: LocalFileStorage | None = None):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.storage = storage

    # ── reads ──────────────────────────────────────────────────────────────────────────────────
    def _get(self, report_id, lock=False) -> NonConformanceReport:
        query = select(NonConformanceReport).where(NonConformanceReport.id == report_id, NonConformanceReport.organization_id == self.org)
        report = self.db.scalar(query.with_for_update() if lock else query)
        if report is None:
            raise QualityError("NCR_NOT_FOUND", 404)
        return report

    def get(self, report_id) -> NonConformanceReport:
        return self._get(report_id)

    def list(self, *, status=None, source_type=None, severity=None, owner_user_id=None, open_only=False, date_from=None, date_to=None,
             search=None, limit=500):
        query = select(NonConformanceReport).where(NonConformanceReport.organization_id == self.org)
        for column, value in ((NonConformanceReport.status, status), (NonConformanceReport.source_type, source_type),
                              (NonConformanceReport.severity, severity), (NonConformanceReport.owner_user_id, owner_user_id)):
            if value:
                query = query.where(column == value)
        if open_only:
            query = query.where(NonConformanceReport.status.notin_(N.FINAL))
        if date_from:
            query = query.where(NonConformanceReport.report_date >= date_from)
        if date_to:
            query = query.where(NonConformanceReport.report_date <= date_to)
        if search:
            like = lambda column: column.icontains(search, autoescape=True)  # noqa: E731
            query = query.where(or_(like(NonConformanceReport.report_number), like(NonConformanceReport.title),
                                    like(NonConformanceReport.reference_code), like(NonConformanceReport.supplier_name),
                                    like(NonConformanceReport.customer_name)))
        return list(self.db.scalars(query.order_by(NonConformanceReport.report_date.desc(), NonConformanceReport.created_at.desc()).limit(limit)))

    def _actions_of(self, report_ids) -> dict:
        out = {i: [] for i in report_ids}
        if report_ids:
            for a in self.db.scalars(select(NCRAction).where(NCRAction.organization_id == self.org, NCRAction.ncr_id.in_(report_ids))
                                     .order_by(NCRAction.line_no)):
                out[a.ncr_id].append(a)
        return out

    def action_view(self, a, names, today, report=None) -> dict:
        view = dict(id=a.id, ncr_id=a.ncr_id, line_no=a.line_no, kind=a.kind, description=a.description, owner_user_id=a.owner_user_id,
                    owner_name=names.get(a.owner_user_id) or a.owner_name, due_date=a.due_date, status=a.status, evidence=a.evidence,
                    completed_at=a.completed_at, completed_by_name=names.get(a.completed_by_user_id), cancel_reason=a.cancel_reason,
                    overdue=N.is_overdue(a, today))
        if report is not None:
            view.update(report_number=report.report_number, report_title=report.title, report_status=report.status)
        return view

    def views(self, reports, can, detail=False) -> list[dict]:
        ids = [r.id for r in reports]
        actions = self._actions_of(ids)
        people = [u for r in reports for u in (r.owner_user_id, r.detected_by_user_id, r.contained_by_user_id, r.investigated_by_user_id,
                                               r.verified_by_user_id, r.effectiveness_reviewed_by_user_id)]
        people += [u for found in actions.values() for a in found for u in (a.owner_user_id, a.completed_by_user_id)]
        names = user_names(self.db, self.org, people)
        orders = ProductionReads(self.db, self.org).numbers([r.production_order_id for r in reports])
        returns = ShippingReads(self.db, self.org).return_numbers([r.return_id for r in reports])
        checks = dict(self.db.execute(select(QualityCheck.id, QualityCheck.inspection_code).where(
            QualityCheck.organization_id == self.org, QualityCheck.id.in_([r.quality_check_id for r in reports if r.quality_check_id]))).all())
        rejections = dict(self.db.execute(select(QualityRejection.id, QualityRejection.rejection_code).where(
            QualityRejection.organization_id == self.org, QualityRejection.id.in_([r.quality_rejection_id for r in reports if r.quality_rejection_id]))).all())
        today = utc_now().date()
        out = []
        for r in reports:
            mine = actions[r.id]
            view = dict(owner_name=names.get(r.owner_user_id), detected_by_name=names.get(r.detected_by_user_id),
                        order_number=orders.get(r.production_order_id), return_no=returns.get(r.return_id),
                        inspection_code=checks.get(r.quality_check_id), rejection_code=rejections.get(r.quality_rejection_id),
                        total_cost=N.total_cost(r), open_actions=sum(1 for a in mine if a.status == N.ACTION_OPEN),
                        overdue_actions=sum(1 for a in mine if N.is_overdue(a, today)),
                        overdue=r.status not in N.FINAL and r.due_date is not None and r.due_date < today,
                        review_pending=N.review_pending(r), review_due=N.review_due(r, today),
                        actions=N.actions(r.status, lambda a: can(NCR_ACTIONS[a]), N.review_pending(r)))
            if detail:
                view.update(contained_by_name=names.get(r.contained_by_user_id), investigated_by_name=names.get(r.investigated_by_user_id),
                            verified_by_name=names.get(r.verified_by_user_id), items=self.items(r.id),
                            effectiveness_reviewed_by_name=names.get(r.effectiveness_reviewed_by_user_id), recurrence=self.recurrence(r),
                            corrective_actions=[self.action_view(a, names, today) for a in mine],
                            attachments=self.attachments(r.id), history=history(self.db, self.org, "ncr", r.id),
                            can_complete_actions=can_complete(can) and r.status not in N.FINAL)
            out.append(view)
        return out

    def items(self, report_id) -> list[NonConformanceItem]:
        return list(self.db.scalars(select(NonConformanceItem).where(NonConformanceItem.non_conformance_report_id == report_id)
                                    .order_by(NonConformanceItem.line_no)))

    def attachments(self, report_id) -> list[dict]:
        rows = list(self.db.scalars(select(NCRAttachment).where(NCRAttachment.organization_id == self.org, NCRAttachment.ncr_id == report_id)
                                    .order_by(NCRAttachment.uploaded_at)))
        names = user_names(self.db, self.org, [r.uploaded_by_user_id for r in rows])
        return [dict(id=r.id, file_name=r.file_name, content_type=r.content_type, size_bytes=r.size_bytes,
                     uploaded_by_name=names.get(r.uploaded_by_user_id), uploaded_at=r.uploaded_at) for r in rows]

    def all_actions(self, *, status=None, owner_user_id=None, overdue=False, search=None, limit=500) -> list[dict]:
        """Corrective actions across reports (the CAPA list)."""
        query = (select(NCRAction, NonConformanceReport).join(NonConformanceReport, NonConformanceReport.id == NCRAction.ncr_id)
                 .where(NCRAction.organization_id == self.org))
        if status:
            query = query.where(NCRAction.status == status)
        if owner_user_id:
            query = query.where(NCRAction.owner_user_id == owner_user_id)
        if overdue:
            query = query.where(NCRAction.status == N.ACTION_OPEN, NCRAction.due_date < utc_now().date())
        if search:
            query = query.where(or_(NCRAction.description.icontains(search, autoescape=True),
                                    NonConformanceReport.report_number.icontains(search, autoescape=True)))
        rows = self.db.execute(query.order_by(NCRAction.due_date.is_(None), NCRAction.due_date, NonConformanceReport.report_number).limit(limit)).all()
        names = user_names(self.db, self.org, [u for a, _r in rows for u in (a.owner_user_id, a.completed_by_user_id)])
        today = utc_now().date()
        return [self.action_view(a, names, today, report) for a, report in rows]

    def _basis(self, report, category=None) -> dict:
        names = self.db.scalars(select(NonConformanceItem.item_name).where(NonConformanceItem.non_conformance_report_id == report.id)).all()
        return N.basis(report.supplier_id, report.report_type, category or report.root_cause_category, names)

    def recurrence(self, report, category=None) -> dict:
        """The reports this one repeats (within the window before it) and those that came after it, matched on the same
        supplier, an affected item of the same name, or the same kind with the same 6M cause. Cancelled reports do not count."""
        this = self._basis(report, category)
        clauses = []
        if this["supplier"]:
            clauses.append(NonConformanceReport.supplier_id == this["supplier"])
        if this["items"]:
            clauses.append(NonConformanceReport.id.in_(select(NonConformanceItem.non_conformance_report_id).where(
                func.lower(func.trim(NonConformanceItem.item_name)).in_(list(this["items"])))))
        if this["category"]:
            clauses.append((NonConformanceReport.report_type == report.report_type) & (NonConformanceReport.root_cause_category == this["category"]))
        found = []
        if clauses:
            found = list(self.db.scalars(select(NonConformanceReport).where(
                NonConformanceReport.organization_id == self.org, NonConformanceReport.id != report.id,
                NonConformanceReport.status != N.CANCELLED, NonConformanceReport.report_date >= report.report_date - timedelta(days=N.RECURRENCE_DAYS),
                or_(*clauses)).order_by(NonConformanceReport.report_date.desc(), NonConformanceReport.created_at.desc()).limit(50)))
        related, earlier, since_closing = [], 0, 0
        for other in found:
            matched = N.matched_on(this, self._basis(other))
            if not matched:  # SQL lower() and Python casefold() may differ on some letters
                continue
            before = (other.report_date, other.created_at) < (report.report_date, report.created_at)
            earlier += before
            since_closing += bool(report.closed_at and other.created_at > report.closed_at)
            related.append(dict(id=other.id, report_number=other.report_number, report_date=other.report_date, title=other.title,
                                status=other.status, severity=other.severity, matched_on=matched, earlier=before))
        return dict(window_days=N.RECURRENCE_DAYS, earlier=earlier, since_closing=since_closing, recurring=N.is_recurring(earlier), related=related)

    def alerts(self, can) -> dict:
        """What needs this user's attention: their open actions late or due soon, their reports past due, and (for whoever
        verifies) effectiveness reviews that are due."""
        today, me = utc_now().date(), self.tenant.user_id
        rows = self.db.execute(select(NCRAction, NonConformanceReport).join(NonConformanceReport, NonConformanceReport.id == NCRAction.ncr_id).where(
            NCRAction.organization_id == self.org, NCRAction.owner_user_id == me, NCRAction.status == N.ACTION_OPEN,
            NonConformanceReport.status.notin_(N.FINAL))).all()
        items = []
        for action, report in rows:
            kind = "overdue" if N.is_overdue(action, today) else "due_soon" if N.due_soon(action, today) else None
            if kind:
                items.append(dict(kind=kind, ncr_id=report.id, report_number=report.report_number, title=action.description, due_date=action.due_date))
        for report in self.db.scalars(select(NonConformanceReport).where(
                NonConformanceReport.organization_id == self.org, NonConformanceReport.owner_user_id == me,
                NonConformanceReport.status.notin_(N.FINAL), NonConformanceReport.due_date < today)):
            items.append(dict(kind="report_overdue", ncr_id=report.id, report_number=report.report_number, title=report.title, due_date=report.due_date))
        if can(NCR_VERIFY):
            for report in self.db.scalars(select(NonConformanceReport).where(
                    NonConformanceReport.organization_id == self.org, NonConformanceReport.status == N.CLOSED,
                    NonConformanceReport.effectiveness_result.is_(None), NonConformanceReport.effectiveness_due_date <= today)):
                items.append(dict(kind="review_due", ncr_id=report.id, report_number=report.report_number, title=report.title,
                                  due_date=report.effectiveness_due_date))
        order = {"overdue": 0, "report_overdue": 1, "review_due": 2, "due_soon": 3}
        items.sort(key=lambda i: (order[i["kind"]], i["due_date"]))
        counts = {k: sum(1 for i in items if i["kind"] == k) for k in order}
        return dict(total=len(items), open_actions=len(rows), **counts, items=items[:50])

    def supplier_options(self, search="") -> list[dict]:
        return ProcurementReads(self.db, self.org).search(search)

    def user_options(self, search="") -> list[dict]:
        users = _t("foundation_users")
        query = select(users.c.id, users.c.full_name).where(users.c.organization_id == self.org)
        if search:
            query = query.where(users.c.full_name.icontains(search, autoescape=True))
        return [dict(id=r.id, name=r.full_name) for r in self.db.execute(query.order_by(users.c.full_name).limit(50)).all()]

    # ── writes ─────────────────────────────────────────────────────────────────────────────────
    def _commit(self, report, action, before=None, reason=None, detail=None):
        record(self.db, self.org, "ncr", report.id, action, before, report.status, self.tenant.user_id, reason=reason, detail=detail)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, f"ncr_report.{action}", "ncr_report", report.id, report.report_number)
        return self._get(report.id)

    def _validate(self, values: dict):
        for field, allowed, code in (("severity", N.SEVERITIES, "SEVERITY_UNKNOWN"), ("supplier_action", N.SUPPLIER_ACTIONS, "SUPPLIER_ACTION_UNKNOWN"),
                                     ("claim_status", N.CLAIM_STATUSES, "CLAIM_STATUS_UNKNOWN")):
            if values.get(field) is not None and values[field] not in allowed:
                raise QualityError(code, 400)
        if values.get("owner_user_id") and not user_names(self.db, self.org, [values["owner_user_id"]]):
            raise QualityError("USER_NOT_FOUND", 404)
        if values.get("quality_check_id") and not self.db.scalar(select(QualityCheck.id).where(
                QualityCheck.organization_id == self.org, QualityCheck.id == values["quality_check_id"])):
            raise QualityError("QUALITY_CHECK_NOT_FOUND", 404)
        if values.get("quality_rejection_id") and not self.db.scalar(select(QualityRejection.id).where(
                QualityRejection.organization_id == self.org, QualityRejection.id == values["quality_rejection_id"])):
            raise QualityError("QUALITY_REJECTION_NOT_FOUND", 404)
        if values.get("production_order_id") and not ProductionReads(self.db, self.org).numbers([values["production_order_id"]]):
            raise QualityError("PRODUCTION_ORDER_NOT_FOUND", 404)
        if values.get("supplier_id"):  # a registered supplier: its name is kept as printed
            supplier = ProcurementReads(self.db, self.org).supplier(values["supplier_id"])
            if supplier is None:
                raise QualityError("SUPPLIER_NOT_FOUND", 404)
            values["supplier_name"] = supplier["name"]

    def open_report(self, *, source_type, report_type, title, description, severity="major", items=(), **refs) -> NonConformanceReport:
        """A new report (also opened by other quality flows, e.g. a customer return's decision). The caller commits."""
        values = dict(report_date=utc_now().date(), supplier_action="none", claim_status="none")
        values.update({k: v for k, v in refs.items() if v is not None})
        report = NonConformanceReport(organization_id=self.org, report_number=next_code(self.db, self.org, "NCR"), source_type=source_type,
                                      report_type=report_type, status=N.OPEN, severity=severity or "major", title=title, description=description,
                                      detected_by_user_id=self.tenant.user_id, verification_attempts=0, **values)
        self.db.add(report)
        self.db.flush()
        for number, item in enumerate(items, 1):
            self.db.add(NonConformanceItem(non_conformance_report_id=report.id, line_no=number, **item))
        record(self.db, self.org, "ncr", report.id, "create", None, N.OPEN, self.tenant.user_id)
        return report

    def create(self, data) -> NonConformanceReport:
        values = data.model_dump(exclude={"items"})
        self._validate(values)
        report = self.open_report(**values, items=[item.model_dump() for item in data.items])
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "ncr_report.created", "ncr_report", report.id, report.report_number)
        return self._get(report.id)

    def update(self, report_id, data) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        N.assert_editable(report.status)
        values = data.model_dump(exclude_unset=True)
        self._validate(values)
        for field in HEADER:
            if field in values and not (field in ("source_type", "report_type", "severity", "title", "description", "report_date",
                                                  "supplier_action", "claim_status") and values[field] is None):
                setattr(report, field, values[field])
        return self._commit(report, "update", report.status, detail={k: str(v) for k, v in values.items()})

    # items
    def add_item(self, report_id, data) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        N.assert_editable(report.status)
        line_no = (self.db.scalar(select(func.max(NonConformanceItem.line_no)).where(NonConformanceItem.non_conformance_report_id == report.id)) or 0) + 1
        self.db.add(NonConformanceItem(non_conformance_report_id=report.id, line_no=line_no, **data.model_dump()))
        return self._commit(report, "item_added", report.status)

    def _item(self, report, item_id) -> NonConformanceItem:
        item = self.db.scalar(select(NonConformanceItem).where(NonConformanceItem.id == item_id, NonConformanceItem.non_conformance_report_id == report.id))
        if item is None:
            raise QualityError("NCR_ITEM_NOT_FOUND", 404)
        return item

    def update_item(self, report_id, item_id, data) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        N.assert_editable(report.status)
        item = self._item(report, item_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            if not (field in ("item_name", "issue_description") and value is None):
                setattr(item, field, value)
        return self._commit(report, "item_updated", report.status)

    def remove_item(self, report_id, item_id) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        N.assert_editable(report.status)
        self.db.delete(self._item(report, item_id))
        return self._commit(report, "item_removed", report.status)

    # stages
    def contain(self, report_id, containment) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        N.assert_can_contain(report.status, containment)
        report.containment, report.contained_at, report.contained_by_user_id = containment.strip(), utc_now(), self.tenant.user_id
        report.status = N.INVESTIGATION
        return self._commit(report, "contain", N.OPEN, reason=report.containment)

    def investigate(self, report_id, data) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        recurring = not data.action_required and self.recurrence(report, data.root_cause_category)["recurring"]
        N.assert_can_investigate(report.status, data.root_cause_category, data.root_cause, data.action_required, data.no_action_justification,
                                 recurring)
        if data.root_cause_method is not None and data.root_cause_method not in N.ROOT_CAUSE_METHODS:
            raise QualityError("ROOT_CAUSE_METHOD_UNKNOWN", 400)
        report.root_cause_category, report.root_cause_method, report.root_cause = data.root_cause_category, data.root_cause_method, data.root_cause.strip()
        report.action_required, report.investigated_at, report.investigated_by_user_id = data.action_required, utc_now(), self.tenant.user_id
        if data.action_required:
            report.status, report.no_action_justification = N.ACTION, None
        else:  # a minor, isolated case: closed with the reason no corrective action is needed
            report.no_action_justification = data.no_action_justification.strip()
            report.status, report.closed_at = N.CLOSED, utc_now()
        return self._commit(report, "investigate", N.INVESTIGATION, reason=report.no_action_justification or report.root_cause)

    def submit(self, report_id) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        N.assert_can_submit(report.status, [a.status for a in self._actions_of([report.id])[report.id]])
        report.status = N.VERIFICATION
        return self._commit(report, "submit", N.ACTION)

    def verify(self, report_id, effective, notes, review_days=0) -> NonConformanceReport:
        """Effective: closed, and reviewed again after review_days (0: no later review). Not effective: back to the actions."""
        report = self._get(report_id, lock=True)
        N.assert_can_verify(report.status, effective, notes)
        report.verification_attempts += 1
        report.verification_notes, report.verified_at, report.verified_by_user_id = (notes or "").strip() or None, utc_now(), self.tenant.user_id
        report.status = N.CLOSED if effective else N.ACTION
        if effective:
            report.closed_at = utc_now()
            report.effectiveness_due_date = report.closed_at.date() + timedelta(days=review_days) if review_days else None
            report.effectiveness_result = report.effectiveness_notes = report.effectiveness_reviewed_at = report.effectiveness_reviewed_by_user_id = None
        return self._commit(report, "verify", N.VERIFICATION, reason=report.verification_notes,
                            detail=dict(effective=str(bool(effective)), review_days=str(review_days if effective else 0)))

    def review_effectiveness(self, report_id, effective, notes) -> NonConformanceReport:
        """The later review of a closed report: the problem did not come back (effective), or it did and the report reopens
        to its corrective actions."""
        report = self._get(report_id, lock=True)
        N.assert_can_review(report, effective, notes)
        report.effectiveness_result = N.EFFECTIVE if effective else N.NOT_EFFECTIVE
        report.effectiveness_notes = (notes or "").strip() or None
        report.effectiveness_reviewed_at, report.effectiveness_reviewed_by_user_id = utc_now(), self.tenant.user_id
        if not effective:
            report.status, report.closed_at = N.ACTION, None
        return self._commit(report, "effectiveness_review", N.CLOSED, reason=report.effectiveness_notes, detail=dict(effective=str(bool(effective))))

    def cancel(self, report_id, reason) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        N.assert_can_cancel(report.status, reason)
        before = report.status
        report.status, report.cancel_reason = N.CANCELLED, reason.strip()
        return self._commit(report, "cancel", before, reason=report.cancel_reason)

    # corrective actions
    def _action(self, report, action_id, lock=True) -> NCRAction:
        query = select(NCRAction).where(NCRAction.id == action_id, NCRAction.ncr_id == report.id, NCRAction.organization_id == self.org)
        action = self.db.scalar(query.with_for_update() if lock else query)
        if action is None:
            raise QualityError("ACTION_NOT_FOUND", 404)
        return action

    def add_action(self, report_id, data) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        if report.status not in (N.INVESTIGATION, N.ACTION):
            raise QualityError("NCR_NOT_IN_ACTION", ncr_status=report.status)
        N.assert_action_kind(data.kind)
        if data.owner_user_id:
            self._validate(dict(owner_user_id=data.owner_user_id))
        line_no = (self.db.scalar(select(func.max(NCRAction.line_no)).where(NCRAction.ncr_id == report.id)) or 0) + 1
        action = NCRAction(organization_id=self.org, ncr_id=report.id, line_no=line_no, kind=data.kind, description=data.description.strip(),
                           owner_user_id=data.owner_user_id, owner_name=(data.owner_name or "").strip() or None, due_date=data.due_date,
                           status=N.ACTION_OPEN, created_by_user_id=self.tenant.user_id)
        self.db.add(action)
        result = self._commit(report, "action_added", report.status, detail=dict(kind=data.kind))
        self._notify(action, result)
        return result

    def _notify(self, action, report):
        """Tell the person given an action (not someone assigning it to themselves); a failed email changes nothing."""
        if action.owner_user_id and action.owner_user_id != self.tenant.user_id:
            try:
                capa_notices.action_assigned(self.db, self.org, action, report)
            except Exception:  # noqa: BLE001
                logger.exception("Corrective-action assignment email not sent")

    def update_action(self, report_id, action_id, data) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        action = self._action(report, action_id)
        N.assert_action_open(report.status, action.status)
        values = data.model_dump(exclude_unset=True)
        if values.get("kind") is not None:
            N.assert_action_kind(values["kind"])
        if values.get("owner_user_id"):
            self._validate(dict(owner_user_id=values["owner_user_id"]))
        reassigned = "owner_user_id" in values and values["owner_user_id"] != action.owner_user_id
        for field in ("kind", "description", "owner_user_id", "owner_name", "due_date"):
            if field in values and not (field in ("kind", "description") and values[field] is None):
                setattr(action, field, values[field])
        result = self._commit(report, "action_updated", report.status)
        if reassigned:
            self._notify(action, result)
        return result

    def complete_action(self, report_id, action_id, evidence) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        action = self._action(report, action_id)
        N.assert_can_complete(report.status, action.status, evidence)
        action.status, action.evidence, action.completed_at, action.completed_by_user_id = N.ACTION_DONE, evidence.strip(), utc_now(), self.tenant.user_id
        return self._commit(report, "action_done", report.status, reason=action.evidence)

    def cancel_action(self, report_id, action_id, reason) -> NonConformanceReport:
        report = self._get(report_id, lock=True)
        action = self._action(report, action_id)
        N.assert_action_open(report.status, action.status)
        if not (reason or "").strip():
            raise QualityError("REASON_REQUIRED", 400)
        action.status, action.cancel_reason = N.ACTION_CANCELLED, reason.strip()
        return self._commit(report, "action_cancelled", report.status, reason=action.cancel_reason)

    # files
    def _storage(self):
        return self.storage or LocalFileStorage()

    def add_attachment(self, report_id, file_name, content) -> list[dict]:
        report = self._get(report_id)
        N.assert_editable(report.status)
        count = self.db.scalar(select(func.count()).select_from(NCRAttachment).where(NCRAttachment.ncr_id == report.id))
        if count >= MAX_FILES:
            raise QualityError("TOO_MANY_FILES", 400, limit=MAX_FILES)
        try:
            path, content_type = save_attachment(content, self.org, "quality", self._storage())
        except InvalidAttachmentError as exc:
            raise QualityError(f"FILE_{exc}", 400) from exc
        with compensate_new_file(self.db, self._storage(), path, lambda: self.db.scalar(select(NCRAttachment.id).where(
                NCRAttachment.organization_id == self.org, NCRAttachment.storage_path == path)) is not None):
            self.db.add(NCRAttachment(organization_id=self.org, ncr_id=report.id, file_name=(file_name or "file")[-255:], content_type=content_type,
                                  size_bytes=len(content), storage_path=path, uploaded_by_user_id=self.tenant.user_id))
            self.db.commit()
        return self.attachments(report.id)

    def _attachment(self, report_id, attachment_id) -> NCRAttachment:
        row = self.db.scalar(select(NCRAttachment).where(NCRAttachment.id == attachment_id, NCRAttachment.ncr_id == report_id,
                                                         NCRAttachment.organization_id == self.org))
        if row is None:
            raise QualityError("ATTACHMENT_NOT_FOUND", 404)
        return row

    def attachment_file(self, report_id, attachment_id):
        row = self._attachment(report_id, attachment_id)
        try:
            path = self._storage().resolve(row.storage_path)
        except FileNotFoundError as exc:
            raise QualityError("ATTACHMENT_NOT_FOUND", 404) from exc
        if not path.is_file():
            raise QualityError("ATTACHMENT_NOT_FOUND", 404)
        return path, row.content_type, row.file_name

    def remove_attachment(self, report_id, attachment_id) -> list[dict]:
        report = self._get(report_id)
        N.assert_editable(report.status)
        row = self._attachment(report.id, attachment_id)
        path = row.storage_path
        self.db.delete(row)
        self.db.commit()
        try:
            self._storage().delete(path)
        except FileNotFoundError:
            pass
        return self.attachments(report.id)


def can_complete(can) -> bool:
    return bool(can(NCR_ACTIONS_COMPLETE))

