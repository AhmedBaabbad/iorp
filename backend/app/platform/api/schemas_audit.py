from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    occurred_at: datetime
    event_type: str
    category: Literal["identity", "organization", "authentication", "authorization", "security", "configuration", "audit"]
    outcome: Literal["success", "failure", "denied"]
    severity: Literal["info", "warning", "critical"]
    actor_type: Literal["platform", "tenant", "system", "anonymous"]
    actor_id: UUID | None = Field(validation_alias="account_id")
    actor_email_snapshot: str | None
    actor_name_snapshot: str | None
    target_type: str | None
    target_id: str | None
    target_display_snapshot: str | None
    organization_id: UUID | None
    request_id: str | None
    correlation_id: str | None
    ip_address: str | None
    user_agent: str | None
    reason: str | None
    changes: Any = None
    metadata: Any = Field(default=None, validation_alias="event_metadata")
    error_code: str | None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    pages: int
