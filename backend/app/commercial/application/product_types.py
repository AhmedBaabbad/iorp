"""The product types sales stores (MD-001): on samples, quotation lines and commercial order lines. Registered at the
composition root so master data can show and map legacy values without touching these tables itself."""
from sqlalchemy import select

from app.commercial.infrastructure.models import CommercialOrder, CommercialOrderItem, Customer, Quote, QuoteItem, Sample
from app.core.interfaces.product_types import holder_for

HOLDER = holder_for("commercial", (
    (Sample, Sample.product_type, lambda org: Sample.customer_id.in_(select(Customer.id).where(Customer.organization_id == org))),
    (QuoteItem, QuoteItem.product_type, lambda org: QuoteItem.quote_id.in_(select(Quote.id).where(Quote.organization_id == org))),
    (CommercialOrderItem, CommercialOrderItem.product_type,
     lambda org: CommercialOrderItem.commercial_order_id.in_(select(CommercialOrder.id).where(CommercialOrder.organization_id == org))),
))
