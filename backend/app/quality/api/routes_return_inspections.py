"""Returned goods (QUAL-RET-001): the shipping returns awaiting quality, an inspection per returned line, the split
decision that closes it, and the other shipments of the same production order (containment)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_permission
from app.quality.api.inspection_schemas import AwaitingReturn, BatchShipment, QualityCheckRead, ReturnDecision
from app.quality.application.check_service import QualityCheckService
from app.quality.application.return_inspection_service import ReturnInspectionService
from app.quality.domain import permissions as Q
from app.quality.domain.rules import QualityError

router = APIRouter(tags=["quality-returns"])


def _error(exc: QualityError):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def _read(db, tenant, check, can):
    service = QualityCheckService(db, tenant)
    return QualityCheckRead.model_validate({**QualityCheckRead.model_validate(check).model_dump(), **service.views([check], can, detail=True)[0]})


@router.get("/returns/awaiting", response_model=list[AwaitingReturn], dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def awaiting_returns(q: str = Query(default="", max_length=60), include_done: bool = False, tenant: TenantContext = Depends(get_current_tenant),
                     db: Session = Depends(get_db)):
    """Returned goods received for quality, each line with its inspection once opened."""
    return ReturnInspectionService(db, tenant).awaiting(q, include_done)


@router.post("/returns/lines/{line_id}/inspection", response_model=QualityCheckRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.CHECKS_CREATE))])
def open_return_inspection(line_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                           can=Depends(permission_check)):
    """An inspection of the returned line (issue triggered), of the quantity that came back."""
    try:
        return _read(db, tenant, ReturnInspectionService(db, tenant).open(line_id), can)
    except QualityError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.post("/quality-checks/{check_id}/return-decision", response_model=QualityCheckRead,
             dependencies=[Depends(require_permission(Q.CHECKS_CLOSE)), Depends(require_permission(Q.REJECTIONS_DECIDE))])
def decide_return(check_id: UUID, payload: ReturnDecision, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)):
    """Closes a return inspection: the accepted part back to stock, each rejected part a decided rejection, an NCR if asked."""
    try:
        return _read(db, tenant, ReturnInspectionService(db, tenant).decide(check_id, payload), can)
    except QualityError as exc:
        db.rollback()
        raise _error(exc) from exc


@router.get("/quality-checks/{check_id}/batch-shipments", response_model=list[BatchShipment], dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def batch_shipments(check_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Every delivery note that carried the inspected production order: who else has the goods, and what is about to leave."""
    try:
        check = QualityCheckService(db, tenant).get(check_id)
    except QualityError as exc:
        raise _error(exc) from exc
    return ReturnInspectionService(db, tenant).batch(check)
