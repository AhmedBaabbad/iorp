from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Integer, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.commercial.domain.enums import FollowUpPriority, FollowUpStatus
from app.core.utils import utc_now

if TYPE_CHECKING:
    from app.core.interfaces.authorization_policy import AuthorizationContext, AuthorizationPolicy
from app.commercial.infrastructure.models import (
    CommercialOrder,
    Customer,
    CustomerCodeCounter,
    CustomerInteraction,
    FollowUp,
    OrderCodeCounter,
    Quote,
    QuoteCodeCounter,
    Sample,
    SampleCodeCounter,
    SampleEvaluation,
)


class CustomerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, customer: Customer) -> Customer:
        self.db.add(customer)
        self.db.flush()
        return customer

    def delete(self, customer: Customer) -> None:
        self.db.delete(customer)
        self.db.flush()

    def get_by_id(
        self, organization_id: UUID, customer_id: UUID,
        policy: "AuthorizationPolicy | None" = None, auth_context: "AuthorizationContext | None" = None,
    ) -> Customer | None:
        statement = select(Customer).where(
            Customer.organization_id == organization_id,
            Customer.id == customer_id,
        )
        customer = self.db.scalar(statement)
        if customer is not None and policy is not None and auth_context is not None:
            if not policy.can_access_record(auth_context, record_owner_id=customer.sales_owner_user_id):
                return None
        return customer

    def get_by_code(self, organization_id: UUID, customer_code: str) -> Customer | None:
        statement = select(Customer).where(
            Customer.organization_id == organization_id,
            Customer.customer_code == customer_code,
        )
        return self.db.scalar(statement)

    def list_by_organization(
        self, organization_id: UUID,
        policy: "AuthorizationPolicy | None" = None, auth_context: "AuthorizationContext | None" = None,
    ) -> list[Customer]:
        statement = (
            select(Customer)
            .where(Customer.organization_id == organization_id)
            .order_by(Customer.created_at.desc())
        )
        if policy is not None and auth_context is not None:
            statement = policy.apply_query_filter(auth_context, statement, owner_field="sales_owner_user_id")
        return list(self.db.scalars(statement))

    def count_active_by_sales_owner(self, organization_id: UUID, user_id: UUID) -> int:
        from app.commercial.domain.enums import CustomerStatus
        statement = select(func.count()).select_from(Customer).where(
            Customer.organization_id == organization_id,
            Customer.sales_owner_user_id == user_id,
            Customer.status == CustomerStatus.ACTIVE,
        )
        return int(self.db.scalar(statement) or 0)

    def reassign_active_by_sales_owner(self, organization_id: UUID, from_user_id: UUID, to_user_id: UUID) -> int:
        from app.commercial.domain.enums import CustomerStatus
        result = self.db.execute(
            update(Customer).where(
                Customer.organization_id == organization_id,
                Customer.sales_owner_user_id == from_user_id,
                Customer.status == CustomerStatus.ACTIVE,
            ).values(sales_owner_user_id=to_user_id)
        )
        return result.rowcount or 0

    def get_highest_customer_code_sequence(self, organization_id: UUID) -> int:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            statement = select(Customer.customer_code).where(
                Customer.organization_id == organization_id,
            )
            highest_sequence = 0
            for customer_code in self.db.scalars(statement):
                upper = customer_code.upper()
                if not upper.startswith("CUST-"):
                    continue
                sequence_text = upper.removeprefix("CUST-")
                if sequence_text.isdigit():
                    highest_sequence = max(highest_sequence, int(sequence_text))
            return highest_sequence

        # Case-insensitive: lower() the code then match against lowercase pattern
        sequence_text = func.substring(func.lower(Customer.customer_code), r"^cust-([0-9]+)$")
        statement = select(func.coalesce(func.max(sequence_text.cast(Integer)), 0)).where(
            Customer.organization_id == organization_id,
        )
        return int(self.db.scalar(statement) or 0)

    def ensure_code_counter(self, organization_id: UUID, last_value: int) -> None:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            counter = self.db.get(CustomerCodeCounter, organization_id)
            if counter is None:
                self.db.add(
                    CustomerCodeCounter(
                        organization_id=organization_id,
                        last_value=last_value,
                    ),
                )
                self.db.flush()
            return

        statement = (
            insert(CustomerCodeCounter)
            .values(organization_id=organization_id, last_value=last_value)
            .on_conflict_do_nothing(index_elements=[CustomerCodeCounter.organization_id])
        )
        self.db.execute(statement)
        self.db.flush()

    def get_code_counter_for_update(
        self,
        organization_id: UUID,
    ) -> CustomerCodeCounter | None:
        statement = (
            select(CustomerCodeCounter)
            .where(CustomerCodeCounter.organization_id == organization_id)
            .with_for_update()
        )
        return self.db.scalar(statement)


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
        policy: "AuthorizationPolicy | None" = None,
        auth_context: "AuthorizationContext | None" = None,
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
        if policy is not None and auth_context is not None:
            statement = policy.apply_query_filter(auth_context, statement, owner_field="created_by_user_id")
        return list(self.db.scalars(statement))

    def get_for_customer(
        self,
        organization_id: UUID,
        customer_id: UUID,
        interaction_id: UUID,
        policy: "AuthorizationPolicy | None" = None,
        auth_context: "AuthorizationContext | None" = None,
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
        interaction = self.db.scalar(statement)
        if interaction is not None and policy is not None and auth_context is not None:
            if not policy.can_access_record(auth_context, record_owner_id=interaction.created_by_user_id):
                return None
        return interaction

    def count_by_customer(self, customer_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(CustomerInteraction)
            .where(CustomerInteraction.customer_id == customer_id)
        )
        return self.db.scalar(statement) or 0

    def delete_for_customer(self, customer_id: UUID) -> None:
        self.db.execute(
            delete(CustomerInteraction).where(CustomerInteraction.customer_id == customer_id),
        )
        self.db.flush()


NOT_OVERDUE_STATUSES = (FollowUpStatus.COMPLETED, FollowUpStatus.CANCELLED)


@dataclass
class FollowUpListFilters:
    status: FollowUpStatus | None = None
    priority: FollowUpPriority | None = None
    customer_id: UUID | None = None
    assigned_user_id: UUID | None = None
    unassigned_only: bool = False
    due_from: datetime | None = None
    due_to: datetime | None = None
    overdue_only: bool = False
    search: str | None = None
    page: int = 1
    page_size: int = 50


class FollowUpRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, follow_up: FollowUp) -> FollowUp:
        self.db.add(follow_up)
        self.db.flush()
        return follow_up

    def delete(self, follow_up: FollowUp) -> None:
        self.db.delete(follow_up)
        self.db.flush()

    def get_by_id(
        self, organization_id: UUID, follow_up_id: UUID,
        policy: "AuthorizationPolicy | None" = None, auth_context: "AuthorizationContext | None" = None,
    ) -> FollowUp | None:
        statement = (
            select(FollowUp)
            .join(Customer, Customer.id == FollowUp.customer_id)
            .where(
                Customer.organization_id == organization_id,
                FollowUp.id == follow_up_id,
            )
        )
        follow_up = self.db.scalar(statement)
        if follow_up is not None and policy is not None and auth_context is not None:
            if not policy.can_access_record(auth_context, record_owner_id=follow_up.assigned_user_id):
                return None
        return follow_up

    def list_by_customer(
        self,
        organization_id: UUID,
        customer_id: UUID,
        policy: "AuthorizationPolicy | None" = None,
        auth_context: "AuthorizationContext | None" = None,
    ) -> list[FollowUp]:
        statement = (
            select(FollowUp)
            .join(Customer, Customer.id == FollowUp.customer_id)
            .where(
                Customer.organization_id == organization_id,
                FollowUp.customer_id == customer_id,
            )
        )
        if policy is not None and auth_context is not None:
            statement = policy.apply_query_filter(auth_context, statement, owner_field="assigned_user_id")
        statement = (
            statement
            .order_by(FollowUp.due_date.asc(), FollowUp.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def _base_org_statement(self, organization_id: UUID):
        return (
            select(FollowUp)
            .join(Customer, Customer.id == FollowUp.customer_id)
            .where(Customer.organization_id == organization_id)
        )

    def _apply_filters(self, statement, filters: FollowUpListFilters):
        if filters.status is not None:
            statement = statement.where(FollowUp.status == filters.status)
        if filters.priority is not None:
            statement = statement.where(FollowUp.priority == filters.priority)
        if filters.customer_id is not None:
            statement = statement.where(FollowUp.customer_id == filters.customer_id)
        if filters.assigned_user_id is not None:
            statement = statement.where(FollowUp.assigned_user_id == filters.assigned_user_id)
        if filters.unassigned_only:
            statement = statement.where(FollowUp.assigned_user_id.is_(None))
        if filters.due_from is not None:
            statement = statement.where(FollowUp.due_date >= filters.due_from)
        if filters.due_to is not None:
            statement = statement.where(FollowUp.due_date <= filters.due_to)
        if filters.overdue_only:
            statement = statement.where(
                FollowUp.due_date < utc_now(),
                FollowUp.status.notin_(NOT_OVERDUE_STATUSES),
            )
        if filters.search:
            pattern = f"%{filters.search}%"
            statement = statement.where(
                or_(FollowUp.reason.ilike(pattern), Customer.name.ilike(pattern)),
            )
        return statement

    def list_filtered(
        self,
        organization_id: UUID,
        filters: FollowUpListFilters,
        policy: "AuthorizationPolicy | None" = None,
        auth_context: "AuthorizationContext | None" = None,
    ) -> tuple[list[FollowUp], int]:
        base = self._apply_filters(self._base_org_statement(organization_id), filters)
        if policy is not None and auth_context is not None:
            base = policy.apply_query_filter(auth_context, base, owner_field="assigned_user_id")

        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0

        page = max(filters.page, 1)
        page_size = max(min(filters.page_size, 200), 1)
        statement = (
            base.order_by(FollowUp.due_date.asc(), FollowUp.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.scalars(statement))
        return items, total

    def count_by_customer(self, customer_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(FollowUp)
            .where(FollowUp.customer_id == customer_id)
        )
        return self.db.scalar(statement) or 0

    def delete_for_customer(self, customer_id: UUID) -> None:
        self.db.execute(delete(FollowUp).where(FollowUp.customer_id == customer_id))
        self.db.flush()

    def reassign_open_by_user(
        self,
        organization_id: UUID,
        from_user_id: UUID,
        to_user_id: UUID,
    ) -> int:
        customer_ids = select(Customer.id).where(Customer.organization_id == organization_id)
        statement = (
            update(FollowUp)
            .where(
                FollowUp.customer_id.in_(customer_ids),
                FollowUp.assigned_user_id == from_user_id,
                FollowUp.status.in_(
                    (FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS),
                ),
            )
            .values(assigned_user_id=to_user_id)
        )
        result = self.db.execute(statement)
        return result.rowcount or 0

    def count_unassigned_open(self, organization_id: UUID) -> int:
        statement = self._base_org_statement(organization_id).where(
            FollowUp.assigned_user_id.is_(None),
            FollowUp.status.in_(
                (FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS),
            ),
        )
        return self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    def _dashboard_base(self, organization_id: UUID, user_id: UUID | None):
        statement = self._base_org_statement(organization_id)
        if user_id is not None:
            statement = statement.where(FollowUp.assigned_user_id == user_id)
        return statement

    def count_today(self, organization_id: UUID, user_id: UUID | None = None) -> int:
        now = utc_now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        statement = self._dashboard_base(organization_id, user_id).where(
            FollowUp.due_date >= start,
            FollowUp.due_date <= end,
            FollowUp.status.notin_(NOT_OVERDUE_STATUSES),
        )
        return self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    def count_overdue(self, organization_id: UUID, user_id: UUID | None = None) -> int:
        statement = self._dashboard_base(organization_id, user_id).where(
            FollowUp.due_date < utc_now(),
            FollowUp.status.notin_(NOT_OVERDUE_STATUSES),
        )
        return self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    def count_upcoming_7days(self, organization_id: UUID, user_id: UUID | None = None) -> int:
        now = utc_now()
        statement = self._dashboard_base(organization_id, user_id).where(
            FollowUp.due_date > now,
            FollowUp.due_date <= now + timedelta(days=7),
            FollowUp.status.notin_(NOT_OVERDUE_STATUSES),
        )
        return self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    def count_completed_today(self, organization_id: UUID, user_id: UUID | None = None) -> int:
        now = utc_now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        statement = self._dashboard_base(organization_id, user_id).where(
            FollowUp.status == FollowUpStatus.COMPLETED,
            FollowUp.completed_at >= start,
            FollowUp.completed_at <= end,
        )
        return self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0


class SampleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, sample: Sample) -> Sample:
        self.db.add(sample)
        self.db.flush()
        return sample

    def delete(self, sample: Sample) -> None:
        self.db.delete(sample)
        self.db.flush()

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

    def count_by_customer(self, customer_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(Sample)
            .where(Sample.customer_id == customer_id)
        )
        return self.db.scalar(statement) or 0

    def delete_for_customer(self, customer_id: UUID) -> None:
        sample_ids = select(Sample.id).where(Sample.customer_id == customer_id)
        self.db.execute(delete(SampleEvaluation).where(SampleEvaluation.sample_id.in_(sample_ids)))
        self.db.execute(delete(Sample).where(Sample.customer_id == customer_id))
        self.db.flush()

    def get_highest_sample_code_sequence(self, organization_id: UUID, year: int) -> int:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            import re
            statement = (
                select(Sample.sample_code)
                .join(Customer, Customer.id == Sample.customer_id)
                .where(Customer.organization_id == organization_id)
            )
            highest = 0
            for code in self.db.scalars(statement):
                m = re.match(rf"^RFS-{year}-([0-9]+)$", code, re.IGNORECASE)
                if m:
                    highest = max(highest, int(m.group(1)))
            return highest

        pattern = f"^RFS-{year}-([0-9]+)$"
        sequence_text = func.substring(Sample.sample_code, pattern)
        statement = (
            select(func.coalesce(func.max(sequence_text.cast(Integer)), 0))
            .join(Customer, Customer.id == Sample.customer_id)
            .where(Customer.organization_id == organization_id)
        )
        return int(self.db.scalar(statement) or 0)

    def ensure_code_counter(self, organization_id: UUID, year: int, last_value: int) -> None:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            counter = self.db.get(SampleCodeCounter, (organization_id, year))
            if counter is None:
                self.db.add(
                    SampleCodeCounter(
                        organization_id=organization_id,
                        year=year,
                        last_value=last_value,
                    )
                )
                self.db.flush()
            return

        statement = (
            insert(SampleCodeCounter)
            .values(organization_id=organization_id, year=year, last_value=last_value)
            .on_conflict_do_nothing(
                index_elements=[SampleCodeCounter.organization_id, SampleCodeCounter.year]
            )
        )
        self.db.execute(statement)
        self.db.flush()

    def get_code_counter_for_update(self, organization_id: UUID, year: int) -> SampleCodeCounter | None:
        statement = (
            select(SampleCodeCounter)
            .where(
                SampleCodeCounter.organization_id == organization_id,
                SampleCodeCounter.year == year,
            )
            .with_for_update()
        )
        return self.db.scalar(statement)


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

    def count_by_sample(self, sample_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(SampleEvaluation)
            .where(SampleEvaluation.sample_id == sample_id)
        )
        return self.db.scalar(statement) or 0

    def delete_for_sample(self, sample_id: UUID) -> None:
        self.db.execute(delete(SampleEvaluation).where(SampleEvaluation.sample_id == sample_id))
        self.db.flush()


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

    def count_by_customer(self, customer_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(Quote)
            .where(Quote.customer_id == customer_id)
        )
        return self.db.scalar(statement) or 0

    def count_by_sample(self, sample_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(Quote)
            .where(Quote.sample_id == sample_id)
        )
        return self.db.scalar(statement) or 0

    def count_by_year_prefix(self, organization_id: UUID, prefix: str) -> int:
        from sqlalchemy import func
        statement = (
            select(func.count())
            .select_from(Quote)
            .where(
                Quote.organization_id == organization_id,
                Quote.quote_number.like(f"{prefix}%"),
            )
        )
        return self.db.scalar(statement) or 0

    def get_highest_quote_number_sequence(self, organization_id: UUID, year: int) -> int:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            import re

            statement = select(Quote.quote_number).where(
                Quote.organization_id == organization_id,
            )
            highest = 0
            for quote_number in self.db.scalars(statement):
                match = re.match(rf"^(?:RFQ|QT)-{year}-([0-9]+)$", quote_number, re.IGNORECASE)
                if match:
                    highest = max(highest, int(match.group(1)))
            return highest

        pattern = f"^(?:RFQ|QT)-{year}-([0-9]+)$"
        sequence_text = func.substring(Quote.quote_number, pattern)
        statement = select(func.coalesce(func.max(sequence_text.cast(Integer)), 0)).where(
            Quote.organization_id == organization_id,
        )
        return int(self.db.scalar(statement) or 0)

    def ensure_code_counter(self, organization_id: UUID, year: int, last_value: int) -> None:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            counter = self.db.get(QuoteCodeCounter, (organization_id, year))
            if counter is None:
                self.db.add(
                    QuoteCodeCounter(
                        organization_id=organization_id,
                        year=year,
                        last_value=last_value,
                    ),
                )
                self.db.flush()
            return

        statement = (
            insert(QuoteCodeCounter)
            .values(organization_id=organization_id, year=year, last_value=last_value)
            .on_conflict_do_nothing(
                index_elements=[QuoteCodeCounter.organization_id, QuoteCodeCounter.year],
            )
        )
        self.db.execute(statement)
        self.db.flush()

    def get_code_counter_for_update(
        self,
        organization_id: UUID,
        year: int,
    ) -> QuoteCodeCounter | None:
        statement = (
            select(QuoteCodeCounter)
            .where(
                QuoteCodeCounter.organization_id == organization_id,
                QuoteCodeCounter.year == year,
            )
            .with_for_update()
        )
        return self.db.scalar(statement)

    def delete(self, quote: Quote) -> None:
        self.db.delete(quote)
        self.db.flush()


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

    def count_by_customer(self, customer_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(CommercialOrder)
            .where(CommercialOrder.customer_id == customer_id)
        )
        return self.db.scalar(statement) or 0

    def count_by_quote(self, quote_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(CommercialOrder)
            .where(CommercialOrder.quote_id == quote_id)
        )
        return self.db.scalar(statement) or 0

    def get_highest_order_number_sequence(self, organization_id: UUID, year: int) -> int:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            import re

            statement = select(CommercialOrder.order_number).where(
                CommercialOrder.organization_id == organization_id,
            )
            highest = 0
            for order_number in self.db.scalars(statement):
                match = re.match(rf"^(?:RFS|SO)-{year}-([0-9]+)$", order_number, re.IGNORECASE)
                if match:
                    highest = max(highest, int(match.group(1)))
            return highest

        pattern = f"^(?:RFS|SO)-{year}-([0-9]+)$"
        sequence_text = func.substring(CommercialOrder.order_number, pattern)
        statement = select(func.coalesce(func.max(sequence_text.cast(Integer)), 0)).where(
            CommercialOrder.organization_id == organization_id,
        )
        return int(self.db.scalar(statement) or 0)

    def ensure_code_counter(self, organization_id: UUID, year: int, last_value: int) -> None:
        if self.db.bind is not None and self.db.bind.dialect.name != "postgresql":
            counter = self.db.get(OrderCodeCounter, (organization_id, year))
            if counter is None:
                self.db.add(
                    OrderCodeCounter(
                        organization_id=organization_id,
                        year=year,
                        last_value=last_value,
                    ),
                )
                self.db.flush()
            return

        statement = (
            insert(OrderCodeCounter)
            .values(organization_id=organization_id, year=year, last_value=last_value)
            .on_conflict_do_nothing(
                index_elements=[OrderCodeCounter.organization_id, OrderCodeCounter.year],
            )
        )
        self.db.execute(statement)
        self.db.flush()

    def get_code_counter_for_update(self, organization_id: UUID, year: int) -> OrderCodeCounter | None:
        statement = (
            select(OrderCodeCounter)
            .where(
                OrderCodeCounter.organization_id == organization_id,
                OrderCodeCounter.year == year,
            )
            .with_for_update()
        )
        return self.db.scalar(statement)

    def delete(self, order: CommercialOrder) -> None:
        self.db.delete(order)
        self.db.flush()
