from datetime import date, datetime, time
from decimal import Decimal
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Date,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.utils import TZDateTime, enum_values, utc_now
from app.production.domain.enums import (
    DowntimeStatus,
    ProductionOrderPriority,
    ProductionOrderStatus,
    ShiftDefinitionStatus,
    ShiftType,
    WorkCenterStatus,
    WorkCenterType,
)


class WorkCenter(Base):
    __tablename__ = "production_work_centers"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_production_work_centers_org_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    center_type: Mapped[WorkCenterType] = mapped_column(
        SqlEnum(WorkCenterType, name="production_work_center_type", values_callable=enum_values),
        nullable=False,
        default=WorkCenterType.GENERIC,
    )
    status: Mapped[WorkCenterStatus] = mapped_column(
        SqlEnum(WorkCenterStatus, name="production_work_center_status", values_callable=enum_values),
        nullable=False,
        default=WorkCenterStatus.ACTIVE,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    commissioned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    production_orders: Mapped[list["ProductionOrder"]] = relationship(
        "ProductionOrder", cascade="all, delete-orphan",
    )
    downtime_events: Mapped[list["DowntimeEvent"]] = relationship(
        "DowntimeEvent", cascade="all, delete-orphan",
    )
    waste_records: Mapped[list["WasteRecord"]] = relationship(
        "WasteRecord",
        foreign_keys="[WasteRecord.work_center_id]",
        cascade="all, delete-orphan",
    )


class ShiftDefinition(Base):
    # A ShiftDefinition is a recurring time template, not a live daily shift execution instance.
    # Actual daily shift execution and handover belongs to future shift reports.
    __tablename__ = "production_shift_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_production_shift_definitions_org_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    shift_type: Mapped[ShiftType] = mapped_column(
        SqlEnum(ShiftType, name="production_shift_type", values_callable=enum_values),
        nullable=False,
        default=ShiftType.CUSTOM,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ShiftDefinitionStatus] = mapped_column(
        SqlEnum(
            ShiftDefinitionStatus,
            name="production_shift_definition_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=ShiftDefinitionStatus.ACTIVE,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class ProductionOrder(Base):
    __tablename__ = "production_orders"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "production_order_number",
            name="uq_production_orders_org_number",
        ),
        CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_production_order_priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        nullable=False,
        index=True,
    )
    production_order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    legacy_commercial_order_ref: Mapped[dict | None] = mapped_column(JSON)
    legacy_shift_ref: Mapped[dict | None] = mapped_column(JSON)
    work_center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_work_centers.id"),
        nullable=False,
        index=True,
    )
    product_type: Mapped[str] = mapped_column(String(120), nullable=False)
    target_spec_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[ProductionOrderPriority] = mapped_column(
        SqlEnum(
            ProductionOrderPriority,
            name="production_order_priority",
            values_callable=enum_values,
            native_enum=False,
            length=10,
        ),
        nullable=False,
        default=ProductionOrderPriority.NORMAL,
    )
    status: Mapped[ProductionOrderStatus] = mapped_column(
        SqlEnum(
            ProductionOrderStatus,
            name="production_order_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=ProductionOrderStatus.DRAFT,
    )
    planned_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    planned_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Set by OrderStatusService: first entry to in_progress (kept on resume), and completion.
    actual_start_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    actual_end_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    # Increments on every status transition; a stale value means someone else changed it first.
    status_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    items: Mapped[list["ProductionOrderItem"]] = relationship(
        "ProductionOrderItem", cascade="all, delete-orphan", order_by="ProductionOrderItem.line_no",
    )
    allocations: Mapped[list["ProductionAllocation"]] = relationship(back_populates="production_order", lazy="selectin")


class ProductionOrderStatusHistory(Base):
    """One row per status transition; never updated or deleted."""
    __tablename__ = "production_order_status_history"
    __table_args__ = (
        Index("ix_order_status_history_order", "organization_id", "production_order_id", "created_at"),
        CheckConstraint("trigger IN ('manual','activity','schedule')", name="ck_order_status_history_trigger"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    production_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_orders.id", ondelete="RESTRICT"), nullable=False)
    from_status: Mapped[str] = mapped_column(String(20), nullable=False)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger: Mapped[str] = mapped_column(String(10), nullable=False)
    # NULL for automatic (system) transitions; manual ones are always written with the acting user.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"))
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)


class ProductionOrderItem(Base):
    # Items are tenant-scoped through the parent ProductionOrder organization check.
    # product_type lives on the ProductionOrder header; items only carry line-specific variation.
    # target_spec_json holds flexible item variation fields such as size, color, grade, or dimension.
    __tablename__ = "production_order_items"
    __table_args__ = (
        UniqueConstraint(
            "production_order_id",
            "line_no",
            name="uq_production_order_items_order_line",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    production_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_orders.id"),
        nullable=False,
        index=True,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    target_spec_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    # Same precision as allocations: planning lines are sums of allocated quantities.
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class DowntimeEvent(Base):
    """A period in which a work center did not produce (PROD-DOWNTIME-001).

    Belongs to the work center; the production order and run it interrupted are optional.
    status (open/closed), duration_minutes and planned are derived by the service, never input.
    Rules: domain/downtime_rules.py. reason_code is free text for plant detail.
    """
    __tablename__ = "production_downtime_events"
    __table_args__ = (
        CheckConstraint("category IN ('planned_maintenance','break_meeting','no_orders','changeover_setup','breakdown',"
                        "'material_shortage','waiting_labor','quality_issue','utilities','other')", name="ck_downtime_category"),
        CheckConstraint("planned = (category IN ('planned_maintenance','break_meeting','no_orders'))", name="ck_downtime_planned"),
        CheckConstraint("end_time IS NULL OR end_time > start_time", name="ck_downtime_period"),
        CheckConstraint("(status = 'open' AND end_time IS NULL AND duration_minutes IS NULL)"
                        " OR (status = 'closed' AND end_time IS NOT NULL AND duration_minutes IS NOT NULL)", name="ck_downtime_status"),
        Index("ix_downtime_org_center_start", "organization_id", "work_center_id", "start_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    work_center_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_work_centers.id"), nullable=False, index=True)
    production_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("production_orders.id"), nullable=True, index=True)
    production_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_runs.id", ondelete="RESTRICT", name="fk_downtime_run"), nullable=True, index=True)
    start_time: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    duration_minutes: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    planned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DowntimeStatus] = mapped_column(
        SqlEnum(DowntimeStatus, name="production_downtime_status", values_callable=enum_values),
        nullable=False, default=DowntimeStatus.OPEN, index=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=False)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foundation_users.id", name="fk_downtime_closed_by"), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foundation_users.id", name="fk_downtime_updated_by"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)


class WasteRecord(Base):
    """Operational waste: material lost while an order runs (PROD-WASTE-001).

    Always belongs to a production order; optionally to one of its runs, which gives the work
    center and shift. It has no status of its own: the order's status decides whether it can
    change (domain/waste_rules.py). It is not the order's scrap, which lives in the final result.
    reason_code is free text for plant detail. Costing and inventory posting are out of scope.
    """
    __tablename__ = "production_waste_records"
    __table_args__ = (
        CheckConstraint("waste_category IN ('startup_setup','changeover','process','material_defect','machine_fault',"
                        "'handling_damage','contamination','other')", name="ck_waste_category"),
        CheckConstraint("quantity_wasted > 0", name="ck_waste_quantity"),
        Index("ix_waste_org_order", "organization_id", "production_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        nullable=False,
        index=True,
    )
    production_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_orders.id"),
        nullable=False,
        index=True,
    )
    work_center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_work_centers.id"),
        nullable=False,
        index=True,
    )
    production_order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_order_items.id"),
        nullable=True,
        index=True,
    )
    # Optional: the run (machine, shift, team) the waste happened in.
    production_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_runs.id", ondelete="RESTRICT", name="fk_waste_run"),
        nullable=True,
        index=True,
    )
    waste_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity_wasted: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    waste_category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=False,
        index=False,
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foundation_users.id", name="fk_waste_updated_by"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class ProductionDemandCounter(Base):
    __tablename__ = "production_demand_counters"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProductionDemand(Base):
    __tablename__ = "production_demands"
    __table_args__ = (
        UniqueConstraint("organization_id", "demand_number", name="uq_production_demands_org_number"),
        UniqueConstraint("organization_id", "transfer_key", name="uq_demands_transfer_key"),
        Index("ix_production_demands_org_status", "organization_id", "status"),
        Index("ix_production_demands_org_customer", "organization_id", "customer_id"),
        Index("ix_production_demands_org_sequence", "organization_id", "planning_sequence"),
        CheckConstraint("status IN ('draft','ready_for_planning','partially_planned','planned','cancelled')", name="ck_demand_status"),
        CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_demand_priority"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    demand_number: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("commercial_customers.id", ondelete="RESTRICT"), nullable=False)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("commercial_quotes.id", ondelete="SET NULL"))
    source_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    source_order_number: Mapped[str | None] = mapped_column(String(64))
    transfer_key: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="draft")
    planning_sequence: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)
    items: Mapped[list["ProductionDemandItem"]] = relationship(cascade="all, delete-orphan", order_by="ProductionDemandItem.line_no", lazy="selectin")
    allocations: Mapped[list["ProductionAllocation"]] = relationship(back_populates="demand", lazy="selectin")


class ProductionDemandItem(Base):
    __tablename__ = "production_demand_items"
    __table_args__ = (
        UniqueConstraint("production_demand_id", "line_no", name="uq_production_demand_items_line"),
        CheckConstraint("required_quantity > 0", name="ck_demand_item_quantity"),
        CheckConstraint("line_no > 0", name="ck_demand_item_line"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    production_demand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_demands.id", ondelete="CASCADE"), nullable=False, index=True)
    source_order_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_type: Mapped[str | None] = mapped_column(String(100))
    target_spec_json: Mapped[dict | None] = mapped_column(JSON)
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)
    allocations: Mapped[list["ProductionAllocation"]] = relationship(back_populates="demand_item", lazy="selectin")

    # Quantities are always derived from allocations; only ACTIVE ones reserve demand.
    @property
    def active_allocated_quantity(self) -> Decimal:
        return sum((a.allocated_quantity for a in self.allocations if a.status == "active"), Decimal(0))

    @property
    def released_allocated_quantity(self) -> Decimal:
        return sum((a.allocated_quantity for a in self.allocations if a.status == "released"), Decimal(0))

    @property
    def allocated_quantity(self) -> Decimal:
        # Backward-compatible name for the active allocated quantity.
        return self.active_allocated_quantity

    @property
    def remaining_quantity(self) -> Decimal:
        return self.required_quantity - self.active_allocated_quantity

    @property
    def planning_state(self) -> str:
        allocated = self.active_allocated_quantity
        if allocated == 0:
            return "ready_for_planning"
        return "planned" if allocated >= self.required_quantity else "partially_planned"


class ProductionAllocation(Base):
    __tablename__ = "production_allocations"
    __table_args__ = (
        CheckConstraint("allocated_quantity > 0", name="ck_allocation_quantity"),
        CheckConstraint("status IN ('active','released')", name="ck_allocation_status"),
        CheckConstraint("(status = 'active' AND released_at IS NULL) OR (status = 'released' AND released_at IS NOT NULL)", name="ck_allocation_release"),
        # One ACTIVE allocation per demand item and order; released history may repeat.
        Index("uq_allocation_active_order_item", "organization_id", "production_order_id", "production_demand_item_id", unique=True,
              postgresql_where=text("status = 'active'"), sqlite_where=text("status = 'active'")),
        Index("ix_allocation_org_item_status", "organization_id", "production_demand_item_id", "status"),
        Index("ix_allocation_org_order", "organization_id", "production_order_id"),
        Index("ix_allocation_org_item", "organization_id", "production_demand_item_id"),
        Index("ix_allocation_org_demand", "organization_id", "production_demand_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    production_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_orders.id", ondelete="RESTRICT"), nullable=False)
    production_demand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_demands.id", ondelete="RESTRICT"), nullable=False)
    production_demand_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_demand_items.id", ondelete="RESTRICT"), nullable=False)
    # The specification line this allocation feeds; lines are regenerated from ACTIVE allocations.
    production_order_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("production_order_items.id", ondelete="SET NULL", name="fk_allocation_order_item"), index=True)
    allocated_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    # ACTIVE reserves demand quantity; RELEASED is kept as history and never counts.
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active", server_default="active")
    released_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL", name="fk_allocation_released_by"))
    release_reason: Mapped[str | None] = mapped_column(String(500))
    # The order's status when this allocation was made (PROD-QUALITY-FIX-001): in_progress / on_hold means it was
    # added after execution started, which screens and reports show apart.
    order_status_at_allocation: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)
    production_order: Mapped["ProductionOrder"] = relationship(back_populates="allocations")
    demand: Mapped["ProductionDemand"] = relationship(back_populates="allocations")
    demand_item: Mapped["ProductionDemandItem"] = relationship(back_populates="allocations")

    @property
    def production_order_number(self):
        return self.production_order.production_order_number

    @property
    def production_order_status(self):
        return self.production_order.status

class ProductionResultEntry(Base):
    """One line of an order's final result: how much ended up in which disposition.

    Belongs to the production order only: no work center, shift, run or workforce.
    Has no status of its own; the order's status decides whether it can change
    (completed: edit freely, closed: correction entries only).
    """

    __tablename__ = "production_result_entries"
    __table_args__ = (
        CheckConstraint("disposition IN ('customer_good','stock_good','sample','scrap','rework')", name="ck_result_disposition"),
        CheckConstraint(
            "(entry_type = 'original' AND quantity > 0 AND corrects_entry_id IS NULL AND correction_reason IS NULL)"
            " OR (entry_type = 'correction' AND quantity <> 0 AND corrects_entry_id IS NOT NULL AND correction_reason IS NOT NULL)",
            name="ck_result_entry_type"),
        # Loss is fixed for every disposition except samples, where the user decides.
        CheckConstraint(
            "disposition = 'sample' OR (disposition = 'scrap' AND counts_as_loss)"
            " OR (disposition IN ('customer_good','stock_good','rework') AND NOT counts_as_loss)",
            name="ck_result_counts_as_loss"),
        CheckConstraint("(secondary_quantity IS NULL) = (secondary_unit IS NULL)", name="ck_result_secondary_measure"),
        Index("ix_result_org_order", "organization_id", "production_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    production_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("production_orders.id", ondelete="RESTRICT"), nullable=False)
    # Null only for orders without items (legacy orders); then the unit is the order's.
    production_order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_order_items.id", ondelete="RESTRICT"), nullable=True, index=True)
    disposition: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    # Informational second measure (e.g. weight in kg); totalled per unit, never converted.
    secondary_quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    secondary_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    counts_as_loss: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_type: Mapped[str] = mapped_column(String(12), nullable=False, default="original")
    corrects_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_result_entries.id", ondelete="RESTRICT"), nullable=True, index=True)
    correction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)


# Register execution tables for metadata, migrations, and test databases.
from app.production.infrastructure.execution_models import ShiftRoster, ShiftRosterMember, ProductionRun, ProductionRunMember  # noqa: F401,E402
