from datetime import date
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.quality.api.schemas import (
    NonConformanceItemCreate,
    NonConformanceItemUpdate,
    NonConformanceReportCreate,
    NonConformanceReportUpdate,
    QualityCheckCreate,
    QualityCheckUpdate,
    QualityDefectCreate,
    QualityDefectUpdate,
    QualityRejectionCreate,
    QualityRejectionUpdate,
)
from app.quality.domain.enums import (
    DefectCategory,
    DefectSeverity,
    Disposition,
    DispositionStatus,
    NCRReportType,
    NCRSourceType,
    NCRStatus,
    QualityCheckStatus,
    RejectionReason,
)
from app.quality.infrastructure.models import (
    NonConformanceItem,
    NonConformanceReport,
    QualityCheck,
    QualityDefect,
    QualityRejection,
)
from app.quality.infrastructure.repositories import (
    NonConformanceItemRepository,
    NonConformanceReportRepository,
    QualityCheckRepository,
    QualityDefectRepository,
    QualityRejectionRepository,
)


class QualityCheckService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.checks = QualityCheckRepository(db)

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_quality_check(
        self,
        tenant: TenantContext,
        data: QualityCheckCreate,
    ) -> QualityCheck:
        # Soft check: at least one of production_order_id / production_output_id /
        # shift_report_id should be provided. Not enforced in v0.1 — promoted in QUAL-002.
        self._validate_production_refs(tenant.organization_id, data)

        inspection_code = self._generate_inspection_code(tenant.organization_id)

        quality_check = QualityCheck(
            organization_id=tenant.organization_id,
            inspection_code=inspection_code,
            status=QualityCheckStatus.OPEN,  # always open on creation — never caller input
            checked_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.checks.add(quality_check)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError(
                "Quality check could not be saved due to a conflict or invalid data."
            ) from exc

        self.db.refresh(quality_check)
        return quality_check

    def list_quality_checks(
        self,
        tenant: TenantContext,
        *,
        check_type=None,
        status=None,
        result=None,
        production_order_id: UUID | None = None,
        shift_report_id: UUID | None = None,
        check_date: date | None = None,
    ) -> list[QualityCheck]:
        return self.checks.list_by_organization(
            tenant.organization_id,
            check_type=check_type,
            status=status,
            result=result,
            production_order_id=production_order_id,
            shift_report_id=shift_report_id,
            check_date=check_date,
        )

    def get_quality_check(
        self,
        tenant: TenantContext,
        check_id: UUID,
    ) -> QualityCheck | None:
        return self.checks.get_by_id(tenant.organization_id, check_id)

    def update_quality_check(
        self,
        tenant: TenantContext,
        check_id: UUID,
        data: QualityCheckUpdate,
    ) -> QualityCheck | None:
        quality_check = self.checks.get_by_id(tenant.organization_id, check_id)
        if quality_check is None:
            return None

        payload = data.model_dump(exclude_unset=True)

        # Re-validate quantity balance after merging incoming partial values
        # with existing values, so callers can update only one or two fields.
        merged_inspected = payload.get("qty_inspected", quality_check.qty_inspected)
        merged_accepted  = payload.get("qty_accepted",  quality_check.qty_accepted)
        merged_rejected  = payload.get("qty_rejected",  quality_check.qty_rejected)
        if merged_accepted + merged_rejected != merged_inspected:
            raise ValueError(
                "qty_accepted + qty_rejected must equal qty_inspected "
                f"({merged_accepted} + {merged_rejected} ≠ {merged_inspected})."
            )

        # Validate that result is present when transitioning to closed.
        incoming_status = payload.get("status")
        incoming_result = payload.get("result", quality_check.result)
        if incoming_status == QualityCheckStatus.CLOSED and incoming_result is None:
            raise ValueError(
                "result must be set when transitioning status to 'closed'."
            )

        self._validate_production_refs(
            tenant.organization_id,
            SimpleNamespace(
                production_order_id=payload.get(
                    "production_order_id",
                    quality_check.production_order_id,
                ),
                production_order_item_id=payload.get(
                    "production_order_item_id",
                    quality_check.production_order_item_id,
                ),
                production_output_id=payload.get(
                    "production_output_id",
                    quality_check.production_output_id,
                ),
                shift_report_id=payload.get(
                    "shift_report_id",
                    quality_check.shift_report_id,
                ),
            ),
        )

        for field, value in payload.items():
            setattr(quality_check, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError(
                "Quality check could not be saved due to a conflict or invalid data."
            ) from exc

        self.db.refresh(quality_check)
        return quality_check

    # ── Private helpers ────────────────────────────────────────────────────────

    def _generate_inspection_code(self, organization_id: UUID) -> str:
        """Auto-generate QI-YYYY-NNNN, unique within the organization.

        Sequence is derived from the count of existing checks in the current
        year for this org, incremented until a free slot is found. A retry
        loop guards against race conditions in low-concurrency scenarios.
        """
        year = utc_now().year
        for attempt in range(20):
            count = self.checks.count_for_year(organization_id, year)
            candidate = f"QI-{year}-{(count + 1 + attempt):04d}"
            if self.checks.get_by_code(organization_id, candidate) is None:
                return candidate
        raise ValueError(
            "Could not generate a unique inspection code. Please try again."
        )

    def _validate_production_refs(
        self,
        organization_id: UUID,
        data: Any,
    ) -> None:
        """Validate that provided production reference IDs belong to this org.

        Uses raw SQL select against production tables to avoid importing any
        Production model into Quality code (ADR-004 module boundary rule).
        Only validates non-None references.
        """
        if data.production_order_id is not None:
            self._assert_production_row_belongs_to_org(
                "production_orders",
                data.production_order_id,
                organization_id,
                "production_order_id",
            )
        if data.production_output_id is not None:
            self._assert_production_row_belongs_to_org(
                "production_outputs",
                data.production_output_id,
                organization_id,
                "production_output_id",
            )
        if data.shift_report_id is not None:
            self._assert_production_row_belongs_to_org(
                "production_shift_reports",
                data.shift_report_id,
                organization_id,
                "shift_report_id",
            )
        if data.production_order_item_id is not None:
            # Items are validated via their parent order's org — join needed.
            self._assert_order_item_belongs_to_org(
                data.production_order_item_id,
                organization_id,
            )

    def _assert_production_row_belongs_to_org(
        self,
        table: str,
        row_id: UUID,
        organization_id: UUID,
        field_name: str,
    ) -> None:
        stmt = text(
            f"SELECT 1 FROM {table} WHERE id = :id AND organization_id = :org_id LIMIT 1"
        )
        row = self.db.execute(stmt, {"id": str(row_id), "org_id": str(organization_id)}).first()
        if row is None:
            raise ValueError(
                f"{field_name} '{row_id}' does not exist or belongs to a different organization."
            )

    def _assert_order_item_belongs_to_org(
        self,
        item_id: UUID,
        organization_id: UUID,
    ) -> None:
        stmt = text(
            """
            SELECT 1
            FROM production_order_items poi
            JOIN production_orders po ON po.id = poi.production_order_id
            WHERE poi.id = :item_id
              AND po.organization_id = :org_id
            LIMIT 1
            """
        )
        row = self.db.execute(
            stmt,
            {"item_id": str(item_id), "org_id": str(organization_id)},
        ).first()
        if row is None:
            raise ValueError(
                f"production_order_item_id '{item_id}' does not exist or belongs to a different organization."
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


class QualityRejectionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.checks = QualityCheckRepository(db)
        self.defects = QualityDefectRepository(db)
        self.rejections = QualityRejectionRepository(db)

    def create_quality_rejection(
        self,
        tenant: TenantContext,
        data: QualityRejectionCreate,
    ) -> QualityRejection:
        # Soft rule v0.1: at least one of quality_check_id / quality_defect_id should be present.
        self._validate_quality_check_if_present(tenant, data.quality_check_id)
        self._validate_quality_defect_if_present(tenant, data.quality_defect_id)
        self._validate_defect_belongs_to_check(tenant, data.quality_check_id, data.quality_defect_id)
        self._validate_rejection_notes(data.rejection_notes)

        quality_rejection = QualityRejection(
            organization_id=tenant.organization_id,
            disposition_status=DispositionStatus.PENDING,
            rejected_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.rejections.add(quality_rejection)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Quality rejection could not be saved due to invalid data.") from exc

        self.db.refresh(quality_rejection)
        return quality_rejection

    def list_quality_rejections(
        self,
        tenant: TenantContext,
        *,
        rejection_reason: RejectionReason | None = None,
        disposition: Disposition | None = None,
        disposition_status: DispositionStatus | None = None,
        quality_check_id: UUID | None = None,
        production_output_id: UUID | None = None,
        rejection_date: date | None = None,
    ) -> list[QualityRejection]:
        return self.rejections.list_by_organization(
            tenant.organization_id,
            rejection_reason=rejection_reason,
            disposition=disposition,
            disposition_status=disposition_status,
            quality_check_id=quality_check_id,
            production_output_id=production_output_id,
            rejection_date=rejection_date,
        )

    def get_quality_rejection(
        self,
        tenant: TenantContext,
        rejection_id: UUID,
    ) -> QualityRejection | None:
        return self.rejections.get_by_id(tenant.organization_id, rejection_id)

    def update_quality_rejection(
        self,
        tenant: TenantContext,
        rejection_id: UUID,
        data: QualityRejectionUpdate,
    ) -> QualityRejection | None:
        quality_rejection = self.rejections.get_by_id(tenant.organization_id, rejection_id)
        if quality_rejection is None:
            return None

        payload = data.model_dump(exclude_unset=True)

        if "quality_check_id" in payload:
            self._validate_quality_check_if_present(tenant, payload["quality_check_id"])
        if "quality_defect_id" in payload:
            self._validate_quality_defect_if_present(tenant, payload["quality_defect_id"])
        if "rejection_notes" in payload:
            self._validate_rejection_notes(payload["rejection_notes"])

        for field, value in payload.items():
            setattr(quality_rejection, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Quality rejection could not be saved due to invalid data.") from exc

        self.db.refresh(quality_rejection)
        return quality_rejection

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

    def _validate_quality_defect_if_present(
        self,
        tenant: TenantContext,
        quality_defect_id: UUID | None,
    ) -> None:
        if quality_defect_id is None:
            return
        quality_defect = self.defects.get_by_id(tenant.organization_id, quality_defect_id)
        if quality_defect is None:
            raise ValueError("Quality defect must belong to the current organization.")

    def _validate_defect_belongs_to_check(
        self,
        tenant: TenantContext,
        quality_check_id: UUID | None,
        quality_defect_id: UUID | None,
    ) -> None:
        if quality_check_id is None or quality_defect_id is None:
            return
        defect = self.defects.get_by_id(tenant.organization_id, quality_defect_id)
        if defect is not None and defect.quality_check_id != quality_check_id:
            raise ValueError(
                "quality_defect_id must belong to the quality_check_id referenced in this rejection."
            )

    def _validate_rejection_notes(self, rejection_notes: str) -> None:
        # Pydantic min_length=1 blocks empty strings; this guard blocks whitespace-only values.
        if not rejection_notes.strip():
            raise ValueError("rejection_notes is required.")


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

instrument_activity_methods(QualityCheckService, {"create_quality_check": ("quality_check.created", "quality_check"), "update_quality_check": ("quality_check.updated", "quality_check")})
instrument_activity_methods(QualityDefectService, {"create_quality_defect": ("quality_defect.created", "quality_defect"), "update_quality_defect": ("quality_defect.updated", "quality_defect")})
instrument_activity_methods(QualityRejectionService, {"create_quality_rejection": ("quality_rejection.created", "quality_rejection"), "update_quality_rejection": ("quality_rejection.updated", "quality_rejection")})
instrument_activity_methods(NonConformanceReportService, {"create_report": ("ncr_report.created", "ncr_report"), "update_report": ("ncr_report.updated", "ncr_report")})
instrument_activity_methods(NonConformanceItemService, {"create_item": ("ncr_item.created", "ncr_item"), "update_item": ("ncr_item.updated", "ncr_item")})
