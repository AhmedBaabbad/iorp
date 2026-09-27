from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from app.production.infrastructure.models import ProductionDemand, ProductionDemandItem, ProductionDemandCounter, ProductionAllocation


PLANNABLE = ("ready_for_planning", "partially_planned")


class ProductionDemandRepository:
    def __init__(self, db):
        self.db = db

    def lock_counter(self, org_id, year):
        key = (org_id, year)
        if self.db.bind.dialect.name == "postgresql":
            self.db.execute(insert(ProductionDemandCounter).values(organization_id=org_id, year=year, last_value=0).on_conflict_do_nothing())
        elif self.db.get(ProductionDemandCounter, key) is None:
            self.db.add(ProductionDemandCounter(organization_id=org_id, year=year, last_value=0))
            self.db.flush()
        return self.db.scalar(select(ProductionDemandCounter).where(ProductionDemandCounter.organization_id == org_id, ProductionDemandCounter.year == year).with_for_update().execution_options(populate_existing=True))

    def lock_organization(self, org_id):
        # Year zero is a persistent organization-level mutex for queue and item writes.
        self.lock_counter(org_id, 0)

    def get(self, org_id, demand_id):
        return self.db.scalar(select(ProductionDemand).where(ProductionDemand.organization_id == org_id, ProductionDemand.id == demand_id).execution_options(populate_existing=True))

    @staticmethod
    def ordering():
        d = ProductionDemand
        return (d.planning_sequence.asc().nulls_last(), case({"urgent": 0, "high": 1, "normal": 2, "low": 3}, value=d.priority), d.requested_delivery_date.asc().nulls_last(), d.created_at.asc(), d.id.asc())

    def queue(self, org_id):
        return list(self.db.scalars(select(ProductionDemand).where(ProductionDemand.organization_id == org_id, ProductionDemand.status.in_(PLANNABLE)).order_by(*self.ordering())))

    @staticmethod
    def has_remaining(org_id):
        # Only ACTIVE allocations reserve quantity; computed in the database for filtering and paging.
        active = select(func.coalesce(func.sum(ProductionAllocation.allocated_quantity), 0)).where(
            ProductionAllocation.organization_id == org_id, ProductionAllocation.production_demand_item_id == ProductionDemandItem.id,
            ProductionAllocation.status == "active").correlate(ProductionDemandItem).scalar_subquery()
        return ProductionDemand.items.any(ProductionDemandItem.required_quantity > active)

    def list(self, org_id, filters, customer_ids=None, planning=False):
        d = ProductionDemand
        query = select(d).where(d.organization_id == org_id)
        if planning:
            # The planning queue is a derived view over demands; nothing is moved or deleted.
            if filters.view == "active":
                query = query.where(d.status.in_(PLANNABLE), self.has_remaining(org_id))
            elif filters.view == "planned":
                query = query.where(d.status == "planned")
        for name in ("customer_id", "quote_id", "status", "priority"):
            value = getattr(filters, name)
            if value is not None:
                query = query.where(getattr(d, name) == value)
        if filters.requested_delivery_from:
            query = query.where(d.requested_delivery_date >= filters.requested_delivery_from)
        if filters.requested_delivery_to:
            query = query.where(d.requested_delivery_date <= filters.requested_delivery_to)
        if filters.has_remaining:
            query = query.where(self.has_remaining(org_id))
        if filters.product_type:
            query = query.where(d.items.any(ProductionDemandItem.product_type == filters.product_type))
        if filters.search:
            query = query.where(or_(d.demand_number.icontains(filters.search, autoescape=True), d.customer_id.in_(customer_ids or [])))
        total = self.db.scalar(select(func.count()).select_from(query.subquery()))
        ordering = self.ordering() if planning and filters.view == "active" else (d.created_at.desc(), d.id.asc())
        if filters.sort_by != "planning_sequence" or filters.sort_order != "asc":
            column = getattr(d, filters.sort_by)
            if filters.sort_by == "priority":
                column = case({"urgent": 0, "high": 1, "normal": 2, "low": 3}, value=d.priority)
            ordering = ((column.desc() if filters.sort_order == "desc" else column.asc()).nulls_last(), d.id.asc())
        rows = list(self.db.scalars(query.order_by(*ordering).offset((filters.page - 1) * filters.page_size).limit(filters.page_size)))
        return rows, total


class ProductionDemandCount:
    def count_demands_for_customer(self, db, customer_id, org_id, active_only=False):
        query = select(func.count()).select_from(ProductionDemand).where(ProductionDemand.customer_id == customer_id, ProductionDemand.organization_id == org_id)
        if active_only:
            query = query.where(ProductionDemand.status.not_in(("cancelled", "planned")))
        return db.scalar(query) or 0
