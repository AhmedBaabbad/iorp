from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: UUID
    occurred_at: datetime
    event_type: str
    category: str
    outcome: str
    severity: str
    actor_type: str
    actor_id: UUID | None = Field(validation_alias="account_id")
    actor_email_snapshot: str | None
    actor_name_snapshot: str | None
    target_type: str | None
    target_id: str | None
    target_display_snapshot: str | None
    organization_id: UUID
    request_id: str | None
    correlation_id: str | None
    ip_address: str | None
    user_agent: str | None
    reason: str | None
    changes: Any = None
    metadata: Any = Field(default=None, validation_alias="event_metadata")
    error_code: str | None


class TenantAuditListResponse(BaseModel):
    items: list[TenantAuditResponse]
    total: int
    page: int
    page_size: int
    pages: int
