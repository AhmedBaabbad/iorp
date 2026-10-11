"""Dated roster history and independent execution participation."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class ExecutionRecord:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_organizations.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now, onupdate=utc_now)


class ShiftRoster(ExecutionRecord, Base):
    __tablename__ = "production_shift_rosters"
    __table_args__ = (
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_roster_period"),
        CheckConstraint("status IN ('active', 'closed')", name="ck_roster_status"),
    )
    shift_definition_id: Mapped[UUID] = mapped_column(ForeignKey("production_shift_definitions.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notes: Mapped[str | None] = mapped_column(Text)


class ShiftRosterMember(ExecutionRecord, Base):
    __tablename__ = "production_shift_roster_members"
    __table_args__ = (UniqueConstraint("organization_id", "shift_roster_id", "workforce_member_id", name="uq_roster_worker"),)
    shift_roster_id: Mapped[UUID] = mapped_column(ForeignKey("production_shift_rosters.id", ondelete="RESTRICT"), index=True)
    workforce_member_id: Mapped[UUID] = mapped_column(ForeignKey("workforce_members.id", ondelete="RESTRICT"), index=True)
    is_shift_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    role_note: Mapped[str | None] = mapped_column(String(255))


class ProductionRun(ExecutionRecord, Base):
    __tablename__ = "production_runs"
    __table_args__ = (
        CheckConstraint("ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at)", name="ck_run_window"),
        CheckConstraint("planned_quantity IS NULL OR planned_quantity > 0", name="ck_run_quantity"),
        CheckConstraint("status IN ('planned','in_progress','paused','completed','cancelled')", name="ck_run_status"),
    )
    production_order_id: Mapped[UUID] = mapped_column(ForeignKey("production_orders.id", ondelete="RESTRICT"), index=True)
    work_center_id: Mapped[UUID] = mapped_column(ForeignKey("production_work_centers.id", ondelete="RESTRICT"), index=True)
    shift_definition_id: Mapped[UUID | None] = mapped_column(ForeignKey("production_shift_definitions.id", ondelete="RESTRICT"), index=True)
    shift_roster_id: Mapped[UUID | None] = mapped_column(ForeignKey("production_shift_rosters.id", ondelete="RESTRICT"), index=True)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    started_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    ended_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    planned_quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("foundation_users.id", ondelete="RESTRICT"))


class ProductionRunMember(ExecutionRecord, Base):
    __tablename__ = "production_run_members"
    __table_args__ = (
        # A worker may rejoin a run, but only one participation per worker can be open.
        Index("uq_run_worker_open", "production_run_id", "workforce_member_id", unique=True,
              postgresql_where=text("ended_at IS NULL"), sqlite_where=text("ended_at IS NULL")),
        CheckConstraint("ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at)", name="ck_run_member_window"),
    )
    production_run_id: Mapped[UUID] = mapped_column(ForeignKey("production_runs.id", ondelete="RESTRICT"), index=True)
    workforce_member_id: Mapped[UUID] = mapped_column(ForeignKey("workforce_members.id", ondelete="RESTRICT"), index=True)
    role_code: Mapped[str] = mapped_column(String(64))
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    ended_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    notes: Mapped[str | None] = mapped_column(Text)


# Paged roster list (ARCH-PAGE-001, migration f6a1b2m6).
Index("ix_roster_org_from", ShiftRoster.organization_id, ShiftRoster.effective_from)
