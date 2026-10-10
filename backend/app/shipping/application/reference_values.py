"""Where shipping stores reference-list values (MD-002): a shipment's delivery city. Registered at the composition root
so master data can show and map legacy texts without touching this table itself."""
from app.core.interfaces.reference_lists import holder_for
from app.shipping.infrastructure.models import Shipment

HOLDERS = (holder_for("shipping", "city", ((Shipment, Shipment.delivery_city, lambda org: Shipment.organization_id == org),)),)
