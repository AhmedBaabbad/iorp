from uuid import UUID

from sqlalchemy.orm import Session

from app.core.interfaces.workforce_queries import WorkforceQueryInterface
from app.workforce.infrastructure.repositories import WorkforceRepository


class WorkforceQueries(WorkforceQueryInterface):
    def __init__(self, db: Session) -> None:
        self.members = WorkforceRepository(db)

    def has_linked_member(self, user_id: UUID, organization_id: UUID) -> bool:
        return self.members.get_by_user_id(user_id, organization_id) is not None

    def linked_member_id(self, user_id: UUID, organization_id: UUID) -> UUID | None:
        member = self.members.get_by_user_id(user_id, organization_id)
        return member.id if member else None
