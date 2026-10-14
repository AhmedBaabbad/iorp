from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class QuoteTermsSnapshot(Base):
    """Immutable bilingual terms for one issued revision; never read live settings for it."""
    __tablename__ = 'commercial_quote_terms_snapshots'
    __table_args__ = (UniqueConstraint('quote_id', 'revision', name='uq_quote_terms_revision'),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    quote_id: Mapped[UUID] = mapped_column(ForeignKey('commercial_quotes.id', ondelete='CASCADE'), index=True)
    revision: Mapped[int]
    terms: Mapped[list] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(32), default='issued')
    captured_by: Mapped[UUID | None] = mapped_column(ForeignKey('foundation_users.id'))
    captured_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)
