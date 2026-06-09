from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.core.tenancy import TenantContext
from app.foundation.api.schemas import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    OrganizationCreate,
    PermissionCreate,
    RoleCreate,
    RolePermissionAssign,
    UserCreate,
    UserRoleAssign,
)
from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.repositories import (
    OrganizationRepository,
    PermissionRepository,
    RoleRepository,
    RolePermissionRepository,
    UserRepository,
    UserRoleRepository,
)


class FoundationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.organizations = OrganizationRepository(db)
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.permissions = PermissionRepository(db)
        self.role_permissions = RolePermissionRepository(db)
        self.user_roles = UserRoleRepository(db)

    def create_organization(self, data: OrganizationCreate) -> Organization:
        organization = Organization(**data.model_dump())
        self.organizations.add(organization)
        self.db.commit()
        self.db.refresh(organization)
        return organization

    def get_organization(self, organization_id: UUID) -> Organization | None:
        return self.organizations.get(organization_id)

    def list_organizations(self) -> list[Organization]:
        return self.organizations.list_all()

    def create_user(self, data: UserCreate) -> User:
        payload = data.model_dump(exclude={"password"})
        user = User(
            **payload,
            password_hash=hash_password(data.password),
        )
        self.users.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_user_by_id_in_organization(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> User | None:
        user = self.users.get(user_id)
        if user is None or user.organization_id != organization_id:
            return None
        return user

    def list_users(self, organization_id: UUID) -> list[User]:
        return self.users.list_by_organization(organization_id)

    def list_users_for_tenant(self, tenant: TenantContext) -> list[User]:
        return self.users.list_by_organization(tenant.organization_id)

    def create_role(self, data: RoleCreate) -> Role:
        role = Role(**data.model_dump())
        self.roles.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    def get_role(self, role_id: UUID) -> Role | None:
        return self.roles.get(role_id)

    def list_roles(self, organization_id: UUID) -> list[Role]:
        return self.roles.list_by_organization(organization_id)

    def list_roles_for_tenant(self, tenant: TenantContext) -> list[Role]:
        return self.roles.list_by_organization(tenant.organization_id)

    def create_permission(self, data: PermissionCreate) -> Permission:
        permission = Permission(**data.model_dump())
        self.permissions.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def assign_permission_to_role(self, data: RolePermissionAssign) -> RolePermission:
        role = self.roles.get(data.role_id)
        if role is None:
            raise ValueError("Role not found.")

        permission = self.permissions.get(data.permission_id)
        if permission is None:
            raise ValueError("Permission not found.")

        existing = self.role_permissions.get_by_pair(data.role_id, data.permission_id)
        if existing is not None:
            return existing

        role_permission = RolePermission(**data.model_dump())
        self.role_permissions.add(role_permission)
        self.db.commit()
        self.db.refresh(role_permission)
        return role_permission

    def assign_role_to_user(self, data: UserRoleAssign) -> UserRole:
        user = self.users.get(data.user_id)
        if user is None:
            raise ValueError("User not found.")

        role = self.roles.get(data.role_id)
        if role is None:
            raise ValueError("Role not found.")

        if user.organization_id != role.organization_id:
            raise ValueError("User and role must belong to the same organization.")

        existing = self.user_roles.get_by_pair(data.user_id, data.role_id)
        if existing is not None:
            return existing

        user_role = UserRole(**data.model_dump())
        self.user_roles.add(user_role)
        self.db.commit()
        self.db.refresh(user_role)
        return user_role

    def assign_role_to_user_for_tenant(
        self,
        tenant: TenantContext,
        data: UserRoleAssign,
    ) -> UserRole:
        user = self.users.get(data.user_id)
        if user is None:
            raise ValueError("User not found.")
        if tenant.organization_id != user.organization_id:
            raise ValueError("Resource does not belong to the current organization.")

        role = self.roles.get(data.role_id)
        if role is None:
            raise ValueError("Role not found.")
        if tenant.organization_id != role.organization_id:
            raise ValueError("Resource does not belong to the current organization.")

        return self.assign_role_to_user(data)

    def list_permissions_for_role(self, role_id: UUID) -> list[Permission]:
        return self.role_permissions.list_permissions_for_role(role_id)

    def list_roles_for_user(self, user_id: UUID) -> list[Role]:
        return self.user_roles.list_roles_for_user(user_id)

    def authenticate_user(self, data: LoginRequest) -> User | None:
        matches = self.users.list_by_email(str(data.email))
        if len(matches) != 1:
            return None

        user = matches[0]
        if user.status != UserStatus.ACTIVE:
            return None

        if not verify_password(data.password, user.password_hash):
            return None

        return user

    def login(self, data: LoginRequest) -> LoginResponse | None:
        user = self.authenticate_user(data)
        if user is None:
            return None

        token = create_access_token(
            subject=str(user.id),
            claims={"organization_id": str(user.organization_id)},
        )
        return LoginResponse(access_token=token)

    def build_current_user_response(self, user: User) -> CurrentUserResponse:
        organization = self.organizations.get(user.organization_id)
        if organization is None:
            raise ValueError("User organization not found.")

        roles = self.user_roles.list_roles_for_user(user.id)
        return CurrentUserResponse(
            id=user.id,
            organization_id=user.organization_id,
            organization_code=organization.code,
            full_name=user.full_name,
            email=user.email,
            status=user.status,
            roles=[role.code for role in roles],
        )
