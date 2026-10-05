from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.quality.domain.enums import (
    DefectCategory,
    DefectSeverity,
    Disposition,
    DispositionStatus,
    QualityCheckResult,
    QualityCheckStatus,
    QualityCheckType,
    RejectionReason,
)
from app.quality.infrastructure.models import (
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
        if rejection_date is not None:
            statement = statement.where(QualityRejection.rejection_date == rejection_date)
        statement = statement.order_by(
            QualityRejection.rejection_date.desc(),
            QualityRejection.created_at.desc(),
        )
        return list(self.db.scalars(statement))
