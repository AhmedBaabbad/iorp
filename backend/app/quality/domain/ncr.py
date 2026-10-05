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

Follow-up (QUAL-CAPA-001): a report that repeats earlier ones (same supplier, same affected item, or the same kind of
non-conformance with the same 6M cause) is recurring and cannot be closed without a corrective action; a closed report
may be reviewed again after a period to confirm the problem did not come back (not effective: it reopens to the actions).
"""
from datetime import timedelta
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

# Recurrence: reports within this many days before this one, matched on any of these; two earlier ones make it recurring.
RECURRENCE_DAYS = 180
RECURRENCE_THRESHOLD = 2
RECURRENCE_KEYS = ("supplier", "item", "cause")
# The later review of a closed report: after this many days (0: none), then effective or not.
REVIEW_DAYS_MAX = 365
EFFECTIVE, NOT_EFFECTIVE = "effective", "not_effective"
# An open action is "due soon" this many days before its date.
DUE_SOON_DAYS = 3


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


def assert_can_investigate(status, category, root_cause, action_required, justification, recurring=False) -> None:
    if status != INVESTIGATION:
        raise QualityError("NCR_NOT_UNDER_INVESTIGATION", ncr_status=status)
    if category not in ROOT_CAUSE_CATEGORIES or not _text(root_cause):
        raise QualityError("ROOT_CAUSE_REQUIRED", 400)
    if not action_required and recurring:  # a repeated problem is not an isolated case
        raise QualityError("RECURRING_NEEDS_ACTION", 400)
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


def review_pending(report) -> bool:
    """Closed, with a later review of its effectiveness still to do."""
    return report.status == CLOSED and report.effectiveness_due_date is not None and report.effectiveness_result is None


def review_due(report, today) -> bool:
    return review_pending(report) and report.effectiveness_due_date <= today


def assert_can_review(report, effective, notes) -> None:
    if not review_pending(report):
        raise QualityError("EFFECTIVENESS_REVIEW_NOT_PENDING", ncr_status=report.status)
    if not effective and not _text(notes):
        raise QualityError("REVIEW_NOTES_REQUIRED", 400)


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


def actions(status, can, pending_review=False) -> list[str]:
    """What may be done on the report now; can(name) checks the permission (see permissions.NCR_ACTIONS)."""
    offered = {
        OPEN: ["edit", "contain", "cancel"],
        INVESTIGATION: ["edit", "investigate", "add_action", "cancel"],
        ACTION: ["edit", "add_action", "submit", "cancel"],
        VERIFICATION: ["edit", "verify", "cancel"],
        CLOSED: ["review_effectiveness"] if pending_review else [],
    }.get(status, [])
    return [a for a in offered if can(a)]


def assert_action_kind(kind) -> None:
    if kind not in ACTION_KINDS:
        raise QualityError("ACTION_KIND_UNKNOWN", 400)


def is_overdue(action, today) -> bool:
    return action.status == ACTION_OPEN and action.due_date is not None and action.due_date < today


def due_soon(action, today) -> bool:
    return (action.status == ACTION_OPEN and action.due_date is not None
            and today <= action.due_date <= today + timedelta(days=DUE_SOON_DAYS))


def basis(supplier_id, report_type, category, item_names) -> dict:
    """What a report is matched on for recurrence."""
    return dict(supplier=supplier_id, report_type=report_type, category=category,
                items=frozenset(n.strip().casefold() for n in item_names if n and n.strip()))


def matched_on(this: dict, other: dict) -> list[str]:
    """Why another report repeats this one: the same supplier, an affected item of the same name, or the same kind with the same cause."""
    found = []
    if this["supplier"] and this["supplier"] == other["supplier"]:
        found.append("supplier")
    if this["items"] & other["items"]:
        found.append("item")
    if this["category"] and this["category"] == other["category"] and this["report_type"] == other["report_type"]:
        found.append("cause")
    return found


def is_recurring(earlier: int) -> bool:
    return earlier >= RECURRENCE_THRESHOLD
