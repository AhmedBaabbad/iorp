"""Where shipping stores reference-list values (MD-002): a shipment's delivery city. Registered at the composition root
so master data can show and map legacy texts without touching this table itself."""
from app.core.interfaces.reference_lists import holder_for
from app.shipping.infrastructure.directory_models import Vehicle
from app.shipping.infrastructure.models import Shipment

HOLDERS = (holder_for("shipping", "city", ((Shipment, Shipment.delivery_city, lambda org: Shipment.organization_id == org),)),
           holder_for("shipping", "country", ((Shipment, Shipment.delivery_country, lambda org: Shipment.organization_id == org),)),
           # MD-003: a vehicle's type (and the copy on each shipment that used it)
           holder_for("shipping", "vehicle_type", ((Vehicle, Vehicle.vehicle_type, lambda org: Vehicle.organization_id == org),
                                                   (Shipment, Shipment.vehicle_type, lambda org: Shipment.organization_id == org))))
