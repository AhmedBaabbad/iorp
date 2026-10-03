"""Quality rejections (QUAL-001): record, decide the disposition, execute it. One permission per action."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_permission
from app.quality.api.inspection_schemas import (
    QualityRejectionCreate, QualityRejectionListItem, QualityRejectionRead, QualityRejectionUpdate, RejectionDecision, RejectionExecution,
)
from app.quality.application.rejection_service import QualityRejectionService
from app.quality.domain import permissions as Q
from app.quality.domain.enums import Disposition, DispositionStatus, RejectionReason
from app.quality.domain.rules import QualityError

router = APIRouter(prefix="/quality-rejections", tags=["quality-rejections"])


def _error(exc: QualityError):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def _read(service, rejection, can):
    # Validated as a whole, so the nested history and rejection rows are typed.
    return QualityRejectionRead.model_validate({**QualityRejectionRead.model_validate(rejection).model_dump(), **service.views([rejection], can, detail=True)[0]})


@router.post("", response_model=QualityRejectionRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Q.REJECTIONS_CREATE))])
def create_quality_rejection(payload: QualityRejectionCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                             can=Depends(permission_check)):
    """A rejection not opened by closing a check (code QR-YYYY-NNNN), awaiting a decision."""
    service = QualityRejectionService(db, tenant)
    try:
        return _read(service, service.create(payload), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.get("", response_model=list[QualityRejectionListItem], dependencies=[Depends(require_permission(Q.REJECTIONS_READ))])
def list_quality_rejections(
    production_order_id: UUID | None = Query(default=None), quality_check_id: UUID | None = Query(default=None),
    rejection_reason: RejectionReason | None = Query(default=None), disposition: Disposition | None = Query(default=None),
    disposition_status: DispositionStatus | None = Query(default=None), date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None), search: str | None = Query(default=None, max_length=60),
    tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check),
):
    service = QualityRejectionService(db, tenant)
    rows = service.list(production_order_id=production_order_id, quality_check_id=quality_check_id, rejection_reason=rejection_reason,
                        disposition=disposition, disposition_status=disposition_status, date_from=date_from, date_to=date_to, search=search)
    return [QualityRejectionListItem.model_validate(r).model_copy(update=v) for r, v in zip(rows, service.views(rows, can))]


@router.get("/{rejection_id}", response_model=QualityRejectionRead, dependencies=[Depends(require_permission(Q.REJECTIONS_READ))])
def get_quality_rejection(rejection_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                          can=Depends(permission_check)):
    service = QualityRejectionService(db, tenant)
    try:
        return _read(service, service.get(rejection_id), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.patch("/{rejection_id}", response_model=QualityRejectionRead, dependencies=[Depends(require_permission(Q.REJECTIONS_UPDATE))])
def update_quality_rejection(rejection_id: UUID, payload: QualityRejectionUpdate, tenant: TenantContext = Depends(get_current_tenant),
                             db: Session = Depends(get_db), can=Depends(permission_check)):
    """Details while no disposition has been decided."""
    service = QualityRejectionService(db, tenant)
    try:
        return _read(service, service.update(rejection_id, payload), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post("/{rejection_id}/decide", response_model=QualityRejectionRead, dependencies=[Depends(require_permission(Q.REJECTIONS_DECIDE))])
def decide_quality_rejection(rejection_id: UUID, payload: RejectionDecision, tenant: TenantContext = Depends(get_current_tenant),
                             db: Session = Depends(get_db), can=Depends(permission_check)):
    """Hold, scrap, rework, return to process, or use as is (with the concession approver and justification)."""
    service = QualityRejectionService(db, tenant)
    try:
        return _read(service, service.decide(rejection_id, payload), can)
    except QualityError as exc:
        raise _error(exc) from exc


@router.post("/{rejection_id}/execute", response_model=QualityRejectionRead, dependencies=[Depends(require_permission(Q.REJECTIONS_EXECUTE))])
def execute_quality_rejection(rejection_id: UUID, payload: RejectionExecution, tenant: TenantContext = Depends(get_current_tenant),
                              db: Session = Depends(get_db), can=Depends(permission_check)):
    service = QualityRejectionService(db, tenant)
    try:
        return _read(service, service.execute(rejection_id, payload.execution_notes), can)
    except QualityError as exc:
        raise _error(exc) from exc
