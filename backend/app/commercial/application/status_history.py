"""The status history of quotations and sales orders (SALES-001): one row per step, never changed afterwards."""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.commercial.domain.lifecycle import value
from app.commercial.infrastructure.models import CommercialStatusHistory
from app.core.db import Base

QUOTE, SALES_ORDER = "quote", "sales_order"


def user_names(db: Session, organization_id: UUID, user_ids) -> dict:
    users = Base.metadata.tables["foundation_users"]
    ids = [i for i in set(user_ids) if i]
    return dict(db.execute(select(users.c.id, users.c.full_name).where(users.c.organization_id == organization_id,
                                                                     users.c.id.in_(ids))).all()) if ids else {}


def record(db: Session, organization_id: UUID, entity_type: str, entity_id: UUID, action: str, before, after,
           revision: int, actor_user_id: UUID | None, reason: str | None = None) -> None:
    db.add(CommercialStatusHistory(organization_id=organization_id, entity_type=entity_type, entity_id=entity_id, action=action,
                                   from_status=value(before) if before is not None else None, to_status=value(after),
                                   revision=revision, reason=(reason or "").strip() or None, actor_user_id=actor_user_id))


def history(db: Session, organization_id: UUID, entity_type: str, entity_id: UUID) -> list[dict]:
    rows = list(db.scalars(select(CommercialStatusHistory).where(
        CommercialStatusHistory.organization_id == organization_id, CommercialStatusHistory.entity_type == entity_type,
        CommercialStatusHistory.entity_id == entity_id).order_by(CommercialStatusHistory.created_at, CommercialStatusHistory.id)))
    names = user_names(db, organization_id, [r.actor_user_id for r in rows if r.actor_user_id])
    return [dict(action=r.action, from_status=r.from_status, to_status=r.to_status, revision=r.revision, reason=r.reason,
                 actor_name=names.get(r.actor_user_id), created_at=r.created_at) for r in rows]


def forget(db: Session, organization_id: UUID, entity_type: str, entity_id: UUID) -> None:
    """Only with the record itself, when a draft that never left the drafts is deleted."""
    db.execute(delete(CommercialStatusHistory).where(CommercialStatusHistory.organization_id == organization_id,
                                                     CommercialStatusHistory.entity_type == entity_type,
                                                     CommercialStatusHistory.entity_id == entity_id))
