"""Request and response shapes for machine downtime (PROD-DOWNTIME-001)."""
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.core.types import ISODatetime
from app.production.domain.enums import DowntimeCategory, DowntimeStatus


class DowntimeEventCreate(BaseModel):
    """status, duration and planned are derived; organization_id never comes from the body.
    Give a run (which carries the machine and the order) or a work center."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    work_center_id: UUID | None = None
    production_order_id: UUID | None = None
    production_run_id: UUID | None = None
    start_time: AwareDatetime
    end_time: AwareDatetime | None = None
    category: DowntimeCategory
    reason_code: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class DowntimeEventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    work_center_id: UUID | None = None
    production_order_id: UUID | None = None
    production_run_id: UUID | None = None
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None
    category: DowntimeCategory | None = None
    reason_code: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def reject_null_required_values(self):
        for field in ("work_center_id", "start_time", "category"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class DowntimeClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Defaults to now.
    end_time: AwareDatetime | None = None


class DowntimeEventListItem(BaseModel):
    id: UUID
    organization_id: UUID
    work_center_id: UUID
    production_order_id: UUID | None
    production_run_id: UUID | None
    start_time: ISODatetime
    end_time: ISODatetime | None
    duration_minutes: Decimal | None
    category: DowntimeCategory
    planned: bool
    reason_code: str | None
    status: DowntimeStatus
    created_by_user_id: UUID
    closed_by_user_id: UUID | None
    updated_by_user_id: UUID | None
    created_at: ISODatetime
    updated_at: ISODatetime
    # Display labels, minutes so far for an open stop, and allowed actions (close/edit/delete).
    labels: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class DowntimeEventRead(DowntimeEventListItem):
    notes: str | None


class DowntimeSummaryRead(BaseModel):
    count: int
    total_minutes: Decimal
    planned_minutes: Decimal
    unplanned_minutes: Decimal
    open_count: int
    open_minutes_so_far: Decimal
    mttr_minutes: Decimal | None
    by_category: list[dict[str, Any]]
    by_work_center: list[dict[str, Any]]


class DowntimeFilters(BaseModel):
    work_center_id: UUID | None = None
    production_order_id: UUID | None = None
    production_run_id: UUID | None = None
    category: DowntimeCategory | None = None
    planned: bool | None = None
    status: DowntimeStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
