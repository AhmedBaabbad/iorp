from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class CustomerSummary:
    id: UUID
    customer_code: str
    customer_name: str
    organization_id: UUID


@dataclass(frozen=True)
class QuoteSummary:
    id: UUID
    quote_number: str
    customer_id: UUID
    issue_date: date | None
    status: str
    organization_id: UUID


@dataclass(frozen=True)
class QuoteItemSummary:
    id: UUID
    line_no: int
    product_type: str | None
    target_spec_json: dict | None
    quantity: Decimal
    unit: str
    notes: str | None


class CustomerLookupInterface(Protocol):
    def get_customer_summary(self, db, customer_id: UUID, organization_id: UUID) -> CustomerSummary | None: ...
    def find_customers(self, db, organization_id: UUID, search: str, active_only: bool = True) -> list[CustomerSummary]: ...


class QuoteLookupInterface(Protocol):
    def get_quote_summary(self, db, quote_id: UUID, organization_id: UUID) -> QuoteSummary | None: ...
    def get_quote_items(self, db, quote_id: UUID, organization_id: UUID) -> list[QuoteItemSummary]: ...
    def find_quotes(self, db, customer_id: UUID, organization_id: UUID) -> list[QuoteSummary]: ...


class ProductionDemandCountInterface(Protocol):
    def count_demands_for_customer(self, db, customer_id: UUID, org_id: UUID, active_only: bool = False) -> int: ...
