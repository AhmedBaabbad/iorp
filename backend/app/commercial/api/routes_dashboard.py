from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.commercial.application.dashboard_service import CommercialDashboard
from app.core.dashboard import Dashboard, Period
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_any_permission

router = APIRouter(tags=["commercial-dashboard"])


@router.get("/dashboard", response_model=Dashboard, dependencies=[Depends(require_any_permission([
    "commercial:customers:read", "commercial:quotes:read", "commercial:orders:read", "commercial:samples:read", "commercial:follow_ups:read"]))])
def commercial_dashboard(period: Period = Query("3m"), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                         can=Depends(permission_check)) -> Dashboard:
    """The customers and sales section's dashboard (DASH-001): each part only with the permission to read its data, and a
    sales representative's figures cover their own customers only."""
    return CommercialDashboard(db, tenant, can).build(period)
