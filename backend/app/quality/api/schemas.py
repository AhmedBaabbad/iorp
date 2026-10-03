from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import ISODatetime
from app.quality.domain.enums import (
    DefectCategory,
    DefectSeverity,
    NCRReportType,
    NCRSourceType,
    NCRStatus,
)


class QualityDefectCreate(BaseModel):
    # quality_check_id is derived from the URL path — never a body field.
    production_order_id: UUID | None = None
    production_order_item_id: UUID | None = None
    defect_date: date
    defect_category: DefectCategory
    severity: DefectSeverity
    defect_count: int = Field(default=1, gt=0)
    description: str = Field(min_length=1)
    notes: str | None = None


class QualityDefectUpdate(BaseModel):
    production_order_id: UUID | None = None
    production_order_item_id: UUID | None = None
    defect_date: date | None = None
    defect_category: DefectCategory | None = None
    severity: DefectSeverity | None = None
    defect_count: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, min_length=1)
    notes: str | None = None


class QualityDefectListItem(BaseModel):
    id: UUID
    organization_id: UUID
    quality_check_id: UUID
    production_order_id: UUID | None
    production_order_item_id: UUID | None
    defect_date: date
    defect_category: DefectCategory
    severity: DefectSeverity
    defect_count: int
    description: str
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class QualityDefectRead(QualityDefectListItem):
    notes: str | None
    detected_by_user_id: UUID


class NonConformanceReportCreate(BaseModel):
    report_date: date
    source_type: NCRSourceType
    report_type: NCRReportType
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    reference_code: str | None = Field(default=None, max_length=255)
    quality_check_id: UUID | None = None
    quality_rejection_id: UUID | None = None


class NonConformanceReportUpdate(BaseModel):
    report_date: date | None = None
    source_type: NCRSourceType | None = None
    report_type: NCRReportType | None = None
    status: NCRStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    reference_code: str | None = Field(default=None, max_length=255)
    quality_check_id: UUID | None = None
    quality_rejection_id: UUID | None = None


class NonConformanceReportListItem(BaseModel):
    id: UUID
    organization_id: UUID
    report_number: str
    report_date: date
    source_type: NCRSourceType
    report_type: NCRReportType
    status: NCRStatus
    title: str
    reference_code: str | None
    quality_check_id: UUID | None
    quality_rejection_id: UUID | None
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class NonConformanceReportRead(NonConformanceReportListItem):
    description: str
    detected_by_user_id: UUID


class NonConformanceItemCreate(BaseModel):
    line_no: int | None = Field(default=None, ge=1)
    item_reference: str | None = Field(default=None, max_length=255)
    item_name: str = Field(min_length=1, max_length=255)
    quantity_affected: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    issue_description: str = Field(min_length=1)
    notes: str | None = None


class NonConformanceItemUpdate(BaseModel):
    line_no: int | None = Field(default=None, ge=1)
    item_reference: str | None = Field(default=None, max_length=255)
    item_name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity_affected: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    issue_description: str | None = Field(default=None, min_length=1)
    notes: str | None = None


class NonConformanceItemListItem(BaseModel):
    id: UUID
    non_conformance_report_id: UUID
    line_no: int
    item_reference: str | None
    item_name: str
    quantity_affected: Decimal | None
    unit: str | None
    issue_description: str
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class NonConformanceItemRead(NonConformanceItemListItem):
    notes: str | None
