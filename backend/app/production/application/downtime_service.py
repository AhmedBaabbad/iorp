"""Machine downtime (PROD-DOWNTIME-001): the only place that writes DowntimeEvent.

Rules live in domain/downtime_rules.py. Every write locks the linked order row (if any) and
then the work center row, so two people cannot record overlapping stops on one machine and
nothing lands on an order after it closes.
"""
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.pagination import paginate
from app.core.db import Base
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.production.domain import downtime_rules as rules
from app.production.domain.downtime_rules import DowntimeError
from app.production.domain.enums import DowntimeCategory as C, DowntimeStatus, ProductionOrderStatus as S
from app.production.infrastructure.execution_models import ProductionRun
from app.production.infrastructure.models import DowntimeEvent, ProductionOrder, WorkCenter

PermissionCheck = Callable[[str], bool]
from app.production.domain.permissions import DOWNTIME_ACTIONS
EDITABLE = ("work_center_id", "production_order_id", "production_run_id", "start_time", "end_time", "category", "reason_code", "notes")


class DowntimeService:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant
        self.org_id = tenant.organization_id

    # ---- lookups (always tenant-scoped) -----------------------------------------------

    def _one(self, model, row_id, code, lock=False, status=404):
        query = select(model).where(model.organization_id == self.org_id, model.id == row_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self.db.scalar(query)
        if row is None:
            raise DowntimeError(code, status)
        return row

    def _event(self, event_id, lock=False):
        return self._one(DowntimeEvent, event_id, "DOWNTIME_EVENT_NOT_FOUND", lock)

    def _zone(self):
        organizations = Base.metadata.tables["foundation_organizations"]
        name = self.db.scalar(select(organizations.c.timezone).where(organizations.c.id == self.org_id))
        try:
            return ZoneInfo(name or "UTC")
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    def _resolve(self, values):
        """Run, order and work center, checked against each other; locks order then work center."""
        run = None
        if values.get("production_run_id") is not None:
            run = self._one(ProductionRun, values["production_run_id"], "RUN_NOT_FOUND", status=422)
            rules.assert_run_usable(run.status)
            if values.get("production_order_id") not in (None, run.production_order_id):
                raise DowntimeError("RUN_NOT_IN_ORDER", 422)
            if values.get("work_center_id") not in (None, run.work_center_id):
                raise DowntimeError("WORK_CENTER_MISMATCH", 422)
        order_id = run.production_order_id if run else values.get("production_order_id")
        center_id = run.work_center_id if run else values.get("work_center_id")
        if center_id is None:
            raise DowntimeError("WORK_CENTER_REQUIRED", 422)
        order = None
        if order_id is not None:
            order = self._one(ProductionOrder, order_id, "PRODUCTION_ORDER_NOT_FOUND", status=422)
            order = self._one(ProductionOrder, order_id, "PRODUCTION_ORDER_NOT_FOUND", lock=True, status=422)
            rules.assert_order_linkable(order.status)
        self._one(WorkCenter, center_id, "WORK_CENTER_NOT_FOUND", status=422)
        self._one(WorkCenter, center_id, "WORK_CENTER_NOT_FOUND", lock=True, status=422)  # serializes stops per machine
        return run, order, center_id

    def _assert_no_overlap(self, center_id, start, end, exclude_id=None):
        query = select(DowntimeEvent).where(DowntimeEvent.organization_id == self.org_id, DowntimeEvent.work_center_id == center_id)
        if exclude_id is not None:
            query = query.where(DowntimeEvent.id != exclude_id)
        if end is not None:
            query = query.where(DowntimeEvent.start_time < end)
        query = query.where((DowntimeEvent.end_time.is_(None)) | (DowntimeEvent.end_time > start))
        clash = self.db.scalar(query.order_by(DowntimeEvent.start_time).limit(1))
        if clash is not None and rules.overlaps(start, end, clash.start_time, clash.end_time):
            raise DowntimeError("DOWNTIME_OVERLAP", conflicting_event_id=str(clash.id), conflicting_start=clash.start_time.isoformat(),
                                conflicting_status=DowntimeStatus(clash.status).value)

    def _apply(self, event, values, center_id, run, order):
        start, end = values["start_time"], values.get("end_time")
        rules.assert_period(start, end, utc_now())
        self._assert_no_overlap(center_id, start, end, exclude_id=event.id)
        was_open = event.end_time is None
        event.work_center_id, event.production_run_id = center_id, run.id if run else None
        event.production_order_id = order.id if order else None
        event.start_time, event.end_time = start, end
        event.category = C(values["category"]).value
        event.planned = rules.is_planned(event.category)
        event.reason_code, event.notes = values.get("reason_code"), values.get("notes")
        event.status = DowntimeStatus.OPEN if end is None else DowntimeStatus.CLOSED
        event.duration_minutes = rules.duration_minutes(start, end)
        if end is not None and (was_open or event.closed_by_user_id is None):
            event.closed_by_user_id = self.tenant.user_id
        if end is None:
            event.closed_by_user_id = None

    def _audit(self, action, event, **details):
        get_registered_activity_logger().log_activity(
            self.db, self.org_id, action, "production_downtime_event", event.id, None, actor_id=self.tenant.user_id,
            details={k: str(v) for k, v in dict(work_center_id=event.work_center_id, **details).items()})

    def _commit(self):
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise DowntimeError("DOWNTIME_EVENT_INVALID", 422) from exc
        self.db.expire_all()

    def _assert_editable(self, event):
        if event.production_order_id is not None:
            order = self._one(ProductionOrder, event.production_order_id, "PRODUCTION_ORDER_NOT_FOUND")
            if S(order.status) == S.CLOSED:
                raise DowntimeError("DOWNTIME_LOCKED", order_status=S.CLOSED.value)

    # ---- writes -------------------------------------------------------------------------

    def create(self, data):
        try:
            values = data.model_dump()
            run, order, center_id = self._resolve(values)
            event = DowntimeEvent(organization_id=self.org_id, created_by_user_id=self.tenant.user_id)
            self._apply(event, values, center_id, run, order)
            self.db.add(event)
            self.db.flush()
            self._audit("production_downtime.created", event, category=event.category, status=DowntimeStatus(event.status).value)
            self._commit()
            return event.id
        except Exception:
            self.db.rollback()
            raise

    def update(self, event_id, data):
        try:
            event = self._event(event_id)
            self._assert_editable(event)
            changes = data.model_dump(exclude_unset=True)
            values = {f: getattr(event, f) for f in EDITABLE} | changes
            if "production_run_id" in changes and "work_center_id" not in changes and changes["production_run_id"] is not None:
                values["work_center_id"] = None  # a new run decides the machine
            if "production_run_id" in changes and "production_order_id" not in changes and changes["production_run_id"] is not None:
                values["production_order_id"] = None  # ... and the order
            run, order, center_id = self._resolve(values)
            event = self._event(event_id, lock=True)
            self._assert_editable(event)
            self._apply(event, values, center_id, run, order)
            event.updated_by_user_id = self.tenant.user_id
            self.db.flush()
            self._audit("production_downtime.updated", event, fields=",".join(sorted(changes)))
            self._commit()
            return event.id
        except Exception:
            self.db.rollback()
            raise

    def close(self, event_id, end_time=None):
        """End an open stop, now unless another end is given."""
        try:
            event = self._event(event_id)
            if event.end_time is not None:
                raise DowntimeError("DOWNTIME_ALREADY_CLOSED")
            self._assert_editable(event)
            values = {f: getattr(event, f) for f in EDITABLE} | {"end_time": end_time or utc_now()}
            run, order, center_id = self._resolve(values)
            event = self._event(event_id, lock=True)
            if event.end_time is not None:
                raise DowntimeError("DOWNTIME_ALREADY_CLOSED")
            self._apply(event, values, center_id, run, order)
            event.updated_by_user_id = self.tenant.user_id
            self.db.flush()
            self._audit("production_downtime.closed", event, duration_minutes=event.duration_minutes)
            self._commit()
            return event.id
        except Exception:
            self.db.rollback()
            raise

    def delete(self, event_id):
        try:
            event = self._event(event_id)
            self._assert_editable(event)
            if event.production_order_id is not None:
                self._one(ProductionOrder, event.production_order_id, "PRODUCTION_ORDER_NOT_FOUND", lock=True)
            event = self._event(event_id, lock=True)
            self._assert_editable(event)
            self._audit("production_downtime.deleted", event, category=event.category)
            self.db.delete(event)
            self._commit()
        except Exception:
            self.db.rollback()
            raise

    # ---- reads --------------------------------------------------------------------------

    def get(self, event_id):
        return self._event(event_id)

    def _filtered(self, work_center_id=None, production_order_id=None, production_run_id=None, category=None, planned=None,
                  status=None, date_from=None, date_to=None):
        query = select(DowntimeEvent).where(DowntimeEvent.organization_id == self.org_id)
        for column, value in ((DowntimeEvent.work_center_id, work_center_id), (DowntimeEvent.production_order_id, production_order_id),
                              (DowntimeEvent.production_run_id, production_run_id), (DowntimeEvent.category, C(category).value if category else None),
                              (DowntimeEvent.planned, planned), (DowntimeEvent.status, status)):
            if value is not None:
                query = query.where(column == value)
        # Dates are the factory's local days: a stop belongs to the day it started.
        zone = self._zone()
        def local_midnight(day):
            return datetime.combine(day, time.min, zone).astimezone(timezone.utc)
        if date_from is not None:
            query = query.where(DowntimeEvent.start_time >= local_midnight(date_from))
        if date_to is not None:
            query = query.where(DowntimeEvent.start_time < local_midnight(date_to + timedelta(days=1)))
        return query

    def list(self, params, **filters):
        """One page of stops, latest first, and the total matching the filters (ARCH-PAGE-001)."""
        return paginate(self.db, self._filtered(**filters).order_by(DowntimeEvent.start_time.desc(), DowntimeEvent.id.desc()), params)

    def labels(self, events, can: PermissionCheck):
        """Display labels and allowed actions for a page of events, in a fixed number of queries."""
        def by_id(model, ids, *columns):
            if not ids:
                return {}
            rows = self.db.execute(select(model.id, *columns).where(model.organization_id == self.org_id, model.id.in_(ids))).all()
            return {row[0]: row[1:] for row in rows}
        centers = by_id(WorkCenter, {e.work_center_id for e in events}, WorkCenter.name)
        orders = by_id(ProductionOrder, {e.production_order_id for e in events if e.production_order_id}, ProductionOrder.production_order_number, ProductionOrder.status)
        runs = by_id(ProductionRun, {e.production_run_id for e in events if e.production_run_id}, ProductionRun.run_date)
        users = Base.metadata.tables["foundation_users"]
        user_ids = {u for e in events for u in (e.created_by_user_id, e.closed_by_user_id) if u}
        names = dict(self.db.execute(select(users.c.id, users.c.full_name).where(users.c.id.in_(user_ids), users.c.organization_id == self.org_id)).all()) if user_ids else {}
        now, result = utc_now(), {}
        for e in events:
            number, status = orders.get(e.production_order_id, (None, None))
            locked = status is not None and S(status) == S.CLOSED
            # Each action needs its own permission (domain/permissions.DOWNTIME_ACTIONS); a closed order locks them all.
            offered = (["close"] if e.end_time is None else []) + ["edit", "delete"]
            actions = [] if locked else [a for a in offered if can(DOWNTIME_ACTIONS[a])]
            result[e.id] = dict(
                work_center_name=centers.get(e.work_center_id, (None,))[0], order_number=number, order_status=S(status).value if status else None,
                run_date=runs.get(e.production_run_id, (None,))[0], created_by_name=names.get(e.created_by_user_id),
                closed_by_name=names.get(e.closed_by_user_id),
                # An open stop keeps growing: minutes so far, for the screen only.
                elapsed_minutes=rules.elapsed_minutes(e.start_time, now) if e.end_time is None else None,
                actions=actions)
        return result

    def summary(self, **filters):
        """Totals for reports: closed stops only; open ones are counted apart with their minutes so far."""
        events = list(self.db.scalars(self._filtered(**filters)))
        names = dict(self.db.execute(select(WorkCenter.id, WorkCenter.name).where(WorkCenter.organization_id == self.org_id,
                                                                                WorkCenter.id.in_({e.work_center_id for e in events}))).all()) if events else {}
        now = utc_now()
        closed = [e for e in events if e.end_time is not None]
        open_ = [e for e in events if e.end_time is None]
        minutes = lambda rows: sum((e.duration_minutes for e in rows), Decimal(0))  # noqa: E731
        by_category = defaultdict(list)
        by_center = defaultdict(list)
        for e in closed:
            by_category[e.category].append(e)
            by_center[e.work_center_id].append(e)
        breakdowns = by_category.get(C.BREAKDOWN.value, [])
        return dict(
            count=len(closed), total_minutes=minutes(closed),
            planned_minutes=minutes([e for e in closed if e.planned]), unplanned_minutes=minutes([e for e in closed if not e.planned]),
            open_count=len(open_), open_minutes_so_far=sum((rules.elapsed_minutes(e.start_time, now) for e in open_), Decimal(0)),
            # Mean time to repair: average length of a closed breakdown.
            mttr_minutes=(minutes(breakdowns) / len(breakdowns)).quantize(Decimal("0.01")) if breakdowns else None,
            by_category=sorted([dict(category=c, planned=rules.is_planned(c), count=len(rows), minutes=minutes(rows)) for c, rows in by_category.items()],
                               key=lambda r: -r["minutes"]),
            by_work_center=sorted([dict(work_center_id=w, work_center_name=names.get(w), count=len(rows), minutes=minutes(rows),
                                        unplanned_minutes=minutes([e for e in rows if not e.planned])) for w, rows in by_center.items()],
                                  key=lambda r: -r["minutes"]),
        )
