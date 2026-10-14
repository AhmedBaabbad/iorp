from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.interfaces.reference_lists import seed_organization_lists
from app.core.exceptions import EmailAlreadyExistsError, OrganizationCodeTakenError
from app.core.interfaces.organization_queries import (
    LogoStorageInterface,
    OrganizationAdminData,
    OrganizationData,
    OrganizationDetail,
    OrganizationRoleSummary,
    OrganizationRootSummary,
    OrganizationSummary,
    ProvisionedOrganization,
    ProvisionedUser,
)
from app.foundation.domain.permission_catalog import ALL_TENANT_PERMISSIONS
from app.core.security import has_usable_password, hash_password, normalize_email, unusable_password_hash
from app.core.utils import utc_now
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.domain.system_roles import SYSTEM_ROLES, permission_matches, scope_for
from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)

from app.core import files
from app.core.storage import InvalidLogoError


def _prepared_logo(encoded: str):
    """A logo sent as base64 (setup, platform): the same policy as an uploaded one (core/files.py)."""
    import base64
    import binascii
    try:
        content = base64.b64decode(encoded.split(",", 1)[-1], validate=True)
        return files.prepare(content, "logo")
    except (binascii.Error, ValueError) as exc:
        raise InvalidLogoError(getattr(exc, "code", "INVALID_IMAGE")) from exc


