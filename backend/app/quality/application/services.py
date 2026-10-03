from datetime import date
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.quality.api.schemas import (
    NonConformanceItemCreate,
    NonConformanceItemUpdate,
    NonConformanceReportCreate,
    NonConformanceReportUpdate,
    QualityDefectCreate,
    QualityDefectUpdate,
)
from app.quality.domain.enums import (
    DefectCategory,
    DefectSeverity,
    NCRReportType,
    NCRSourceType,
    NCRStatus,
)
from app.quality.infrastructure.models import (
    NonConformanceItem,
    NonConformanceReport,
    QualityCheck,
    QualityDefect,
)
from app.quality.infrastructure.repositories import (
    NonConformanceItemRepository,
    NonConformanceReportRepository,
    QualityCheckRepository,
    QualityDefectRepository,
    QualityRejectionRepository,
)


class QualityDefectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.checks = QualityCheckRepository(db)
        self.defects = QualityDefectRepository(db)

    def create_quality_defect(
        self,
        tenant: TenantContext,
        check_id: UUID,
        data: QualityDefectCreate,
    ) -> QualityDefect:
        self._validate_quality_check(tenant, check_id)

        quality_defect = QualityDefect(
            organization_id=tenant.organization_id,
            quality_check_id=check_id,
            detected_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.defects.add(quality_defect)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Quality defect could not be saved due to invalid data.") from exc

        self.db.refresh(quality_defect)
        return quality_defect

    def list_defects_by_quality_check(
        self,
        tenant: TenantContext,
        check_id: UUID,
    ) -> list[QualityDefect]:
        self._validate_quality_check(tenant, check_id)
        return self.defects.list_by_quality_check(tenant.organization_id, check_id)

    def list_quality_defects(
        self,
        tenant: TenantContext,
        *,
        defect_category: DefectCategory | None = None,
        severity: DefectSeverity | None = None,
        production_order_id: UUID | None = None,
        defect_date: date | None = None,
    ) -> list[QualityDefect]:
        return self.defects.list_by_organization(
            tenant.organization_id,
            defect_category=defect_category,
            severity=severity,
            production_order_id=production_order_id,
            defect_date=defect_date,
        )

    def get_quality_defect(
        self,
        tenant: TenantContext,
        defect_id: UUID,
    ) -> QualityDefect | None:
        return self.defects.get_by_id(tenant.organization_id, defect_id)

    def update_quality_defect(
        self,
        tenant: TenantContext,
        defect_id: UUID,
        data: QualityDefectUpdate,
    ) -> QualityDefect | None:
        quality_defect = self.defects.get_by_id(tenant.organization_id, defect_id)
        if quality_defect is None:
            return None

        payload = data.model_dump(exclude_unset=True)

        for field, value in payload.items():
            setattr(quality_defect, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Quality defect could not be saved due to invalid data.") from exc

        self.db.refresh(quality_defect)
        return quality_defect

    def _validate_quality_check(self, tenant: TenantContext, check_id: UUID) -> QualityCheck:
        quality_check = self.checks.get_by_id(tenant.organization_id, check_id)
        if quality_check is None:
            raise ValueError("Quality check must belong to the current organization.")
        return quality_check


class NonConformanceReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.checks = QualityCheckRepository(db)
        self.rejections = QualityRejectionRepository(db)
        self.reports = NonConformanceReportRepository(db)

    def create_report(
        self,
        tenant: TenantContext,
        data: NonConformanceReportCreate,
    ) -> NonConformanceReport:
        self._validate_quality_check_if_present(tenant, data.quality_check_id)
        self._validate_quality_rejection_if_present(tenant, data.quality_rejection_id)

        report = NonConformanceReport(
            organization_id=tenant.organization_id,
            report_number=self._generate_report_number(tenant.organization_id),
            status=NCRStatus.DRAFT,
            detected_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.reports.add(report)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Non-conformance report could not be saved due to invalid data.") from exc

        self.db.refresh(report)
        return report

    def list_reports(
        self,
        tenant: TenantContext,
        *,
        source_type: NCRSourceType | None = None,
        report_type: NCRReportType | None = None,
        status: NCRStatus | None = None,
        report_date: date | None = None,
    ) -> list[NonConformanceReport]:
        return self.reports.list_by_organization(
            tenant.organization_id,
            source_type=source_type,
            report_type=report_type,
            status=status,
            report_date=report_date,
        )

    def get_report(
        self,
        tenant: TenantContext,
        report_id: UUID,
    ) -> NonConformanceReport | None:
        return self.reports.get_by_id(tenant.organization_id, report_id)

    def update_report(
        self,
        tenant: TenantContext,
        report_id: UUID,
        data: NonConformanceReportUpdate,
    ) -> NonConformanceReport | None:
        report = self.reports.get_by_id(tenant.organization_id, report_id)
        if report is None:
            return None

        payload = data.model_dump(exclude_unset=True)

        if "status" in payload and report.status == NCRStatus.CLOSED and payload["status"] != NCRStatus.CLOSED:
            raise ValueError("A closed NCR report cannot be reopened.")

        if "quality_check_id" in payload:
            self._validate_quality_check_if_present(tenant, payload["quality_check_id"])
        if "quality_rejection_id" in payload:
            self._validate_quality_rejection_if_present(tenant, payload["quality_rejection_id"])

        for field, value in payload.items():
            setattr(report, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Non-conformance report could not be saved due to invalid data.") from exc

        self.db.refresh(report)
        return report

    def _generate_report_number(self, organization_id: UUID) -> str:
        year = utc_now().year
        for attempt in range(20):
            count = self.reports.count_for_year(organization_id, year)
            candidate = f"NCR-{year}-{(count + 1 + attempt):04d}"
            if self.reports.get_by_number(organization_id, candidate) is None:
                return candidate
        raise ValueError("Could not generate a unique NCR report number. Please try again.")

    def _validate_quality_check_if_present(
        self,
        tenant: TenantContext,
        quality_check_id: UUID | None,
    ) -> None:
        if quality_check_id is None:
            return
        quality_check = self.checks.get_by_id(tenant.organization_id, quality_check_id)
        if quality_check is None:
            raise ValueError("Quality check must belong to the current organization.")

    def _validate_quality_rejection_if_present(
        self,
        tenant: TenantContext,
        quality_rejection_id: UUID | None,
    ) -> None:
        if quality_rejection_id is None:
            return
        quality_rejection = self.rejections.get_by_id(tenant.organization_id, quality_rejection_id)
        if quality_rejection is None:
            raise ValueError("Quality rejection must belong to the current organization.")


class NonConformanceItemService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.items = NonConformanceItemRepository(db)
        self.reports = NonConformanceReportRepository(db)

    def create_item(
        self,
        tenant: TenantContext,
        report_id: UUID,
        data: NonConformanceItemCreate,
    ) -> NonConformanceItem:
        report = self._validate_open_parent_report(tenant, report_id)
        line_no = data.line_no
        if line_no is None:
            line_no = (self.items.max_line_no(report.id) or 0) + 1

        item = NonConformanceItem(
            non_conformance_report_id=report.id,
            line_no=line_no,
            **data.model_dump(exclude={"line_no"}),
        )

        try:
            self.items.add(item)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Non-conformance item could not be saved due to invalid data.") from exc

        self.db.refresh(item)
        return item

    def list_items(
        self,
        tenant: TenantContext,
        report_id: UUID,
    ) -> list[NonConformanceItem]:
        report = self._validate_parent_report(tenant, report_id)
        return self.items.list_by_report(tenant.organization_id, report.id)

    def get_item(
        self,
        tenant: TenantContext,
        item_id: UUID,
    ) -> NonConformanceItem | None:
        return self.items.get_by_id(tenant.organization_id, item_id)

    def update_item(
        self,
        tenant: TenantContext,
        item_id: UUID,
        data: NonConformanceItemUpdate,
    ) -> NonConformanceItem | None:
        item = self.items.get_by_id(tenant.organization_id, item_id)
        if item is None:
            return None

        self._validate_open_parent_report(tenant, item.non_conformance_report_id)
        payload = data.model_dump(exclude_unset=True)

        for field, value in payload.items():
            setattr(item, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Non-conformance item could not be saved due to invalid data.") from exc

        self.db.refresh(item)
        return item

    def _validate_parent_report(
        self,
        tenant: TenantContext,
        report_id: UUID,
    ) -> NonConformanceReport:
        report = self.reports.get_by_id(tenant.organization_id, report_id)
        if report is None:
            raise ValueError("Non-conformance report must belong to the current organization.")
        return report

    def _validate_open_parent_report(
        self,
        tenant: TenantContext,
        report_id: UUID,
    ) -> NonConformanceReport:
        report = self._validate_parent_report(tenant, report_id)
        if report.status == NCRStatus.CLOSED:
            raise ValueError("Cannot create or modify items for a closed NCR.")
        return report


from app.core.interfaces.activity_log import instrument_activity_methods

instrument_activity_methods(QualityDefectService, {"create_quality_defect": ("quality_defect.created", "quality_defect"), "update_quality_defect": ("quality_defect.updated", "quality_defect")})
instrument_activity_methods(NonConformanceReportService, {"create_report": ("ncr_report.created", "ncr_report"), "update_report": ("ncr_report.updated", "ncr_report")})
instrument_activity_methods(NonConformanceItemService, {"create_item": ("ncr_item.created", "ncr_item"), "update_item": ("ncr_item.updated", "ncr_item")})
