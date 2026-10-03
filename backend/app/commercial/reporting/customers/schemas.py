from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.core.reporting.contracts import CommonParams


class CustomerParams(CommonParams):
    audience: Literal['internal', 'customer'] = 'internal'
    customer_id: UUID | None = Field(None, json_schema_extra={'lookup': 'customers', 'title_ar': 'العميل', 'title_en': 'Customer'})
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode='after')
    def dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError('Invalid date range')
        return self


class ProfileParams(CustomerParams):
    customer_id: UUID = Field(json_schema_extra={'lookup': 'customers', 'title_ar': 'العميل', 'title_en': 'Customer'})


class DirectoryParams(CustomerParams):
    audience: Literal['internal'] = 'internal'
    orientation: Literal['portrait', 'landscape'] = 'landscape'
    status: Literal['active', 'inactive', 'on_hold', 'archived', 'blacklisted'] | None = None
    sector: str | None = Field(None, max_length=120)
    city: str | None = Field(None, max_length=120)
    sales_owner_id: UUID | None = Field(None, json_schema_extra={'lookup': 'sales_owners', 'title_ar': 'مسؤول المبيعات', 'title_en': 'Sales owner'})
    has_active_orders: bool = False
    grouping: Literal['none', 'status', 'sector', 'city', 'sales_owner'] = 'none'
    sort: Literal['name', 'created'] = 'name'


class ActivityParams(DirectoryParams):
    top_n: int = Field(10, ge=1, le=50)
    rank_by: Literal['quotation_value', 'demanded_quantity'] = 'quotation_value'


class QuotesParams(DirectoryParams):
    quote_status: Literal['draft', 'issued', 'accepted', 'rejected', 'expired'] | None = None


class FulfillmentParams(CustomerParams):
    product: str | None = Field(None, max_length=100, json_schema_extra={'lookup':'products','title_ar':'المنتج','title_en':'Product'})
    demand_status: Literal['draft', 'ready_for_planning', 'partially_planned', 'planned', 'cancelled'] | None = None


class GrowthParams(DirectoryParams):
    inactive_days: int = Field(90, ge=1, le=3650)
    period: Literal['month', 'quarter'] = 'month'


class StatementParams(ProfileParams):
    audience: Literal['internal', 'customer'] = 'customer'
    recent_days: int = Field(90, ge=1, le=3650)
