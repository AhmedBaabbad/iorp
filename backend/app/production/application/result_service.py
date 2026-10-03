"""Final order result (PROD-OUTPUT-001): the only place that writes ProductionResultEntry.

Rules and formulas live in domain/result_rules.py. Every write locks the production order
row first and re-reads its status under the lock, so an entry can never slip in after the
order is closed, and two users cannot push customer_good past the allocation together.
The close guard itself lives in OrderStatusService, which calls close_readiness() here.
"""
from collections import defaultdict
from collections.abc import Callable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.db import Base
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.production.domain import result_rules as rules
from app.production.domain.enums import ProductionOrderStatus as S, ResultDisposition as D, ResultEntryType as T
from app.production.domain.result_rules import ResultError
from app.production.infrastructure.models import ProductionAllocation, ProductionOrder, ProductionResultEntry

PermissionCheck = Callable[[str], bool]
from app.production.domain.permissions import RESULT_ACTIONS
EDITABLE_FIELDS = ("production_order_item_id", "disposition", "quantity", "unit", "secondary_quantity", "secondary_unit",
                   "counts_as_loss", "reason_code", "notes")


def close_readiness(db, organization_id, order):
    """What the close guard needs: whether entries exist, and which items still have none."""
    counted = dict(db.execute(select(ProductionResultEntry.production_order_item_id, func.count()).where(
        ProductionResultEntry.organization_id == organization_id, ProductionResultEntry.production_order_id == order.id,
        ProductionResultEntry.entry_type == T.ORIGINAL.value).group_by(ProductionResultEntry.production_order_item_id)).all())
    missing = [item.id for item in sorted(order.items, key=lambda i: i.line_no) if not counted.get(item.id)] if len(order.items) > 1 else []
    return dict(has_entries=bool(counted), missing_item_ids=missing)


