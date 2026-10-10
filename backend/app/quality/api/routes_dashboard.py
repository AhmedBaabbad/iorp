from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dashboard import Dashboard, Period
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_any_permission
from app.quality.application.dashboard_service import QualityDashboard
from app.quality.domain import permissions as Q

router = APIRouter(tags=["quality-dashboard"])


@router.get("/dashboard", response_model=Dashboard,
            dependencies=[Depends(require_any_permission([Q.CHECKS_READ, Q.REJECTIONS_READ, Q.DEFECTS_READ, Q.NCR_READ, Q.COA_READ]))])
def quality_dashboard(period: Period = Query("3m"), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                      can=Depends(permission_check)) -> Dashboard:
    """The quality section's dashboard (DASH-001): each part only with the permission to read its data."""
    return QualityDashboard(db, tenant.organization_id, can).build(period)
