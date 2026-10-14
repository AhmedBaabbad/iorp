"""Where sales stores reference-list values (MD-002): a customer's sector, opportunity source, country and city.
Registered at the composition root so master data can show and map legacy texts without touching this table itself."""
from sqlalchemy import select

from app.commercial.infrastructure.complaint_models import Complaint
from app.commercial.infrastructure.models import Customer, CustomerInteraction
from app.core.interfaces.reference_lists import holder_for

HOLDERS = tuple(holder_for("commercial", list_name, ((Customer, column, lambda org: Customer.organization_id == org),))
                for list_name, column in (("sector", Customer.sector), ("opportunity_source", Customer.opportunity_source),
                                          ("country", Customer.country), ("city", Customer.city)))
# MD-003: a complaint's category and an interaction's type (an interaction belongs to the organization through its customer).
HOLDERS += (
    holder_for("commercial", "complaint_category", ((Complaint, Complaint.category, lambda org: Complaint.organization_id == org),)),
    holder_for("commercial", "interaction_type", ((CustomerInteraction, CustomerInteraction.interaction_type,
                                                   lambda org: CustomerInteraction.customer_id.in_(select(Customer.id).where(Customer.organization_id == org))),)),
)
