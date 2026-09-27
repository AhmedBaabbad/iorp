from uuid import UUID

from sqlalchemy.orm import Session

from app.commercial.application.follow_up_queries import count_open_follow_ups_for_user
from app.core.interfaces.follow_up_queries import FollowUpQueryInterface


class CommercialFollowUpQueries(FollowUpQueryInterface):
    def __init__(self, db: Session) -> None:
        self.db = db

    def count_open_follow_ups_for_user(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> int:
        return count_open_follow_ups_for_user(
            self.db,
            user_id,
            organization_id,
        )
