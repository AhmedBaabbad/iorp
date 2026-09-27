from copy import deepcopy
from datetime import date
from decimal import Decimal
from pydantic import ValidationError
from sqlalchemy import select
from app.core.db import Base
from app.core.utils import utc_now
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

    def _add_item(self, row, data):
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
        year = date.today().year
        counter = self.repo.lock_counter(self.org_id, year)
        counter.last_value += 1
        row = ProductionDemand(organization_id=self.org_id, demand_number=f"PD-{year}-{counter.last_value:06d}", created_by_user_id=self.tenant.user_id, **data.model_dump(exclude={"items", "request_date"}), request_date=data.request_date or date.today())
        self.db.add(row)
        for item in data.items:
            self._add_item(row, item)
        self.db.commit()
        return row

    def update(self, demand_id, data):
        row = self.get(demand_id, write=True)
        self.editable(row)
        values = data.model_dump(exclude_unset=True, exclude={"items"})
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
        imported = [self._add_item(row, item) for item in self.quote_items(row.customer_id, row.quote_id)]
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

    def list(self, filters, planning=False):
        if filters.requested_delivery_from and filters.requested_delivery_to and filters.requested_delivery_from > filters.requested_delivery_to:
            raise DemandError("invalid_date_range")
        customers = self.customers.find_customers(self.db, self.org_id, filters.search, active_only=False) if filters.search else []
        rows, total = self.repo.list(self.org_id, filters, [c.id for c in customers], planning)
        return {"items": [self.response(row, planning=planning) for row in rows], "total": total, "page": filters.page, "page_size": filters.page_size}
