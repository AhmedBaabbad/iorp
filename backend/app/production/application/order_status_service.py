"""Applies production order status transitions. Nothing else writes ProductionOrder.status.

Rules come from domain.order_lifecycle; this service adds locking, permissions (a predicate
supplied by the API layer), preconditions, actual dates, history and the audit log.
"""
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from app.production.application import notices
from app.core.interfaces import approvals
from app.core.db import Base
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.production.application.allocation_service import AllocationLifecycleService
from app.production.domain import order_lifecycle as lifecycle
from app.production.domain.enums import OrderTransitionTrigger as Trigger, ProductionOrderStatus as S
from app.production.domain.order_lifecycle import TransitionError
from app.production.infrastructure.demand_repository import ProductionDemandRepository
from app.production.application.result_service import close_readiness
from app.core.interfaces.order_close_guards import close_blockers
from app.production.infrastructure.models import ProductionOrder, ProductionOrderStatusHistory

PermissionCheck = Callable[[str], bool]


def organization_today(db, organization_id):
    """The calendar date at the organization's location; planned dates are local, not UTC."""
    # Shared-table read, as elsewhere in production: no foundation model import.
    organizations = Base.metadata.tables["foundation_organizations"]
    zone = db.scalar(select(organizations.c.timezone).where(organizations.c.id == organization_id))
    try:
        return datetime.now(ZoneInfo(zone or "UTC")).date()
    except ZoneInfoNotFoundError:
        return utc_now().date()


def _record(db, order, action, *, trigger, actor_user_id, reason, now):
    """The single write of an order's status: target, actual dates, version and history."""
    previous = S(order.status)
    order.status = action.target
    if action.target == S.IN_PROGRESS and order.actual_start_at is None:
        order.actual_start_at = now  # first start only; resuming keeps the original start
    if action.target == S.COMPLETED:
        order.actual_end_at = now
    order.status_version += 1
    order.updated_at = now
    db.add(ProductionOrderStatusHistory(organization_id=order.organization_id, production_order_id=order.id, from_status=previous.value,
                                        to_status=action.target.value, action=action.name, trigger=trigger.value,
                                        actor_user_id=actor_user_id, reason=(reason or "").strip() or None, created_at=now))
    return previous


