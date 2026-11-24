"""Audited scheduling changes, serialized against status transitions and allocations."""
from sqlalchemy import select
from app.core.db import Base
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.production.domain.order_lifecycle import TransitionError, validate_reschedule
from app.production.infrastructure.models import ProductionOrder


def audit_reschedule(db, tenant, order, old_start, old_end, reason=None):
    users = Base.metadata.tables["foundation_users"]
    actor_name = db.scalar(select(users.c.full_name).where(users.c.id == tenant.user_id, users.c.organization_id == tenant.organization_id))
    get_registered_activity_logger().log_activity_strict(db, tenant.organization_id, "production_order.rescheduled", "production_order",
        entity_id=order.id, entity_name=order.production_order_number, actor_id=tenant.user_id, actor_name=actor_name,
        details=dict(old_start=old_start.isoformat(), new_start=order.planned_start_date.isoformat(),
                     old_end=old_end.isoformat(), new_end=order.planned_end_date.isoformat(), reason=reason))


def reschedule_history(db, organization_id, order_id):
    # Shared-table projection, like the production status actor lookup; no foreign model imports.
    logs = Base.metadata.tables["foundation_activity_log"]
    return [dict(id=row.id, created_at=row.created_at, actor_user_id=row.actor_id, actor_name=row.actor_name, **(row.details or {}))
            for row in db.execute(select(logs).where(logs.c.organization_id == organization_id, logs.c.entity_type == "production_order",
                logs.c.entity_id == order_id, logs.c.action == "production_order.rescheduled").order_by(logs.c.created_at, logs.c.id))]


class OrderRescheduleService:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant

    def reschedule(self, order_id, data):
        order = self.db.scalar(select(ProductionOrder).where(ProductionOrder.organization_id == self.tenant.organization_id,
            ProductionOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order is None:
            raise TransitionError("PRODUCTION_ORDER_NOT_FOUND", 404)
        reason = data.reason.strip()
        if not 3 <= len(reason) <= 500:
            raise TransitionError("RESCHEDULE_REASON_INVALID", 400)
        start, end = data.planned_start_date or order.planned_start_date, data.planned_end_date
        validate_reschedule(order, start, end)
        old_start, old_end = order.planned_start_date, order.planned_end_date
        try:
            order.planned_start_date, order.planned_end_date = start, end
            order.updated_at = utc_now()
            audit_reschedule(self.db, self.tenant, order, old_start, old_end, reason)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(order)
        return order
