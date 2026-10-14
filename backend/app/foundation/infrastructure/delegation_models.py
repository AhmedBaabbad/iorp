"""Approval delegations and the record of every signed step (PROJECT-GOV-004). Foundation is their only writer."""
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class ApprovalDelegation(Base):
    """A temporary grant of one permission the delegator holds, to another user of the same organization.

    Governed (Delegation of Authority): it is in force only once the other side has agreed. Asked by its holder, a
    delegation manager approves it; made by a manager on a holder's behalf, the holder approves it; made by someone
    who is both, it is in force at once. Never deleted: an ended, rejected or revoked delegation stays, so the
    signatures made under it keep their meaning."""
    __tablename__ = "foundation_approval_delegations"
    __table_args__ = (
        CheckConstraint("effective_to >= effective_from", name="ck_delegation_period"),
        CheckConstraint("delegator_user_id <> delegate_user_id", name="ck_delegation_not_self"),
        CheckConstraint("approval IN ('awaiting_manager', 'awaiting_holder', 'approved', 'rejected')", name="ck_delegation_approval"),
        Index("ix_delegation_delegate", "organization_id", "delegate_user_id", "permission_code"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_organizations.id"), index=True)
    delegator_user_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_users.id"))
    delegate_user_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_users.id"))
    permission_code: Mapped[str] = mapped_column(String(120))
    effective_from: Mapped[date] = mapped_column(Date)  # the organization's dates, the end day included
    effective_to: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_users.id"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)
    # Whose agreement it waits for, or the answer: awaiting_manager | awaiting_holder | approved | rejected.
    approval: Mapped[str] = mapped_column(String(20), default="awaiting_manager")
    decided_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("foundation_users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("foundation_users.id"))
    revoke_reason: Mapped[str | None] = mapped_column(Text)


class ApprovalRecord(Base):
    """One signed step: whose authority it was and who signed, fixed when it was signed (later permission changes do
    not rewrite it)."""
    __tablename__ = "foundation_approval_records"
    __table_args__ = (Index("ix_approval_record_resource", "organization_id", "resource_type", "resource_id"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_organizations.id"))
    resource_type: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[UUID]
    step: Mapped[str] = mapped_column(String(60))
    permission_code: Mapped[str] = mapped_column(String(120))
    authority_user_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_users.id"))
    signed_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_users.id"))
    delegation_id: Mapped[UUID | None] = mapped_column(ForeignKey("foundation_approval_delegations.id"))
    authority_name: Mapped[str] = mapped_column(String(255))  # as they were named when it was signed
    signer_name: Mapped[str] = mapped_column(String(255))
    signed_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)
    notes: Mapped[str | None] = mapped_column(Text)
