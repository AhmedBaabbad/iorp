from collections.abc import Generator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser
from app.core.config import settings
from app.core.db import get_db_session
from app.core.security import decode_access_token
from app.core.tenancy import TenantContext
from app.foundation.api.schemas import CurrentUserResponse
from app.foundation.application.services import FoundationService
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Organization, User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


@dataclass(frozen=True)
class CurrentUserContext:
    user: User
    profile: CurrentUserResponse
    auth_user: AuthenticatedUser
    tenant: TenantContext


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> CurrentUserContext:
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    try:
        user_id = UUID(str(payload["sub"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc

    service = FoundationService(db)
    user = service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not active.",
        )

    try:
        profile = service.build_current_user_response(user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user context.",
        ) from exc

    roles = tuple(profile.roles)
    return CurrentUserContext(
        user=user,
        profile=profile,
        auth_user=AuthenticatedUser(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            roles=roles,
        ),
        tenant=TenantContext(
            user_id=user.id,
            organization_id=user.organization_id,
            roles=roles,
        ),
    )


def get_current_organization_id(
    current: CurrentUserContext = Depends(get_current_user),
) -> UUID:
    return current.user.organization_id


def get_current_tenant(
    current: CurrentUserContext = Depends(get_current_user),
) -> TenantContext:
    return current.tenant


def get_current_authenticated_user(
    current: CurrentUserContext = Depends(get_current_user),
) -> AuthenticatedUser:
    return current.auth_user


def get_current_organization(
    current: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    service = FoundationService(db)
    organization = service.get_organization(current.user.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current organization not found.",
        )
    return organization
