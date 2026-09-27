from fastapi import FastAPI, Request
from app.production.api.routes_demands import router as demands_router
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.core.organization_access import OrganizationAccessError
from app.core.account_access import AccountAccessError
from app.commercial.api.routes_customers import router as customers_router
from app.commercial.api.routes_followups import (
    customer_router as followups_router,
    router as followups_global_router,
)
from app.commercial.api.routes_interactions import router as interactions_router
from app.commercial.api.routes_orders import router as orders_router
from app.commercial.api.routes_quotes import router as quotes_router
from app.commercial.api.routes_sample_evaluations import router as sample_evaluations_router
from app.commercial.api.routes_samples import router as samples_router
from app.dashboard.api.routes_dashboard import router as dashboard_router
from app.foundation.api.routes_auth import router as auth_router
from app.foundation.api.routes_password_reset import router as tenant_password_reset_router
from app.foundation.api.routes_users import router as users_router
from app.foundation.api.routes_roles import router as roles_router
from app.foundation.api.routes_permissions import router as permissions_router
from app.foundation.api.routes_organizations import router as organizations_router
from app.foundation.api.routes_audit import router as tenant_audit_router
from app.foundation.api.routes_logs import activity_router as tenant_activity_router, security_router as tenant_security_router
from app.production.api.routes_downtime_events import router as downtime_events_router
from app.production.api.routes_production_order_items import router as production_order_items_router
from app.production.api.routes_production_outputs import router as production_outputs_router
from app.production.api.routes_production_orders import router as production_orders_router
from app.production.api.routes_planning_orders import router as planning_orders_router
from app.production.api.routes_shift_definitions import router as shift_definitions_router
from app.production.api.routes_shift_reports import router as shift_reports_router
from app.production.api.routes_waste_records import router as waste_records_router
from app.production.api.routes_work_centers import router as work_centers_router
from app.quality.api.routes_non_conformance_items import router as non_conformance_items_router
from app.quality.api.routes_non_conformance_reports import router as non_conformance_reports_router
from app.quality.api.routes_quality_checks import router as quality_checks_router
from app.quality.api.routes_quality_defects import router as quality_defects_router
from app.quality.api.routes_quality_rejections import router as quality_rejections_router
from app.workforce.api.routes_workforce import router as workforce_router
from app.platform.api.routes_bootstrap import router as bootstrap_router
from app.platform.api.routes_platform_auth import router as platform_router
from app.platform.api.routes_password_reset import router as platform_password_reset_router
from app.platform.api.routes_platform_admin import router as platform_organizations_router
from app.platform.api.routes_platform_administrators import router as platform_administrators_router
from app.platform.api.routes_platform_audit import router as platform_audit_router
from app.platform.api.routes_logs import activity_router as platform_activity_router, security_router as platform_security_router


configure_logging()
from app.core.interfaces.activity_log import register_activity_logger
from app.foundation.application.activity_log import TenantActivityLogger
register_activity_logger(TenantActivityLogger())

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
)

register_middleware(app)
app.include_router(demands_router, prefix=f"{settings.api_prefix}/production")


@app.exception_handler(OrganizationAccessError)
def organization_access_error_handler(
    _request: Request, exc: OrganizationAccessError
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"code": exc.code, "message": exc.message},
    )


@app.exception_handler(AccountAccessError)
def account_access_error_handler(_request: Request, exc: AccountAccessError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"code": exc.code, "message": exc.message})


app.include_router(auth_router, prefix=f"{settings.api_prefix}/auth")
app.include_router(tenant_password_reset_router, prefix=settings.api_prefix)
app.include_router(platform_password_reset_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=f"{settings.api_prefix}/admin")
app.include_router(roles_router, prefix=f"{settings.api_prefix}/admin")
app.include_router(permissions_router, prefix=f"{settings.api_prefix}/admin")
app.include_router(customers_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(interactions_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(followups_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(followups_global_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(samples_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(sample_evaluations_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(quotes_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(orders_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(work_centers_router, prefix=f"{settings.api_prefix}/production")
app.include_router(shift_definitions_router, prefix=f"{settings.api_prefix}/production")
app.include_router(production_orders_router, prefix=f"{settings.api_prefix}/production")
app.include_router(planning_orders_router, prefix=f"{settings.api_prefix}/production")
app.include_router(production_order_items_router, prefix=f"{settings.api_prefix}/production")
app.include_router(shift_reports_router, prefix=f"{settings.api_prefix}/production")
app.include_router(production_outputs_router, prefix=f"{settings.api_prefix}/production")
app.include_router(downtime_events_router, prefix=f"{settings.api_prefix}/production")
app.include_router(waste_records_router, prefix=f"{settings.api_prefix}/production")
app.include_router(quality_checks_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(quality_defects_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(quality_rejections_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(non_conformance_reports_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(non_conformance_items_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(workforce_router, prefix=settings.api_prefix)
app.include_router(dashboard_router, prefix=settings.api_prefix)
app.include_router(bootstrap_router, prefix=settings.api_prefix)
app.include_router(platform_router, prefix=settings.api_prefix)
app.include_router(platform_organizations_router, prefix=settings.api_prefix)
app.include_router(platform_administrators_router, prefix=settings.api_prefix)
app.include_router(platform_audit_router, prefix=settings.api_prefix)
app.include_router(platform_security_router, prefix=settings.api_prefix)
app.include_router(platform_activity_router, prefix=settings.api_prefix)
app.include_router(organizations_router, prefix=settings.api_prefix)
app.include_router(tenant_audit_router, prefix=f"{settings.api_prefix}/admin")
app.include_router(tenant_security_router, prefix=f"{settings.api_prefix}/admin")
app.include_router(tenant_activity_router, prefix=f"{settings.api_prefix}/admin")


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
    }

from app.production.api.routes_execution import router as execution_router
app.include_router(execution_router, prefix=f"{settings.api_prefix}/production")
