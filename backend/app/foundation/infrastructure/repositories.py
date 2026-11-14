from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.core.security import normalize_email


class OrganizationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, organization: Organization) -> Organization:
        self.db.add(organization)
        self.db.flush()
        return organization

    def get(self, organization_id: UUID) -> Organization | None:
        return self.db.get(Organization, organization_id)

    def get_by_code(self, code: str) -> Organization | None:
        statement = select(Organization).where(Organization.code == code)
        return self.db.scalar(statement)

    def list_all(self) -> list[Organization]:
        statement = select(Organization).order_by(Organization.created_at.desc())
        return list(self.db.scalars(statement))


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def get(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_for_organization(self, organization_id: UUID, user_id: UUID) -> User | None:
        return self.db.scalar(select(User).where(
            User.id == user_id,
            User.organization_id == organization_id,
        ))

    def get_by_email(self, organization_id: UUID, email: str) -> User | None:
        statement = select(User).where(
            User.organization_id == organization_id,
            User.email == normalize_email(email),
        )
        return self.db.scalar(statement)

    def list_by_email(self, email: str) -> list[User]:
        statement = select(User).where(User.email == normalize_email(email))
        return list(self.db.scalars(statement))

    def get_by_email_global(self, email: str, exclude_user_id: UUID | None = None) -> User | None:
        statement = select(User).where(User.email == normalize_email(email))
        if exclude_user_id is not None:
            statement = statement.where(User.id != exclude_user_id)
        return self.db.scalar(statement.limit(1))

    def list_by_organization(self, organization_id: UUID, *, active_only: bool = False) -> list[User]:
        statement = (
            select(User)
            .where(User.organization_id == organization_id)
            .order_by(User.created_at.desc())
        )
        if active_only:
            statement = statement.where(User.status == 'active', User.archived_at.is_(None))
        return list(self.db.scalars(statement))

    def count_organization_roots(
        self,
        organization_id: UUID,
        exclude_user_id: UUID | None = None,
    ) -> int:
        statement = select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.is_organization_root.is_(True),
        )
        if exclude_user_id is not None:
            statement = statement.where(User.id != exclude_user_id)
        return self.db.scalar(statement) or 0


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, role: Role) -> Role:
        self.db.add(role)
        self.db.flush()
        return role

    def get(self, role_id: UUID) -> Role | None:
        return self.db.get(Role, role_id)

    def get_for_organization(self, organization_id: UUID, role_id: UUID) -> Role | None:
        return self.db.scalar(select(Role).where(
            Role.id == role_id,
            Role.organization_id == organization_id,
        ))

    def get_by_code(self, organization_id: UUID, code: str) -> Role | None:
        statement = select(Role).where(
            Role.organization_id == organization_id,
            Role.code == code,
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[Role]:
        statement = (
            select(Role)
            .where(Role.organization_id == organization_id)
            .order_by(Role.created_at.desc())
        )
        return list(self.db.scalars(statement))


class PermissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, permission: Permission) -> Permission:
        self.db.add(permission)
        self.db.flush()
        return permission

    def get(self, permission_id: UUID) -> Permission | None:
        return self.db.get(Permission, permission_id)

    def get_for_organization(self, organization_id: UUID, permission_id: UUID) -> Permission | None:
        return self.db.scalar(select(Permission).where(
            Permission.id == permission_id,
            Permission.organization_id == organization_id,
        ))

    def get_by_code(self, organization_id: UUID, code: str) -> Permission | None:
        statement = select(Permission).where(
            Permission.organization_id == organization_id, Permission.code == code
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[Permission]:
        statement = select(Permission).where(Permission.organization_id == organization_id).order_by(Permission.module_name, Permission.resource_name, Permission.action_name)
        return list(self.db.scalars(statement))

    def list_for_user(self, user_id: UUID, organization_id: UUID) -> list[Permission]:
        statement = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.organization_id == organization_id,
                Permission.organization_id == organization_id,
            )
            .distinct()
            .order_by(Permission.module_name, Permission.action_name)
        )
        return list(self.db.scalars(statement))

    def get_permissions_for_user(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> set[str]:
        statement = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.organization_id == organization_id,
                Permission.organization_id == organization_id,
            )
            .distinct()
        )
        return set(self.db.scalars(statement))


class RolePermissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, role_permission: RolePermission) -> RolePermission:
        self.db.add(role_permission)
        self.db.flush()
        return role_permission

    def get_by_pair(self, role_id: UUID, permission_id: UUID) -> RolePermission | None:
        statement = select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
        return self.db.scalar(statement)

    def get_by_pair_for_organization(
        self, organization_id: UUID, role_id: UUID, permission_id: UUID,
    ) -> RolePermission | None:
        statement = (
            select(RolePermission)
            .join(Role, Role.id == RolePermission.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id,
                Role.organization_id == organization_id,
                Permission.organization_id == organization_id,
            )
        )
        return self.db.scalar(statement)

    def list_permissions_for_role_in_organization(
        self, organization_id: UUID, role_id: UUID,
    ) -> list[Permission]:
        statement = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(
                RolePermission.role_id == role_id,
                Role.organization_id == organization_id,
                Permission.organization_id == organization_id,
            )
            .order_by(Permission.module_name, Permission.action_name)
        )
        return list(self.db.scalars(statement))

    def list_permissions_for_role(self, role_id: UUID) -> list[Permission]:
        statement = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.module_name, Permission.action_name)
        )
        return list(self.db.scalars(statement))

    def list_permissions_for_role_with_scope(self, role_id: UUID) -> list[tuple[Permission, str]]:
        statement = (
            select(Permission, RolePermission.scope)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.module_name, Permission.action_name)
        )
        return [(permission, scope) for permission, scope in self.db.execute(statement)]


class UserRoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, user_role: UserRole) -> UserRole:
        self.db.add(user_role)
        self.db.flush()
        return user_role

    def get_by_pair(self, user_id: UUID, role_id: UUID) -> UserRole | None:
        statement = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        )
        return self.db.scalar(statement)

    def get_by_pair_for_organization(
        self, organization_id: UUID, user_id: UUID, role_id: UUID,
    ) -> UserRole | None:
        statement = (
            select(UserRole)
            .join(User, User.id == UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                User.organization_id == organization_id,
                Role.organization_id == organization_id,
            )
        )
        return self.db.scalar(statement)

    def count_for_role_in_organization(self, organization_id: UUID, role_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.role_id == role_id, Role.organization_id == organization_id)
        )
        return self.db.scalar(statement) or 0

    def list_roles_for_users(self, user_ids: list[UUID], organization_id: UUID) -> dict[UUID, list[Role]]:
        if not user_ids:
            return {}
        rows = self.db.execute(select(UserRole.user_id, Role)
            .join(Role, UserRole.role_id == Role.id)
            .where(UserRole.user_id.in_(user_ids), Role.organization_id == organization_id)
            .order_by(Role.created_at.desc()))
        result = {}
        for user_id, role in rows:
            result.setdefault(user_id, []).append(role)
        return result

    def list_roles_for_user(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> list[Role]:
        statement = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                Role.organization_id == organization_id,
            )
            .order_by(Role.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_assignments_for_user(self, user_id: UUID, organization_id: UUID) -> list[UserRole]:
        statement = (
            select(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id, Role.organization_id == organization_id)
            .order_by(UserRole.assigned_at.desc())
        )
        return list(self.db.scalars(statement))

    def count_for_role(self, role_id: UUID) -> int:
        statement = select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
        return self.db.scalar(statement) or 0
