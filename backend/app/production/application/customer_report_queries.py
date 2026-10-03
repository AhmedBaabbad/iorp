"""Public production read API. Uses active allocations and the existing signed result summary.

Results remain at order level, including for shared orders. No actual-demand settlement is inferred.
"""
from collections import defaultdict
from decimal import Decimal
from sqlalchemy import select
from app.core.interfaces.customer_reporting import DemandRead, OrderRead, ResultRead, InternalResultRead
from app.core.reporting.contracts import ReportLimitError
from app.production.infrastructure.models import ProductionDemand, ProductionAllocation, ProductionOrder
from app.production.application.result_service import OrderResultService


def bounded(rows):
    rows = list(rows)
    if len(rows) > 5000:
        raise ReportLimitError()
    return rows


class ProductionReportQueries:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant
        self.org = tenant.organization_id

    def demands(self, customer_ids):
        rows = self.db.scalars(select(ProductionDemand).where(ProductionDemand.organization_id == self.org,
                    ProductionDemand.customer_id.in_(customer_ids)).order_by(ProductionDemand.request_date, ProductionDemand.id).limit(5001))
        result = []
        for d in bounded(rows):
            for i in d.items:
                result.append(DemandRead(customer_id=d.customer_id, demand_id=d.id, number=d.demand_number,
                    requested=d.request_date, expected=d.requested_delivery_date, status=d.status, product=i.product_type or '',
                    quantity=i.required_quantity, allocated=i.active_allocated_quantity,
                    unallocated=i.remaining_quantity, unit=i.unit))
                if len(result) > 5000:
                    raise ReportLimitError()
        return result

    def orders(self, customer_ids):
        linked = select(ProductionAllocation.production_order_id).join(ProductionDemand,
            ProductionDemand.id == ProductionAllocation.production_demand_id).where(
            ProductionAllocation.organization_id == self.org, ProductionDemand.organization_id == self.org,
            ProductionDemand.customer_id.in_(customer_ids), ProductionAllocation.status == 'active')
        orders = bounded(self.db.scalars(select(ProductionOrder).where(ProductionOrder.organization_id == self.org,
                    ProductionOrder.id.in_(linked)).order_by(ProductionOrder.created_at, ProductionOrder.id).limit(5001)))
        allocations = bounded(self.db.execute(select(ProductionAllocation, ProductionDemand.customer_id).join(
            ProductionDemand, ProductionDemand.id == ProductionAllocation.production_demand_id).where(
            ProductionAllocation.organization_id == self.org, ProductionDemand.organization_id == self.org,
            ProductionAllocation.production_order_id.in_([o.id for o in orders]), ProductionAllocation.status == 'active').limit(5001)))
        totals, own, owners = defaultdict(Decimal), defaultdict(Decimal), defaultdict(set)
        demand_ids = defaultdict(set)
        for a, customer_id in allocations:
            totals[a.production_order_id, a.unit] += a.allocated_quantity
            own[a.production_order_id, customer_id, a.unit] += a.allocated_quantity
            owners[a.production_order_id].add(customer_id)
            demand_ids[a.production_order_id, customer_id].add(a.production_demand_id)
        result = []
        for o in orders:
            for (oid, cid, unit), qty in own.items():
                if oid != o.id or cid not in customer_ids:
                    continue
                result.append(OrderRead(customer_id=cid, order_id=o.id, number=o.production_order_number,
                    product=o.product_type, status=getattr(o.status, 'value', o.status),
                    planned_start=o.planned_start_date, planned_end=o.planned_end_date,
                    actual_start=o.actual_start_at, actual_end=o.actual_end_at, created=o.created_at,
                    allocated=qty, total_allocated=totals[oid, unit], unit=unit, shared=len(owners[oid]) > 1,
                    demand_ids=tuple(sorted(demand_ids[oid,cid],key=str))))
        return bounded(result)

    def results(self, order_ids, *, internal=False):
        # One batch read of the signed result summary (completed and closed orders with entries).
        totals = OrderResultService(self.db, self.tenant).unit_totals(order_ids)
        result = []
        for (oid, unit), t in sorted(totals.items(), key=lambda pair: (str(pair[0][0]), pair[0][1])):
            fields = dict(order_id=oid, unit=unit, customer_good=t['customer_good'], stock_good=t['stock_good'])
            if internal:
                fields.update(sample=t['samples_total'], scrap=t['scrap_total'], rework=t['rework_total'], loss_total=t['loss_total'])
            result.append((InternalResultRead if internal else ResultRead)(**fields))
        return bounded(result)
