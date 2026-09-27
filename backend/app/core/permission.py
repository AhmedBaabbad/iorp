from app.core.auth import AuthenticatedUser


def has_role(user: AuthenticatedUser, role_code: str) -> bool:
    return role_code in user.roles


def has_any_role(user: AuthenticatedUser, role_codes: list[str]) -> bool:
    return any(role_code in user.roles for role_code in role_codes)


def has_permission(user: AuthenticatedUser, permission_code: str) -> bool:
    return permission_code in user.permissions


def has_any_permission(user: AuthenticatedUser, permission_codes: list[str]) -> bool:
    return any(permission_code in user.permissions for permission_code in permission_codes)