class FoundationOrganizationQueries:
    """Foundation-owned implementation of the cross-module organization contract."""

    def __init__(self, db: Session, storage: LogoStorageInterface) -> None:
        self.db = db
        self.storage = storage

    def create_organization(
        self,
        organization: OrganizationData,
        administrator: OrganizationAdminData,
    ) -> tuple[ProvisionedOrganization, ProvisionedUser]:
        if self.db.scalar(select(Organization).where(Organization.code == organization.code)):
            raise OrganizationCodeTakenError
        normalized_email = normalize_email(administrator.email)
        if self.db.scalar(select(User.id).where(User.email == normalized_email).limit(1)):
            raise EmailAlreadyExistsError
        logo = _prepared_logo(organization.logo_base64) if organization.logo_base64 else None

        model = Organization(
            name=organization.name,
            code=organization.code,
            industry_type=organization.industry_type,
            timezone=organization.timezone,
            default_locale=organization.default_locale,
            status=OrganizationStatus.ACTIVE,
        )
        self.db.add(model)
        self.db.flush()
        stored_logo: str | None = None
        try:
            if logo is not None:
                stored_logo = files.new_key(model.id, "organization", logo.extension)
                self.storage.put(stored_logo, logo.content)
                model.logo_path = stored_logo
            permissions = self._get_or_create_permissions(model.id)
            roles = self._seed_roles(model, permissions)
            admin = User(
                organization_id=model.id,
                full_name=administrator.full_name,
                email=normalized_email,
                phone=administrator.phone,
                password_hash=hash_password(administrator.password) if administrator.password else unusable_password_hash(),
                status=UserStatus.ACTIVE,
                is_organization_root=True,
            )
            self.db.add(admin)
            self.db.flush()
            self.db.add(UserRole(user_id=admin.id, role_id=roles["organization_admin"].id))
            seed_organization_lists(self.db, model.id)  # MD-003: the usual reference values, editable afterwards
        except Exception:
            if stored_logo:
                self.storage.delete(stored_logo)
            raise
        return (
            ProvisionedOrganization(
                id=model.id,
                name=model.name,
                code=model.code,
                logo_path=stored_logo,
                role_codes=tuple(roles),
            ),
            ProvisionedUser(id=admin.id, email=admin.email),
        )

    def cleanup_logo(self, relative_path: str) -> None:
        self.storage.delete(relative_path)

    def list_organizations(self) -> list[OrganizationSummary]:
        organizations = self.db.scalars(select(Organization).order_by(Organization.created_at)).all()
        return [self._summarize(item) for item in organizations]

    def get_organization(self, organization_id: UUID) -> OrganizationSummary | None:
        organization = self.db.get(Organization, organization_id)
        return self._summarize(organization) if organization else None

    def get_organization_detail(self, organization_id: UUID) -> OrganizationDetail | None:
        organization = self.db.get(Organization, organization_id)
        if organization is None:
            return None
        root = self.db.scalar(
            select(User).where(
                User.organization_id == organization_id,
                User.is_organization_root.is_(True),
            ).order_by(User.created_at).limit(1)
        )
        roles = self.db.execute(
            select(Role, func.count(UserRole.id))
            .outerjoin(UserRole, UserRole.role_id == Role.id)
            .where(Role.organization_id == organization_id)
            .group_by(Role.id)
            .order_by(Role.created_at)
        ).all()
        return OrganizationDetail(
            summary=self._summarize(organization),
            root_user=(
                OrganizationRootSummary(
                    id=root.id, full_name=root.full_name, email=root.email,
                    status=root.status.value, last_login_at=root.last_login_at,
                    activation_pending=not has_usable_password(root.password_hash),
                ) if root else None
            ),
            roles=[OrganizationRoleSummary(id=role.id, code=role.code, user_count=count) for role, count in roles],
        )

    def get_logo_path(self, organization_id: UUID) -> str | None:
        organization = self.db.get(Organization, organization_id)
        return organization.logo_path if organization else None

    def storage(self, organization_id: UUID) -> dict | None:
        """What the organization's files occupy against its quota (core/files.py)."""
        if self.db.get(Organization, organization_id) is None:
            return None
        used, quota = files.usage(self.db, organization_id), files.quota(self.db, organization_id)
        return dict(used_bytes=used, quota_bytes=quota, percent=round(used * 100 / quota, 1) if quota else 0.0,
                    custom=self.db.get(Organization, organization_id).storage_quota_bytes is not None)

    def set_storage_quota(self, organization_id: UUID, quota_bytes: int | None) -> dict | None:
        organization = self.db.get(Organization, organization_id)
        if organization is None:
            return None
        organization.storage_quota_bytes = quota_bytes
        self.db.commit()
        return self.storage(organization_id)

    def set_organization_status(
        self, organization_id: UUID, status: str, changed_by: UUID, reason: str | None
    ) -> OrganizationSummary | None:
        organization = self.db.get(Organization, organization_id)
        if organization is None:
            return None
        organization.status = OrganizationStatus(status)
        organization.status_changed_at = utc_now()
        organization.status_changed_by = changed_by
        organization.status_change_reason = reason
        self.db.flush()
        return self._summarize(organization)

    def _get_or_create_permissions(self, organization_id: UUID | None = None) -> list[Permission]:
        if organization_id is None:
            organization_id = self.db.scalar(select(Organization.id).order_by(Organization.created_at.desc()))
        existing = {
            item.code: item for item in self.db.scalars(
                select(Permission).where(Permission.organization_id == organization_id)
            )
        }
        permissions: list[Permission] = []
        for definition in ALL_TENANT_PERMISSIONS:
            permission = existing.get(definition.code)
            if permission is None:
                permission = Permission(
                    organization_id=organization_id,
                    code=definition.code,
                    name=definition.name_en,
                    description=definition.description_en,
                    module_name=definition.module,
                    resource_name=definition.resource,
                    action_name=definition.action,
                )
                self.db.add(permission)
            else:
                permission.name = definition.name_en
                permission.description = definition.description_en
                permission.module_name = definition.module
                permission.resource_name = definition.resource
                permission.action_name = definition.action
            permissions.append(permission)
        self.db.flush()
        return permissions

    def _seed_roles(
        self, organization: Organization, permissions: list[Permission]
    ) -> dict[str, Role]:
        roles: dict[str, Role] = {}
        for definition in SYSTEM_ROLES:
            code = str(definition["code"])
            role = self.db.scalar(select(Role).where(Role.organization_id == organization.id, Role.code == code))
            if role is None:
                locale = organization.default_locale
                role = Role(
                    organization_id=organization.id,
                    code=code,
                    name=str(definition[f"name_{locale}"]),
                    description=str(definition[f"description_{locale}"]),
                    is_system=True,
                    is_protected=bool(definition.get("is_protected", False)),
                    is_editable=False,
                )
                self.db.add(role)
            roles[code] = role
        self.db.flush()
        existing_pairs = set(self.db.execute(select(RolePermission.role_id, RolePermission.permission_id)).all())
        for definition in SYSTEM_ROLES:
            code = str(definition["code"])
            role = roles[code]
            patterns = tuple(definition["permissions"])
            for permission in permissions:
                if any(permission_matches(permission.code, pattern) for pattern in patterns) and (role.id, permission.id) not in existing_pairs:
                    self.db.add(RolePermission(
                        role_id=role.id, permission_id=permission.id,
                        scope=scope_for(code, permission.code),
                    ))
        return roles

    def _summarize(self, organization: Organization) -> OrganizationSummary:
        user_count = self.db.scalar(
            select(func.count(User.id)).where(User.organization_id == organization.id)
        ) or 0
        admin_email = self.db.scalar(
            select(User.email)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(User.organization_id == organization.id, Role.code == "organization_admin")
            .order_by(User.created_at)
            .limit(1)
        )
        return OrganizationSummary(
            id=organization.id,
            name=organization.name,
            code=organization.code,
            status=organization.status.value,
            status_changed_at=organization.status_changed_at,
            status_changed_by=organization.status_changed_by,
            status_change_reason=organization.status_change_reason,
            industry_type=organization.industry_type,
            timezone=organization.timezone,
            default_locale=organization.default_locale,
            user_count=user_count,
            admin_email=admin_email,
            root_user_email=admin_email,
            has_logo=bool(organization.logo_path),
            created_at=organization.created_at,
            updated_at=organization.updated_at,
        )
