"""The product types production stores (MD-001): on demand lines and production orders. Registered at the composition
root so master data can show and map legacy values without touching these tables itself."""
from sqlalchemy import select

from app.core.interfaces.product_types import holder_for
from app.production.infrastructure.models import ProductionDemand, ProductionDemandItem, ProductionOrder

HOLDER = holder_for("production", (
    (ProductionDemandItem, ProductionDemandItem.product_type,
     lambda org: ProductionDemandItem.production_demand_id.in_(select(ProductionDemand.id).where(ProductionDemand.organization_id == org))),
    (ProductionOrder, ProductionOrder.product_type, lambda org: ProductionOrder.organization_id == org),
))
