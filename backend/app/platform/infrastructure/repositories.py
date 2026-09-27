from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.infrastructure.models import BootstrapState, PlatformAccount
from app.core.security import normalize_email


class PlatformAccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, account_id: UUID) -> PlatformAccount | None:
        return self.db.get(PlatformAccount, account_id)

    def get_by_email(self, email: str) -> PlatformAccount | None:
        return self.db.scalar(
            select(PlatformAccount).where(PlatformAccount.email == normalize_email(email))
        )

    def add(self, account: PlatformAccount) -> PlatformAccount:
        self.db.add(account)
        self.db.flush()
        return account


class BootstrapRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> BootstrapState | None:
        return self.db.get(BootstrapState, 1)

    def get_for_update(self) -> BootstrapState | None:
        return self.db.scalar(
            select(BootstrapState).where(BootstrapState.id == 1).with_for_update()
        )

    def add(self, state: BootstrapState) -> BootstrapState:
        self.db.add(state)
        self.db.flush()
        return state
