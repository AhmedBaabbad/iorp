"""Commercial owns approved snapshots; Production owns demand consumption. No cross-module ORM."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class SalesLine:
    id: UUID
    line_no: int
    product_type: str
    properties: dict | None
    quantity: Decimal
    unit: str


@dataclass(frozen=True)
class SalesOrder:
    id: UUID
    customer_id: UUID
    quote_id: UUID | None
    number: str
    status: str
    delivery: datetime | None
    lines: tuple[SalesLine, ...]


class SalesOrderSource(Protocol):
    def get(self, db: Session, organization_id: UUID, order_id: UUID, *, lock: bool = False) -> SalesOrder | None: ...
    def list(self, db: Session, organization_id: UUID, customer_id: UUID) -> list[SalesOrder]: ...


class SalesDemandUsage(Protocol):
    def quantities(self, db: Session, organization_id: UUID, order_id: UUID) -> dict[UUID, Decimal]: ...
    def has_history(self, db: Session, organization_id: UUID, order_id: UUID) -> bool: ...


source: SalesOrderSource | None = None
usage: SalesDemandUsage | None = None
# The permission that lets a user send a confirmed sales order to production; production owns it and names it here.
transfer_permission: str | None = None


def register_sales_integration(order_source: SalesOrderSource, demand_usage: SalesDemandUsage, demand_permission: str | None = None):
    global source, usage, transfer_permission
    source, usage, transfer_permission = order_source, demand_usage, demand_permission
