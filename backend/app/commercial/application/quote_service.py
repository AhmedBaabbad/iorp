"""Quotations. A draft is edited; issuing sends it to the customer, who accepts or rejects it. An accepted quotation is
final (a sales order is made from it); an issued, rejected or expired one goes back to a draft as a new revision, with a
reason. Every step is written to the status history (SALES-001, commercial/domain/lifecycle.py)."""
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commercial.application import status_history
from app.commercial.application.product_rules import assert_known_products, assert_vat_rate
from app.commercial.domain import lifecycle as L
from app.commercial.api.schemas import QuoteCreate, QuoteDeletionImpact, QuoteItemCreate, QuoteUpdate
from app.commercial.domain.enums import QuoteStatus
from app.commercial.infrastructure.models import Quote, QuoteItem
from app.commercial.infrastructure.repositories import (
    customer_labels,
    CommercialOrderRepository,
    CustomerRepository,
    QuoteRepository,
    SampleRepository,
)
from app.core.tenancy import TenantContext
from app.core.utils import utc_now


def _all(_action) -> bool:
    return True


class QuoteService:
    def __init__(self, db: Session, owner_user_id: UUID | None = None) -> None:
        """owner_user_id: see only the records of this sales owner's customers (RBAC-002, visibility.py)."""
        self.db = db
        self.customers = CustomerRepository(db)
        self.samples = SampleRepository(db)
        self.quotes = QuoteRepository(db)
        self.orders = CommercialOrderRepository(db)
        self.samples.owner_user_id = owner_user_id
        self.quotes.owner_user_id = owner_user_id
        self.customers.owner_user_id = owner_user_id
        self.orders.owner_user_id = owner_user_id

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
                description_ar=item.description_ar,
                description_en=item.description_en,
            )
            for item in items
        ]

    @staticmethod
    def _tax_from_rate(items: list[QuoteItem], discount_amount: Decimal, tax_rate: Decimal) -> Decimal:
        """VAT on the discounted subtotal, rounded to halalas (0.01)."""
        subtotal_amount = sum((item.line_total for item in items), Decimal("0"))
        return (max(subtotal_amount - discount_amount, Decimal("0")) * tax_rate / 100).quantize(Decimal("0.01"))

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
        # QT = quotation issued by us. The sequence continues across the former RFQ- numbers.
        return f"QT-{year}-{counter.last_value:04d}"

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

        assert_known_products(self.db, tenant.organization_id, [item.product_type for item in data.items])
        assert_vat_rate(self.db, tenant.organization_id, data.tax_rate)
        items = self._build_quote_items(data.items)
        if data.tax_rate is not None:
            data = data.model_copy(update={"tax_amount": self._tax_from_rate(items, data.discount_amount, data.tax_rate)})
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
            self.db.flush()
            status_history.record(self.db, tenant.organization_id, status_history.QUOTE, quote.id, "create", None,
                                  quote.status, quote.revision, tenant.user_id)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Quote could not be saved due to invalid or duplicate data.") from exc

        return self.get_quote(tenant, quote.id)

    def list_quotes(self, tenant: TenantContext) -> list[Quote]:
        return self.quotes.list_by_organization(tenant.organization_id)

    def page_quotes(self, tenant: TenantContext, filters, params):
        """One page of quotations, each with its customer's name (read once for the whole page)."""
        quotes, total = self.quotes.page(tenant.organization_id, filters, params)
        labels = customer_labels(self.db, tenant.organization_id, [q.customer_id for q in quotes])
        for quote in quotes:
            quote.customer_name, quote.customer_code = labels.get(quote.customer_id, (None, None))
        return quotes, total

    def list_quotes_for_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> list[Quote] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        return self.quotes.list_by_customer(tenant.organization_id, customer_id)

    def get_quote(self, tenant: TenantContext, quote_id: UUID, can=_all) -> Quote | None:
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id)
        if quote is not None:
            orders = self.orders.list_by_quote(tenant.organization_id, quote.id)
            quote.orders = [dict(id=o.id, order_number=o.order_number, status=o.status) for o in orders]
            open_order = any(L.value(o.status) != L.CANCELLED for o in orders)
            quote.allowed_actions = [a for a in L.quote_actions(quote.status, True, True)
                                     if can(a) and not (a == "create_order" and open_order)]
            quote.history = status_history.history(self.db, tenant.organization_id, status_history.QUOTE, quote.id)
        return quote

    def transition(self, tenant: TenantContext, quote_id: UUID, action: str, reason: str | None = None) -> Quote | None:
        """issue · accept · reject · expire · revise (back to a draft as a new revision)."""
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id, lock=True)
        if quote is None:
            return None
        new = {"issue": L.ISSUED, "accept": L.ACCEPTED, "reject": L.REJECTED, "expire": L.EXPIRED, "revise": L.DRAFT}[action]
        L.assert_quote_transition(quote.status, new, reason)
        before = quote.status
        if action == "revise":
            quote.revision += 1
        quote.status = QuoteStatus(new)
        status_history.record(self.db, tenant.organization_id, status_history.QUOTE, quote.id, action, before, new,
                              quote.revision, tenant.user_id, reason)
        self.db.commit()
        return self.get_quote(tenant, quote.id)

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
            is_blocked=orders > 0 or quote.status == QuoteStatus.ACCEPTED,
        )

    def delete_quote(self, tenant: TenantContext, quote_id: UUID) -> bool:
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id)
        if quote is None:
            return False

        if self.orders.count_by_quote(quote.id) > 0:
            raise ValueError(
                "Cannot delete a quote that is referenced by orders. Remove the orders first.",
            )
        if quote.status == QuoteStatus.ACCEPTED:
            raise ValueError("QUOTE_ACCEPTED")

        status_history.forget(self.db, tenant.organization_id, status_history.QUOTE, quote.id)
        self.quotes.delete(quote)
        self.db.commit()
        return True

    def update_quote(
        self,
        tenant: TenantContext,
        quote_id: UUID,
        data: QuoteUpdate,
    ) -> Quote | None:
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id, lock=True)
        if quote is None:
            return None
        L.assert_quote_editable(quote.status)

        payload = data.model_dump(exclude_unset=True)
        items_payload = payload.pop("items", None)

        if "sample_id" in payload and payload["sample_id"] is not None:
            sample = self.samples.get_by_id(tenant.organization_id, payload["sample_id"])
            if sample is None or sample.customer_id != quote.customer_id:
                raise ValueError("Sample must belong to the target customer.")

        if "tax_rate" in payload:
            assert_vat_rate(self.db, tenant.organization_id, payload["tax_rate"], keep=quote.tax_rate)
        for field, value in payload.items():
            setattr(quote, field, value)

        if items_payload is not None:
            assert_known_products(self.db, tenant.organization_id, [item["product_type"] for item in items_payload],
                                  keep=[item.product_type for item in quote.items])
            quote.items = self._build_quote_items(
                [QuoteItemCreate(**item) for item in items_payload]
            )
        if quote.tax_rate is not None:
            quote.tax_amount = self._tax_from_rate(quote.items, quote.discount_amount, quote.tax_rate)

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

        return self.get_quote(tenant, quote.id)
