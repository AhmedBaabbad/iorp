import asyncio
from contextlib import asynccontextmanager
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
from app.commercial.api.routes_quote_settings import router as quote_settings_router
from app.commercial.api.routes_sample_evaluations import router as sample_evaluations_router
from app.commercial.api.routes_complaints import router as complaints_router
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
from app.production.api.routes_order_results import overview_router as result_overview_router, router as order_results_router
from app.production.api.routes_production_orders import router as production_orders_router
from app.production.api.routes_planning_orders import router as planning_orders_router
from app.production.api.routes_shift_definitions import router as shift_definitions_router
from app.production.api.routes_waste_records import router as waste_records_router
from app.production.api.routes_work_centers import router as work_centers_router
from app.quality.api.routes_ncr import router as ncr_router
from app.quality.api.routes_quality_checks import router as quality_checks_router
from app.quality.api.routes_return_inspections import router as quality_returns_router
from app.quality.api.routes_incoming_inspections import router as quality_incoming_router
from app.quality.api.routes_specifications import router as quality_specifications_router
from app.quality.api.routes_certificates import router as quality_certificates_router
from app.shipping.api.routes_shipments import router as shipping_router
from app.shipping.api.routes_returns import router as shipping_returns_router
from app.procurement.api.routes import router as procurement_router
from app.procurement.api.routes_purchase_orders import router as purchase_orders_router
from app.masterdata.api.routes import router as masterdata_router
from app.quality.api.routes_quality_defects import router as quality_defects_router
from app.quality.api.routes_quality_rejections import router as quality_rejections_router
from app.workforce.api.routes_workforce import router as workforce_router
from app.platform.api.routes_bootstrap import router as bootstrap_router
from app.platform.api.routes_system import router as system_router
from app.platform.api.routes_platform_auth import router as platform_router
from app.platform.api.routes_password_reset import router as platform_password_reset_router
from app.platform.api.routes_platform_admin import router as platform_organizations_router
from app.platform.api.routes_platform_administrators import router as platform_administrators_router
from app.platform.api.routes_platform_audit import router as platform_audit_router
from app.platform.api.routes_logs import activity_router as platform_activity_router, security_router as platform_security_router


configure_logging()
from app.foundation.api.routes_branding import router as branding_router
from app.foundation.api.routes_delegations import router as delegations_router
from app.foundation.api.routes_approvals import router as approvals_router
from app.core.reporting.routes import router as reporting_router
from app.production.reporting.routes import router as report_shortcuts_router
from app.production.reporting.definitions import register_reports
from app.core.reporting import providers as reporting_providers
from app.foundation.application.branding_service import BrandingService
register_reports()
from app.commercial.reporting.customers.definitions import register_reports as register_customer_reports
from app.commercial.reporting.customers import providers as customer_report_providers
from app.commercial.reporting.customers.routes import router as customer_reports_router
from app.commercial.application.report_queries import CommercialReportQueries
from app.production.application.customer_report_queries import ProductionReportQueries
from app.foundation.application.report_identity_queries import ReportIdentityQueries
customer_report_providers.commercial_factory = CommercialReportQueries
customer_report_providers.production_factory = ProductionReportQueries
customer_report_providers.identity_factory = ReportIdentityQueries
register_customer_reports()
from app.commercial.reporting.complaints import register as register_complaint_reports
register_complaint_reports()
from app.commercial.reporting.quotation.definitions import register_quotation
register_quotation()
# The quality report center (QUAL-REPORT-001).
from app.quality.reporting.definitions import register_reports as register_quality_reports
from app.quality.reporting.routes import router as quality_reports_router
register_quality_reports()
# Shipping and delivery notes (SHIP-001).
from app.shipping.reporting.document import register_delivery_note
from app.shipping.reporting.return_document import register_return_note
from app.procurement.reporting.receipt_document import register_receipt_document
from app.procurement.reporting.po_document import register_purchase_order_document
register_delivery_note()
register_return_note()
register_receipt_document()
register_purchase_order_document()
# Quality's gate on closing a production order (QUAL-001): production asks, it never imports quality.
from app.core.interfaces.order_close_guards import register_close_guard
from app.quality.application.rejection_service import close_blockers as quality_close_blockers
register_close_guard(quality_close_blockers)
# Master data (MD-001): modules ask the catalogue through core, and declare the product types they store, at this root.
from app.core.interfaces.product_catalog import register_product_catalog
from app.core.interfaces.product_types import register_product_type_holder
from app.core.interfaces.reference_lists import register_list_seeder, register_reference_holder, register_reference_lists
from app.masterdata.application.list_service import seed_standard_lists
from app.masterdata.application.catalog_provider import MasterDataCatalog, MasterDataLists
from app.commercial.application.product_types import HOLDER as commercial_product_types
from app.production.application.product_types import HOLDER as production_product_types
from app.quality.application.product_types import HOLDER as quality_product_types
from app.procurement.application.product_types import HOLDER as procurement_product_types
register_product_catalog(MasterDataCatalog())
from app.core.interfaces.complaint_quality import register_complaint_quality
from app.quality.application.complaint_adapter import refer_complaint
register_complaint_quality(refer_complaint)
from app.core.interfaces.sales_order_source import register_sales_integration
from app.commercial.application.sales_order_source import CommercialSalesOrderSource
from app.production.application.sales_demand_usage import ProductionSalesDemandUsage
from app.production.domain.permissions import DEMANDS_CREATE as _DEMANDS_CREATE
register_sales_integration(CommercialSalesOrderSource(), ProductionSalesDemandUsage(), _DEMANDS_CREATE)
for _holder in (commercial_product_types, production_product_types, quality_product_types, procurement_product_types):
    register_product_type_holder(_holder)
