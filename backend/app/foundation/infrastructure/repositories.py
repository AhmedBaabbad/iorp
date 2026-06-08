from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)


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

    def get_by_email(self, organization_id: UUID, email: str) -> User | None:
        statement = select(User).where(
            User.organization_id == organization_id,
            User.email == email,
        )
        return self.db.scalar(statement)

    def list_by_email(self, email: str) -> list[User]:
        statement = select(User).where(User.email == email)
        return list(self.db.scalars(statement))

    def list_by_organization(self, organization_id: UUID) -> list[User]:
        statement = (
            select(User)
            .where(User.organization_id == organization_id)
            .order_by(User.created_at.desc())
        )
        return list(self.db.scalars(statement))


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, role: Role) -> Role:
        self.db.add(role)
        self.db.flush()
        return role

    def get(self, role_id: UUID) -> Role | None:
        return self.db.get(Role, role_id)

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

    def get_by_code(self, code: str) -> Permission | None:
        statement = select(Permission).where(Permission.code == code)
        return self.db.scalar(statement)

    def list_all(self) -> list[Permission]:
        statement = select(Permission).order_by(Permission.module_name, Permission.action_name)
        return list(self.db.scalars(statement))


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

    def list_permissions_for_role(self, role_id: UUID) -> list[Permission]:
        statement = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.module_name, Permission.action_name)
        )
        return list(self.db.scalars(statement))


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

    def list_roles_for_user(self, user_id: UUID) -> list[Role]:
        statement = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.created_at.desc())
        )
        return list(self.db.scalars(statement))
