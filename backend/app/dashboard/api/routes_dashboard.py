from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.commercial.infrastructure.models import Customer, Sample
from app.commercial.infrastructure.repositories import FollowUpRepository
from app.core.interfaces.authorization_policy import AuthorizationPolicy
from app.core.permission import has_permission
from app.dashboard.api.schemas import DashboardSummaryResponse
from app.dependencies import CurrentUserContext, build_auth_context, get_authorization_policy, get_current_tenant, get_current_user, get_db
from app.foundation.infrastructure.models import Role, User
from app.production.domain import permissions as production_permissions
from app.production.infrastructure.models import ProductionOrder
from app.quality.infrastructure.models import QualityCheck
from app.core.utils import utc_now
from app.workforce.domain.enums import WorkforceMemberStatus
from app.workforce.infrastructure.models import WorkforceMember
from app.core.tenancy import TenantContext


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    current: CurrentUserContext = Depends(get_current_user),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> DashboardSummaryResponse:
    org_id = tenant.organization_id
    auth_user = current.auth_user
    summary = DashboardSummaryResponse()

    if has_permission(auth_user, "commercial:customers:read"):
        customers_statement = select(Customer).where(Customer.organization_id == org_id)
        ctx = build_auth_context(db, tenant, "commercial:customers:read")
        customers_statement = policy.apply_query_filter(ctx, customers_statement, owner_field="sales_owner_user_id")
        summary.customers_count = db.scalar(
            select(func.count()).select_from(customers_statement.subquery())
        ) or 0

    if has_permission(auth_user, "commercial:samples:read"):
        summary.samples_count = db.scalar(
            select(func.count(Sample.id))
            .select_from(Sample)
            .join(Customer, Sample.customer_id == Customer.id)
            .where(Customer.organization_id == org_id)
        ) or 0

    if has_permission(auth_user, "workforce:members:read"):
        summary.workforce_count = db.scalar(
            select(func.count(WorkforceMember.id)).where(WorkforceMember.organization_id == org_id)
        ) or 0
        summary.workforce_active_count = db.scalar(
            select(func.count(WorkforceMember.id)).where(
                WorkforceMember.organization_id == org_id,
                WorkforceMember.status == WorkforceMemberStatus.ACTIVE,
            )
        ) or 0
        rows = db.execute(
            select(WorkforceMember.worker_type, func.count(WorkforceMember.id))
            .where(WorkforceMember.organization_id == org_id)
            .group_by(WorkforceMember.worker_type)
        ).all()
        summary.workforce_by_type = {worker_type.value: count for worker_type, count in rows}

        status_rows = db.execute(
            select(WorkforceMember.status, func.count(WorkforceMember.id))
            .where(WorkforceMember.organization_id == org_id)
            .group_by(WorkforceMember.status)
        ).all()
        summary.workforce_by_status = {status.value: count for status, count in status_rows}

    if has_permission(auth_user, "foundation:users:read"):
        summary.users_count = db.scalar(
            select(func.count(User.id)).where(User.organization_id == org_id)
        ) or 0

    if has_permission(auth_user, "foundation:roles:read"):
        summary.roles_count = db.scalar(
            select(func.count(Role.id)).where(Role.organization_id == org_id)
        ) or 0

    # Like require_permission, the organization root sees these sections without a role.
    def section(code: str) -> bool:
        return current.user.is_organization_root or has_permission(auth_user, code)

    if section("quality:quality_checks:read"):
        summary.quality_checks_count = db.scalar(
            select(func.count(QualityCheck.id)).where(QualityCheck.organization_id == org_id)
        ) or 0
        quality_rows = db.execute(
            select(QualityCheck.result, func.count(QualityCheck.id))
            .where(QualityCheck.organization_id == org_id, QualityCheck.result.is_not(None))
            .group_by(QualityCheck.result)
        ).all()
        summary.quality_checks_by_result = {result.value: count for result, count in quality_rows}

    if section(production_permissions.ORDERS_READ):
        summary.production_orders_count = db.scalar(
            select(func.count(ProductionOrder.id)).where(ProductionOrder.organization_id == org_id)
        ) or 0
        production_rows = db.execute(
            select(ProductionOrder.status, func.count(ProductionOrder.id))
            .where(ProductionOrder.organization_id == org_id)
            .group_by(ProductionOrder.status)
        ).all()
        summary.production_by_status = {status.value: count for status, count in production_rows}

    if has_permission(auth_user, "commercial:follow_ups:read"):
        follow_ups = FollowUpRepository(db)
        user_id = current.user.id
        summary.follow_ups_due_today = follow_ups.count_today(org_id, user_id)
        summary.follow_ups_overdue = follow_ups.count_overdue(org_id, user_id)
        summary.follow_ups_upcoming_7days = follow_ups.count_upcoming_7days(org_id, user_id)
        summary.follow_ups_completed_today = follow_ups.count_completed_today(org_id, user_id)
        if has_permission(auth_user, "commercial:follow_ups:assign"):
            summary.follow_ups_needing_assignment = follow_ups.count_unassigned_open(org_id)

    summary.last_updated_at = utc_now()
    return summary
