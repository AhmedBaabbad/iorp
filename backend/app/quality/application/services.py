from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.pagination import paginate
from app.core.tenancy import TenantContext
from app.quality.domain.rules import QualityError
from app.quality.api.schemas import (
    QualityDefectCreate,
    QualityDefectUpdate,
)
from app.quality.domain.enums import (
    DefectCategory,
    DefectSeverity,
)
from app.quality.infrastructure.models import (
    QualityCheck,
    QualityDefect,
)
from app.quality.infrastructure.repositories import (
    QualityCheckRepository,
    QualityDefectRepository,
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
        self._assert_new_type(tenant, check_id, [data.defect_category])

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

    def create_quality_defects(self, tenant: TenantContext, check_id: UUID, items: list[QualityDefectCreate]) -> list[QualityDefect]:
        """Several defects found on one inspection, recorded together: all or none."""
        self._validate_quality_check(tenant, check_id)
        self._assert_new_type(tenant, check_id, [item.defect_category for item in items])
        defects = [QualityDefect(organization_id=tenant.organization_id, quality_check_id=check_id, detected_by_user_id=tenant.user_id,
                                 **item.model_dump()) for item in items]
        try:
            for defect in defects:
                self.defects.add(defect)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Quality defect could not be saved due to invalid data.") from exc
        for defect in defects:
            self.db.refresh(defect)
        return defects

    def _assert_new_type(self, tenant: TenantContext, check_id: UUID, categories, excluding: UUID | None = None) -> None:
        """An inspection records each defect type once (more occurrences go in defect_count)."""
        values = [getattr(c, "value", c) for c in categories]
        if len(values) != len(set(values)):
            raise QualityError("DEFECT_ALREADY_RECORDED", 409, defect_category=sorted({v for v in values if values.count(v) > 1})[0])
        query = select(QualityDefect.defect_category).where(QualityDefect.organization_id == tenant.organization_id,
                                                            QualityDefect.quality_check_id == check_id, QualityDefect.defect_category.in_(values))
        if excluding is not None:
            query = query.where(QualityDefect.id != excluding)
        taken = self.db.scalar(query.limit(1))
        if taken is not None:
            raise QualityError("DEFECT_ALREADY_RECORDED", 409, defect_category=getattr(taken, "value", taken))

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
        params,
        *,
        defect_category: DefectCategory | None = None,
        severity: DefectSeverity | None = None,
        production_order_id: UUID | None = None,
        defect_date: date | None = None,
    ) -> tuple[list[QualityDefect], int]:
        """One page of the organization's defects, newest first, and the total (ARCH-PAGE-001)."""
        return paginate(self.db, self.defects.list_by_organization(
            tenant.organization_id,
            defect_category=defect_category,
            severity=severity,
            production_order_id=production_order_id,
            defect_date=defect_date,
        ), params)

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
        if payload.get("defect_category") is not None:
            self._assert_new_type(tenant, quality_defect.quality_check_id, [payload["defect_category"]], excluding=quality_defect.id)

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


from app.core.interfaces.activity_log import instrument_activity_methods

instrument_activity_methods(QualityDefectService, {"create_quality_defect": ("quality_defect.created", "quality_defect"), "update_quality_defect": ("quality_defect.updated", "quality_defect")})
