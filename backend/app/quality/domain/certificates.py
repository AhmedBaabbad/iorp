"""Certificates of Analysis (QUAL-COA-001). Pure: no database, no HTTP.

A COA certifies that one identified batch (a production order line) conforms to its specification.
  draft ─issue→ issued ─revoke(reason)→ revoked
A draft is prepared from a closed inspection whose result is accepted (or conditionally accepted, with the
deviation stated) and whose measurement plan has no failed parameter. Its values are copied from the
inspection when the draft is made, so they never change afterwards; the number is given only on issue
(drafts are not certificates, and numbers have no gaps). An issued certificate is final: a correction is a
replacement — a new draft that supersedes it, issued with its own number — and the old one is revoked.
"""
from decimal import Decimal

from app.quality.domain.rules import QualityError

DRAFT, ISSUED, REVOKED = "draft", "issued", "revoked"
STATUSES = (DRAFT, ISSUED, REVOKED)
CERTIFIABLE_RESULTS = ("accepted", "conditional_accept")
DEFAULT_PREFIX = "COA-"


def assert_certifiable(check_status, result, measurement_statuses) -> None:
    if str(check_status) != "closed":
        raise QualityError("CHECK_NOT_CLOSED")
    if str(result) not in CERTIFIABLE_RESULTS:
        raise QualityError("CHECK_NOT_CERTIFIABLE", result=str(result))
    if not measurement_statuses:
        raise QualityError("CERTIFICATE_NEEDS_MEASUREMENTS")
    if any(s == "fail" for s in measurement_statuses):
        raise QualityError("CERTIFICATE_HAS_FAILED_MEASUREMENT")


def assert_draft(status) -> None:
    if status != DRAFT:
        raise QualityError("CERTIFICATE_NOT_DRAFT", certificate_status=status)


def assert_quantity(quantity: Decimal | None, accepted: Decimal) -> None:
    if quantity is None or quantity <= 0:
        raise QualityError("QUANTITY_REQUIRED", 400)
    if quantity > accepted:
        raise QualityError("QUANTITY_EXCEEDS_ACCEPTED", 400, available=format(accepted.normalize(), "f"))


def assert_can_issue(status, customer_name, batch_no, result, deviation_note) -> None:
    assert_draft(status)
    if not (customer_name or "").strip():
        raise QualityError("CUSTOMER_REQUIRED", 400)
    if not (batch_no or "").strip():
        raise QualityError("BATCH_REQUIRED", 400)
    if str(result) == "conditional_accept" and not (deviation_note or "").strip():
        raise QualityError("DEVIATION_NOTE_REQUIRED", 400)


def assert_can_revoke(status, reason) -> None:
    if status != ISSUED:
        raise QualityError("CERTIFICATE_NOT_ISSUED", certificate_status=status)
    if not (reason or "").strip():
        raise QualityError("REASON_REQUIRED", 400)


def number(prefix: str, value: int) -> str:
    return f"{prefix}{value:04d}"


def assert_next_number(current: int, requested: int) -> None:
    """The numbering continues from paper certificates, but never goes back (no number is issued twice)."""
    if requested < current:
        raise QualityError("CERTIFICATE_NUMBER_BACKWARDS", 400, current=current)


def actions(status, can) -> list[str]:
    offered = {DRAFT: ["edit", "issue"], ISSUED: ["revoke", "replace"], REVOKED: []}[status]
    permission = {"edit": "update", "issue": "issue", "revoke": "revoke", "replace": "create"}
    return [a for a in offered if can(permission[a])]
