from fastapi import Request, Response

from app.core.config import settings


def request_metadata(request: Request) -> tuple[str | None, str | None]:
    """The device's address (the forwarded one when the request came through a trusted proxy, SEC-001) and browser."""
    from app.core.rate_limit import get_client_ip
    ip = get_client_ip(request) if request.client else None
    return ip, request.headers.get("user-agent")


def set_refresh_cookie(response: Response, token: str, *, account_type: str) -> None:
    max_age = settings.tenant_refresh_token_days * 86400 if account_type == "tenant" else settings.platform_refresh_token_hours * 3600
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path="/api/v1/auth" if account_type == "tenant" else "/api/v1/platform",
    )


def clear_refresh_cookie(response: Response, *, account_type: str) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path="/api/v1/auth" if account_type == "tenant" else "/api/v1/platform",
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )
