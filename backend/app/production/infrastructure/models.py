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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.utils import TZDateTime, enum_values, utc_now
from app.production.domain.enums import (
    DowntimeCategory,
    DowntimeStatus,
    ProductionOutputStatus,
    ProductionOrderPriority,
    ProductionOrderStatus,
    ShiftDefinitionStatus,
    ShiftReportStatus,
    ShiftType,
    WasteCategory,
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
    production_outputs: Mapped[list["ProductionOutput"]] = relationship(
        "ProductionOutput",
        foreign_keys="[ProductionOutput.work_center_id]",
        cascade="all, delete-orphan",
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

    shift_reports: Mapped[list["ShiftReport"]] = relationship(
        "ShiftReport",
        foreign_keys="[ShiftReport.shift_definition_id]",
        cascade="all, delete-orphan",
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
        "ProductionOrderItem", cascade="all, delete-orphan",
    )
    allocations: Mapped[list["ProductionAllocation"]] = relationship(back_populates="production_order", lazy="selectin")


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
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
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


class ShiftReport(Base):
    # Status semantics:
    # draft = report is open, shift execution may still be in progress.
    # submitted = shift has ended, report is closed and pending approval.
    # approved = report has been reviewed and approved by management.
    #
    # shift_started_at and shift_ended_at are intentionally present in this simplified v0.1
    # baseline so future production output, downtime, and waste records can correlate to the
    # actual execution window without changing the core report schema.
    #
    # shift_definition_id references the recurring ShiftDefinition time template, not a live
    # shift execution instance.
    __tablename__ = "production_shift_reports"

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
    work_center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_work_centers.id"),
        nullable=False,
        index=True,
    )
    shift_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_shift_definitions.id"),
        nullable=False,
        index=True,
    )
    production_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_orders.id"),
        nullable=True,
        index=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_started_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    shift_ended_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    status: Mapped[ShiftReportStatus] = mapped_column(
        SqlEnum(
            ShiftReportStatus,
            name="production_shift_report_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=ShiftReportStatus.DRAFT,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
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


class ProductionOutput(Base):
    # work_center_id is stored at output level because actual production may run on a
    # different line than the planned work center on the ProductionOrder header.
    #
    # output_date is the calendar reporting date; recorded_at is the exact optional timestamp
    # for a specific output entry. Keeping both supports multiple entries within one shift.
    #
    # shift_report_id present = output is tied to documented shift context.
    # shift_report_id absent = output was recorded directly against the order.
    #
    # Quality quantities such as approved, rejected, and rework are intentionally excluded
    # from this Production baseline; they belong to future Quality integration.
    __tablename__ = "production_outputs"

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
    shift_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_shift_reports.id"),
        nullable=True,
        index=True,
    )
    production_order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_order_items.id"),
        nullable=True,
        index=True,
    )
    output_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    recorded_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    quantity_produced: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    output_status: Mapped[ProductionOutputStatus] = mapped_column(
        SqlEnum(
            ProductionOutputStatus,
            name="production_output_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=ProductionOutputStatus.RECORDED,
    )
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


class DowntimeEvent(Base):
    # duration_minutes is calculated by the service from start_time/end_time and is never
    # accepted as caller input, which avoids inconsistent manual duration values.
    #
    # status mirrors end_time: open means end_time is NULL; closed means end_time is set.
    #
    # category is the controlled downtime classification, while reason_code is free text
    # for the operator's specific reason and is not an enum or lookup table in v0.1.
    __tablename__ = "production_downtime_events"

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
    work_center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_work_centers.id"),
        nullable=False,
        index=True,
    )
    shift_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_shift_reports.id"),
        nullable=True,
        index=True,
    )
    production_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_orders.id"),
        nullable=True,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[DowntimeCategory] = mapped_column(
        SqlEnum(
            DowntimeCategory,
            name="production_downtime_category",
            values_callable=enum_values,
        ),
        nullable=False,
        index=True,
    )
    reason_code: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DowntimeStatus] = mapped_column(
        SqlEnum(
            DowntimeStatus,
            name="production_downtime_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=DowntimeStatus.OPEN,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=False,
        index=False,
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


class WasteRecord(Base):
    # work_center_id is stored on each waste record because waste happens at a specific
    # physical line/location and may differ from the planned work center on the order.
    #
    # reason_code is intentionally free text in v0.1: no enum, FK, or lookup table.
    #
    # Costing, scrap inventory posting, and detailed quality rejection fields are excluded
    # from this Production baseline and belong to future costing, inventory, and Quality work.
    __tablename__ = "production_waste_records"

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
    shift_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_shift_reports.id"),
        nullable=True,
        index=True,
    )
    production_order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_order_items.id"),
        nullable=True,
        index=True,
    )
    waste_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity_wasted: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    waste_category: Mapped[WasteCategory] = mapped_column(
        SqlEnum(
            WasteCategory,
            name="production_waste_category",
            values_callable=enum_values,
        ),
        nullable=False,
        index=True,
    )
    reason_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=False,
        index=False,
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
        UniqueConstraint("organization_id", "production_order_id", "production_demand_item_id", name="uq_allocation_org_order_item"),
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
    allocated_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    # ACTIVE reserves demand quantity; RELEASED is kept as history and never counts.
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active", server_default="active")
    released_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL", name="fk_allocation_released_by"))
    release_reason: Mapped[str | None] = mapped_column(String(500))
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

# Register execution tables for metadata, migrations, and test databases.
from app.production.infrastructure.execution_models import ShiftRoster, ShiftRosterMember, ProductionRun, ProductionRunMember  # noqa: F401,E402
