"""Idempotently add demand/planning grants to existing system roles."""
from sqlalchemy import select
from app.core.db import SessionLocal
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission
from app.foundation.domain.permission_catalog import PRODUCTION_PERMISSIONS
from app.foundation.domain.system_roles import SYSTEM_ROLE_BY_CODE, permission_matches, scope_for


def seed(db):
    definitions = [p for p in PRODUCTION_PERMISSIONS if p.resource in ("demands", "planning")]
    for org in db.scalars(select(Organization)):
        for definition in definitions:
            permission = db.scalar(select(Permission).where(Permission.organization_id == org.id, Permission.code == definition.code))
            if permission is None:
                permission = Permission(organization_id=org.id, code=definition.code, name=definition.name_en, description=definition.description_en, module_name=definition.module, resource_name=definition.resource, action_name=definition.action)
                db.add(permission)
                db.flush()
            for role in db.scalars(select(Role).where(Role.organization_id == org.id, Role.is_system.is_(True))):
                definition_role = SYSTEM_ROLE_BY_CODE.get(role.code)
                if not definition_role or not any(permission_matches(permission.code, p) for p in definition_role["permissions"]):
                    continue
                if db.scalar(select(RolePermission).where(RolePermission.role_id == role.id, RolePermission.permission_id == permission.id)) is None:
                    db.add(RolePermission(role_id=role.id, permission_id=permission.id, scope=scope_for(role.code, permission.code)))
    db.commit()


if __name__ == "__main__":
    # Import all mapped tables before configuring relationships.
    from app.main import app  # noqa: F401
    with SessionLocal() as session:
        seed(session)
    print("Production demand permissions synchronized.")
