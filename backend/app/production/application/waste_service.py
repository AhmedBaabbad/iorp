"""Operational waste records (PROD-WASTE-001): the only place that writes WasteRecord.

Rules live in domain/waste_rules.py. Every write locks the production order row first and
re-reads its status under the lock, so no record slips in after the order is closed.
"""
from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.db import Base
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.production.domain import waste_rules as rules
from app.production.domain.enums import ProductionOrderStatus as S, WasteCategory
from app.production.domain.waste_rules import WasteError
from app.production.infrastructure.execution_models import ProductionRun
from app.production.infrastructure.models import ProductionOrder, ProductionOrderItem, WasteRecord, WorkCenter

PermissionCheck = Callable[[str], bool]
from app.production.domain.permissions import WASTE_ACTIONS
EDITABLE = ("production_order_item_id", "production_run_id", "work_center_id", "waste_date", "quantity_wasted", "unit",
            "waste_category", "reason_code", "notes")


class WasteService:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant
        self.org_id = tenant.organization_id

    # ---- lookups (always tenant-scoped) -----------------------------------------------

    def _order(self, order_id, lock=False):
        query = select(ProductionOrder).where(ProductionOrder.organization_id == self.org_id, ProductionOrder.id == order_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        order = self.db.scalar(query)
        if order is None:
            raise WasteError("PRODUCTION_ORDER_NOT_FOUND", 404)
        return order

    def _record(self, record_id, lock=False):
        query = select(WasteRecord).where(WasteRecord.organization_id == self.org_id, WasteRecord.id == record_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        record = self.db.scalar(query)
        if record is None:
            raise WasteError("WASTE_RECORD_NOT_FOUND", 404)
        return record

    def _item(self, order, item_id):
        if item_id is not None and not any(i.id == item_id for i in order.items):
            raise WasteError("ORDER_ITEM_NOT_IN_ORDER", 422)
        return item_id

    def _run(self, order, run_id):
        if run_id is None:
            return None
        run = self.db.scalar(select(ProductionRun).where(ProductionRun.organization_id == self.org_id, ProductionRun.id == run_id))
        if run is None:
            raise WasteError("RUN_NOT_IN_ORDER", 422)
        rules.assert_run_usable(run.production_order_id, order.id, run.status)
        return run

    def _work_center(self, order, run, requested):
        center_id = rules.resolve_work_center(requested, run.work_center_id if run else None, order.work_center_id)
        if self.db.scalar(select(WorkCenter.id).where(WorkCenter.organization_id == self.org_id, WorkCenter.id == center_id)) is None:
            raise WasteError("WORK_CENTER_NOT_FOUND", 422)
        return center_id

    def _audit(self, action, order, record, **details):
        get_registered_activity_logger().log_activity(
            self.db, self.org_id, action, "production_waste_record", record.id, order.production_order_number,
            actor_id=self.tenant.user_id, details={k: str(v) for k, v in dict(production_order_id=order.id, **details).items()})

    def _commit(self):
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise WasteError("WASTE_RECORD_INVALID", 422) from exc
        self.db.expire_all()

    def _locked_order(self, order_id):
        self._order(order_id)  # 404 before taking any lock
        return self._order(order_id, lock=True)

    # ---- writes -------------------------------------------------------------------------

    def create(self, data):
        try:
            order = self._locked_order(data.production_order_id)
            rules.assert_writable(order.status)
            run = self._run(order, data.production_run_id)
            rules.assert_unit(data.unit)
            record = WasteRecord(
                organization_id=self.org_id, production_order_id=order.id, production_order_item_id=self._item(order, data.production_order_item_id),
                production_run_id=run.id if run else None, work_center_id=self._work_center(order, run, data.work_center_id),
                waste_date=data.waste_date, quantity_wasted=data.quantity_wasted, unit=data.unit,
                waste_category=WasteCategory(data.waste_category).value, reason_code=data.reason_code, notes=data.notes,
                created_by_user_id=self.tenant.user_id)
            self.db.add(record)
            self.db.flush()
            self._audit("production_waste.created", order, record, category=record.waste_category, quantity=record.quantity_wasted, unit=record.unit)
            self._commit()
            return record.id
        except Exception:
            self.db.rollback()
            raise

    def update(self, record_id, data):
        try:
            order_id = self._record(record_id).production_order_id
            order = self._locked_order(order_id)
            rules.assert_writable(order.status)
            record = self._record(record_id, lock=True)
            changes = data.model_dump(exclude_unset=True)
            values = {f: getattr(record, f) for f in EDITABLE} | changes
            run = self._run(order, values["production_run_id"])
            # A new run decides the work center unless one is given with it.
            requested = changes.get("work_center_id") if ("production_run_id" in changes or "work_center_id" in changes) else (None if run else record.work_center_id)
            record.production_order_item_id = self._item(order, values["production_order_item_id"])
            record.production_run_id = run.id if run else None
            record.work_center_id = self._work_center(order, run, requested)
            # A record flagged at migration (unit not in the list) cannot be saved until a unit from the list is chosen.
            rules.assert_unit(values["unit"])
            record.waste_date, record.quantity_wasted, record.unit = values["waste_date"], values["quantity_wasted"], values["unit"]
            record.unit_needs_review = False
            record.waste_category = WasteCategory(values["waste_category"]).value
            record.reason_code, record.notes = values["reason_code"], values["notes"]
            record.updated_by_user_id = self.tenant.user_id
            self.db.flush()
            self._audit("production_waste.updated", order, record, fields=",".join(sorted(changes)))
            self._commit()
            return record.id
        except Exception:
            self.db.rollback()
            raise

    def delete(self, record_id):
        try:
            order = self._locked_order(self._record(record_id).production_order_id)
            rules.assert_writable(order.status)
            record = self._record(record_id, lock=True)
            self._audit("production_waste.deleted", order, record, category=record.waste_category, quantity=record.quantity_wasted)
            self.db.delete(record)
            self._commit()
        except Exception:
            self.db.rollback()
            raise

    # ---- reads --------------------------------------------------------------------------

    def get(self, record_id):
        return self._record(record_id)

    def list(self, production_order_id=None, production_run_id=None, work_center_id=None, waste_category=None, date_from=None, date_to=None):
        query = select(WasteRecord).where(WasteRecord.organization_id == self.org_id)
        for column, value in ((WasteRecord.production_order_id, production_order_id), (WasteRecord.production_run_id, production_run_id),
                              (WasteRecord.work_center_id, work_center_id),
                              (WasteRecord.waste_category, WasteCategory(waste_category).value if waste_category else None)):
            if value is not None:
                query = query.where(column == value)
        if date_from is not None:
            query = query.where(WasteRecord.waste_date >= date_from)
        if date_to is not None:
            query = query.where(WasteRecord.waste_date <= date_to)
        return list(self.db.scalars(query.order_by(WasteRecord.waste_date.desc(), WasteRecord.created_at.desc())))

    def labels(self, records, can: PermissionCheck):
        """Display labels and allowed actions for a page of records, in a fixed number of queries."""
        def by_id(model, ids, *columns):
            if not ids:
                return {}
            rows = self.db.execute(select(model.id, *columns).where(model.organization_id == self.org_id, model.id.in_(ids))).all()
            return {row[0]: row[1:] for row in rows}
        orders = by_id(ProductionOrder, {r.production_order_id for r in records}, ProductionOrder.production_order_number, ProductionOrder.status)
        centers = by_id(WorkCenter, {r.work_center_id for r in records}, WorkCenter.name)
        runs = by_id(ProductionRun, {r.production_run_id for r in records if r.production_run_id}, ProductionRun.run_date)
        users = Base.metadata.tables["foundation_users"]
        user_ids = {r.created_by_user_id for r in records}
        names = dict(self.db.execute(select(users.c.id, users.c.full_name).where(users.c.id.in_(user_ids), users.c.organization_id == self.org_id)).all()) if user_ids else {}
        items = {}
        order_ids = {r.production_order_id for r in records}
        if order_ids:
            items = dict(self.db.execute(select(ProductionOrderItem.id, ProductionOrderItem.line_no).where(ProductionOrderItem.production_order_id.in_(order_ids))).all())
        allowed = [a for a in ("edit", "delete") if can(WASTE_ACTIONS[a])]  # domain/permissions.WASTE_ACTIONS
        result = {}
        for r in records:
            number, status = orders.get(r.production_order_id, (None, None))
            open_order = status is not None and S(status) in rules.WRITABLE
            result[r.id] = dict(
                order_number=number, order_status=S(status).value if status else None, line_no=items.get(r.production_order_item_id),
                work_center_name=centers.get(r.work_center_id, (None,))[0], run_date=runs.get(r.production_run_id, (None,))[0],
                created_by_name=names.get(r.created_by_user_id), actions=allowed if open_order else [])
        return result

    def summary(self, order_id, can: PermissionCheck):
        """An order's waste: totals per unit and per category. Never added to the final result."""
        order = self._order(order_id)
        rows = self.db.execute(select(WasteRecord.waste_category, WasteRecord.unit, func.sum(WasteRecord.quantity_wasted), func.count()).where(
            WasteRecord.organization_id == self.org_id, WasteRecord.production_order_id == order.id,
        ).group_by(WasteRecord.waste_category, WasteRecord.unit)).all()
        by_unit = defaultdict(lambda: [Decimal(0), 0])
        for _, unit, quantity, count in rows:
            by_unit[unit][0] += quantity
            by_unit[unit][1] += count
        status = S(order.status)
        return dict(
            order=dict(id=order.id, number=order.production_order_number, status=status.value, unit=order.unit),
            available=status in rules.WRITABLE or status == rules.LOCKED, locked=status == rules.LOCKED,
            totals=[dict(unit=u, quantity=q, count=c) for u, (q, c) in sorted(by_unit.items())],
            by_category=[dict(category=cat, unit=u, quantity=q, count=c) for cat, u, q, c in sorted(rows, key=lambda r: (r[1], -r[2]))],
            actions=["create"] if status in rules.WRITABLE and can(WASTE_ACTIONS["create"]) else [],
        )
