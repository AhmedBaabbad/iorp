from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.commercial.domain.enums import FollowUpStatus
from app.commercial.infrastructure.models import Customer, FollowUp


OPEN_FOLLOW_UP_STATUSES = (
    FollowUpStatus.PENDING,
    FollowUpStatus.IN_PROGRESS,
)


def count_open_follow_ups_for_user(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
) -> int:
    statement = (
        select(func.count(FollowUp.id))
        .join(Customer, Customer.id == FollowUp.customer_id)
        .where(
            Customer.organization_id == organization_id,
            FollowUp.assigned_user_id == user_id,
            FollowUp.status.in_(OPEN_FOLLOW_UP_STATUSES),
        )
    )
    return db.scalar(statement) or 0
