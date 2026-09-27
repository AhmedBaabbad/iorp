from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.commercial.application.workforce_enrichment import get_workforce_summary_row
from app.core.tenancy import TenantContext
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Permission, Role, RolePermission, User, UserRole
from app.foundation.infrastructure.repositories import PermissionRepository


# Single source of truth for who may be assigned as a customer's Sales Owner.
# Permission-based only -- never hardcode role names/codes here.
REQUIRED_SALES_OWNER_PERMISSIONS: frozenset[str] = frozenset(
    {"commercial:customers:read", "commercial:customers:update"}
)


class SalesOwnerEligibilityService:
    """Centralized Sales Owner eligibility policy.

    Used by the eligible-sales-owners endpoint and by customer create/update
    validation -- do not re-implement this query anywhere else.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_eligible_users(self, organization_id: UUID) -> list[User]:
        statement = (
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                User.organization_id == organization_id,
                User.status == UserStatus.ACTIVE,
                Permission.code.in_(REQUIRED_SALES_OWNER_PERMISSIONS),
            )
            .group_by(User.id)
            .having(func.count(func.distinct(Permission.code)) == len(REQUIRED_SALES_OWNER_PERMISSIONS))
            .order_by(User.full_name)
        )
        return list(self.db.scalars(statement))

    def is_user_eligible(self, user_id: UUID, organization_id: UUID) -> bool:
        user = self.db.scalar(select(User).where(
            User.id == user_id,
            User.organization_id == organization_id,
        ))
        if user is None:
            return False
        if user.status != UserStatus.ACTIVE:
            return False

        permissions = PermissionRepository(self.db).get_permissions_for_user(user_id, organization_id)
        return REQUIRED_SALES_OWNER_PERMISSIONS.issubset(permissions)

    def is_current_user_eligible(self, tenant: TenantContext) -> bool:
        return REQUIRED_SALES_OWNER_PERMISSIONS.issubset(tenant.permissions)

    def get_workforce_summary_row(self, user_id: UUID, organization_id: UUID) -> dict | None:
        return get_workforce_summary_row(self.db, user_id, organization_id)
