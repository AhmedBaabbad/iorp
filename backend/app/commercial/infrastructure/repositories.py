from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.commercial.infrastructure.models import (
    CommercialOrder,
    Customer,
    CustomerInteraction,
    FollowUp,
    Quote,
    Sample,
    SampleEvaluation,
)


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


class SampleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, sample: Sample) -> Sample:
        self.db.add(sample)
        self.db.flush()
        return sample

    def get_by_id(self, organization_id: UUID, sample_id: UUID) -> Sample | None:
        statement = (
            select(Sample)
            .join(Customer, Customer.id == Sample.customer_id)
            .where(
                Customer.organization_id == organization_id,
                Sample.id == sample_id,
            )
        )
        return self.db.scalar(statement)

    def get_by_code_for_customer(
        self,
        organization_id: UUID,
        customer_id: UUID,
        sample_code: str,
    ) -> Sample | None:
        statement = (
            select(Sample)
            .join(Customer, Customer.id == Sample.customer_id)
            .where(
                Customer.organization_id == organization_id,
                Sample.customer_id == customer_id,
                Sample.sample_code == sample_code,
            )
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[Sample]:
        statement = (
            select(Sample)
            .join(Customer, Customer.id == Sample.customer_id)
            .where(Customer.organization_id == organization_id)
            .order_by(Sample.request_date.desc(), Sample.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_by_customer(self, organization_id: UUID, customer_id: UUID) -> list[Sample]:
        statement = (
            select(Sample)
            .join(Customer, Customer.id == Sample.customer_id)
            .where(
                Customer.organization_id == organization_id,
                Sample.customer_id == customer_id,
            )
            .order_by(Sample.request_date.desc(), Sample.created_at.desc())
        )
        return list(self.db.scalars(statement))


class SampleEvaluationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, evaluation: SampleEvaluation) -> SampleEvaluation:
        self.db.add(evaluation)
        self.db.flush()
        return evaluation

    def get_by_id(
        self,
        organization_id: UUID,
        evaluation_id: UUID,
    ) -> SampleEvaluation | None:
        statement = (
            select(SampleEvaluation)
            .join(Sample, Sample.id == SampleEvaluation.sample_id)
            .join(Customer, Customer.id == Sample.customer_id)
            .where(
                Customer.organization_id == organization_id,
                SampleEvaluation.id == evaluation_id,
            )
        )
        return self.db.scalar(statement)

    def list_by_sample(
        self,
        organization_id: UUID,
        sample_id: UUID,
    ) -> list[SampleEvaluation]:
        statement = (
            select(SampleEvaluation)
            .join(Sample, Sample.id == SampleEvaluation.sample_id)
            .join(Customer, Customer.id == Sample.customer_id)
            .where(
                Customer.organization_id == organization_id,
                SampleEvaluation.sample_id == sample_id,
            )
            .order_by(SampleEvaluation.evaluation_date.desc(), SampleEvaluation.created_at.desc())
        )
        return list(self.db.scalars(statement))


class QuoteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, quote: Quote) -> Quote:
        self.db.add(quote)
        self.db.flush()
        return quote

    def get_by_id(self, organization_id: UUID, quote_id: UUID) -> Quote | None:
        statement = (
            select(Quote)
            .options(selectinload(Quote.items))
            .where(
                Quote.organization_id == organization_id,
                Quote.id == quote_id,
            )
        )
        return self.db.scalar(statement)

    def get_by_number(self, organization_id: UUID, quote_number: str) -> Quote | None:
        statement = select(Quote).where(
            Quote.organization_id == organization_id,
            Quote.quote_number == quote_number,
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[Quote]:
        statement = (
            select(Quote)
            .where(Quote.organization_id == organization_id)
            .order_by(Quote.issue_date.desc(), Quote.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_by_customer(self, organization_id: UUID, customer_id: UUID) -> list[Quote]:
        statement = (
            select(Quote)
            .where(
                Quote.organization_id == organization_id,
                Quote.customer_id == customer_id,
            )
            .order_by(Quote.issue_date.desc(), Quote.created_at.desc())
        )
        return list(self.db.scalars(statement))


class CommercialOrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, order: CommercialOrder) -> CommercialOrder:
        self.db.add(order)
        self.db.flush()
        return order

    def get_by_id(self, organization_id: UUID, order_id: UUID) -> CommercialOrder | None:
        statement = (
            select(CommercialOrder)
            .options(selectinload(CommercialOrder.items))
            .where(
                CommercialOrder.organization_id == organization_id,
                CommercialOrder.id == order_id,
            )
        )
        return self.db.scalar(statement)

    def get_by_number(self, organization_id: UUID, order_number: str) -> CommercialOrder | None:
        statement = select(CommercialOrder).where(
            CommercialOrder.organization_id == organization_id,
            CommercialOrder.order_number == order_number,
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[CommercialOrder]:
        statement = (
            select(CommercialOrder)
            .where(CommercialOrder.organization_id == organization_id)
            .order_by(CommercialOrder.order_date.desc(), CommercialOrder.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_by_customer(self, organization_id: UUID, customer_id: UUID) -> list[CommercialOrder]:
        statement = (
            select(CommercialOrder)
            .where(
                CommercialOrder.organization_id == organization_id,
                CommercialOrder.customer_id == customer_id,
            )
            .order_by(CommercialOrder.order_date.desc(), CommercialOrder.created_at.desc())
        )
        return list(self.db.scalars(statement))
