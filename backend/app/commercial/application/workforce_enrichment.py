from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session


def get_workforce_summary_row(db: Session, user_id: UUID, organization_id: UUID) -> dict | None:
    """Optional display enrichment only -- reads workforce_members directly by
    raw SQL rather than importing the Workforce ORM model, preserving the
    Commercial/Workforce module boundary (matches the Quality/Production
    ADR-004 convention already used in this codebase).

    Shared by SalesOwnerEligibilityService and FollowUpAssigneeEligibilityService
    -- both enrich a foundation User with the same optional workforce fields.
    """
    statement = text(
        "SELECT id, employee_code, worker_type, display_name "
        "FROM workforce_members "
        "WHERE user_id = :user_id AND organization_id = :organization_id"
    ).bindparams(
        bindparam("user_id", type_=PG_UUID(as_uuid=True)),
        bindparam("organization_id", type_=PG_UUID(as_uuid=True)),
    )
    row = db.execute(
        statement,
        {"user_id": user_id, "organization_id": organization_id},
    ).mappings().first()
    return dict(row) if row is not None else None
