from copy import deepcopy
from datetime import date
from decimal import Decimal
from pydantic import ValidationError
from sqlalchemy import select
from app.core.pagination import page_of
from app.core.db import Base
from app.core.utils import utc_now
from app.core.interfaces import sales_order_source
from app.core.interfaces.product_catalog import unknown_product_types
from app.core import numbering
from app.production.api.demand_schemas import CreateDemandItemRequest
from app.production.infrastructure.models import ProductionDemand, ProductionDemandItem
from app.production.infrastructure.demand_repository import ProductionDemandRepository, PLANNABLE


class DemandError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code = code
        self.status = status


VALID_TRANSITIONS = {
    "draft": {"ready_for_planning", "cancelled"},
    "ready_for_planning": {"draft", "cancelled"},
    "partially_planned": set(),
    "planned": set(),
    "cancelled": {"draft"},
}


class ProductionDemandService:
    def __init__(self, db, tenant, customer_lookup, quote_lookup):
        self.db, self.tenant = db, tenant
        self.customers, self.quotes = customer_lookup, quote_lookup
        self.repo = ProductionDemandRepository(db)
        self.org_id = tenant.organization_id

    def get(self, demand_id, write=False):
        if write:
            self.repo.lock_organization(self.org_id)
        row = self.repo.get(self.org_id, demand_id)
        if row is None:
            raise DemandError("demand_not_found", 404)
        return row

    def validate_references(self, customer_id, quote_id):
        if not self.customers.get_customer_summary(self.db, customer_id, self.org_id):
            raise DemandError("customer_not_found", 404)
        if quote_id:
            quote = self.quotes.get_quote_summary(self.db, quote_id, self.org_id)
            if not quote:
                raise DemandError("quote_not_found", 404)
            if quote.customer_id != customer_id:
                raise DemandError("quote_customer_mismatch")

    @staticmethod
    def editable(row):
        if row.allocations or row.status not in ("draft", "ready_for_planning"):
            raise DemandError("demand_not_editable", 409)

    # --- From a confirmed sales order (SALES-001) -------------------------------------------------------------------
    # A demand takes part (or all) of a confirmed sales order's lines. Its lines keep the order's product, specification
    # and unit; only the quantity may change, never above what the order still has. Cancelling the demand gives the
    # quantity back. transfer_key makes a repeated request (a retry, a double click) return the same demand.

    def _sales_order(self, order_id, lock=False):
        source = sales_order_source.source
        order = source.get(self.db, self.org_id, order_id, lock=lock) if source else None
        if order is None:
            raise DemandError("sales_order_not_found", 404)
        return order

    def _sent(self, order_id, excluding=None):
        """{order line id: quantity the demands in force took}, leaving out one demand (the one being changed)."""
        usage = sales_order_source.usage
        sent = dict(usage.quantities(self.db, self.org_id, order_id)) if usage else {}
        if excluding is not None and excluding.status != "cancelled":
            for item in excluding.items:
                if item.source_order_item_id:
                    sent[item.source_order_item_id] = sent.get(item.source_order_item_id, Decimal(0)) - item.required_quantity
        return sent

    @staticmethod
    def remaining(order, sent):
        return {line.id: max(Decimal(0), line.quantity - sent.get(line.id, Decimal(0))) for line in order.lines}

    def sales_orders(self, customer_id):
        """The customer's confirmed sales orders with what each line still has for production."""
        self.validate_references(customer_id, None)
        source = sales_order_source.source
        out = []
        for order in (source.list(self.db, self.org_id, customer_id) if source else []):
            sent = self._sent(order.id)
            left = self.remaining(order, sent)
            lines = [dict(id=l.id, line_no=l.line_no, product_type=l.product_type, target_spec_json=l.properties, unit=l.unit,
                          ordered_quantity=l.quantity, transferred_quantity=sent.get(l.id, Decimal(0)), remaining_quantity=left[l.id])
                     for l in order.lines]
            if any(l["remaining_quantity"] > 0 for l in lines):
                out.append(dict(id=order.id, number=order.number, quote_id=order.quote_id, requested_delivery_date=order.delivery,
                                lines=lines))
        return out

    def create_from_sales_order(self, data):
        self.repo.lock_organization(self.org_id)
        if data.transfer_key:
            done = self.db.scalar(select(ProductionDemand).where(ProductionDemand.organization_id == self.org_id,
                                                                 ProductionDemand.transfer_key == data.transfer_key))
            if done is not None:
                return done
        order = self._sales_order(data.sales_order_id, lock=True)
        if order.status != "confirmed":
            raise DemandError("sales_order_not_confirmed", 409)
        lines = {line.id: line for line in order.lines}
        left = self.remaining(order, self._sent(order.id))
        if len({w.order_item_id for w in data.lines}) != len(data.lines):
            raise DemandError("duplicate_order_line")
        for wanted in data.lines:
            if wanted.order_item_id not in lines:
                raise DemandError("sales_order_line_not_found", 404)
            if wanted.quantity > left[wanted.order_item_id]:
                raise DemandError("quantity_exceeds_remaining", 409)
        year = numbering.organization_year(self.db, self.org_id)
        counter = self.repo.lock_counter(self.org_id, year)
        counter.last_value += 1
        delivery = data.requested_delivery_date or (order.delivery.date() if order.delivery else None)
        row = ProductionDemand(organization_id=self.org_id, demand_number=f"PD-{year}-{counter.last_value:06d}",
                               created_by_user_id=self.tenant.user_id, customer_id=order.customer_id, quote_id=order.quote_id,
                               source_order_id=order.id, source_order_number=order.number, transfer_key=data.transfer_key,
                               request_date=date.today(), requested_delivery_date=delivery, priority=data.priority, notes=data.notes)
        self.db.add(row)
        for number, wanted in enumerate(sorted(data.lines, key=lambda w: lines[w.order_item_id].line_no), 1):
            line = lines[wanted.order_item_id]
            row.items.append(ProductionDemandItem(line_no=number, product_type=line.product_type, target_spec_json=deepcopy(line.properties),
                                                  required_quantity=wanted.quantity, unit=line.unit, notes=wanted.notes,
                                                  source_order_item_id=line.id))
        self.db.commit()
        return row

    def _assert_within_order(self, row, item=None, quantity=None):
        """A sales-order line never goes above what the order still has (this demand's own quantity counted back)."""
        order = self._sales_order(row.source_order_id, lock=True)
        left = self.remaining(order, self._sent(order.id, excluding=row))
        wanted = {}
        for i in row.items:
            if i.source_order_item_id:
                q = quantity if item is not None and i.id == item.id else i.required_quantity
                wanted[i.source_order_item_id] = wanted.get(i.source_order_item_id, Decimal(0)) + q
        if any(q > left.get(line, Decimal(0)) for line, q in wanted.items()):
            raise DemandError("quantity_exceeds_remaining", 409)

    def _assert_products(self, values, keep=()):
        """MD-001: a product type comes from the organization's products (asked through core); one already stored may stay."""
        if unknown_product_types(self.db, self.org_id, values, keep):
            raise DemandError("product_type_unknown")

    def _quote_types(self, row):
        """A quotation's lines carry their product types over, even those written before the product list."""
        return [i.product_type for i in self.quotes.get_quote_items(self.db, row.quote_id, self.org_id)] if row.quote_id else []

    def _add_item(self, row, data, keep=()):
        self._assert_products([data.product_type], keep)
        used = {item.line_no for item in row.items}
        line = data.line_no or max(used, default=0) + 1
        if line in used:
            raise DemandError("duplicate_line_number", 409)
        item = ProductionDemandItem(**deepcopy(data.model_dump(exclude={"line_no"})), line_no=line)
        row.items.append(item)
        row.updated_at = utc_now()
        return item

    def create(self, data):
        self.repo.lock_organization(self.org_id)
        self.validate_references(data.customer_id, data.quote_id)
        year = numbering.organization_year(self.db, self.org_id)
        counter = self.repo.lock_counter(self.org_id, year)
        counter.last_value += 1
        row = ProductionDemand(organization_id=self.org_id, demand_number=f"PD-{year}-{counter.last_value:06d}", created_by_user_id=self.tenant.user_id, **data.model_dump(exclude={"items", "request_date"}), request_date=data.request_date or date.today())
        self.db.add(row)
        keep = self._quote_types(row)
        for item in data.items:
            self._add_item(row, item, keep)
        self.db.commit()
        return row

    def update(self, demand_id, data):
        row = self.get(demand_id, write=True)
        self.editable(row)
        values = data.model_dump(exclude_unset=True, exclude={"items"})
        if row.source_order_id and (data.items is not None or values.get("customer_id", row.customer_id) != row.customer_id
                                    or values.get("quote_id", row.quote_id) != row.quote_id):
            raise DemandError("sales_order_lines_locked", 409)
        customer_id = values.get("customer_id", row.customer_id)
        if customer_id != row.customer_id and row.status != "draft":
            raise DemandError("customer_change_draft_only", 409)
        self.validate_references(customer_id, values.get("quote_id", row.quote_id))
        if data.items is not None:
            if not data.items and row.status == "ready_for_planning":
                raise DemandError("items_required")
            row.items.clear()
            self.db.flush()
            for item in data.items:
                self._add_item(row, item)
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = utc_now()
        self.db.commit()
        return row

    def delete(self, demand_id):
        row = self.get(demand_id, write=True)
        if row.status != "draft":
            raise DemandError("delete_draft_only", 409)
        if row.allocations:
            # Released allocations are planning history and keep the demand alive.
            raise DemandError("demand_has_allocation_history", 409)
        self.db.delete(row)
        self.db.commit()

    def add_item(self, demand_id, data):
        row = self.get(demand_id, write=True)
        self.editable(row)
        if row.source_order_id:
            raise DemandError("sales_order_lines_locked", 409)
        item = self._add_item(row, data)
        self.db.commit()
        return item

    def change_item(self, demand_id, item_id, data=None):
        row = self.get(demand_id, write=True)
        self.editable(row)
        item = next((item for item in row.items if item.id == item_id), None)
        if item is None:
            raise DemandError("item_not_found", 404)
        if data is None:
            if row.status == "ready_for_planning" and len(row.items) == 1:
                raise DemandError("items_required")
            row.items.remove(item)
        else:
            values = data.model_dump(exclude_unset=True)
            if item.source_order_item_id:
                if any(key in values and values[key] != getattr(item, key) for key in ("product_type", "target_spec_json", "unit")):
                    raise DemandError("sales_order_lines_locked", 409)
                if "required_quantity" in values:
                    self._assert_within_order(row, item, values["required_quantity"])
            if values.get("product_type"):
                self._assert_products([values["product_type"]], keep=[item.product_type, *self._quote_types(row)])
            if "line_no" in values and any(other.id != item.id and other.line_no == values["line_no"] for other in row.items):
                raise DemandError("duplicate_line_number", 409)
            for key, value in values.items():
                setattr(item, key, deepcopy(value))
        row.updated_at = utc_now()
        self.db.commit()
        return item

    def quote_items(self, customer_id, quote_id):
        self.validate_references(customer_id, quote_id)
        try:
            return [CreateDemandItemRequest(product_type=i.product_type, target_spec_json=deepcopy(i.target_spec_json), required_quantity=i.quantity, unit=i.unit, notes=i.notes) for i in self.quotes.get_quote_items(self.db, quote_id, self.org_id)]
        except ValidationError as exc:
            raise DemandError("invalid_request") from exc

    def import_quote_items(self, demand_id):
        row = self.get(demand_id, write=True)
        self.editable(row)
        if not row.quote_id:
            raise DemandError("no_quote_attached")
        if row.source_order_id:
            raise DemandError("sales_order_lines_locked", 409)
        items = self.quote_items(row.customer_id, row.quote_id)
        imported = [self._add_item(row, item, keep=[i.product_type for i in items]) for item in items]
        self.db.commit()
        return imported

    def update_status(self, demand_id, new_status):
        row = self.get(demand_id, write=True)
        if new_status in ("partially_planned", "planned"):
            # Planning progress is derived from ACTIVE allocations and cannot be forced.
            raise DemandError("status_derived_from_allocations", 409)
        if any(a.status == "active" for a in row.allocations):
            raise DemandError("invalid_transition", 409)
        if new_status not in VALID_TRANSITIONS.get(row.status, set()):
            raise DemandError("invalid_transition", 409)
        if new_status in PLANNABLE and not row.items:
            raise DemandError("items_required")
        if row.status == "cancelled" and row.source_order_id:
            # Back from cancelled, it takes its quantities from the sales order again.
            if self._sales_order(row.source_order_id, lock=True).status != "confirmed":
                raise DemandError("sales_order_not_confirmed", 409)
            self._assert_within_order(row)
        row.status = new_status
        row.planning_sequence = None
        self.db.flush()
        # Compact only manually ordered rows, leaving automatic priority ordering intact.
        for position, demand in enumerate((d for d in self.repo.queue(self.org_id) if d.planning_sequence is not None), 1):
            demand.planning_sequence = position
        self.db.commit()
        return row

    def reorder(self, demand_id, new_position):
        row = self.get(demand_id, write=True)
        if row.status not in PLANNABLE:
            raise DemandError("not_plannable", 409)
        queue = self.repo.queue(self.org_id)
        if new_position > len(queue):
            raise DemandError("invalid_position")
        queue = [d for d in queue if d.id != row.id]
        queue.insert(new_position - 1, row)
        for position, demand in enumerate(queue, 1):
            demand.planning_sequence = position
        self.db.commit()
        return {"demand_id": row.id, "new_position": new_position}

    def response(self, row, detail=False, planning=False):
        customer = self.customers.get_customer_summary(self.db, row.customer_id, self.org_id)
        quote = self.quotes.get_quote_summary(self.db, row.quote_id, self.org_id) if row.quote_id else None
        users = Base.metadata.tables["foundation_users"]
        name = self.db.scalar(select(users.c.full_name).where(users.c.id == row.created_by_user_id, users.c.organization_id == self.org_id)) if row.created_by_user_id else None
        result = {key: getattr(row, key) for key in ("id", "demand_number", "request_date", "requested_delivery_date", "priority", "status", "planning_sequence", "notes", "created_at", "updated_at")}
        result.update(sales_order={"id": row.source_order_id, "number": row.source_order_number} if row.source_order_id else None)
        result.update(customer={"id": customer.id, "code": customer.customer_code, "name": customer.customer_name}, quote={"id": quote.id, "number": quote.quote_number, "status": quote.status} if quote else None, item_count=len(row.items), created_by=name)
        totals = {}
        for item in row.items:
            totals[item.unit] = totals.get(item.unit, Decimal(0)) + item.required_quantity
        result.update(total_quantity=sum(totals.values(), Decimal(0)), quantities_by_unit=totals)
        allocated = sum((i.active_allocated_quantity for i in row.items), Decimal(0))
        released = sum((i.released_allocated_quantity for i in row.items), Decimal(0))
        required = sum((i.required_quantity for i in row.items), Decimal(0))
        result.update(total_required=required, total_allocated=allocated, total_active_allocated=allocated, total_released_allocated=released,
                      total_remaining=required-allocated, allocation_percentage=(allocated / required * 100 if required else Decimal(0)))
        if detail or planning:
            result["items"] = row.items
        if planning:
            result["spec_summary"] = row.items[0].target_spec_json if row.items else None
        return result

    def list(self, filters, planning=False, statuses=None):
        if filters.requested_delivery_from and filters.requested_delivery_to and filters.requested_delivery_from > filters.requested_delivery_to:
            raise DemandError("invalid_date_range")
        customers = self.customers.find_customers(self.db, self.org_id, filters.search, active_only=False) if filters.search else []
        rows, total, hidden = self.repo.list(self.org_id, filters, [c.id for c in customers], planning, statuses)
        # The same envelope as every paged list (core/pagination.py page_of), plus what the status filter hides.
        return {**page_of([self.response(row, planning=planning) for row in rows], total, filters), "hidden_by_status": hidden}