# MD-002: customers, suppliers and shipments declare where they store reference-list values.
from app.commercial.application.reference_values import HOLDERS as commercial_reference_values
from app.procurement.application.reference_values import HOLDERS as procurement_reference_values
from app.shipping.application.reference_values import HOLDERS as shipping_reference_values
from app.quality.application.reference_values import HOLDERS as quality_reference_values
from app.production.application.reference_values import HOLDERS as production_reference_values
from app.workforce.application.reference_values import HOLDERS as workforce_reference_values
register_reference_lists(MasterDataLists())
register_list_seeder(seed_standard_lists)
for _holder in (*commercial_reference_values, *procurement_reference_values, *shipping_reference_values, *quality_reference_values,
                *production_reference_values, *workforce_reference_values):
    register_reference_holder(_holder)
# Composition root: reporting reads the organization identity through this seam, never by importing foundation.
reporting_providers.branding_provider = lambda db, organization_id: BrandingService(db).get_branding(organization_id)
from app.core.interfaces.activity_log import register_activity_logger
from app.foundation.application.activity_log import TenantActivityLogger
register_activity_logger(TenantActivityLogger())
from app.core.interfaces.approvals import register_approvals  # noqa: E402
from app.foundation.application.delegation_service import FoundationApprovals  # noqa: E402
from app.foundation.infrastructure import delegation_models  # noqa: E402,F401  (tables in the metadata)
register_approvals(FoundationApprovals())
# PROJECT-NOTIFY-001: foundation tells who is who; the notifications module keeps every notification.
from app.core.interfaces.notifications import register_notifications  # noqa: E402
from app.core.interfaces.user_directory import register_user_directory  # noqa: E402
from app.foundation.application.user_directory import FoundationUserDirectory  # noqa: E402
from app.notifications.application.service import NotificationProvider  # noqa: E402
from app.notifications.api.routes import announcements as announcements_router, router as notifications_router  # noqa: E402
register_user_directory(FoundationUserDirectory())
register_notifications(NotificationProvider())
from app.core.interfaces.audit_trail import register_audit_trail  # noqa: E402
from app.foundation.application.audit import FoundationAuditTrail  # noqa: E402
register_audit_trail(FoundationAuditTrail())
from app.core.interfaces.approvals import in_organization, register_visibility  # noqa: E402


def _quote_visible(db, tenant, quote_id):
    from app.commercial.application.quote_service import QuoteService
    from app.commercial.application.visibility import QUOTES_READ, visible_owner
    return QuoteService(db, visible_owner(db, tenant, QUOTES_READ)).get_quote(tenant, quote_id) is not None


