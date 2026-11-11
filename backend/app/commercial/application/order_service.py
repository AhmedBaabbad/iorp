"""Sales orders (أمر البيع الداخلي, SALES-001): the agreement with the customer, the source of production demands.

A draft is edited freely; confirming locks its lines, quantities, specifications and prices. Production takes it in parts
(production demands record how much of each line they took); a confirmed order goes back to a draft or is cancelled only
while nothing of it is with production. Every step is written to the status history. Rules: commercial/domain/lifecycle.py.
"""
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.interfaces import approvals
from app.commercial.application import status_history
from app.commercial.application.product_rules import assert_known_products
from app.commercial.api.schemas import (
    CommercialOrderCreate,
    CommercialOrderItemCreate,
    CommercialOrderUpdate,
    OrderDeletionImpact,
)
from app.commercial.domain import pricing
from app.commercial.domain import lifecycle as L
from app.commercial.domain.enums import CommercialOrderStatus, QuoteStatus
from app.commercial.infrastructure.models import CommercialOrder, CommercialOrderItem, Quote
from app.commercial.infrastructure.repositories import (
    customer_labels,
    CommercialOrderRepository,
    CustomerRepository,
    QuoteRepository,
)
from app.core.interfaces import product_catalog, sales_order_source
from app.core.tenancy import TenantContext
from app.core.units import UNITS
from app.core.utils import utc_now
from app.core import numbering

CURRENCIES = ("SAR", "USD")


def _all(_action) -> bool:
    return True


