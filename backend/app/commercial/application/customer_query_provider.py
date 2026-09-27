from uuid import UUID

from sqlalchemy.orm import Session

from app.commercial.infrastructure.repositories import CustomerRepository
from app.core.interfaces.customer_queries import CustomerQueryInterface


class CommercialCustomerQueries(CustomerQueryInterface):
    def __init__(self, db: Session) -> None:
        self.customers = CustomerRepository(db)

    def count_assigned_customers(self, user_id: UUID, organization_id: UUID) -> int:
        return self.customers.count_active_by_sales_owner(organization_id, user_id)
