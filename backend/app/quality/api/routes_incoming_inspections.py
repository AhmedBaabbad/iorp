"""Incoming inspection (QUAL-INC-001): the received lots awaiting inspection, an inspection per lot, and the lot decision
that closes it (anything not released opens a non-conformance report about the supplier)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_permission
from app.quality.api.inspection_schemas import AwaitingReceipt, LotDecision, QualityCheckRead
from app.quality.application.check_service import QualityCheckService
from app.quality.application.incoming_inspection_service import IncomingInspectionService
from app.quality.domain import permissions as Q
from app.quality.domain.rules import QualityError

router = APIRouter(tags=["quality-incoming"])


def _read(db, tenant, check, can):
    service = QualityCheckService(db, tenant)
    return QualityCheckRead.model_validate({**QualityCheckRead.model_validate(check).model_dump(), **service.views([check], can, detail=True)[0]})


def _run(db, tenant, can, action):
    try:
        return _read(db, tenant, action(IncomingInspectionService(db, tenant)), can)
    except QualityError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc


@router.get("/incoming/awaiting", response_model=list[AwaitingReceipt], dependencies=[Depends(require_permission(Q.CHECKS_READ))])
def awaiting_lots(q: str = Query(default="", max_length=60), include_done: bool = False, tenant: TenantContext = Depends(get_current_tenant),
                  db: Session = Depends(get_db)):
    """Received lots of materials inspected on arrival, each with its inspection once opened."""
    return IncomingInspectionService(db, tenant).awaiting(q, include_done)


@router.post("/incoming/lines/{line_id}/inspection", response_model=QualityCheckRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.CHECKS_CREATE))])
def open_incoming_inspection(line_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                             can=Depends(permission_check)):
    """An inspection of the received lot, of the quantity received, against its material's specification."""
    return _run(db, tenant, can, lambda s: s.open(line_id))


@router.post("/quality-checks/{check_id}/lot-decision", response_model=QualityCheckRead,
             dependencies=[Depends(require_permission(Q.CHECKS_CLOSE)), Depends(require_permission(Q.NCR_CREATE))])
def decide_lot(check_id: UUID, payload: LotDecision, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
               can=Depends(permission_check)):
    """Closes an incoming inspection: the released part, and what is not released (an NCR about the supplier)."""
    return _run(db, tenant, can, lambda s: s.decide(check_id, payload))
