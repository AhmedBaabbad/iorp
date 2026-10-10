"""Where sales stores reference-list values (MD-002): a customer's sector, opportunity source, country and city.
Registered at the composition root so master data can show and map legacy texts without touching this table itself."""
from app.commercial.infrastructure.models import Customer
from app.core.interfaces.reference_lists import holder_for

HOLDERS = tuple(holder_for("commercial", list_name, ((Customer, column, lambda org: Customer.organization_id == org),))
                for list_name, column in (("sector", Customer.sector), ("opportunity_source", Customer.opportunity_source),
                                          ("country", Customer.country), ("city", Customer.city)))
