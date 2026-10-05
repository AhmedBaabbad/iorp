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


# ── quality of received lots and supplier evaluation (PROC-002) ───────────────────────────────

def lot_status(inspection_required, checks: list[dict]) -> str:
    """Where a received lot stands with quality (read from its incoming inspection):
    not_required · awaiting · inspecting · released · partly_released · rejected."""
    if not inspection_required:
        return "not_required"
    live = [c for c in checks if c["status"] != "cancelled"]
    if not live:
        return "awaiting"
    check = live[-1]
    if check["status"] != "closed":
        return "inspecting"
    if check["qty_accepted"] >= check["qty_inspected"]:
        return "released"
    return "partly_released" if check["qty_accepted"] > ZERO else "rejected"


# How a supplier is scored over a period (out of 100):
#   quality   = 100 × lots released in full ÷ lots inspected (no inspected lot: not scored)
#   penalty   = per non-conformance report about it: critical 10, major 5, minor 2 (at most 30)
#             + 1 point per 1 000 of non-conformance cost (at most 20)
#   score     = quality − penalty, never below 0;  grade A ≥ 90, B ≥ 75, C ≥ 60, D below
# The grade suggests a standing (A, B: approved · C: conditional · D: blocked); deciding it stays with whoever approves suppliers.
SEVERITY_POINTS = {"critical": 10, "major": 5, "minor": 2}
NCR_PENALTY_CAP, COST_PER_POINT, COST_PENALTY_CAP = 30, Decimal("1000"), 20
GRADES = ((90, "A", APPROVED), (75, "B", APPROVED), (60, "C", CONDITIONAL), (0, "D", BLOCKED))


def evaluate(lots_inspected: int, lots_released: int, ncr_severities: list[str], ncr_cost: Decimal) -> dict:
    ncr_penalty = min(NCR_PENALTY_CAP, sum(SEVERITY_POINTS.get(s, 0) for s in ncr_severities))
    cost_penalty = min(COST_PENALTY_CAP, int(ncr_cost / COST_PER_POINT)) if ncr_cost else 0
    if lots_inspected == 0:
        return dict(lots_inspected=0, lots_released=0, lots_rejected=0, acceptance_pct=None, ncr_count=len(ncr_severities),
                    ncr_penalty=ncr_penalty, ncr_cost=ncr_cost, cost_penalty=cost_penalty, score=None, grade=None, suggested_status=None)
    acceptance = Decimal(lots_released * 100) / Decimal(lots_inspected)
    score = max(Decimal("0"), acceptance - ncr_penalty - cost_penalty).quantize(Decimal("0.1"))
    grade, suggested = next((g, st) for floor, g, st in GRADES if score >= floor)
    return dict(lots_inspected=lots_inspected, lots_released=lots_released, lots_rejected=lots_inspected - lots_released,
                acceptance_pct=acceptance.quantize(Decimal("0.1")), ncr_count=len(ncr_severities), ncr_penalty=ncr_penalty, ncr_cost=ncr_cost,
                cost_penalty=cost_penalty, score=score, grade=grade, suggested_status=suggested)


def receipt_actions(status, can) -> list[str]:
    offered = {DRAFT: ["edit", "receive", "cancel"], RECEIVED: ["cancel"]}.get(status, [])
    return [a for a in offered if can(a)]
