from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.interfaces.platform_email_queries import PlatformEmailQueryInterface
from app.core.security import normalize_email
from app.platform.infrastructure.models import PlatformAccount


class PlatformEmailQueries(PlatformEmailQueryInterface):
    def __init__(self, db: Session) -> None:
        self.db = db

    def email_exists(self, email: str, exclude_account_id: UUID | None = None) -> bool:
        statement = select(PlatformAccount.id).where(PlatformAccount.email == normalize_email(email))
        if exclude_account_id is not None:
            statement = statement.where(PlatformAccount.id != exclude_account_id)
        return self.db.scalar(statement.limit(1)) is not None