class OrderService:
    def __init__(self, db: Session, owner_user_id: UUID | None = None) -> None:
        """owner_user_id: see only the records of this sales owner's customers (RBAC-002, visibility.py)."""
        self.db = db
        self.customers = CustomerRepository(db)
        self.quotes = QuoteRepository(db)
        self.orders = CommercialOrderRepository(db)
        self.quotes.owner_user_id = owner_user_id
        self.customers.owner_user_id = owner_user_id
        self.orders.owner_user_id = owner_user_id

    @staticmethod
    def _build_order_items(items: list[CommercialOrderItemCreate]) -> list[CommercialOrderItem]:
        return [
            CommercialOrderItem(
                line_no=item.line_no,
                product_type=item.product_type,
                requested_spec_json=item.requested_spec_json,
                quantity=item.quantity,
                unit=item.unit,
                agreed_unit_price=item.agreed_unit_price,
                line_total=(
                    pricing.line_total(item.quantity, item.agreed_unit_price)
                    if item.agreed_unit_price is not None
                    else None
                ),
            )
            for item in items
        ]

    def _generate_order_number(self, tenant: TenantContext) -> str:
        year = numbering.organization_year(self.db, tenant.organization_id)
        highest_sequence = self.orders.get_highest_order_number_sequence(tenant.organization_id, year)
        self.orders.ensure_code_counter(tenant.organization_id, year, highest_sequence)
        counter = self.orders.get_code_counter_for_update(tenant.organization_id, year)
        if counter is None:
            raise ValueError("Order number counter could not be initialized.")
        counter.last_value += 1
        return f"RFS-{year}-{counter.last_value:04d}"

    def _quote_of(self, tenant, quote_id, customer_id):
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id)
        if quote is None or quote.customer_id != customer_id:
            raise ValueError("Quote must belong to the target customer.")
        return quote

    def _assert_quote_free(self, tenant, quote_id, order_id=None):
        """One sales order in force per quotation (a cancelled one frees it)."""
        query = select(CommercialOrder.order_number).where(
            CommercialOrder.organization_id == tenant.organization_id, CommercialOrder.quote_id == quote_id,
            CommercialOrder.status != CommercialOrderStatus.CANCELLED)
        if order_id is not None:
            query = query.where(CommercialOrder.id != order_id)
        taken = self.db.scalar(query.limit(1))
        if taken:
            raise ValueError(f"ORDER_EXISTS_FOR_QUOTE:{taken}")

    def _validate_items(self, tenant, items, previous=()):
        """Lines numbered once, units from the catalogue, and the specification of a catalogue product by its template.

        previous: lines already written (on this order, or on its quotation); a product and specification carried from
        them as they are is not re-checked, so a quotation written before the product list still becomes an order.
        """
        lines = [i.line_no for i in items]
        if len(lines) != len(set(lines)):
            raise ValueError("ORDER_DUPLICATE_LINE")
        known = product_catalog.products(self.db, tenant.organization_id, [i.product_type for i in items])
        before = [(p.product_type, p.requested_spec_json or {}) for p in previous]
        for item in items:
            if item.unit not in UNITS:
                raise ValueError("ORDER_UNIT_INVALID")
            spec = item.requested_spec_json or {}
            if item.product_type not in known or (item.product_type, spec) in before:
                continue
            same = next((s for k, s in before if k == item.product_type), None)
            try:
                product_catalog.validate_sample_properties(self.db, tenant.organization_id, item.product_type, spec,
                                                           existing_key=item.product_type if same is not None else None,
                                                           existing_values=same)
            except product_catalog.ProductSpecificationError as exc:
                raise ValueError(f"ORDER_SPEC_INVALID:{exc.property_key or ''}") from exc

    @staticmethod
    def _currency(currency, items, default):
        if currency and currency not in CURRENCIES:
            raise ValueError("ORDER_CURRENCY_UNKNOWN")
        priced = any(i.agreed_unit_price is not None for i in items)
        return currency or (default if priced else None)

    def _save(self):
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Order could not be saved due to invalid or duplicate data.") from exc

    def create_order(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: CommercialOrderCreate,
    ) -> CommercialOrder | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        quote = self._quote_of(tenant, data.quote_id, customer.id) if data.quote_id is not None else None
        if quote is not None:
            self._assert_quote_free(tenant, quote.id)
        # From a quotation, its lines' product types carry over even if written before the product list.
        assert_known_products(self.db, tenant.organization_id, [item.product_type for item in data.items],
                              keep=[item.product_type for item in quote.items] if quote is not None else ())
        self._validate_items(tenant, data.items, quote.items if quote is not None else ())
        default = quote.currency if quote is not None else product_catalog.business_settings(self.db, tenant.organization_id).default_currency
        order = CommercialOrder(
            organization_id=tenant.organization_id,
            customer_id=customer.id,
            order_number=self._generate_order_number(tenant),
            created_by_user_id=tenant.user_id,
            status=CommercialOrderStatus.DRAFT,
            items=self._build_order_items(data.items),
            **data.model_dump(exclude={"items", "currency"}),
            currency=self._currency(data.currency, data.items, default),
        )
        self.orders.add(order)
        self.db.flush()
        status_history.record(self.db, tenant.organization_id, status_history.SALES_ORDER, order.id, "create", None,
                              order.status, order.revision, tenant.user_id)
        self._save()
        return self.get_order(tenant, order.id)

    def create_from_quote(self, tenant: TenantContext, quote_id: UUID) -> CommercialOrder | None:
        """A draft sales order with the accepted quotation's lines, specifications, prices and currency. From then on
        the two documents are independent: changing the order does not change the quotation."""
        quote = self.quotes.get_by_id(tenant.organization_id, quote_id)
        if quote is None:
            return None
        if quote.status != QuoteStatus.ACCEPTED:
            raise ValueError("ORDER_QUOTE_NOT_ACCEPTED")
        self._assert_quote_free(tenant, quote.id)
        lines = sorted(quote.items, key=lambda i: i.line_no)
        # The price the customer accepted: after each line's discount (domain/pricing.py).
        items = [CommercialOrderItemCreate(line_no=i.line_no, product_type=i.product_type, requested_spec_json=i.requested_spec_json,
                                           quantity=i.quantity, unit=i.unit, agreed_unit_price=pricing.net_unit_price(i.unit_price, i.discount_percent))
                 for i in lines]
        order = CommercialOrder(
            organization_id=tenant.organization_id, customer_id=quote.customer_id, quote_id=quote.id,
            order_number=self._generate_order_number(tenant), created_by_user_id=tenant.user_id,
            status=CommercialOrderStatus.DRAFT, order_date=utc_now(), currency=quote.currency,
            items=self._build_order_items(items),
        )
        for line, source in zip(order.items, lines):
            line.line_total = source.net_total  # exactly the quotation's line after discount
        self.orders.add(order)
        self.db.flush()
        status_history.record(self.db, tenant.organization_id, status_history.SALES_ORDER, order.id, "create", None,
                              order.status, order.revision, tenant.user_id, quote.quote_number)
        self._save()
        return self.get_order(tenant, order.id)

    def list_orders(self, tenant: TenantContext) -> list[CommercialOrder]:
        return self.orders.list_by_organization(tenant.organization_id)

    def page_orders(self, tenant: TenantContext, filters, params):
        """One page of sales orders, each with its customer's name and its quotation's number (read once per page)."""
        orders, total = self.orders.page(tenant.organization_id, filters, params)
        labels = customer_labels(self.db, tenant.organization_id, [o.customer_id for o in orders])
        quote_ids = {o.quote_id for o in orders if o.quote_id}
        numbers = dict(self.db.execute(select(Quote.id, Quote.quote_number).where(
            Quote.organization_id == tenant.organization_id, Quote.id.in_(quote_ids))).all()) if quote_ids else {}
        for order in orders:
            order.customer_name, order.customer_code = labels.get(order.customer_id, (None, None))
            order.quote_number = numbers.get(order.quote_id)
        return orders, total

    def list_orders_for_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> list[CommercialOrder] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        return self.orders.list_by_customer(tenant.organization_id, customer_id)

    def _sent(self, tenant, order) -> dict[UUID, Decimal]:
        """How much of each line the production demands in force took."""
        usage = sales_order_source.usage
        return usage.quantities(self.db, tenant.organization_id, order.id) if usage else {}

    def _has_history(self, tenant, order) -> bool:
        usage = sales_order_source.usage
        return bool(usage and usage.has_history(self.db, tenant.organization_id, order.id))

    def get_order(self, tenant: TenantContext, order_id: UUID, can=_all) -> CommercialOrder | None:
        order = self.orders.get_by_id(tenant.organization_id, order_id)
        if order:
            sent = self._sent(tenant, order)
            lines = [(i.quantity, sent.get(i.id, Decimal(0))) for i in order.items]
            order.fulfilment = L.fulfilment(lines)
            in_production = any(q > 0 for q in sent.values())
            order.allowed_actions = L.order_actions(order.status, in_production, order.fulfilment == "full", can)
            order.confirm_blocked_reason = None
            if (order.created_by_user_id == tenant.user_id and not tenant.is_organization_root
                    and "confirm" in order.allowed_actions):
                order.allowed_actions.remove("confirm")
                order.confirm_blocked_reason = "preparer"
            if "delete" in order.allowed_actions and (order.revision > 1 or self._has_history(tenant, order)):
                order.allowed_actions.remove("delete")
            order.transferred_quantities = {str(i.id): sent.get(i.id, Decimal(0)) for i in order.items}
            order.history = status_history.history(self.db, tenant.organization_id, status_history.SALES_ORDER, order.id)
        return order

    def _lock(self, tenant, order_id):
        self.db.scalar(select(CommercialOrder.id).where(CommercialOrder.organization_id == tenant.organization_id,
                                                        CommercialOrder.id == order_id).with_for_update())
        self.db.expire_all()
        return self.orders.get_by_id(tenant.organization_id, order_id)

    def update_order(
        self,
        tenant: TenantContext,
        order_id: UUID,
        data: CommercialOrderUpdate,
    ) -> CommercialOrder | None:
        """A draft only; the status changes through confirm, revise and cancel."""
        order = self._lock(tenant, order_id)
        if order is None:
            return None
        L.assert_order_editable(order.status)

        payload = data.model_dump(exclude_unset=True)
        items_payload = payload.pop("items", None)
        if payload.get("quote_id") is not None:
            self._quote_of(tenant, payload["quote_id"], order.customer_id)
            self._assert_quote_free(tenant, payload["quote_id"], order.id)
        for field, value in payload.items():
            if field != "currency":
                setattr(order, field, value)

        if items_payload is not None:
            items = [CommercialOrderItemCreate(**item) for item in items_payload]
            quote = self.quotes.get_by_id(tenant.organization_id, order.quote_id) if order.quote_id else None
            previous = [*order.items, *(quote.items if quote is not None else [])]
            assert_known_products(self.db, tenant.organization_id, [item.product_type for item in items],
                                  keep=[item.product_type for item in previous])
            self._validate_items(tenant, items, previous)
            order.items = self._build_order_items(items)
        if "currency" in payload or items_payload is not None:
            default = product_catalog.business_settings(self.db, tenant.organization_id).default_currency
            order.currency = self._currency(payload.get("currency", order.currency), order.items, default)
        self._save()
        return self.get_order(tenant, order.id)

    def _transition(self, tenant, order, action, new_status, reason=None):
        before = order.status
        order.status = new_status
        status_history.record(self.db, tenant.organization_id, status_history.SALES_ORDER, order.id, action, before,
                              new_status, order.revision, tenant.user_id, reason)
        self._save()
        return self.get_order(tenant, order.id)

    def confirm(self, tenant: TenantContext, order_id: UUID) -> CommercialOrder | None:
        """The order becomes the agreement production works from: nothing on it changes afterwards."""
        order = self._lock(tenant, order_id)
        if order is None:
            return None
        L.assert_order_transition(order.status, L.CONFIRMED, None, False)
        quote = self.quotes.get_by_id(tenant.organization_id, order.quote_id) if order.quote_id else None
        L.assert_can_confirm(len(order.items), quote.status if quote is not None else None, order.customer_reference,
                             any(i.agreed_unit_price is not None for i in order.items), order.currency)
        if order.created_by_user_id == tenant.user_id and not tenant.is_organization_root:
            raise ValueError("ORDER_CONFIRMER_IS_PREPARER")  # separation of duties (the organization's root excepted)
        order.confirmed_at, order.confirmed_by_user_id = utc_now(), tenant.user_id
        approvals.sign(self.db, tenant, "sales_order", order.id, "confirm", "commercial:orders:confirm")
        return self._transition(tenant, order, "confirm", CommercialOrderStatus.CONFIRMED)

    def revise(self, tenant: TenantContext, order_id: UUID, reason: str) -> CommercialOrder | None:
        """Back to a draft as a new revision, only while nothing of it is with production."""
        order = self._lock(tenant, order_id)
        if order is None:
            return None
        L.assert_order_transition(order.status, L.DRAFT, reason, any(q > 0 for q in self._sent(tenant, order).values()))
        order.revision += 1
        order.confirmed_at = order.confirmed_by_user_id = None
        return self._transition(tenant, order, "revise", CommercialOrderStatus.DRAFT, reason)

    def cancel(self, tenant: TenantContext, order_id: UUID, reason: str) -> CommercialOrder | None:
        order = self._lock(tenant, order_id)
        if order is None:
            return None
        L.assert_order_transition(order.status, L.CANCELLED, reason, any(q > 0 for q in self._sent(tenant, order).values()))
        return self._transition(tenant, order, "cancel", CommercialOrderStatus.CANCELLED, reason)

    def get_deletion_impact(
        self,
        tenant: TenantContext,
        order_id: UUID,
    ) -> OrderDeletionImpact | None:
        order = self.orders.get_by_id(tenant.organization_id, order_id)
        if order is None:
            return None

        return OrderDeletionImpact(
            items=len(order.items),
            is_blocked=order.status != CommercialOrderStatus.DRAFT or order.revision > 1 or self._has_history(tenant, order),
        )

    def delete_order(self, tenant: TenantContext, order_id: UUID) -> bool:
        """A draft that was never confirmed and never sent to production; otherwise it is cancelled, so its history stays."""
        order = self._lock(tenant, order_id)
        if order is None:
            return False
        if order.status != CommercialOrderStatus.DRAFT or order.revision > 1 or self._has_history(tenant, order):
            raise ValueError("ORDER_LOCKED")
        status_history.forget(self.db, tenant.organization_id, status_history.SALES_ORDER, order.id)
        self.orders.delete(order)
        self.db.commit()
        return True
