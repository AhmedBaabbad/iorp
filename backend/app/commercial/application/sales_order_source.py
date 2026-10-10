from copy import deepcopy
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.interfaces.sales_order_source import SalesOrder, SalesLine
from app.commercial.infrastructure.models import CommercialOrder


class CommercialSalesOrderSource:
    def get(self, db, organization_id, order_id, *, lock=False):
        query=select(CommercialOrder).where(CommercialOrder.organization_id==organization_id,CommercialOrder.id==order_id)
        if lock: query=query.with_for_update().execution_options(populate_existing=True)
        row=db.scalar(query.options(selectinload(CommercialOrder.items)))
        return self.snapshot(row) if row else None

    def list(self, db, organization_id, customer_id):
        return [self.snapshot(row) for row in db.scalars(select(CommercialOrder).where(
            CommercialOrder.organization_id==organization_id,CommercialOrder.customer_id==customer_id,
            CommercialOrder.status=='confirmed').options(selectinload(CommercialOrder.items)).order_by(CommercialOrder.order_date.desc()).limit(500))]

    @staticmethod
    def snapshot(row):
        return SalesOrder(row.id,row.customer_id,row.quote_id,row.order_number,row.status.value,row.requested_delivery_date,
            tuple(SalesLine(i.id,i.line_no,i.product_type,deepcopy(i.requested_spec_json),i.quantity,i.unit) for i in sorted(row.items,key=lambda i:i.line_no)))
