from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dashboard import Dashboard, Period
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_any_permission
from app.production.api.order_views import permission_check
from app.production.application.dashboard_service import ProductionDashboard
from app.production.domain import permissions as P

router = APIRouter(tags=["production-dashboard"])


@router.get("/dashboard", response_model=Dashboard,
            dependencies=[Depends(require_any_permission([P.ORDERS_READ, P.RESULTS_READ, P.DOWNTIME_READ, P.DEMANDS_READ]))])
def production_dashboard(period: Period = Query("3m"), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                         can=Depends(permission_check)) -> Dashboard:
    """The production section's dashboard (DASH-001): each card and list only with the permission to read its data."""
    return ProductionDashboard(db, tenant.organization_id, can).build(period)
