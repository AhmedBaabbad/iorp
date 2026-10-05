"""Incoming inspection (QUAL-INC-001): the inspection of each received lot of purchased material, and its decision.

Goods receipts are read from procurement's tables; quality writes only its own: an inspection per received lot marked
"inspected on arrival" (type incoming_inspection, of the quantity received, against its material's specification), then
a lot decision that closes it — the released part, and each part not released (used as it is, sorted, returned to the
supplier, scrapped, held). Anything not released opens a non-conformance report about the supplier, one item per part.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.utils import utc_now
from app.quality.domain import incoming_rules as IR
from app.quality.domain import rules
from app.quality.domain.enums import NCRReportType, NCRSourceType, QualityCheckStatus as S, QualityCheckType as T
from app.quality.domain.rules import QualityError, ZERO
from app.quality.infrastructure.models import QualityCheck
from .measurement_service import MeasurementService
from .ncr_service import NCRService
from .support import ProcurementReads, as_decimal, log_activity, next_code, record


class IncomingInspectionService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.procurement = ProcurementReads(db, self.org)

    def _checks_by_line(self, line_ids) -> dict:
        ids = [i for i in set(line_ids) if i]
        if not ids:
            return {}
        rows = self.db.scalars(select(QualityCheck).where(QualityCheck.organization_id == self.org, QualityCheck.receipt_line_id.in_(ids),
                                                          QualityCheck.status != S.CANCELLED).order_by(QualityCheck.created_at))
        return {c.receipt_line_id: c for c in rows}

    # ── reads ──────────────────────────────────────────────────────────────────────────────────
    def awaiting(self, search="", include_done=False) -> list[dict]:
        """Received lots to inspect, grouped by goods receipt, each with its inspection once opened."""
        lots = [lot for lot in self.procurement.received_for_inspection(search) if lot["awaiting_inspection"]]
        checks = self._checks_by_line([lot["line_id"] for lot in lots])
        grouped: dict = {}
        for lot in lots:
            check = checks.get(lot["line_id"])
            entry = grouped.setdefault(lot["receipt_id"], dict(
                receipt_id=lot["receipt_id"], receipt_no=lot["receipt_no"], receipt_date=lot["receipt_date"], received_at=lot["received_at"],
                supplier_id=lot["supplier_id"], supplier_name=lot["supplier_name"], supplier_delivery_no=lot["supplier_delivery_no"], lines=[]))
            entry["lines"].append(dict(
                line_id=lot["line_id"], line_no=lot["line_no"], description=lot["description"], material_code=lot["material_code"],
                spec_product_type=lot["spec_product_type"], supplier_lot=lot["supplier_lot"], quantity=lot["quantity"], unit=lot["unit"],
                inspection_id=check.id if check else None, inspection_code=check.inspection_code if check else None,
                inspection_status=check.status.value if check else None))
        out = list(grouped.values())
        if not include_done:  # a receipt leaves the list once every lot is decided
            out = [r for r in out if any(line["inspection_status"] != S.CLOSED.value for line in r["lines"])]
        return out

    # ── writes ─────────────────────────────────────────────────────────────────────────────────
    def open(self, receipt_line_id) -> QualityCheck:
        """One inspection per received lot, of the quantity received."""
        lot = self.procurement.lot(receipt_line_id)
        IR.assert_awaiting(lot, bool(lot) and receipt_line_id in self._checks_by_line([receipt_line_id]))
        check = QualityCheck(
            organization_id=self.org, inspection_code=next_code(self.db, self.org, "QI"), check_type=T.INCOMING_INSPECTION,
            check_datetime=utc_now(), status=S.OPEN, result=None, receipt_id=lot["receipt_id"], receipt_line_id=lot["line_id"], unit=lot["unit"],
            qty_inspected=as_decimal(lot["quantity"]), qty_accepted=ZERO, qty_rejected=ZERO,
            notes=" / ".join(filter(None, [lot["receipt_no"], lot["supplier_name"], lot["description"], lot["supplier_lot"]])),
            checked_by_user_id=self.tenant.user_id)
        self.db.add(check)
        self.db.flush()
        record(self.db, self.org, "check", check.id, "create", None, S.OPEN.value, self.tenant.user_id, detail=dict(source=lot["receipt_no"]))
        MeasurementService(self.db, self.tenant).auto_apply(check)  # the material's specification, when exactly one is in force
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.created", "quality_check", check.id, check.inspection_code)
        return check

    def decide(self, check_id, data) -> QualityCheck:
        """Close an incoming inspection with where each part of the lot goes; anything not released opens an NCR."""
        check = self.db.scalar(select(QualityCheck).where(QualityCheck.id == check_id, QualityCheck.organization_id == self.org).with_for_update())
        if check is None:
            raise QualityError("QUALITY_CHECK_NOT_FOUND", 404)
        if check.receipt_line_id is None:
            raise QualityError("NOT_AN_INCOMING_INSPECTION")
        rules.assert_can_finish(check.status)
        parts = {name: as_decimal(getattr(data, name)) for name in IR.PARTS}
        released, rejected, result = IR.split(as_decimal(check.qty_inspected), parts)
        if parts["use_as_is"] > ZERO and not ((data.concession_approved_by or "").strip() and (data.notes or "").strip()):
            raise QualityError("CONCESSION_DETAILS_REQUIRED", 400)
        MeasurementService(self.db, self.tenant).assert_complete(check, result)
        lot = self.procurement.lot(check.receipt_line_id) or {}
        notes = (data.notes or "").strip() or None
        before = check.status.value
        check.qty_accepted, check.qty_rejected, check.result = released, rejected, result
        check.status, check.closed_at, check.closed_by_user_id = S.CLOSED, utc_now(), self.tenant.user_id
        if notes:
            check.notes = f"{check.notes}\n{notes}" if check.notes else notes
        record(self.db, self.org, "check", check.id, "close", before, S.CLOSED.value, self.tenant.user_id,
               detail={name: str(value) for name, value in parts.items()})
        if rejected > ZERO:
            items = [dict(item_name=lot.get("description") or check.inspection_code, item_reference=lot.get("supplier_lot"), quantity_affected=parts[name],
                          unit=check.unit, issue_description=notes or check.inspection_code, disposition=name,
                          disposition_notes=data.concession_approved_by.strip() if name == "use_as_is" else None)
                     for name in IR.NOT_RELEASED if parts[name] > ZERO]
            NCRService(self.db, self.tenant).open_report(
                source_type=NCRSourceType.INCOMING_MATERIAL, report_type=NCRReportType.MATERIAL_NON_CONFORMANCE, severity="major",
                title=f"{lot.get('description', '')} — {lot.get('supplier_lot') or lot.get('receipt_no', '')}"[:255],
                description="\n".join(filter(None, [notes, f"{lot.get('receipt_no', '')} · {lot.get('supplier_name', '')}"])) or check.inspection_code,
                reference_code=" / ".join(filter(None, [lot.get("receipt_no"), lot.get("supplier_lot")])) or None, quality_check_id=check.id,
                supplier_id=lot.get("supplier_id"), supplier_name=lot.get("supplier_name"),
                supplier_reference=" / ".join(filter(None, [lot.get("supplier_delivery_no"), lot.get("supplier_lot")])) or None, items=items)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.closed", "quality_check", check.id, check.inspection_code)
        return check
