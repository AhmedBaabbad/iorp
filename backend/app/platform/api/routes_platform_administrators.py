from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.interfaces.user_credentials import UserCredentialInterface
from app.core.audit import AuditActor, PlatformAuditService, audit_request_context
from app.core.security import has_usable_password
from app.dependencies import get_db, get_user_credentials, require_platform_permission
from app.platform.api.schemas import (
    PlatformAccountCreate,
    PlatformAccountListItem,
    PlatformAccountResponse,
    PlatformAccountUpdate,
    PlatformPasswordResetRequest,
)
from app.platform.application.services import (
    PasswordResetLinkNotSentError,
    BootstrapRootProtectedError,
    LastPlatformRootError,
    PlatformAccountNotFoundError,
    PlatformAccountService,
    PlatformEmailTakenError,
)
from app.platform.domain.permissions import PlatformPermission
from app.platform.infrastructure.models import PlatformAccount

router = APIRouter(prefix="/platform/administrators", tags=["platform-administrators"])


def _service(db: Session, credentials: UserCredentialInterface) -> PlatformAccountService:
    return PlatformAccountService(db, credentials)


def _response(service: PlatformAccountService, account: PlatformAccount) -> PlatformAccountResponse:
    return PlatformAccountResponse(
        id=account.id, full_name=account.full_name, email=account.email,
        role=account.role, status=account.status, is_root=account.is_root,
        is_bootstrap_root=service.is_bootstrap_root(account.id), last_login_at=account.last_login_at,
        password_changed_at=account.password_changed_at, created_at=account.created_at,
        updated_at=account.updated_at, activation_pending=not has_usable_password(account.password_hash),
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, PlatformAccountNotFoundError):
        return HTTPException(status_code=404, detail={"code": "PLATFORM_ACCOUNT_NOT_FOUND"})
    if isinstance(exc, PlatformEmailTakenError):
        return HTTPException(status_code=409, detail={"code": "PLATFORM_EMAIL_TAKEN"})
    if isinstance(exc, LastPlatformRootError):
        return HTTPException(status_code=409, detail={"code": "LAST_PLATFORM_ROOT", "message": "Cannot modify the last active Platform Root"})
    if isinstance(exc, BootstrapRootProtectedError):
        return HTTPException(status_code=409, detail={"code": "BOOTSTRAP_ROOT_PROTECTED", "message": "The original Platform Root account cannot be deleted"})
    if isinstance(exc, PasswordResetLinkNotSentError):
        return HTTPException(status_code=409, detail={"code": "RESET_EMAIL_NOT_SENT", "message": "The reset e-mail could not be sent."})
    if isinstance(exc, ValueError):  # a refused input (e.g. a weak password) — its message is meant for the user
        return HTTPException(status_code=400, detail=str(exc))
    raise exc  # AUDIT-001: an unexpected failure (e.g. the audit store) stays a server error, without its details


@router.get("", response_model=list[PlatformAccountListItem])
def list_administrators(
    viewer: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ADMINISTRATORS_READ)),
    db: Session = Depends(get_db), credentials: UserCredentialInterface = Depends(get_user_credentials),
):
    service = _service(db, credentials)
    return [PlatformAccountListItem(**_response(service, item).model_dump()) for item in service.list_accounts()]


@router.get("/{account_id}", response_model=PlatformAccountResponse)
def get_administrator(
    account_id: UUID,
    viewer: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ADMINISTRATORS_READ)),
    db: Session = Depends(get_db), credentials: UserCredentialInterface = Depends(get_user_credentials),
):
    service = _service(db, credentials)
    try:
        return _response(service, service.get_account(account_id))
    except Exception as exc:
        raise _error(exc) from exc