class OrderStatusService:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant
        self.org_id = tenant.organization_id

    # ---- reads -----------------------------------------------------------------------

    def describe(self, order, can: PermissionCheck):
        """Lifecycle facts for the UI, including only the actions this user may take now."""
        today = organization_today(self.db, self.org_id)
        return dict(
            status_version=order.status_version, actual_start_at=order.actual_start_at, actual_end_at=order.actual_end_at,
            start_overdue=lifecycle.start_overdue(order.status, order.planned_start_date, today),
            finish_overdue=lifecycle.finish_overdue(order.status, order.planned_end_date, today),
            terminal=S(order.status) in lifecycle.TERMINAL,
            actions=[dict(action=a.name, target=a.target.value, requires_reason=a.requires_reason, confirm=a.confirm)
                     for a in lifecycle.available(order.status) if can(a.permission)],
        )

    def history(self, order_id):
        if self.db.scalar(select(ProductionOrder.id).where(ProductionOrder.organization_id == self.org_id, ProductionOrder.id == order_id)) is None:
            raise TransitionError("PRODUCTION_ORDER_NOT_FOUND", 404)
        return list(self.db.scalars(select(ProductionOrderStatusHistory).where(
            ProductionOrderStatusHistory.organization_id == self.org_id,
            ProductionOrderStatusHistory.production_order_id == order_id,
        ).order_by(ProductionOrderStatusHistory.created_at, ProductionOrderStatusHistory.id)))

    # ---- writes ----------------------------------------------------------------------

    def transition(self, order_id, action_name: str, *, can: PermissionCheck, reason: str | None = None, expected_version: int | None = None,
                   zero_output: bool = False):
        """A user-requested transition (the action buttons). zero_output: close an order that produced nothing."""
        return self._apply(order_id, action_name, reason=reason, expected_version=expected_version, trigger=Trigger.MANUAL, can=can,
                           zero_output=zero_output)

    def start_from_activity(self, order_id, source: str):
        """Extension point: the first recorded production activity starts a released order.

        Not wired yet. Call it from the service that records the first production output,
        run or material issue for an order, e.g. start_from_activity(order.id, "production_run").
        Does nothing unless the order is still released.
        """
        return self._apply(order_id, "start", reason=f"First activity: {source}", trigger=Trigger.ACTIVITY, only_from=S.RELEASED)

    def _lock(self, order_id):
        order = self.db.scalar(select(ProductionOrder).where(ProductionOrder.organization_id == self.org_id, ProductionOrder.id == order_id)
                               .with_for_update().execution_options(populate_existing=True))
        if order is None:
            raise TransitionError("PRODUCTION_ORDER_NOT_FOUND", 404)
        return order

    def _apply(self, order_id, action_name, *, reason, trigger, expected_version=None, can: PermissionCheck | None = None, only_from=None,
               zero_output=False):
        db = self.db
        try:
            # Same first lock as allocation and demand writes, so a cancellation and a
            # planner's edit can never interleave.
            ProductionDemandRepository(db).lock_organization(self.org_id)
            order = self._lock(order_id)
            if only_from is not None and S(order.status) != only_from:
                db.rollback()  # automatic triggers are idempotent: nothing to do
                return order
            if expected_version is not None and expected_version != order.status_version:
                raise TransitionError("ORDER_STATUS_CHANGED", 409, current_status=S(order.status).value, status_version=order.status_version)
            action = lifecycle.resolve(order.status, action_name, reason)
            if trigger == Trigger.MANUAL and not (can and can(action.permission)):
                raise TransitionError("ACTION_FORBIDDEN", 403, action=action.name, permission=action.permission)
            released = self._preconditions(order, action, reason, zero_output)
            actor = self.tenant.user_id if trigger == Trigger.MANUAL else None
            if trigger == Trigger.MANUAL and action.name in ("release", "close"):
                approvals.sign(db, self.tenant, "production_order", order.id, action.name, action.permission, reason)
            previous = _record(db, order, action, trigger=trigger, actor_user_id=actor, reason=reason, now=utc_now())
            details = dict(action=action.name, from_status=previous.value, to_status=action.target.value, trigger=trigger.value, reason=reason or "")
            if released is not None:
                details["released_allocations"] = len(released)
            if zero_output:
                details["zero_output"] = True
            get_registered_activity_logger().log_activity(db, self.org_id, "production_order.status_changed", "production_order", order.id,
                                                          order.production_order_number, actor_id=actor, details={k: str(v) for k, v in details.items()})
            notices.order_status_changed(db, self.tenant, order, action.name, actor)
            db.commit()
            db.expire_all()
            return db.get(ProductionOrder, order.id)
        except Exception:
            db.rollback()
            raise

    def _preconditions(self, order, action, reason, zero_output=False):
        if action.name == "release" and not (order.planned_quantity and order.planned_quantity > Decimal(0)):
            raise TransitionError("ORDER_HAS_NO_QUANTITY", 409)
        if action.name == "release" and order.allocations and not any(a.status == "active" for a in order.allocations):
            raise TransitionError("ORDER_HAS_NO_ACTIVE_ALLOCATIONS", 409)
        if zero_output and action.name != "close":
            raise TransitionError("ZERO_OUTPUT_ONLY_ON_CLOSE", 400)
        if action.name == "close":
            self._close_guard(order, reason, zero_output)
        if action.name == "cancel":
            # Cancelling returns every reserved quantity to planning in the same transaction.
            return AllocationLifecycleService(self.db, self.tenant).release_all_for_cancellation(order, reason)
        return None


    def _close_guard(self, order, reason, zero_output):
        """Closing freezes the final result: it needs result entries (one per item for multi-item
        orders), or an explicit zero-output confirmation with a reason. Runs under the order lock."""
        # Other modules' blockers first (e.g. quality checks still open, rejections without a decision).
        blockers = close_blockers(self.db, self.org_id, order.id)
        if blockers:
            raise TransitionError("CLOSE_BLOCKED", 409, blockers=[dict(code=b.code, count=b.count, **b.detail) for b in blockers])
        readiness = close_readiness(self.db, self.org_id, order)
        if zero_output:
            if readiness["has_entries"]:
                raise TransitionError("ZERO_OUTPUT_WITH_ENTRIES", 409)
            if not (reason or "").strip():
                raise TransitionError("REASON_REQUIRED", 400, action="close")
            return
        if not readiness["has_entries"]:
            raise TransitionError("RESULT_REQUIRED_TO_CLOSE", 409)
        if readiness["missing_item_ids"]:
            raise TransitionError("RESULT_MISSING_FOR_ITEMS", 409, missing_item_ids=[str(i) for i in readiness["missing_item_ids"]])


def auto_start_due_orders(db, today=None, now=None):
    """Scheduled job: start released orders whose planned start date has come. Idempotent.

    Only runs when PRODUCTION_AUTO_START_BY_DATE is enabled. Rows locked by a user action
    are skipped and picked up on the next run; an order already started is never touched.
    """
    started = 0
    # Each organization's own date decides; `today` pins the date for every organization (tests, backfills).
    horizon = today or (utc_now() + timedelta(days=1)).date()
    candidates = db.execute(select(ProductionOrder.id, ProductionOrder.organization_id, ProductionOrder.planned_start_date)
                            .where(ProductionOrder.status == S.RELEASED, ProductionOrder.planned_start_date <= horizon)).all()
    local_today = {}
    for order_id, organization_id, planned_start in candidates:
        if organization_id not in local_today:
            local_today[organization_id] = today or organization_today(db, organization_id)
        if planned_start > local_today[organization_id]:
            continue
        order = db.scalar(select(ProductionOrder).where(ProductionOrder.id == order_id, ProductionOrder.status == S.RELEASED)
                          .with_for_update(skip_locked=True).execution_options(populate_existing=True))
        if order is None:
            db.rollback()
            continue
        _record(db, order, lifecycle.ACTIONS["start"], trigger=Trigger.SCHEDULE, actor_user_id=None,
                reason="Planned start date reached", now=now or utc_now())
        db.commit()
        started += 1
    return started
