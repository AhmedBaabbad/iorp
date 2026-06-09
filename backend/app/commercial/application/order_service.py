from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commercial.api.schemas import (
    CommercialOrderCreate,
    CommercialOrderItemCreate,
    CommercialOrderUpdate,
)
from app.commercial.domain.enums import CommercialOrderStatus, QuoteStatus
from app.commercial.infrastructure.models import CommercialOrder, CommercialOrderItem
from app.commercial.infrastructure.repositories import (
    CommercialOrderRepository,
    CustomerRepository,
    QuoteRepository,
)
from app.core.tenancy import TenantContext


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.quotes = QuoteRepository(db)
        self.orders = CommercialOrderRepository(db)

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
                    item.quantity * item.agreed_unit_price
                    if item.agreed_unit_price is not None
                    else None
                ),
            )
            for item in items
        ]

    def create_order(
        self,
        tenant: TenantContext,
        customer_id: UUID,
        data: CommercialOrderCreate,
    ) -> CommercialOrder | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        existing = self.orders.get_by_number(tenant.organization_id, data.order_number)
        if existing is not None:
            raise ValueError(f"Order number '{data.order_number}' already exists.")

        if data.quote_id is not None:
            quote = self.quotes.get_by_id(tenant.organization_id, data.quote_id)
            if quote is None or quote.customer_id != customer.id:
                raise ValueError("Quote must belong to the target customer.")
            if quote.status not in (QuoteStatus.ISSUED, QuoteStatus.ACCEPTED):
                raise ValueError("Only an issued or accepted quote can be linked to an order.")

        order = CommercialOrder(
            organization_id=tenant.organization_id,
            customer_id=customer.id,
            created_by_user_id=tenant.user_id,
            status=CommercialOrderStatus.DRAFT,
            items=self._build_order_items(data.items),
            **data.model_dump(exclude={"items"}),
        )

        try:
            self.orders.add(order)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Order could not be saved due to invalid or duplicate data.") from exc

        return self.orders.get_by_id(tenant.organization_id, order.id)

    def list_orders(self, tenant: TenantContext) -> list[CommercialOrder]:
        return self.orders.list_by_organization(tenant.organization_id)

    def list_orders_for_customer(
        self,
        tenant: TenantContext,
        customer_id: UUID,
    ) -> list[CommercialOrder] | None:
        customer = self.customers.get_by_id(tenant.organization_id, customer_id)
        if customer is None:
            return None

        return self.orders.list_by_customer(tenant.organization_id, customer_id)

    def get_order(self, tenant: TenantContext, order_id: UUID) -> CommercialOrder | None:
        return self.orders.get_by_id(tenant.organization_id, order_id)

    def update_order(
        self,
        tenant: TenantContext,
        order_id: UUID,
        data: CommercialOrderUpdate,
    ) -> CommercialOrder | None:
        order = self.orders.get_by_id(tenant.organization_id, order_id)
        if order is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        items_payload = payload.pop("items", None)

        new_order_number = payload.get("order_number")
        if new_order_number is not None and new_order_number != order.order_number:
            existing = self.orders.get_by_number(tenant.organization_id, new_order_number)
            if existing is not None and existing.id != order.id:
                raise ValueError(f"Order number '{new_order_number}' already exists.")

        if "quote_id" in payload and payload["quote_id"] is not None:
            quote = self.quotes.get_by_id(tenant.organization_id, payload["quote_id"])
            if quote is None or quote.customer_id != order.customer_id:
                raise ValueError("Quote must belong to the target customer.")
            if quote.status not in (QuoteStatus.ISSUED, QuoteStatus.ACCEPTED):
                raise ValueError("Only an issued or accepted quote can be linked to an order.")

        for field, value in payload.items():
            setattr(order, field, value)

        if items_payload is not None:
            order.items = self._build_order_items(
                [CommercialOrderItemCreate(**item) for item in items_payload]
            )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Order could not be saved due to invalid or duplicate data.") from exc

        return self.orders.get_by_id(tenant.organization_id, order.id)