@router.post("", response_model=PlatformAccountResponse, status_code=status.HTTP_201_CREATED)
def create_administrator(
    payload: PlatformAccountCreate,
    request: Request,
    viewer: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ADMINISTRATORS_CREATE)),
    db: Session = Depends(get_db), credentials: UserCredentialInterface = Depends(get_user_credentials),
):
    service = _service(db, credentials)
    try:
        account = service.create_account(payload.full_name, str(payload.email), payload.role)
        PlatformAuditService(db).record(event_type="platform_account_created", category="identity", actor=AuditActor("platform", viewer.id, viewer.email, viewer.full_name), target_type="platform_account", target_id=account.id, target_display=account.email, changes={"role": {"before": None, "after": account.role.value}, "status": {"before": None, "after": account.status.value}}, request=audit_request_context(request))
        db.commit()  # AUDIT-001: the account and its audit record together
        db.refresh(account)
        sent = service.send_activation_link(account)  # SEC-003: they choose their own password
        return _response(service, account).model_copy(update={"invitation_sent": sent})
    except PlatformEmailTakenError:
        return JSONResponse(status_code=409, content={"code": "EMAIL_ALREADY_EXISTS", "message": "This email is already registered in the system"})
    except Exception as exc:
        raise _error(exc) from exc


@router.patch("/{account_id}", response_model=PlatformAccountResponse)
def update_administrator(
    account_id: UUID, payload: PlatformAccountUpdate, request: Request,
    viewer: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ADMINISTRATORS_UPDATE)),
    db: Session = Depends(get_db), credentials: UserCredentialInterface = Depends(get_user_credentials),
):
    service = _service(db, credentials)
    try:
        before = service.get_account(account_id)
        snapshot = {"full_name": before.full_name, "email": before.email, "role": before.role.value, "status": before.status.value}
        account = service.update_account(account_id, **payload.model_dump(exclude_unset=True))
        after = {"full_name": account.full_name, "email": account.email, "role": account.role.value, "status": account.status.value}
        changes = {key: {"before": snapshot[key], "after": after[key]} for key in snapshot if snapshot[key] != after[key]}
        event = "platform_account_role_changed" if "role" in changes else "platform_account_updated"
        PlatformAuditService(db).record(event_type=event, category="identity", actor=AuditActor("platform", viewer.id, viewer.email, viewer.full_name), target_type="platform_account", target_id=account.id, target_display=account.email, changes=changes, request=audit_request_context(request))
        db.commit()  # AUDIT-001: the change and its audit record together
        db.refresh(account)
        return _response(service, account)
    except PlatformEmailTakenError:
        return JSONResponse(status_code=409, content={"code": "EMAIL_ALREADY_EXISTS", "message": "This email is already registered in the system"})
    except Exception as exc:
        raise _error(exc) from exc


@router.delete("/{account_id}", response_model=PlatformAccountResponse)
def deactivate_administrator(
    account_id: UUID,
    request: Request,
    viewer: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ADMINISTRATORS_DEACTIVATE)),
    db: Session = Depends(get_db), credentials: UserCredentialInterface = Depends(get_user_credentials),
):
    service = _service(db, credentials)
    try:
        account = service.deactivate_account(account_id)
        PlatformAuditService(db).record(event_type="platform_account_deactivated", category="identity", actor=AuditActor("platform", viewer.id, viewer.email, viewer.full_name), target_type="platform_account", target_id=account.id, target_display=account.email, changes={"status": {"before": "active", "after": "inactive"}}, request=audit_request_context(request))
        db.commit()  # AUDIT-001: the change and its audit record together
        db.refresh(account)
        return _response(service, account)
    except Exception as exc:
        raise _error(exc) from exc


@router.post("/{account_id}/reset-password")
def reset_administrator_password(
    account_id: UUID, payload: PlatformPasswordResetRequest,
    request: Request,
    viewer: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ADMINISTRATORS_UPDATE)),
    db: Session = Depends(get_db), credentials: UserCredentialInterface = Depends(get_user_credentials),
):
    service = _service(db, credentials)
    try:
        target = service.reset_password(account_id)
        PlatformAuditService(db).record(event_type="platform_account_password_reset", category="identity", severity="warning", actor=AuditActor("platform", viewer.id, viewer.email, viewer.full_name), target_type="platform_account", target_id=target.id, target_display=target.email, changes={"reset_link_sent": True}, request=audit_request_context(request))
        db.commit()
        return {"message": "A reset link was sent", "email": target.email}
    except Exception as exc:
        raise _error(exc) from exc
