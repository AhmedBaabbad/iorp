from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.storage import LocalFileStorage
from app.foundation.api.schemas import OrganizationProfileResponse, OrganizationProfileUpdate
from app.foundation.infrastructure.models import Organization
from app.foundation.infrastructure.models import User
from app.foundation.application.audit import ORG_LOGO_REMOVED, ORG_LOGO_UPLOADED, ORG_PROFILE_UPDATED, log_tenant_audit


class InvalidTimezoneError(ValueError):
    pass


class OrganizationProfileService:
    def __init__(self, db: Session, storage: LocalFileStorage | None = None) -> None:
        self.db = db
        self.storage = storage or LocalFileStorage()

    def get(self, organization_id: UUID) -> Organization:
        organization = self.db.get(Organization, organization_id)
        if organization is None:
            raise LookupError("Organization not found")
        return organization

    def response(self, organization: Organization) -> OrganizationProfileResponse:
        return OrganizationProfileResponse(
            id=organization.id, name=organization.name, code=organization.code,
            status=organization.status, industry_type=organization.industry_type,
            timezone=organization.timezone, default_locale=organization.default_locale,
            has_logo=bool(organization.logo_path),
            logo_url="/api/v1/organization/logo" if organization.logo_path else None,
            created_at=organization.created_at, updated_at=organization.updated_at,
            max_sessions_per_user=organization.max_sessions_per_user or 2,
        )

    def update(self, organization_id: UUID, data: OrganizationProfileUpdate, actor: User | None = None) -> Organization:
        organization = self.get(organization_id)
        values = data.model_dump(exclude_unset=True)
        before = {field: getattr(organization, field) for field in values}
        timezone = values.get("timezone")
        if timezone:
            try:
                ZoneInfo(timezone)
            except ZoneInfoNotFoundError as exc:
                raise InvalidTimezoneError("Invalid timezone") from exc
        for field, value in values.items():
            setattr(organization, field, value)
        changes = {field: {"before": before[field], "after": getattr(organization, field)} for field in values if before[field] != getattr(organization, field)}
        if changes:
            log_tenant_audit(self.db, organization_id, ORG_PROFILE_UPDATED, "organization", organization_id, actor.id if actor else None, actor.full_name if actor else None, actor.email if actor else None, organization.name, changes)
        self.db.commit(); self.db.refresh(organization)
        return organization

    def replace_logo(self, organization_id: UUID, content: bytes, actor: User | None = None) -> Organization:
        from app.foundation.application.branding_service import BrandingService
        BrandingService(self.db, self.storage).upload(organization_id, content, actor.id if actor else None)
        return self.get(organization_id)

    def remove_logo(self, organization_id: UUID, actor: User | None = None) -> bool:
        from app.foundation.application.branding_service import BrandingService
        existed = bool(self.get(organization_id).logo_path)
        BrandingService(self.db, self.storage).remove(organization_id, actor.id if actor else None)
        return existed

