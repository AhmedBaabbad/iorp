from datetime import date
from uuid import UUID
from typing import Literal
from pydantic import Field, model_validator
from app.core.reporting.contracts import CommonParams
from app.production.domain.enums import ProductionOrderStatus, ProductionOrderPriority


class OrderParams(CommonParams):
    order_id: UUID = Field(json_schema_extra={'widget': 'entity_lookup', 'lookup': 'orders', 'title_ar': 'أمر الإنتاج', 'title_en': 'Production order'})


class SummaryParams(CommonParams):
    orientation: Literal['portrait', 'landscape'] = 'landscape'
    date_from: date | None = Field(None, json_schema_extra={'widget': 'date_range', 'title_ar': 'من تاريخ'})
    date_to: date | None = Field(None, json_schema_extra={'widget': 'date_range', 'title_ar': 'إلى تاريخ'})
    date_basis: Literal['planned_start', 'completion'] = 'planned_start'
    status: list[ProductionOrderStatus] = Field(default_factory=list, max_length=7, json_schema_extra={'widget': 'multi_select', 'title_ar': 'الحالة'})
    product: str | None = Field(None, max_length=120, json_schema_extra={'widget': 'entity_lookup', 'lookup': 'products', 'title_ar': 'المنتج'})
    customer_id: UUID | None = Field(None, json_schema_extra={'widget': 'entity_lookup', 'lookup': 'customers', 'title_ar': 'العميل'})
    priority: ProductionOrderPriority | None = None
    work_center_id: UUID | None = Field(None, json_schema_extra={'widget': 'entity_lookup', 'lookup': 'centers', 'title_ar': 'مركز العمل عبر التشغيل'})
    grouping: Literal['none', 'status', 'product', 'customer', 'month'] = 'none'
    sort: Literal['date_asc', 'date_desc', 'number'] = 'date_desc'

    @model_validator(mode='after')
    def dates(self):
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError('Invalid date range')
        return self


class AnalysisParams(SummaryParams):
    date_basis: Literal['completion'] = 'completion'
    period: Literal['day', 'week', 'month'] = 'month'


class WorkforceParams(CommonParams):
    date_from: date | None = None
    date_to: date | None = None
    sort: Literal['date_asc', 'date_desc'] = 'date_desc'

    @model_validator(mode='after')
    def dates(self):
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError('Invalid date range')
        return self