def _order_visible(db, tenant, order_id):
    from app.commercial.application.order_service import OrderService
    from app.commercial.application.visibility import ORDERS_READ, visible_owner
    return OrderService(db, visible_owner(db, tenant, ORDERS_READ)).get_order(tenant, order_id) is not None


def _complaint_visible(db, tenant, complaint_id):
    from fastapi import HTTPException
    from app.commercial.application.complaint_service import ComplaintService
    try:
        ComplaintService(db, tenant).get(complaint_id)
        return True
    except HTTPException:
        return False


# Documents whose approvals are signed (PROJECT-GOV-004): sales documents follow the sales representative's own
# customers; the others are read across the organization.
register_visibility("quote", "commercial:quotes:read", _quote_visible)
register_visibility("sales_order", "commercial:orders:read", _order_visible)
register_visibility("complaint", "commercial:complaints:read", _complaint_visible)
register_visibility("purchase_order", "procurement:purchase_orders:read", in_organization("procurement_purchase_orders"))
register_visibility("supplier", "procurement:suppliers:read", in_organization("procurement_suppliers"))
from app.production.domain.permissions import ORDERS_READ as _PRODUCTION_ORDERS_READ  # noqa: E402
register_visibility("production_order", _PRODUCTION_ORDERS_READ, in_organization("production_orders"))
register_visibility("quality_check", "quality:quality_checks:read", in_organization("quality_checks"))
register_visibility("quality_rejection", "quality:rejections:read", in_organization("quality_rejections"))
register_visibility("ncr", "quality:ncr_reports:read", in_organization("non_conformance_reports"))
register_visibility("quality_certificate", "quality:certificates:read", in_organization("quality_certificates"))
register_visibility("shipment_return", "shipping:returns:read", in_organization("shipping_returns"))

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Date-based production order start is opt-in (PRODUCTION_AUTO_START_BY_DATE).
    stop, task = asyncio.Event(), None
    if settings.production_auto_start_by_date:
        from app.production.application.order_scheduler import auto_start_loop
        task = asyncio.create_task(auto_start_loop(stop))
    yield
    if task:
        stop.set()
        await task


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
    docs_url=None if settings.app_env == 'production' else '/docs',
    redoc_url=None if settings.app_env == 'production' else '/redoc',
    openapi_url=None if settings.app_env == 'production' else '/openapi.json',
)

register_middleware(app)
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler


@app.exception_handler(RequestValidationError)
async def safe_platform_validation(request: Request, exc: RequestValidationError):
    if request.url.path.startswith(f'{settings.api_prefix}/platform/'):
        return JSONResponse(status_code=422, content={'detail': 'Invalid request data.'})
    return await request_validation_exception_handler(request, exc)

app.include_router(branding_router, prefix=settings.api_prefix)
app.include_router(delegations_router, prefix=settings.api_prefix)
app.include_router(approvals_router, prefix=settings.api_prefix)
app.include_router(notifications_router, prefix=settings.api_prefix)
app.include_router(announcements_router, prefix=settings.api_prefix)
app.include_router(reporting_router, prefix=settings.api_prefix)
app.include_router(customer_reports_router, prefix=settings.api_prefix)
app.include_router(report_shortcuts_router, prefix=settings.api_prefix)
app.include_router(quality_reports_router, prefix=settings.api_prefix)
app.include_router(demands_router, prefix=f"{settings.api_prefix}/production")
from app.production.api.routes_dashboard import router as production_dashboard_router
app.include_router(production_dashboard_router, prefix=f"{settings.api_prefix}/production")


@app.exception_handler(OrganizationAccessError)
def organization_access_error_handler(
    _request: Request, exc: OrganizationAccessError
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"code": exc.code, "message": exc.message},
    )


from app.core.interfaces.approvals import ApprovalAuthorityError  # noqa: E402


