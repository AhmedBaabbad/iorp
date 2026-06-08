from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commercial.infrastructure.models import Customer, CustomerInteraction, FollowUp


class CustomerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, customer: Customer) -> Customer:
        self.db.add(customer)
        self.db.flush()
        return customer

    def get_by_id(self, organization_id: UUID, customer_id: UUID) -> Customer | None:
        statement = select(Customer).where(
            Customer.organization_id == organization_id,
            Customer.id == customer_id,
        )
        return self.db.scalar(statement)

    def get_by_code(self, organization_id: UUID, customer_code: str) -> Customer | None:
        statement = select(Customer).where(
            Customer.organization_id == organization_id,
            Customer.customer_code == customer_code,
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[Customer]:
        statement = (
            select(Customer)
            .where(Customer.organization_id == organization_id)
            .order_by(Customer.created_at.desc())
        )
        return list(self.db.scalars(statement))


class CustomerInteractionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, interaction: CustomerInteraction) -> CustomerInteraction:
        self.db.add(interaction)
        self.db.flush()
        return interaction

    def list_for_customer(
        self,
        organization_id: UUID,
        customer_id: UUID,
    ) -> list[CustomerInteraction]:
        statement = (
            select(CustomerInteraction)
            .join(Customer, Customer.id == CustomerInteraction.customer_id)
            .where(
                Customer.organization_id == organization_id,
                CustomerInteraction.customer_id == customer_id,
            )
            .order_by(
                CustomerInteraction.interaction_date.desc(),
                CustomerInteraction.created_at.desc(),
            )
        )
        return list(self.db.scalars(statement))

    def get_for_customer(
        self,
        organization_id: UUID,
        customer_id: UUID,
        interaction_id: UUID,
    ) -> CustomerInteraction | None:
        statement = (
            select(CustomerInteraction)
            .join(Customer, Customer.id == CustomerInteraction.customer_id)
            .where(
                Customer.organization_id == organization_id,
                CustomerInteraction.customer_id == customer_id,
                CustomerInteraction.id == interaction_id,
            )
        )
        return self.db.scalar(statement)


class FollowUpRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, follow_up: FollowUp) -> FollowUp:
        self.db.add(follow_up)
        self.db.flush()
        return follow_up

    def get_by_id(self, organization_id: UUID, follow_up_id: UUID) -> FollowUp | None:
        statement = (
            select(FollowUp)
            .join(Customer, Customer.id == FollowUp.customer_id)
            .where(
                Customer.organization_id == organization_id,
                FollowUp.id == follow_up_id,
            )
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[FollowUp]:
        statement = (
            select(FollowUp)
            .join(Customer, Customer.id == FollowUp.customer_id)
            .where(Customer.organization_id == organization_id)
            .order_by(FollowUp.due_date.asc(), FollowUp.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_by_customer(
        self,
        organization_id: UUID,
        customer_id: UUID,
    ) -> list[FollowUp]:
        statement = (
            select(FollowUp)
            .join(Customer, Customer.id == FollowUp.customer_id)
            .where(
                Customer.organization_id == organization_id,
                FollowUp.customer_id == customer_id,
            )
            .order_by(FollowUp.due_date.asc(), FollowUp.created_at.desc())
        )
        return list(self.db.scalars(statement))
