"""Non-conformance reports (QUAL-NCR-002). Pure: no database, no HTTP.

One report per non-conformance, whatever its source (incoming material from a supplier, production, the warehouse, a
customer return or complaint). It moves through the stages of a corrective action, each step recorded with who and when:

  open ─contain(actions taken)→ investigation ─investigate(root cause)→ action ─submit→ verification ─verify(effective)→ closed
                                investigation ─investigate(no action needed, why)→ closed      (a minor, isolated case)
                                                                       verification ─verify(not effective)→ action
  any stage before closed ─cancel(reason)→ cancelled

The report's items are what is affected (a material lot, a product batch), each with its quantity and the decision on it.
Its corrective actions (correction, corrective, preventive) have an owner, a due date and are completed with evidence;
the report goes to verification only when every action is finished and at least one was done. Costs are optional, and
so is the claim against the party responsible (a supplier or a carrier).
"""
from decimal import Decimal

from .rules import QualityError

OPEN, INVESTIGATION, ACTION, VERIFICATION, CLOSED, CANCELLED = "open", "investigation", "action", "verification", "closed", "cancelled"
STATUSES = (OPEN, INVESTIGATION, ACTION, VERIFICATION, CLOSED, CANCELLED)
FINAL = frozenset({CLOSED, CANCELLED})

SEVERITIES = ("minor", "major", "critical")
# The 6M of a cause-and-effect analysis.
ROOT_CAUSE_CATEGORIES = ("man", "machine", "material", "method", "measurement", "environment")
ROOT_CAUSE_METHODS = ("five_whys", "fishbone", "other")

# What is decided on an affected item. Material from a supplier may go back to it; product follows quality's dispositions.
DISPOSITIONS = ("return_to_supplier", "use_as_is", "sort", "rework", "regrade", "return_to_process", "scrap", "hold")

ACTION_KINDS = ("correction", "corrective", "preventive")
ACTION_OPEN, ACTION_DONE, ACTION_CANCELLED = "open", "done", "cancelled"
ACTION_STATUSES = (ACTION_OPEN, ACTION_DONE, ACTION_CANCELLED)

# With the responsible party: nothing, a notice, the goods sent back, or a formal corrective action request (SCAR).
SUPPLIER_ACTIONS = ("none", "notify", "return_goods", "scar")
CLAIM_STATUSES = ("none", "claimed", "accepted", "rejected", "recovered")
COSTS = ("cost_material", "cost_labor", "cost_scrap", "cost_transport", "cost_other")
ZERO = Decimal("0")


def _text(value) -> bool:
    return bool((value or "").strip())


def assert_editable(status) -> None:
    if status in FINAL:
        raise QualityError("NCR_IS_FINAL", ncr_status=status)


def assert_can_contain(status, containment) -> None:
    if status != OPEN:
        raise QualityError("NCR_NOT_OPEN", ncr_status=status)
    if not _text(containment):
        raise QualityError("CONTAINMENT_REQUIRED", 400)


def assert_can_investigate(status, category, root_cause, action_required, justification) -> None:
    if status != INVESTIGATION:
        raise QualityError("NCR_NOT_UNDER_INVESTIGATION", ncr_status=status)
    if category not in ROOT_CAUSE_CATEGORIES or not _text(root_cause):
        raise QualityError("ROOT_CAUSE_REQUIRED", 400)
    if not action_required and not _text(justification):
        raise QualityError("NO_ACTION_JUSTIFICATION_REQUIRED", 400)


def assert_can_submit(status, action_statuses: list[str]) -> None:
    """Every corrective action finished, and at least one done."""
    if status != ACTION:
        raise QualityError("NCR_NOT_IN_ACTION", ncr_status=status)
    if any(s == ACTION_OPEN for s in action_statuses):
        raise QualityError("ACTIONS_STILL_OPEN", open=sum(1 for s in action_statuses if s == ACTION_OPEN))
    if not any(s == ACTION_DONE for s in action_statuses):
        raise QualityError("ACTION_REQUIRED", 400)


def assert_can_verify(status, effective, notes) -> None:
    if status != VERIFICATION:
        raise QualityError("NCR_NOT_IN_VERIFICATION", ncr_status=status)
    if not effective and not _text(notes):
        raise QualityError("VERIFICATION_NOTES_REQUIRED", 400)


def assert_can_cancel(status, reason) -> None:
    assert_editable(status)
    if not _text(reason):
        raise QualityError("REASON_REQUIRED", 400)


def assert_action_open(report_status, action_status) -> None:
    assert_editable(report_status)
    if action_status != ACTION_OPEN:
        raise QualityError("ACTION_NOT_OPEN", action_status=action_status)


def assert_can_complete(report_status, action_status, evidence) -> None:
    assert_action_open(report_status, action_status)
    if not _text(evidence):
        raise QualityError("EVIDENCE_REQUIRED", 400)


def total_cost(report) -> Decimal | None:
    values = [getattr(report, name) for name in COSTS if getattr(report, name) is not None]
    return sum(values, ZERO) if values else None


def actions(status, can) -> list[str]:
    """What may be done on the report now; can(name) checks the permission (see permissions.NCR_ACTIONS)."""
    offered = {
        OPEN: ["edit", "contain", "cancel"],
        INVESTIGATION: ["edit", "investigate", "add_action", "cancel"],
        ACTION: ["edit", "add_action", "submit", "cancel"],
        VERIFICATION: ["edit", "verify", "cancel"],
    }.get(status, [])
    return [a for a in offered if can(a)]


def assert_action_kind(kind) -> None:
    if kind not in ACTION_KINDS:
        raise QualityError("ACTION_KIND_UNKNOWN", 400)


def is_overdue(action, today) -> bool:
    return action.status == ACTION_OPEN and action.due_date is not None and action.due_date < today
