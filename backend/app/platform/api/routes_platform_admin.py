from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import EmailAlreadyExistsError, OrganizationCodeTakenError
from app.core.audit import AuditActor, PlatformAuditService, audit_request_context
from app.core.storage import InvalidLogoError
from app.core.storage import LocalFileStorage
from app.core.interfaces.organization_queries import OrganizationProvisioningInterface
from app.core.interfaces.user_credentials import UserCredentialInterface
from app.dependencies import (
    get_db,
    get_organization_queries,
    get_user_credentials,
    require_platform_permission,
)
from app.platform.domain.permissions import PlatformPermission
from app.platform.api.schemas import (
    CreatePlatformOrganizationRequest,
    CreatePlatformOrganizationResponse,
    PlatformOrganizationSummary,
    PlatformOrganizationDetail,
    OrganizationStatusChangeRequest,
    ResetOrganizationRootPasswordRequest,
    ResetOrganizationRootPasswordResponse,
)
from app.platform.application.services import (
    ArchiveReasonRequiredError,
    OrganizationNotFoundError,
    OrganizationRootNotFoundError,
    PlatformOrganizationService,
)
from app.platform.domain.policies import InvalidStateTransitionError, VALID_TRANSITIONS
from app.platform.infrastructure.models import PlatformAccount

router = APIRouter(prefix="/platform/organizations", tags=["platform-organizations"])


def _service(
    db: Session,
    organizations: OrganizationProvisioningInterface,
    user_credentials: UserCredentialInterface | None = None,
) -> PlatformOrganizationService:
    return PlatformOrganizationService(db, organizations, user_credentials)


def _resolve_account_name(db: Session, account_id: UUID | None) -> str | None:
    if account_id is None:
        return None
    return db.scalar(select(PlatformAccount.full_name).where(PlatformAccount.id == account_id))


def _summary_response(item, db: Session) -> PlatformOrganizationSummary:
    data = asdict(item)
    data["allowed_transitions"] = sorted(VALID_TRANSITIONS.get(item.status, frozenset()))
    data["logo_url"] = f"/api/v1/platform/organizations/{item.id}/logo" if item.has_logo else None
    data["status_changed_by_name"] = _resolve_account_name(db, item.status_changed_by)
    return PlatformOrganizationSummary(**data)


@router.get("", response_model=list[PlatformOrganizationSummary])
def list_organizations(
    account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ORGANIZATIONS_READ)),
    db: Session = Depends(get_db),
    organizations: OrganizationProvisioningInterface = Depends(get_organization_queries),
) -> list[PlatformOrganizationSummary]:
    return [
        _summary_response(item, db)
        for item in _service(db, organizations).list_organizations()
    ]


@router.get("/{organization_id}", response_model=PlatformOrganizationDetail)
def get_organization(
    organization_id: UUID,
    account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ORGANIZATIONS_READ)),
    db: Session = Depends(get_db),
    organizations: OrganizationProvisioningInterface = Depends(get_organization_queries),
) -> PlatformOrganizationDetail:
    try:
        detail = _service(db, organizations).get_organization_detail(organization_id)
        summary = asdict(detail.summary)
        summary["allowed_transitions"] = sorted(VALID_TRANSITIONS.get(detail.summary.status, frozenset()))
        summary["logo_url"] = f"/api/v1/platform/organizations/{detail.summary.id}/logo" if detail.summary.has_logo else None
        summary["status_changed_by_name"] = _resolve_account_name(db, detail.summary.status_changed_by)
        return PlatformOrganizationDetail(
            **summary,
            root_user=asdict(detail.root_user) if detail.root_user else None,
            roles=[asdict(role) for role in detail.roles],
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )


@router.get("/{organization_id}/logo")
def get_organization_logo(
    organization_id: UUID,
    account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ORGANIZATIONS_READ)),
    organizations: OrganizationProvisioningInterface = Depends(get_organization_queries),
):
    relative_path = organizations.get_logo_path(organization_id)
    if not relative_path:
        raise HTTPException(status_code=404, detail="Logo not found.")
    path = LocalFileStorage().resolve(relative_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Logo not found.")
    media = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}.get(path.suffix.lstrip("."))
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=3600"})


