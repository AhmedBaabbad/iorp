from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.core.reporting.contracts import CommonParams
from app.quality.domain.enums import (DefectCategory, DefectSeverity, Disposition, DispositionStatus, QualityCheckResult,
                                      QualityCheckStatus, QualityCheckType, RejectionReason)

# Field labels come from the locale files (reports.params.*); the widgets from json_schema_extra.
ORDER = Field(None, json_schema_extra={'widget': 'entity_lookup', 'lookup': 'orders'})
PRODUCT = Field(None, max_length=120, json_schema_extra={'widget': 'entity_lookup', 'lookup': 'products'})


class _Period(CommonParams):
    orientation: Literal['portrait', 'landscape'] = 'landscape'
    date_from: date | None = None
    date_to: date | None = None
    order_id: UUID | None = ORDER
    product: str | None = PRODUCT

    @model_validator(mode='after')
    def dates(self):
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError('Invalid date range')
        return self


class CheckParams(CommonParams):
    check_id: UUID = Field(json_schema_extra={'widget': 'entity_lookup', 'lookup': 'checks'})


class ChecksSummaryParams(_Period):
    check_type: list[QualityCheckType] = Field(default_factory=list, max_length=6)
    status: list[QualityCheckStatus] = Field(default_factory=list, max_length=4)
    result: list[QualityCheckResult] = Field(default_factory=list, max_length=4)
    grouping: Literal['none', 'check_type', 'result', 'product', 'month'] = 'none'
    sort: Literal['date_desc', 'date_asc', 'code'] = 'date_desc'


class RejectionsParams(_Period):
    reason: list[RejectionReason] = Field(default_factory=list, max_length=8)
    disposition: list[Disposition] = Field(default_factory=list, max_length=5)
    disposition_status: list[DispositionStatus] = Field(default_factory=list, max_length=3)
    period: Literal['day', 'week', 'month'] = 'month'


class DefectsParams(_Period):
    category: list[DefectCategory] = Field(default_factory=list, max_length=11)
    severity: list[DefectSeverity] = Field(default_factory=list, max_length=3)