class OrderResultService:
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
            raise ResultError("PRODUCTION_ORDER_NOT_FOUND", 404)
        return order

    def _entries(self, order_id):
        return list(self.db.scalars(select(ProductionResultEntry).where(
            ProductionResultEntry.organization_id == self.org_id, ProductionResultEntry.production_order_id == order_id,
        ).order_by(ProductionResultEntry.created_at, ProductionResultEntry.id)))

    def _entry(self, order, entry_id, lock=False):
        query = select(ProductionResultEntry).where(ProductionResultEntry.organization_id == self.org_id,
                                                    ProductionResultEntry.production_order_id == order.id, ProductionResultEntry.id == entry_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        entry = self.db.scalar(query)
        if entry is None:
            raise ResultError("RESULT_ENTRY_NOT_FOUND", 404)
        return entry

    def _item(self, order, item_id):
        """C4: auto-assigned for a single item, required for several, and it must belong to this order."""
        if not order.items:
            if item_id is not None:
                raise ResultError("ORDER_ITEM_NOT_IN_ORDER", 422)
            return None
        if item_id is None:
            if len(order.items) == 1:
                return order.items[0]
            raise ResultError("ORDER_ITEM_REQUIRED", 422)
        item = next((i for i in order.items if i.id == item_id), None)
        if item is None:
            raise ResultError("ORDER_ITEM_NOT_IN_ORDER", 422)
        return item

    def _allocations(self, order):
        """Active customer allocations: per item when the allocations carry items, otherwise per order and unit."""
        rows = self.db.execute(select(ProductionAllocation.production_order_item_id, ProductionAllocation.unit, ProductionAllocation.allocated_quantity).where(
            ProductionAllocation.organization_id == self.org_id, ProductionAllocation.production_order_id == order.id,
            ProductionAllocation.status == "active")).all()
        item_level = any(item_id is not None for item_id, _, _ in rows)
        per_item, per_unit = defaultdict(lambda: Decimal(0)), defaultdict(lambda: Decimal(0))
        for item_id, unit, quantity in rows:
            per_unit[unit] += quantity
            if item_id is not None:
                per_item[item_id] += quantity
        level = "item" if item_level else ("order" if rows else "none")
        return level, dict(per_item), dict(per_unit)

    def _allocated_for(self, order, item, unit):
        level, per_item, per_unit = self._allocations(order)
        if level == "item":
            return per_item.get(item.id) if item is not None else None
        return per_unit.get(unit) if level == "order" else None

    def _customer_good(self, order, item, unit, exclude_id=None):
        """Effective customer_good in the cap's scope: the item (item-level allocation) or the whole order in this unit."""
        level, _, _ = self._allocations(order)
        query = select(func.coalesce(func.sum(ProductionResultEntry.quantity), 0)).where(
            ProductionResultEntry.organization_id == self.org_id, ProductionResultEntry.production_order_id == order.id,
            ProductionResultEntry.disposition == D.CUSTOMER_GOOD.value, ProductionResultEntry.unit == unit)
        if level == "item":
            query = query.where(ProductionResultEntry.production_order_item_id == (item.id if item else None))
        if exclude_id is not None:
            query = query.where(ProductionResultEntry.id != exclude_id)
        return Decimal(self.db.scalar(query))

    def _check_cap(self, order, item, unit, adding, exclude_id=None):
        rules.assert_customer_cap(self._allocated_for(order, item, unit), self._customer_good(order, item, unit, exclude_id), Decimal(adding))

    def _effective(self, original):
        corrections = self.db.execute(select(
            func.coalesce(func.sum(ProductionResultEntry.quantity), 0), func.coalesce(func.sum(ProductionResultEntry.secondary_quantity), 0)).where(
            ProductionResultEntry.organization_id == self.org_id, ProductionResultEntry.corrects_entry_id == original.id)).one()
        return original.quantity + Decimal(corrections[0]), (original.secondary_quantity or Decimal(0)) + Decimal(corrections[1])

    def _audit(self, action, order, entry, **details):
        get_registered_activity_logger().log_activity(
            self.db, self.org_id, action, "production_result_entry", entry.id, order.production_order_number,
            actor_id=self.tenant.user_id, details={k: str(v) for k, v in dict(production_order_id=order.id, **details).items()})

    def _commit(self):
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ResultError("RESULT_ENTRY_INVALID", 422) from exc
        self.db.expire_all()

    def _locked_order(self, order_id):
        self._order(order_id)  # 404 before taking any lock
        return self._order(order_id, lock=True)

    def _validated(self, order, values):
        """Checks shared by create and edit; returns the item, unit and loss flag to store."""
        item = self._item(order, values.get("production_order_item_id"))
        unit = item.unit if item is not None else order.unit
        if values.get("unit") not in (None, unit):
            raise ResultError("UNIT_MISMATCH", 422, expected_unit=unit, unit=values.get("unit"))
        if (values.get("secondary_quantity") is None) != (values.get("secondary_unit") is None):
            raise ResultError("SECONDARY_MEASURE_INCOMPLETE", 422)
        if values.get("secondary_quantity") is not None and values["secondary_quantity"] <= 0:
            raise ResultError("SECONDARY_QUANTITY_NOT_POSITIVE", 422)
        counts_as_loss = rules.resolve_counts_as_loss(values["disposition"], values.get("counts_as_loss"))
        return item, unit, counts_as_loss

    # ---- writes -------------------------------------------------------------------------

    def create(self, order_id, data):
        try:
            order = self._locked_order(order_id)
            rules.assert_writable(order.status)
            values = data.model_dump()
            item, unit, counts_as_loss = self._validated(order, values)
            if D(values["disposition"]) == D.CUSTOMER_GOOD:
                self._check_cap(order, item, unit, values["quantity"])
            entry = ProductionResultEntry(
                organization_id=self.org_id, production_order_id=order.id, production_order_item_id=item.id if item else None,
                disposition=D(values["disposition"]).value, quantity=values["quantity"], unit=unit,
                secondary_quantity=values.get("secondary_quantity"), secondary_unit=values.get("secondary_unit"),
                counts_as_loss=counts_as_loss, reason_code=values.get("reason_code"), notes=values.get("notes"),
                entry_type=T.ORIGINAL.value, created_by_user_id=self.tenant.user_id)
            self.db.add(entry)
            self.db.flush()
            self._audit("production_result.created", order, entry, disposition=entry.disposition, quantity=entry.quantity, unit=unit)
            self._commit()
            return entry.id
        except Exception:
            self.db.rollback()
            raise

    def update(self, order_id, entry_id, data):
        try:
            order = self._locked_order(order_id)
            rules.assert_writable(order.status)
            entry = self._entry(order, entry_id, lock=True)
            changes = data.model_dump(exclude_unset=True)
            values = {f: getattr(entry, f) for f in EDITABLE_FIELDS} | changes
            if "disposition" in changes and "counts_as_loss" not in changes:
                values["counts_as_loss"] = None  # a new disposition decides its own loss flag
            if "unit" not in changes:
                values["unit"] = None  # re-derived from the (possibly new) item
            item, unit, counts_as_loss = self._validated(order, values)
            if D(values["disposition"]) == D.CUSTOMER_GOOD:
                self._check_cap(order, item, unit, values["quantity"], exclude_id=entry.id)
            entry.production_order_item_id = item.id if item else None
            entry.disposition, entry.quantity, entry.unit = D(values["disposition"]).value, values["quantity"], unit
            entry.secondary_quantity, entry.secondary_unit = values["secondary_quantity"], values["secondary_unit"]
            entry.counts_as_loss, entry.reason_code, entry.notes = counts_as_loss, values["reason_code"], values["notes"]
            entry.updated_by_user_id = self.tenant.user_id
            self.db.flush()
            self._audit("production_result.updated", order, entry, fields=",".join(sorted(changes)))
            self._commit()
            return entry.id
        except Exception:
            self.db.rollback()
            raise

    def delete(self, order_id, entry_id):
        try:
            order = self._locked_order(order_id)
            rules.assert_writable(order.status)
            entry = self._entry(order, entry_id, lock=True)
            self._audit("production_result.deleted", order, entry, disposition=entry.disposition, quantity=entry.quantity)
            self.db.delete(entry)
            self._commit()
        except Exception:
            self.db.rollback()
            raise

    def correct(self, order_id, entry_id, data):
        """A signed delta against an original entry of a closed order; the original is never changed."""
        try:
            order = self._locked_order(order_id)
            rules.assert_correctable(order.status)
            original = self._entry(order, entry_id, lock=True)
            if original.entry_type != T.ORIGINAL.value:
                raise ResultError("CORRECT_THE_ORIGINAL", 422, original_id=str(original.corrects_entry_id))
            if data.secondary_quantity is not None and original.secondary_unit is None:
                raise ResultError("SECONDARY_MEASURE_NOT_SET", 422)
            effective, effective_secondary = self._effective(original)
            rules.assert_effective_not_negative(effective, data.quantity)
            if data.secondary_quantity is not None:
                rules.assert_effective_not_negative(effective_secondary, data.secondary_quantity, field="secondary_quantity")
            item = next((i for i in order.items if i.id == original.production_order_item_id), None)
            if D(original.disposition) == D.CUSTOMER_GOOD and data.quantity > 0:
                self._check_cap(order, item, original.unit, data.quantity)
            correction = ProductionResultEntry(
                organization_id=self.org_id, production_order_id=order.id, production_order_item_id=original.production_order_item_id,
                disposition=original.disposition, quantity=data.quantity, unit=original.unit,
                secondary_quantity=data.secondary_quantity, secondary_unit=original.secondary_unit if data.secondary_quantity is not None else None,
                counts_as_loss=original.counts_as_loss, reason_code=original.reason_code, entry_type=T.CORRECTION.value,
                corrects_entry_id=original.id, correction_reason=data.correction_reason, created_by_user_id=self.tenant.user_id)
            self.db.add(correction)
            self.db.flush()
            self._audit("production_result.corrected", order, correction, corrects_entry_id=original.id, quantity=data.quantity, reason=data.correction_reason)
            self._commit()
            return correction.id
        except Exception:
            self.db.rollback()
            raise

    # ---- read ---------------------------------------------------------------------------

    def overview(self, status=None):
        """Completed and closed orders with their result totals, for the results list. Three queries in all."""
        statuses = [S(status)] if status else sorted(rules.AVAILABLE, key=lambda s: s.value)
        if any(s not in rules.AVAILABLE for s in statuses):
            return []
        orders = list(self.db.scalars(select(ProductionOrder).where(
            ProductionOrder.organization_id == self.org_id, ProductionOrder.status.in_(statuses)).order_by(ProductionOrder.updated_at.desc())))
        ids = [o.id for o in orders]
        entries = defaultdict(list)
        if ids:
            for e in self.db.scalars(select(ProductionResultEntry).where(
                    ProductionResultEntry.organization_id == self.org_id, ProductionResultEntry.production_order_id.in_(ids))):
                entries[e.production_order_id].append(e)
        allocated = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
        if ids:
            for order_id, unit, quantity in self.db.execute(select(ProductionAllocation.production_order_id, ProductionAllocation.unit, ProductionAllocation.allocated_quantity).where(
                    ProductionAllocation.organization_id == self.org_id, ProductionAllocation.production_order_id.in_(ids), ProductionAllocation.status == "active")):
                allocated[order_id][unit] += quantity
        rows = []
        for order in orders:
            own = entries.get(order.id, [])
            planned = defaultdict(lambda: Decimal(0))
            for item in order.items:
                planned[item.unit] += item.planned_quantity
            if not order.items:
                planned[order.unit] += order.planned_quantity or Decimal(0)
            as_rule = [rules.Entry(e.production_order_item_id, e.disposition, e.quantity, e.unit, e.counts_as_loss, e.secondary_quantity, e.secondary_unit) for e in own]
            units = sorted(set(planned) | {e.unit for e in as_rule})
            # Same rule as close_readiness, from the entries already loaded.
            with_entries = {e.production_order_item_id for e in own if e.entry_type == T.ORIGINAL.value}
            missing = [i for i in order.items if i.id not in with_entries] if len(order.items) > 1 else []
            ready = S(order.status) == rules.WRITABLE and bool(with_entries) and not missing
            rows.append(dict(
                id=order.id, number=order.production_order_number, status=S(order.status).value, product_type=order.product_type,
                entry_count=sum(1 for e in own if e.entry_type == T.ORIGINAL.value), correction_count=sum(1 for e in own if e.entry_type == T.CORRECTION.value),
                ready_to_close=ready,
                totals=[dict(unit=u, **rules.summarize([e for e in as_rule if e.unit == u], planned.get(u, Decimal(0)), allocated[order.id].get(u))) for u in units],
            ))
        return rows

    def unit_totals(self, order_ids) -> dict:
        """Read-only: {(order_id, unit): summary} for completed and closed orders, in two queries.

        The same signed summary as `result` (corrections included), for reports over many orders.
        """
        ids = list(set(order_ids))
        if not ids:
            return {}
        available = set(self.db.scalars(select(ProductionOrder.id).where(
            ProductionOrder.organization_id == self.org_id, ProductionOrder.id.in_(ids), ProductionOrder.status.in_(rules.AVAILABLE))))
        grouped = defaultdict(list)
        for e in self.db.scalars(select(ProductionResultEntry).where(
                ProductionResultEntry.organization_id == self.org_id, ProductionResultEntry.production_order_id.in_(available))):
            grouped[e.production_order_id, e.unit].append(rules.Entry(e.production_order_item_id, e.disposition, e.quantity, e.unit,
                                                                      e.counts_as_loss, e.secondary_quantity, e.secondary_unit))
        return {key: rules.summarize(entries, Decimal(0), None) for key, entries in grouped.items()}

    def result(self, order_id, can: PermissionCheck):
        """Entries (corrections under their originals), per-item and per-unit summaries, and allowed actions."""
        order = self._order(order_id)
        status = S(order.status)
        entries = self._entries(order.id)
        level, per_item, per_unit = self._allocations(order)
        users = Base.metadata.tables["foundation_users"]
        ids = {e.created_by_user_id for e in entries}
        names = dict(self.db.execute(select(users.c.id, users.c.full_name).where(
            users.c.id.in_(ids), users.c.organization_id == self.org_id)).all()) if ids else {}

        as_rule = [rules.Entry(e.production_order_item_id, e.disposition, e.quantity, e.unit, e.counts_as_loss, e.secondary_quantity, e.secondary_unit)
                   for e in entries]
        items = sorted(order.items, key=lambda i: i.line_no)
        item_views = [dict(id=i.id, line_no=i.line_no, unit=i.unit, planned_quantity=i.planned_quantity, target_spec_json=i.target_spec_json,
                           allocated_quantity=per_item.get(i.id) if level == "item" else None,
                           summary=rules.summarize([e for e in as_rule if e.item_id == i.id], i.planned_quantity,
                                                   per_item.get(i.id) if level == "item" else None)) for i in items]
        # Whole-order totals, one group per unit: different units are never added together.
        planned_by_unit = defaultdict(lambda: Decimal(0))
        for i in items:
            planned_by_unit[i.unit] += i.planned_quantity
        if not items:
            planned_by_unit[order.unit] += order.planned_quantity or Decimal(0)
        units = sorted(set(planned_by_unit) | {e.unit for e in as_rule})
        totals = [dict(unit=u, **rules.summarize([e for e in as_rule if e.unit == u], planned_by_unit.get(u, Decimal(0)),
                                                 per_unit.get(u) if level != "none" else None)) for u in units]

        # Each action needs its own permission (domain/permissions.RESULT_ACTIONS) and the right order status.
        entry_actions = ([a for a in ("edit", "delete") if status == rules.WRITABLE and can(RESULT_ACTIONS[a])]
                         + (["correct"] if status == rules.CORRECTABLE and can(RESULT_ACTIONS["correct"]) else []))
        corrections = defaultdict(list)
        for e in entries:
            if e.corrects_entry_id:
                corrections[e.corrects_entry_id].append(e)
        lines = {i.id: i.line_no for i in items}

        def view(e):
            return dict(id=e.id, production_order_item_id=e.production_order_item_id, line_no=lines.get(e.production_order_item_id),
                        disposition=e.disposition, quantity=e.quantity, unit=e.unit, secondary_quantity=e.secondary_quantity,
                        secondary_unit=e.secondary_unit, counts_as_loss=e.counts_as_loss, reason_code=e.reason_code, notes=e.notes,
                        entry_type=e.entry_type, corrects_entry_id=e.corrects_entry_id, correction_reason=e.correction_reason,
                        created_by_user_id=e.created_by_user_id, created_by_name=names.get(e.created_by_user_id),
                        updated_by_user_id=e.updated_by_user_id, created_at=e.created_at, updated_at=e.updated_at)
        originals = []
        for e in entries:
            if e.entry_type != T.ORIGINAL.value:
                continue
            own = corrections.get(e.id, [])
            originals.append(view(e) | dict(
                effective_quantity=e.quantity + sum((c.quantity for c in own), Decimal(0)),
                corrections=[view(c) for c in own],
                actions=entry_actions))
        readiness = close_readiness(self.db, self.org_id, order)
        return dict(
            order=dict(id=order.id, number=order.production_order_number, status=status.value, product_type=order.product_type, unit=order.unit),
            available=status in rules.AVAILABLE, editable=status == rules.WRITABLE, locked=status == rules.CORRECTABLE,
            allocation_level=level, items=item_views, totals=totals, entries=originals,
            close_check=dict(ready=readiness["has_entries"] and not readiness["missing_item_ids"], **readiness),
            actions=["create"] if status == rules.WRITABLE and can(RESULT_ACTIONS["create"]) else [],
        )
