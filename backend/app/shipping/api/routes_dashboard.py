from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dashboard import Dashboard, Period
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_any_permission
from app.shipping.application.dashboard_service import ShippingDashboard
from app.shipping.domain import permissions as S

router = APIRouter(tags=["shipping-dashboard"])


@router.get("/dashboard", response_model=Dashboard, dependencies=[Depends(require_any_permission([S.SHIPMENTS_READ, S.RETURNS_READ]))])
def shipping_dashboard(period: Period = Query("3m"), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                       can=Depends(permission_check)) -> Dashboard:
    """The shipping and delivery section's dashboard (DASH-001): each part only with the permission to read its data."""
    return ShippingDashboard(db, tenant.organization_id, can).build(period)
