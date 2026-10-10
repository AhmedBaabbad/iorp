"""Procurement's read-only operational indicators; every query stays tenant scoped."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dashboard import Dashboard, Period
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_any_permission
from app.procurement.domain import permissions as P
from app.procurement.application.dashboard_service import build_dashboard

router = APIRouter(tags=["procurement-dashboard"])


@router.get('/dashboard', response_model=Dashboard, dependencies=[Depends(require_any_permission([P.SUPPLIERS_READ, P.PO_READ, P.RECEIPTS_READ]))])
def dashboard(period: Period = Query('3m'), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return build_dashboard(db, tenant, can, period)
