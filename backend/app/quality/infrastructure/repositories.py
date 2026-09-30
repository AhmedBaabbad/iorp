from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.quality.domain.enums import (
    DefectCategory,
    DefectSeverity,
    Disposition,
    DispositionStatus,
    NCRReportType,
    NCRSourceType,
    NCRStatus,
    QualityCheckResult,
    QualityCheckStatus,
    QualityCheckType,
    RejectionReason,
)
from app.quality.infrastructure.models import (
    NonConformanceItem,
    NonConformanceReport,
    QualityCheck,
    QualityDefect,
    QualityRejection,
)


class QualityCheckRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, quality_check: QualityCheck) -> QualityCheck:
        self.db.add(quality_check)
        self.db.flush()
        return quality_check

    def get_by_id(self, organization_id: UUID, check_id: UUID) -> QualityCheck | None:
        statement = select(QualityCheck).where(
            QualityCheck.organization_id == organization_id,
            QualityCheck.id == check_id,
        )
        return self.db.scalar(statement)

    def get_by_code(self, organization_id: UUID, inspection_code: str) -> QualityCheck | None:
        statement = select(QualityCheck).where(
            QualityCheck.organization_id == organization_id,
            QualityCheck.inspection_code == inspection_code,
        )
        return self.db.scalar(statement)

    def count_for_year(self, organization_id: UUID, year: int) -> int:
        """Return the number of checks created for this org in the given year.

        Used by the service to generate the next sequential inspection_code.
        """
        year_start = datetime(year, 1, 1, tzinfo=timezone.utc)
        year_end   = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        statement = (
            select(func.count())
            .select_from(QualityCheck)
            .where(
                QualityCheck.organization_id == organization_id,
                QualityCheck.created_at >= year_start,
                QualityCheck.created_at < year_end,
            )
        )
        return self.db.scalar(statement) or 0

    def list_by_organization(
        self,
        organization_id: UUID,
        *,
        check_type: QualityCheckType | None = None,
        status: QualityCheckStatus | None = None,
        result: QualityCheckResult | None = None,
        production_order_id: UUID | None = None,
        check_date: date | None = None,
    ) -> list[QualityCheck]:
        statement = (
            select(QualityCheck)
            .where(QualityCheck.organization_id == organization_id)
        )
        if check_type is not None:
            statement = statement.where(QualityCheck.check_type == check_type)
        if status is not None:
            statement = statement.where(QualityCheck.status == status)
        if result is not None:
            statement = statement.where(QualityCheck.result == result)
        if production_order_id is not None:
            statement = statement.where(QualityCheck.production_order_id == production_order_id)
        if check_date is not None:
            # Filter by the date portion of check_datetime using a cast.
            statement = statement.where(
                func.date(QualityCheck.check_datetime) == check_date
            )
        statement = statement.order_by(QualityCheck.check_datetime.desc())
        return list(self.db.scalars(statement))


class QualityDefectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, quality_defect: QualityDefect) -> QualityDefect:
        self.db.add(quality_defect)
        self.db.flush()
        return quality_defect

    def get_by_id(self, organization_id: UUID, defect_id: UUID) -> QualityDefect | None:
        statement = (
            select(QualityDefect)
            .join(QualityCheck, QualityCheck.id == QualityDefect.quality_check_id)
            .where(
                QualityDefect.id == defect_id,
                QualityDefect.organization_id == organization_id,
                QualityCheck.organization_id == organization_id,
            )
        )
        return self.db.scalar(statement)

    def list_by_quality_check(
        self,
        organization_id: UUID,
        quality_check_id: UUID,
    ) -> list[QualityDefect]:
        statement = (
            select(QualityDefect)
            .join(QualityCheck, QualityCheck.id == QualityDefect.quality_check_id)
            .where(
                QualityDefect.quality_check_id == quality_check_id,
                QualityDefect.organization_id == organization_id,
                QualityCheck.organization_id == organization_id,
            )
            .order_by(QualityDefect.defect_date.desc(), QualityDefect.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_by_organization(
        self,
        organization_id: UUID,
        *,
        defect_category: DefectCategory | None = None,
        severity: DefectSeverity | None = None,
        production_order_id: UUID | None = None,
        defect_date: date | None = None,
    ) -> list[QualityDefect]:
        statement = (
            select(QualityDefect)
            .join(QualityCheck, QualityCheck.id == QualityDefect.quality_check_id)
            .where(
                QualityDefect.organization_id == organization_id,
                QualityCheck.organization_id == organization_id,
            )
        )
        if defect_category is not None:
            statement = statement.where(QualityDefect.defect_category == defect_category)
        if severity is not None:
            statement = statement.where(QualityDefect.severity == severity)
        if production_order_id is not None:
            statement = statement.where(QualityDefect.production_order_id == production_order_id)
        if defect_date is not None:
            statement = statement.where(QualityDefect.defect_date == defect_date)
        statement = statement.order_by(QualityDefect.defect_date.desc(), QualityDefect.created_at.desc())
        return list(self.db.scalars(statement))


class QualityRejectionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, quality_rejection: QualityRejection) -> QualityRejection:
        self.db.add(quality_rejection)
        self.db.flush()
        return quality_rejection

    def get_by_id(self, organization_id: UUID, rejection_id: UUID) -> QualityRejection | None:
        statement = select(QualityRejection).where(
            QualityRejection.organization_id == organization_id,
            QualityRejection.id == rejection_id,
        )
        return self.db.scalar(statement)

    def list_by_organization(
        self,
        organization_id: UUID,
        *,
        rejection_reason: RejectionReason | None = None,
        disposition: Disposition | None = None,
        disposition_status: DispositionStatus | None = None,
        quality_check_id: UUID | None = None,
        production_output_id: UUID | None = None,
        rejection_date: date | None = None,
    ) -> list[QualityRejection]:
        statement = select(QualityRejection).where(
            QualityRejection.organization_id == organization_id,
        )
        if rejection_reason is not None:
            statement = statement.where(QualityRejection.rejection_reason == rejection_reason)
        if disposition is not None:
            statement = statement.where(QualityRejection.disposition == disposition)
        if disposition_status is not None:
            statement = statement.where(QualityRejection.disposition_status == disposition_status)
        if quality_check_id is not None:
            statement = statement.where(QualityRejection.quality_check_id == quality_check_id)
        if production_output_id is not None:
            statement = statement.where(QualityRejection.production_output_id == production_output_id)
        if rejection_date is not None:
            statement = statement.where(QualityRejection.rejection_date == rejection_date)
        statement = statement.order_by(
            QualityRejection.rejection_date.desc(),
            QualityRejection.created_at.desc(),
        )
        return list(self.db.scalars(statement))


class NonConformanceReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, report: NonConformanceReport) -> NonConformanceReport:
        self.db.add(report)
        self.db.flush()
        return report

    def get_by_id(self, organization_id: UUID, report_id: UUID) -> NonConformanceReport | None:
        statement = select(NonConformanceReport).where(
            NonConformanceReport.organization_id == organization_id,
            NonConformanceReport.id == report_id,
        )
        return self.db.scalar(statement)

    def get_by_number(self, organization_id: UUID, report_number: str) -> NonConformanceReport | None:
        statement = select(NonConformanceReport).where(
            NonConformanceReport.organization_id == organization_id,
            NonConformanceReport.report_number == report_number,
        )
        return self.db.scalar(statement)

    def count_for_year(self, organization_id: UUID, year: int) -> int:
        year_start = datetime(year, 1, 1, tzinfo=timezone.utc)
        year_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        statement = (
            select(func.count())
            .select_from(NonConformanceReport)
            .where(
                NonConformanceReport.organization_id == organization_id,
                NonConformanceReport.created_at >= year_start,
                NonConformanceReport.created_at < year_end,
            )
        )
        return self.db.scalar(statement) or 0

    def list_by_organization(
        self,
        organization_id: UUID,
        *,
        source_type: NCRSourceType | None = None,
        report_type: NCRReportType | None = None,
        status: NCRStatus | None = None,
        report_date: date | None = None,
    ) -> list[NonConformanceReport]:
        statement = select(NonConformanceReport).where(
            NonConformanceReport.organization_id == organization_id,
        )
        if source_type is not None:
            statement = statement.where(NonConformanceReport.source_type == source_type)
        if report_type is not None:
            statement = statement.where(NonConformanceReport.report_type == report_type)
        if status is not None:
            statement = statement.where(NonConformanceReport.status == status)
        if report_date is not None:
            statement = statement.where(NonConformanceReport.report_date == report_date)
        statement = statement.order_by(
            NonConformanceReport.report_date.desc(),
            NonConformanceReport.created_at.desc(),
        )
        return list(self.db.scalars(statement))


class NonConformanceItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, item: NonConformanceItem) -> NonConformanceItem:
        self.db.add(item)
        self.db.flush()
        return item

    def max_line_no(self, report_id: UUID) -> int | None:
        statement = select(func.max(NonConformanceItem.line_no)).where(
            NonConformanceItem.non_conformance_report_id == report_id,
        )
        return self.db.scalar(statement)

    def list_by_report(self, organization_id: UUID, report_id: UUID) -> list[NonConformanceItem]:
        statement = (
            select(NonConformanceItem)
            .join(NonConformanceReport, NonConformanceReport.id == NonConformanceItem.non_conformance_report_id)
            .where(
                NonConformanceReport.organization_id == organization_id,
                NonConformanceItem.non_conformance_report_id == report_id,
            )
            .order_by(NonConformanceItem.line_no.asc(), NonConformanceItem.created_at.asc())
        )
        return list(self.db.scalars(statement))

    def get_by_id(self, organization_id: UUID, item_id: UUID) -> NonConformanceItem | None:
        statement = (
            select(NonConformanceItem)
            .join(
                NonConformanceReport,
                NonConformanceReport.id == NonConformanceItem.non_conformance_report_id,
            )
            .where(
                NonConformanceItem.id == item_id,
                NonConformanceReport.organization_id == organization_id,
            )
        )
        return self.db.scalar(statement)
