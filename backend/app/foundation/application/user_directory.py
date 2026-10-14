"""Foundation's answer to core/interfaces/user_directory (PROJECT-NOTIFY-001): the organization's active users, who
holds a permission (through a role, as the root, or by a delegation in force), a role's members, and names."""
from sqlalchemy import select

from app.foundation.application.delegation_service import today, usable
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.delegation_models import ApprovalDelegation
from app.foundation.infrastructure.models import Permission, Role, RolePermission, User, UserRole


class FoundationUserDirectory:
    def active_users(self, db, organization_id):
        return set(db.scalars(select(User.id).where(User.organization_id == organization_id, User.status == UserStatus.ACTIVE)))

    def holders(self, db, organization_id, permission):
        active = User.organization_id == organization_id, User.status == UserStatus.ACTIVE
        by_role = db.scalars(select(User.id).join(UserRole, UserRole.user_id == User.id)
                             .join(RolePermission, RolePermission.role_id == UserRole.role_id)
                             .join(Permission, Permission.id == RolePermission.permission_id)
                             .where(*active, Permission.code == permission, Permission.organization_id == organization_id))
        roots = db.scalars(select(User.id).where(*active, User.is_organization_root.is_(True)))
        found = set(by_role) | set(roots)
        delegations = db.scalars(select(ApprovalDelegation).where(ApprovalDelegation.organization_id == organization_id,
                                                                  ApprovalDelegation.permission_code == permission,
                                                                  ApprovalDelegation.revoked_at.is_(None))).all()
        if delegations:
            on = today(db, organization_id)
            found |= {d.delegate_user_id for d in delegations if usable(db, d, on)}
        return found

    def role_members(self, db, organization_id, role_id):
        return set(db.scalars(select(User.id).join(UserRole, UserRole.user_id == User.id)
                              .where(User.organization_id == organization_id, User.status == UserStatus.ACTIVE, UserRole.role_id == role_id)))

    def roles(self, db, organization_id):
        rows = db.execute(select(Role.id, Role.code, Role.name).where(Role.organization_id == organization_id).order_by(Role.name)).all()
        return [dict(id=r.id, code=r.code, name=r.name) for r in rows]

    def names(self, db, organization_id, user_ids):
        ids = {i for i in user_ids if i}
        if not ids:
            return {}
        return dict(db.execute(select(User.id, User.full_name).where(User.organization_id == organization_id, User.id.in_(ids))).all())
