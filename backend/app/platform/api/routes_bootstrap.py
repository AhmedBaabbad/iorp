from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.interfaces.organization_queries import OrganizationProvisioningInterface
from app.core.rate_limit import check_rate_limit
from app.dependencies import get_db, get_organization_queries, get_user_credentials
from app.core.interfaces.user_credentials import UserCredentialInterface
from app.core.exceptions import EmailAlreadyExistsError
from app.core.audit import AuditActor, PlatformAuditService, audit_request_context
from app.platform.api.schemas import (
    BootstrapInitializeRequest,
    BootstrapInitializeResponse,
    BootstrapStatusResponse,
)
from app.platform.application.services import (
    AlreadyInitializedError,
    BootstrapService,
    InvalidBootstrapTokenError,
)

router = APIRouter(prefix="/system/bootstrap", tags=["system-bootstrap"])


@router.get("/status", response_model=BootstrapStatusResponse)
def bootstrap_status(
    db: Session = Depends(get_db),
    organizations: OrganizationProvisioningInterface = Depends(get_organization_queries),
    credentials: UserCredentialInterface = Depends(get_user_credentials),
) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(initialized=BootstrapService(db, organizations, credentials).status())


@router.post("/initialize", response_model=BootstrapInitializeResponse, status_code=201)
def initialize(
    payload: BootstrapInitializeRequest,
    request: Request,
    db: Session = Depends(get_db),
    organizations: OrganizationProvisioningInterface = Depends(get_organization_queries),
    credentials: UserCredentialInterface = Depends(get_user_credentials),
):
    check_rate_limit(request, "bootstrap_initialize")
    try:
        root, organization, admin = BootstrapService(db, organizations, credentials).initialize(payload)
    except InvalidBootstrapTokenError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Initialization is not authorized.",
        )
    except AlreadyInitializedError:
        return JSONResponse(
            status_code=409,
            content={
                "code": "SYSTEM_ALREADY_INITIALIZED",
                "message": "System has already been initialized",
            },
        )
    except EmailAlreadyExistsError:
        return JSONResponse(status_code=409, content={"code": "EMAIL_ALREADY_EXISTS", "message": "This email is already registered in the system"})
    PlatformAuditService(db).record(event_type="platform_bootstrap_completed", category="configuration", severity="critical", actor=AuditActor("system"), target_type="platform", metadata={"organization_id": str(organization.id)}, request=audit_request_context(request))
    db.commit()
    return BootstrapInitializeResponse(
        message="System initialized successfully",
        organization={"id": organization.id, "name": organization.name, "code": organization.code},
        platform_root_email=root.email,
        organization_admin_email=admin.email,
    )
