"""Read-only computation of a tenant user's merged effective access."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.utils import utc_now
from app.foundation.domain.permission_catalog import ALL_TENANT_PERMISSIONS, PERMISSION_BY_CODE
from app.foundation.infrastructure.models import Permission, Role, RolePermission, User, UserRole


@dataclass(frozen=True)
class EffectivePermission:
    code: str
    module: str
    resource: str
    action: str
    name_en: str
    name_ar: str
    description_en: str
    description_ar: str
    effective_scope: str
    scopable: bool
    granted_by_roles: list[dict]
    is_root_bypass: bool


@dataclass(frozen=True)
class EffectiveAccessReport:
    user_id: UUID
    user_full_name: str
    user_email: str
    is_organization_root: bool
    total_permissions: int
    total_roles: int
    roles: list[dict]
    permissions_by_module: dict[str, list[EffectivePermission]]
    missing_permissions: list[dict]
    generated_at: datetime


_SCOPE_RANK = {"own": 0, "team": 1, "organization": 2}


def _broadest(first: str, second: str) -> str:
    return first if _SCOPE_RANK.get(first, 0) >= _SCOPE_RANK.get(second, 0) else second


def _permission(definition, scope: str, sources: list[dict], *, root: bool) -> EffectivePermission:
    return EffectivePermission(
        code=definition.code,
        module=definition.module,
        resource=definition.resource,
        action=definition.action,
        name_en=definition.name_en,
        name_ar=definition.name_ar,
        description_en=definition.description_en,
        description_ar=definition.description_ar,
        effective_scope=scope if definition.scopable else "organization",
        scopable=definition.scopable,
        granted_by_roles=sources,
        is_root_bypass=root,
    )


def compute_effective_access(db: Session, user_id: UUID, organization_id: UUID) -> EffectiveAccessReport:
    """Return the catalog-backed union of all role grants for one tenant user."""
    user = db.scalar(select(User).where(User.id == user_id, User.organization_id == organization_id))
    if user is None:
        raise LookupError("User not found.")

    roles = list(db.scalars(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user.id,
            Role.organization_id == organization_id,
        )
        .order_by(Role.name, Role.code)
    ))
    role_rows = [
        {"id": role.id, "code": role.code, "name": role.name, "is_system": role.is_system}
        for role in roles
    ]

    if user.is_organization_root:
        grouped: dict[str, list[EffectivePermission]] = {}
        for definition in ALL_TENANT_PERMISSIONS:
            grouped.setdefault(definition.module, []).append(
                _permission(definition, "organization", [], root=True)
            )
        for permissions in grouped.values():
            permissions.sort(key=lambda item: (item.resource, item.action))
        return EffectiveAccessReport(
            user.id, user.full_name, user.email, True, len(ALL_TENANT_PERMISSIONS),
            len(roles), role_rows, grouped, [], utc_now(),
        )

    grants = db.execute(
        select(Role, Permission.code, RolePermission.scope)
        .join(UserRole, UserRole.role_id == Role.id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            UserRole.user_id == user.id,
            Role.organization_id == organization_id,
            Permission.organization_id == organization_id,
        )
        .order_by(Role.name, Permission.code)
    ).all()

    merged: dict[str, dict] = {}
    for role, code, stored_scope in grants:
        definition = PERMISSION_BY_CODE.get(code)
        if definition is None:
            continue
        scope = stored_scope if definition.scopable else "organization"
        entry = merged.setdefault(code, {"scope": scope, "sources": []})
        entry["scope"] = _broadest(entry["scope"], scope)
        entry["sources"].append({
            "role_id": role.id,
            "role_code": role.code,
            "role_name": role.name,
            "scope": scope,
        })

    grouped = {}
    for code, data in merged.items():
        definition = PERMISSION_BY_CODE[code]
        grouped.setdefault(definition.module, []).append(
            _permission(definition, data["scope"], data["sources"], root=False)
        )
    for permissions in grouped.values():
        permissions.sort(key=lambda item: (item.resource, item.action))

    missing = [
        {
            "code": definition.code,
            "module": definition.module,
            "name_en": definition.name_en,
            "name_ar": definition.name_ar,
        }
        for definition in sorted(ALL_TENANT_PERMISSIONS, key=lambda item: item.code)
        if definition.code not in merged
    ]
    return EffectiveAccessReport(
        user.id, user.full_name, user.email, False, sum(map(len, grouped.values())),
        len(roles), role_rows, grouped, missing, utc_now(),
    )
