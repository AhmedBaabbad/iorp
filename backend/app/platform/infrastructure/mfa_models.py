"""Platform-only factors and one-use, session-bound step-up grants."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base
from app.core.utils import TZDateTime


class PlatformMFA(Base):
    __tablename__ = "platform_mfa"
    account_id: Mapped[UUID] = mapped_column(ForeignKey("system_platform_accounts.id"), primary_key=True)
    secret: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    last_counter: Mapped[int] = mapped_column(Integer, default=-1, nullable=False)
    recovery_hashes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)


class PlatformStepUp(Base):
    __tablename__ = "platform_step_up"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("system_platform_accounts.id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    binding: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
