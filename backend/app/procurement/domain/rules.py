"""Suppliers, materials and goods receipts (PROC-001). Pure: no database, no HTTP.

Suppliers are numbered SUP-NNNN and carry their standing on the approved supplier list:
  pending (new, not evaluated) · approved · conditional (on probation) · blocked (no receipt is accepted)
A change of standing other than to approved needs a reason, and keeps who decided it and when.

Materials (MAT-NNNN) are what is bought — resin, masterbatch, additives, cores, cartons, film… — with a default unit from
the shared catalogue, whether each lot is inspected on arrival, and the product key of its quality specification.

A goods receipt (GRN-YYYY-NNNN, prefix in the settings) records a delivery from a registered supplier:
  draft ─receive→ received          draft / received ─cancel(reason)→ cancelled
Only a draft is edited; receiving needs at least one line and a supplier that is not blocked. Each line is a material
(or a described item), the supplier's lot, the quantity in a unit of the catalogue, packages and weight.
"""
from decimal import Decimal

from app.core.phones import normalize_phone as _normalize_phone


class ProcurementError(ValueError):
    def __init__(self, code: str, status: int = 409, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


PENDING, APPROVED, CONDITIONAL, BLOCKED = "pending", "approved", "conditional", "blocked"
SUPPLIER_STATUSES = (PENDING, APPROVED, CONDITIONAL, BLOCKED)
SUPPLIER_CATEGORIES = ("raw_material", "packaging", "consumables", "services", "other")
MATERIAL_CATEGORIES = ("resin", "masterbatch", "additive", "core", "carton", "film", "accessory", "other")

DRAFT, RECEIVED, CANCELLED = "draft", "received", "cancelled"
RECEIPT_STATUSES = (DRAFT, RECEIVED, CANCELLED)
DEFAULT_PREFIX = "GRN-"
ZERO = Decimal("0")


def normalize_phone(value):
    try:
        return _normalize_phone(value)
    except ValueError as exc:
        raise ProcurementError("PHONE_INVALID", 400, value=str(value)) from exc


def code(prefix: str, value: int) -> str:
    return f"{prefix}{value:04d}"


def number(prefix: str, year: int, value: int) -> str:
    return f"{prefix}{year}-{value:04d}"


# ── suppliers ────────────────────────────────────────────────────────────────────────────────────

def assert_status_change(current, new, reason) -> None:
    if new not in SUPPLIER_STATUSES or new == PENDING:
        raise ProcurementError("SUPPLIER_STATUS_UNKNOWN", 400)
    if new == current:
        raise ProcurementError("SUPPLIER_STATUS_UNCHANGED", 400)
    if new != APPROVED and not (reason or "").strip():
        raise ProcurementError("REASON_REQUIRED", 400)


def supplier_actions(can) -> list[str]:
    return [a for a in ("edit", "set_status") if can(a)]


# ── receipts ─────────────────────────────────────────────────────────────────────────────────────

def assert_editable(status) -> None:
    if status != DRAFT:
        raise ProcurementError("RECEIPT_NOT_DRAFT", receipt_status=status)


def assert_supplier_usable(status) -> None:
    if status == BLOCKED:
        raise ProcurementError("SUPPLIER_BLOCKED")


def assert_line(line) -> None:
    if line.quantity is None or line.quantity <= ZERO:
        raise ProcurementError("QUANTITY_REQUIRED", 400, line=line.line_no)
    if not (line.description or "").strip():
        raise ProcurementError("DESCRIPTION_REQUIRED", 400, line=line.line_no)


def assert_can_receive(status, line_count, supplier_status) -> None:
    assert_editable(status)
    if line_count == 0:
        raise ProcurementError("LINES_REQUIRED", 400)
    assert_supplier_usable(supplier_status)


def assert_can_cancel(status, reason) -> None:
    if status == CANCELLED:
        raise ProcurementError("RECEIPT_IS_CANCELLED")
    if not (reason or "").strip():
        raise ProcurementError("REASON_REQUIRED", 400)


def receipt_actions(status, can) -> list[str]:
    offered = {DRAFT: ["edit", "receive", "cancel"], RECEIVED: ["cancel"]}.get(status, [])
    return [a for a in offered if can(a)]
