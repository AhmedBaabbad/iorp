from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commercial.api.schemas import QuoteCreate, QuoteDeletionImpact, QuoteItemCreate, QuoteUpdate
from app.commercial.domain.enums import QuoteStatus
from app.commercial.infrastructure.models import Quote, QuoteItem
from app.commercial.infrastructure.repositories import (
    CommercialOrderRepository,
    CustomerRepository,
    QuoteRepository,
    SampleRepository,
)
from app.core.tenancy import TenantContext
from app.core.utils import utc_now


class QuoteService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.samples = SampleRepository(db)
        self.quotes = QuoteRepository(db)
        self.orders = CommercialOrderRepository(db)

    @staticmethod
    def _build_quote_items(items: list[QuoteItemCreate]) -> list[QuoteItem]:
        return [
            QuoteItem(
                line_no=item.line_no,
                product_type=item.product_type,
                requested_spec_json=item.requested_spec_json,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                line_total=item.quantity * item.unit_price,
            )
            for item in items
        ]

    @staticmethod
    def _calculate_quote_total(
        items: list[QuoteItem],
        discount_amount: Decimal,
        tax_amount: Decimal,
    ) -> tuple[Decimal, Decimal]:
        subtotal_amount = sum((item.line_total for item in items), Decimal("0"))
        total_amount = subtotal_amount - discount_amount + tax_amount
        if total_amount < 0:
            raise ValueError("Quote total cannot be negative.")
        return subtotal_amount, total_amount

    def _generate_quote_number(self, tenant: TenantContext) -> str:
        year = utc_now().year
        highest_sequence = self.quotes.get_highest_quote_number_sequence(
            tenant.organization_id,
            year,
        )
        self.quotes.ensure_code_counter(tenant.organization_id, year, highest_sequence)

        counter = self.quotes.get_code_counter_for_update(tenant.organization_id, year)
        if counter is None:
            raise ValueError("Quote number counter could not be initialized.")

        counter.last_value += 1
        return f"RFQ-{year}-{counter.last_value:04d}"

    def create_quote(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: QuoteCreate,
    ) -> Quote | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        if data.sample_id is not None:
            sample = self.samples.get_by_id(tenant.organization_id, data.sample_id)
            if sample is None or sample.customer_id != customer.id:
                raise ValueError("Sample must belong to the target customer.")

        items = self._build_quote_items(data.items)
        subtotal_amount, total_amount = self._calculate_quote_total(
            items,
            data.discount_amount,
            data.tax_amount,
        )

        quote = Quote(
            organization_id=tenant.organization_id,
            customer_id=customer.id,
            quote_number=self._generate_quote_number(tenant),
            created_by_user_id=tenant.user_id,
            status=QuoteStatus.DRAFT,
            subtotal_amount=subtotal_amount,
            total_amount=total_amount,
            items=items,
            **data.model_dump(exclude={"items"}),
        )

        try:
            self.quotes.add(quote)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Quote could not be saved due to invalid or duplicate data.") from exc

        return self.quotes.get_by_id(tenant.organization_id, quote.id)

    def list_quotes(self, tenant: TenantContext) -> list[Quote]:
        return self.quotes.list_by_organization(tenant.organization_id)

    def list_quotes_for_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> list[Quote] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        return self.quotes.list_by_customer(tenant.organization_id, customer_id)

    def get_quote(self, tenant: TenantContext, quote_id: UUID) -> Quote | None:
        return self.quotes.get_by_id(tenant.organization_id, quote_id)

    def get_deletion_impact(
        self,
        tenant: TenantContext,
        quote_id: UUID,
    ) -> QuoteDeletionImpact | None:
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id)
        if quote is None:
            return None

        orders = self.orders.count_by_quote(quote.id)
        return QuoteDeletionImpact(
            items=len(quote.items),
            orders=orders,
            is_blocked=orders > 0,
        )

    def delete_quote(self, tenant: TenantContext, quote_id: UUID) -> bool:
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id)
        if quote is None:
            return False

        if self.orders.count_by_quote(quote.id) > 0:
            raise ValueError(
                "Cannot delete a quote that is referenced by orders. Remove the orders first.",
            )

        self.quotes.delete(quote)
        self.db.commit()
        return True

    def update_quote(
        self,
        tenant: TenantContext,
        quote_id: UUID,
        data: QuoteUpdate,
    ) -> Quote | None:
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id)
        if quote is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        items_payload = payload.pop("items", None)

        if "sample_id" in payload and payload["sample_id"] is not None:
            sample = self.samples.get_by_id(tenant.organization_id, payload["sample_id"])
            if sample is None or sample.customer_id != quote.customer_id:
                raise ValueError("Sample must belong to the target customer.")

        for field, value in payload.items():
            setattr(quote, field, value)

        if items_payload is not None:
            quote.items = self._build_quote_items(
                [QuoteItemCreate(**item) for item in items_payload]
            )

        subtotal_amount, total_amount = self._calculate_quote_total(
            quote.items,
            quote.discount_amount,
            quote.tax_amount,
        )
        quote.subtotal_amount = subtotal_amount
        quote.total_amount = total_amount

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Quote could not be saved due to invalid or duplicate data.") from exc

        return self.quotes.get_by_id(tenant.organization_id, quote.id)