@router.post("", response_model=CreatePlatformOrganizationResponse, status_code=201)
def create_organization(
    payload: CreatePlatformOrganizationRequest,
    request: Request,
    account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ORGANIZATIONS_CREATE)),
    db: Session = Depends(get_db),
    organizations: OrganizationProvisioningInterface = Depends(get_organization_queries),
) -> CreatePlatformOrganizationResponse:
    try:
        organization, admin = _service(db, organizations).create_organization(
            payload.organization, payload.organization_admin
        )
    except OrganizationCodeTakenError:
        return JSONResponse(status_code=409, content={"code": "ORG_CODE_EXISTS", "message": "Organization code is already in use."})
    except EmailAlreadyExistsError:
        return JSONResponse(status_code=409, content={"code": "EMAIL_ALREADY_EXISTS", "message": "This email is already registered in the system"})
    except InvalidLogoError:
        return JSONResponse(status_code=400, content={"code": "INVALID_LOGO", "message": "Invalid organization logo."})
    summary = _service(db, organizations).get_organization(organization.id)
    PlatformAuditService(db).record(event_type="organization_created", category="organization", actor=AuditActor("platform", account.id, account.email, account.full_name), target_type="organization", target_id=organization.id, target_display=organization.name, organization_id=organization.id, changes={"status": {"before": None, "after": summary.status}, "code": {"before": None, "after": organization.code}}, request=audit_request_context(request))
    db.commit()
    return CreatePlatformOrganizationResponse(
        message="Organization created successfully.",
        organization={
            "id": organization.id, "name": organization.name, "code": organization.code,
            "status": summary.status, "default_locale": summary.default_locale,
            "timezone": summary.timezone, "has_logo": summary.has_logo,
            "created_at": summary.created_at,
        },
        root_user={
            "id": admin.id, "full_name": payload.organization_admin.full_name,
            "email": admin.email, "is_organization_root": True,
        },
        roles_created=list(organization.role_codes),
        organization_admin_email=admin.email,
    )


def _change_status(db, organizations, organization_id, target, account, reason, request):
    try:
        previous = _service(db, organizations).get_organization(organization_id)
        summary = _service(db, organizations).change_status(organization_id, target, account, reason)
        event = {"active": "organization_activated", "suspended": "organization_suspended", "inactive": "organization_deactivated", "archived": "organization_archived"}[target]
        PlatformAuditService(db).record(event_type=event, category="organization", severity="warning" if target in {"suspended", "archived"} else "info", actor=AuditActor("platform", account.id, account.email, account.full_name), target_type="organization", target_id=organization_id, target_display=summary.name, organization_id=organization_id, reason=reason, changes={"status": {"before": previous.status, "after": target}}, request=audit_request_context(request))
        db.commit()
        return _summary_response(summary, db)
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Organization not found.") from exc
    except InvalidStateTransitionError as exc:
        return JSONResponse(status_code=409, content={
            "code": exc.code, "message": str(exc), "current_status": exc.current,
            "target_status": exc.target, "allowed_transitions": exc.allowed,
        })
    except ArchiveReasonRequiredError as exc:
        return JSONResponse(status_code=400, content={"code": exc.code, "message": str(exc)})


def _status_route(target: str, permission: PlatformPermission):
    def endpoint(
        organization_id: UUID,
        payload: OrganizationStatusChangeRequest,
        request: Request,
        account: PlatformAccount = Depends(require_platform_permission(permission)),
        db: Session = Depends(get_db),
        organizations: OrganizationProvisioningInterface = Depends(get_organization_queries),
    ):
        return _change_status(db, organizations, organization_id, target, account, payload.reason, request)
    return endpoint


router.post("/{organization_id}/suspend", response_model=PlatformOrganizationSummary)(
    _status_route("suspended", PlatformPermission.ORGANIZATIONS_SUSPEND)
)
router.post("/{organization_id}/activate", response_model=PlatformOrganizationSummary)(
    _status_route("active", PlatformPermission.ORGANIZATIONS_ACTIVATE)
)
router.post("/{organization_id}/deactivate", response_model=PlatformOrganizationSummary)(
    _status_route("inactive", PlatformPermission.ORGANIZATIONS_SUSPEND)
)
router.post("/{organization_id}/archive", response_model=PlatformOrganizationSummary)(
    _status_route("archived", PlatformPermission.ORGANIZATIONS_SUSPEND)
)


@router.delete("/{organization_id}")
def reject_organization_delete(
    organization_id: UUID,
    account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ORGANIZATIONS_SUSPEND)),
):
    return JSONResponse(status_code=403, content={
        "code": "ORGANIZATION_CANNOT_BE_DELETED",
        "message": "Organizations cannot be deleted. Use archive instead.",
    })


@router.post(
    "/{organization_id}/reset-root-password",
    response_model=ResetOrganizationRootPasswordResponse,
)
def reset_root_password(
    organization_id: UUID,
    payload: ResetOrganizationRootPasswordRequest,
    request: Request,
    account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ORGANIZATIONS_UPDATE)),
    db: Session = Depends(get_db),
    organizations: OrganizationProvisioningInterface = Depends(get_organization_queries),
    user_credentials: UserCredentialInterface = Depends(get_user_credentials),
) -> ResetOrganizationRootPasswordResponse:
    try:
        email = _service(db, organizations, user_credentials).reset_root_password(
            organization_id,
            payload.new_password,
            payload.new_password_confirmation,
        )
    except (OrganizationNotFoundError, OrganizationRootNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization Root not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    PlatformAuditService(db).record(event_type="organization_root_password_reset", category="organization", severity="warning", actor=AuditActor("platform", account.id, account.email, account.full_name), target_type="organization_root", target_id=organization_id, target_display=email, organization_id=organization_id, changes={"password_changed": True, "sessions_invalidated": True}, request=audit_request_context(request))
    db.commit()
    return ResetOrganizationRootPasswordResponse(
        message="Organization Root password reset successfully",
        organization_id=organization_id,
        root_user_email=email,
        sessions_invalidated=True,
    )
