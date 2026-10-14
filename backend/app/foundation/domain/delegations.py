"""What may be delegated, and the rules of a delegation (PROJECT-GOV-004).

Governed delegation (Delegation of Authority): a holder lends one approval they hold through a role, for at most 90
days, to another user of the same organization; it is in force only once the other side has agreed:

    asked by its holder           → awaiting_manager → a delegation manager approves or rejects
    made by a manager for a holder → awaiting_holder  → the holder approves or rejects
    made by a holder who is also a delegation manager (the organization's administrator) → approved at once

Revoking needs no agreement (it only takes authority away). A delegated approval is never delegated again. "Prepared
by" is the creator of a document and is never delegated.
"""
from datetime import date

from app.production.domain import permissions as production_permissions  # the single source of production codes (pure)

READ, MANAGE = "foundation:delegations:read", "foundation:delegations:manage"
MAX_DAYS = 90

# The approvals that can be signed under a delegation: each records its signature through core/interfaces/approvals.py.
DELEGABLE = (
    "commercial:quotes:issue",
    "commercial:orders:confirm",
    "commercial:complaints:close",
    "procurement:purchase_orders:approve",
    "procurement:suppliers:approve",
    production_permissions.ORDERS_RELEASE,
    production_permissions.ORDERS_CLOSE,
    "quality:quality_checks:close",
    "quality:rejections:decide",
    "quality:ncr_reports:verify",
    "quality:certificates:issue",
    "shipping:returns:approve",
)

AWAITING_MANAGER, AWAITING_HOLDER, APPROVED, REJECTED = "awaiting_manager", "awaiting_holder", "approved", "rejected"


class DelegationError(ValueError):
    def __init__(self, code: str, status: int = 422):
        super().__init__(code)
        self.code, self.status = code, status


def assert_period(effective_from: date, effective_to: date, today: date) -> None:
    if effective_to < effective_from:
        raise DelegationError("DELEGATION_PERIOD_INVALID")
    if effective_to < today:
        raise DelegationError("DELEGATION_ALREADY_ENDED")
    if (effective_to - effective_from).days + 1 > MAX_DAYS:
        raise DelegationError("DELEGATION_TOO_LONG")


def in_force(delegation, today: date) -> bool:
    return (delegation.approval == APPROVED and delegation.revoked_at is None
            and delegation.effective_from <= today <= delegation.effective_to)


def status(delegation, today: date) -> str:
    """revoked, rejected, awaiting_manager / awaiting_holder, lapsed (its period ended unanswered), scheduled, active, ended."""
    if delegation.revoked_at is not None:
        return "revoked"
    if delegation.approval == REJECTED:
        return "rejected"
    if delegation.approval in (AWAITING_MANAGER, AWAITING_HOLDER):
        return "lapsed" if today > delegation.effective_to else delegation.approval
    if today < delegation.effective_from:
        return "scheduled"
    return "active" if today <= delegation.effective_to else "ended"