@app.exception_handler(ApprovalAuthorityError)
def approval_authority_error_handler(_request: Request, exc: ApprovalAuthorityError) -> JSONResponse:
    """A signature without authority (no role, no delegation in force): PROJECT-GOV-004."""
    return JSONResponse(status_code=403, content={"detail": "APPROVAL_AUTHORITY_REQUIRED"})


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
app.include_router(complaints_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(samples_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(sample_evaluations_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(quotes_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(quote_settings_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(orders_router, prefix=f"{settings.api_prefix}/commercial")
app.include_router(work_centers_router, prefix=f"{settings.api_prefix}/production")
app.include_router(shift_definitions_router, prefix=f"{settings.api_prefix}/production")
app.include_router(production_orders_router, prefix=f"{settings.api_prefix}/production")
app.include_router(planning_orders_router, prefix=f"{settings.api_prefix}/production")
app.include_router(production_order_items_router, prefix=f"{settings.api_prefix}/production")
app.include_router(order_results_router, prefix=f"{settings.api_prefix}/production")
app.include_router(result_overview_router, prefix=f"{settings.api_prefix}/production")
app.include_router(downtime_events_router, prefix=f"{settings.api_prefix}/production")
app.include_router(waste_records_router, prefix=f"{settings.api_prefix}/production")
app.include_router(quality_checks_router, prefix=f"{settings.api_prefix}/quality")
from app.quality.api.routes_dashboard import router as quality_dashboard_router
app.include_router(quality_dashboard_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(quality_returns_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(quality_incoming_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(quality_specifications_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(quality_certificates_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(shipping_router, prefix=f"{settings.api_prefix}/shipping")
from app.shipping.api.routes_dashboard import router as shipping_dashboard_router
app.include_router(shipping_dashboard_router, prefix=f"{settings.api_prefix}/shipping")
app.include_router(shipping_returns_router, prefix=f"{settings.api_prefix}/shipping")
app.include_router(procurement_router, prefix=f"{settings.api_prefix}/procurement")
app.include_router(purchase_orders_router, prefix=f"{settings.api_prefix}/procurement")
app.include_router(masterdata_router, prefix=f"{settings.api_prefix}/masterdata")
app.include_router(quality_defects_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(quality_rejections_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(ncr_router, prefix=f"{settings.api_prefix}/quality")
app.include_router(workforce_router, prefix=settings.api_prefix)
app.include_router(dashboard_router, prefix=settings.api_prefix)
from app.commercial.api.routes_dashboard import router as commercial_dashboard_router
app.include_router(commercial_dashboard_router, prefix=f"{settings.api_prefix}/commercial")
from app.procurement.api.routes_dashboard import router as procurement_dashboard_router
app.include_router(procurement_dashboard_router, prefix=f"{settings.api_prefix}/procurement")
app.include_router(bootstrap_router, prefix=settings.api_prefix)
app.include_router(system_router, prefix=settings.api_prefix)
app.include_router(platform_router, prefix=settings.api_prefix)
from app.platform.api.routes_mfa import router as mfa_router, require_step_up
from fastapi import Depends
app.include_router(mfa_router, prefix=settings.api_prefix)
app.include_router(platform_organizations_router, prefix=settings.api_prefix, dependencies=[Depends(require_step_up)])
app.include_router(platform_administrators_router, prefix=settings.api_prefix, dependencies=[Depends(require_step_up)])
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

@app.get("/health/ready", tags=["system"], include_in_schema=False)
def readiness_check():
    from app.core.db import check_database_connection
    try:
        check_database_connection()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"}, headers={"Cache-Control": "no-store"})
    return JSONResponse(content={"status": "ready"}, headers={"Cache-Control": "no-store"})


from app.production.api.routes_execution import router as execution_router
app.include_router(execution_router, prefix=f"{settings.api_prefix}/production")

# Reusable transport directory, owned by Shipping.
from app.shipping.api.routes_directory import router as transport_directory_router
from app.shipping.application.directory_service import TransportProvider
from app.core.interfaces.transport_directory import register_transport_directory
register_transport_directory(TransportProvider())
app.include_router(transport_directory_router, prefix=settings.api_prefix)

from app.commercial.api.routes_contacts import router as customer_contacts_router
from app.procurement.api.routes_contacts import router as supplier_contacts_router
from app.commercial.application.customer_delivery import CustomerDeliveryProvider
from app.core.interfaces.customer_delivery import register_customer_delivery
register_customer_delivery(CustomerDeliveryProvider())
app.include_router(customer_contacts_router, prefix=settings.api_prefix)
app.include_router(supplier_contacts_router, prefix=settings.api_prefix)
