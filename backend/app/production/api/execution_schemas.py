from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RosterMemberInput(Input):
    workforce_member_id: UUID
    is_shift_lead: bool = False
    role_note: str | None = Field(default=None, max_length=255)


class RosterCreate(Input):
    shift_definition_id: UUID
    name: str | None = Field(default=None, max_length=255)
    effective_from: date
    effective_to: date | None = None
    notes: str | None = None
    members: list[RosterMemberInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_period(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class RosterClose(Input):
    effective_to: date


class RunMemberInput(Input):
    workforce_member_id: UUID
    role_code: str = Field(min_length=1, max_length=64, pattern=r"\S")
    is_lead: bool = False
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.ended_at and (not self.started_at or self.ended_at < self.started_at):
            raise ValueError("Invalid participation time window")
        return self


class RunCreate(Input):
    production_order_id: UUID
    work_center_id: UUID
    shift_definition_id: UUID | None = None
    shift_roster_id: UUID | None = None
    run_date: date
    planned_quantity: Decimal | None = Field(default=None, gt=0, max_digits=15, decimal_places=3)
    notes: str | None = None
    members: list[RunMemberInput] = Field(default_factory=list)


class RunUpdate(Input):
    planned_quantity: Decimal | None = Field(default=None, gt=0, max_digits=15, decimal_places=3)
    notes: str | None = None
