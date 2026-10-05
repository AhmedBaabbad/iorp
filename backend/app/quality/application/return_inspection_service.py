"""Returned goods (QUAL-RET-001): inspections of what customers sent back, and the decision on each returned line.

Shipping returns received for quality are read from shipping's tables; quality writes only its own: an inspection per
returned line (issue triggered, the production order and the line's width and thickness as lot values, so the
product's specification can be measured), then a split decision that closes it — the accepted part back to stock, each
rejected part a rejection already decided (second grade, rework, back to the process, scrap «هالك», hold), executed
later as usual — and, when asked, a draft NCR for the customer return.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.core.utils import utc_now
from app.quality.domain import return_rules as RR
from app.quality.domain import rules
from app.quality.domain.enums import DispositionStatus, NCRReportType, NCRSourceType, QualityCheckStatus as S, QualityCheckType as T
from app.quality.domain.rules import QualityError, ZERO
from app.quality.infrastructure.models import QualityCheck, QualityRejection
from .measurement_service import MeasurementService
from .ncr_service import NCRService
from .support import ShippingReads, as_decimal, log_activity, next_code, record

LOT_KEYS = ("width_mm", "thickness_mm")


def _text(value) -> str:
    return format(Decimal(str(value)).normalize(), "f")


class ReturnInspectionService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.shipping = ShippingReads(db, self.org)

    def _checks_by_line(self, line_ids) -> dict:
        ids = [i for i in set(line_ids) if i]
        if not ids:
            return {}
        rows = self.db.scalars(select(QualityCheck).where(QualityCheck.organization_id == self.org, QualityCheck.return_line_id.in_(ids),
                                                          QualityCheck.status != S.CANCELLED))
        return {c.return_line_id: c for c in rows}

    # ── reads ──────────────────────────────────────────────────────────────────────────────────
    def awaiting(self, search="", include_done=False) -> list[dict]:
        """Returns received for quality, grouped, each line with its inspection (if one was opened)."""
        lines = [line for line in self.shipping.received_for_quality(search) if line["awaiting_quality"]]
        checks = self._checks_by_line([line["line_id"] for line in lines])
        grouped: dict = {}
        for line in lines:
            check = checks.get(line["line_id"])
            entry = grouped.setdefault(line["return_id"], dict(
                return_id=line["return_id"], return_no=line["return_no"], kind=line["kind"], reason=line["reason"],
                responsibility=line["responsibility"], details=line["details"], customer_name=line["customer_name"],
                received_at=line["received_at"], shipment_id=line["shipment_id"], shipment_no=line["shipment_no"], lines=[]))
            entry["lines"].append(dict(
                line_id=line["line_id"], line_no=line["line_no"], description=line["description"], width_mm=line["width_mm"],
                thickness_mm=line["thickness_mm"], unit=line["unit"], production_order_id=line["production_order_id"],
                production_order_no=line["production_order_no"], received_quantity=line["received_quantity"],
                inspection_id=check.id if check else None, inspection_code=check.inspection_code if check else None,
                inspection_status=check.status.value if check else None))
        out = list(grouped.values())
        if not include_done:  # a return leaves the list once every line's inspection is closed
            out = [r for r in out if any(line["inspection_status"] != S.CLOSED.value for line in r["lines"])]
        return out

    def batch(self, check: QualityCheck) -> list[dict]:
        return self.shipping.batch(check.production_order_id)

    # ── writes ─────────────────────────────────────────────────────────────────────────────────
    def open(self, return_line_id) -> QualityCheck:
        """One inspection per returned line, of the quantity that came back."""
        line = self.shipping.line(return_line_id)
        RR.assert_awaiting(line, bool(line) and return_line_id in self._checks_by_line([return_line_id]))
        lot = {key: _text(line[key]) for key in LOT_KEYS if line[key] is not None}
        check = QualityCheck(
            organization_id=self.org, inspection_code=next_code(self.db, self.org, "QI"), check_type=T.ISSUE_TRIGGERED,
            check_datetime=utc_now(), status=S.OPEN, result=None, production_order_id=line["production_order_id"],
            return_id=line["return_id"], return_line_id=line["line_id"], unit=line["unit"],
            qty_inspected=as_decimal(line["received_quantity"]), qty_accepted=ZERO, qty_rejected=ZERO, lot_values=lot or None,
            notes=f"{line['return_no']} / {line['shipment_no']} — {line['description']}" + (f"\n{line['details']}" if line["details"] else ""),
            checked_by_user_id=self.tenant.user_id)
        self.db.add(check)
        self.db.flush()
        record(self.db, self.org, "check", check.id, "create", None, S.OPEN.value, self.tenant.user_id, detail=dict(source=line["return_no"]))
        MeasurementService(self.db, self.tenant).auto_apply(check)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.created", "quality_check", check.id, check.inspection_code)
        return check

    def decide(self, check_id, data) -> QualityCheck:
        """Close a return inspection with where each part of the returned quantity goes."""
        check = self.db.scalar(select(QualityCheck).where(QualityCheck.id == check_id, QualityCheck.organization_id == self.org).with_for_update())
        if check is None:
            raise QualityError("QUALITY_CHECK_NOT_FOUND", 404)
        if check.return_line_id is None:
            raise QualityError("NOT_A_RETURN_INSPECTION")
        rules.assert_can_finish(check.status)
        parts = {name: as_decimal(getattr(data, name)) for name in RR.PARTS}
        accepted, rejected, result = RR.split(as_decimal(check.qty_inspected), parts)
        if parts["use_as_is"] > ZERO:
            rules.assert_decision(RR.DISPOSITION_OF["use_as_is"], data.concession_approved_by, data.notes)
        MeasurementService(self.db, self.tenant).assert_complete(check, result)
        line = self.shipping.line(check.return_line_id) or {}
        now, notes = utc_now(), (data.notes or "").strip() or None
        before = check.status.value
        check.qty_accepted, check.qty_rejected, check.result = accepted, rejected, result
        check.status, check.closed_at, check.closed_by_user_id = S.CLOSED, now, self.tenant.user_id
        if notes:
            check.notes = f"{check.notes}\n{notes}" if check.notes else notes
        record(self.db, self.org, "check", check.id, "close", before, S.CLOSED.value, self.tenant.user_id,
               detail={name: str(value) for name, value in parts.items()})
        first = None
        for name, disposition in RR.DISPOSITION_OF.items():
            if parts[name] <= ZERO:
                continue
            rejection = QualityRejection(
                organization_id=self.org, rejection_code=next_code(self.db, self.org, "QR"), quality_check_id=check.id,
                production_order_id=check.production_order_id, return_id=check.return_id, return_line_id=check.return_line_id,
                rejection_date=now.date(), rejection_reason=RR.rejection_reason(line.get("reason")),
                rejection_notes=notes or line.get("return_no") or check.inspection_code, disposition=disposition,
                disposition_status=DispositionStatus.DECIDED, quantity_rejected=parts[name], unit=check.unit or "",
                decided_at=now, decided_by_user_id=self.tenant.user_id, decision_notes=notes,
                concession_approved_by=(data.concession_approved_by or "").strip() or None if name == "use_as_is" else None,
                rejected_by_user_id=self.tenant.user_id)
            self.db.add(rejection)
            self.db.flush()
            first = first or rejection
            record(self.db, self.org, "rejection", rejection.id, "decide", None, DispositionStatus.DECIDED.value, self.tenant.user_id,
                   reason=notes, detail=dict(source=line.get("return_no") or check.inspection_code, disposition=disposition.value))
        if data.open_ncr and rejected > ZERO:
            items = [dict(item_name=line.get("description") or check.inspection_code, item_reference=line.get("production_order_no"),
                          quantity_affected=rejected, unit=check.unit, issue_description=notes or line.get("details") or check.inspection_code)]
            NCRService(self.db, self.tenant).open_report(
                source_type=NCRSourceType.CUSTOMER_RETURN, report_type=NCRReportType.PRODUCT_NON_CONFORMANCE, severity="major",
                title=f"{line.get('return_no', '')} — {line.get('description', '')}"[:255],
                description="\n".join(filter(None, [line.get("details"), notes, f"{line.get('shipment_no', '')} · {line.get('customer_name', '')}"])),
                reference_code=line.get("return_no"), quality_check_id=check.id, quality_rejection_id=first.id if first else None,
                production_order_id=check.production_order_id, return_id=check.return_id, customer_name=line.get("customer_name"), items=items)
        self.db.commit()
        log_activity(self.db, self.org, self.tenant.user_id, "quality_check.closed", "quality_check", check.id, check.inspection_code)
        return check
