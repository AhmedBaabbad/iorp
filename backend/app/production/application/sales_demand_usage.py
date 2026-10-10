from sqlalchemy import select, func
from app.production.infrastructure.models import ProductionDemand, ProductionDemandItem


class ProductionSalesDemandUsage:
    def quantities(self, db, organization_id, order_id):
        return dict(db.execute(select(ProductionDemandItem.source_order_item_id,func.sum(ProductionDemandItem.required_quantity))
            .join(ProductionDemand,ProductionDemand.id==ProductionDemandItem.production_demand_id)
            .where(ProductionDemand.organization_id==organization_id,ProductionDemand.source_order_id==order_id,
                   ProductionDemand.status!='cancelled').group_by(ProductionDemandItem.source_order_item_id)).all())

    def has_history(self, db, organization_id, order_id):
        return db.scalar(select(ProductionDemand.id).where(ProductionDemand.organization_id==organization_id,
            ProductionDemand.source_order_id==order_id).limit(1)) is not None
