from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.interfaces.user_credentials import OrganizationRootCredential
from app.foundation.infrastructure.models import User
from app.core.security import normalize_email, revoke_account_sessions


class FoundationUserCredentials:
    def __init__(self, db: Session) -> None:
        self.db = db

    def email_exists(self, email: str) -> bool:
        return self.db.scalar(
            select(User.id).where(User.email == normalize_email(email)).limit(1)
        ) is not None

    def get_organization_root(
        self, organization_id: UUID
    ) -> OrganizationRootCredential | None:
        user = self.db.scalar(
            select(User)
            .where(
                User.organization_id == organization_id,
                User.is_organization_root.is_(True),
            )
            .order_by(User.created_at, User.id)
            .limit(1)
        )
        if user is None:
            return None
        return OrganizationRootCredential(user.id, user.organization_id, user.email)

    def reset_user_password(self, user_id: UUID, new_password_hash: str) -> None:
        user = self.db.get(User, user_id)
        if user is None:
            raise LookupError("User not found")
        user.password_hash = new_password_hash
        user.token_version += 1
        revoke_account_sessions(self.db, "tenant", user.id, reason="password_reset")
        self.db.flush()
