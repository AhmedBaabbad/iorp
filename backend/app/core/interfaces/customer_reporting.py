"""Read contracts shared by customer reports and owning modules. No ORM objects cross this boundary."""
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class ReadDTO(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class QuoteRead(ReadDTO):
    customer_id: UUID
    number: str
    issued: datetime
    status: str
    currency: str
    total: Decimal


class DemandRead(ReadDTO):
    customer_id: UUID
    demand_id: UUID
    number: str
    requested: date
    expected: date | None
    status: str
    product: str
    quantity: Decimal
    allocated: Decimal
    unallocated: Decimal
    unit: str


class OrderRead(ReadDTO):
    customer_id: UUID
    order_id: UUID
    number: str
    product: str
    status: str
    planned_start: date
    planned_end: date
    actual_start: datetime | None
    actual_end: datetime | None
    created: datetime
    allocated: Decimal
    total_allocated: Decimal
    unit: str
    shared: bool
    demand_ids: tuple[UUID, ...] = ()


class ResultRead(ReadDTO):
    order_id: UUID
    unit: str
    customer_good: Decimal
    stock_good: Decimal
    # Internal output has its own DTO; the customer output never contains these fields.


class InternalResultRead(ResultRead):
    sample: Decimal
    scrap: Decimal
    rework: Decimal
    loss_total: Decimal


class ProductionCustomerReads(Protocol):
    def demands(self, customer_ids: list[UUID]) -> list[DemandRead]: ...
    def orders(self, customer_ids: list[UUID]) -> list[OrderRead]: ...
    def results(self, order_ids: list[UUID], *, internal: bool = False) -> list[ResultRead]: ...


class CommercialCustomerReads(Protocol):
    def quotations(self, customer_ids: list[UUID]) -> list[QuoteRead]: ...
