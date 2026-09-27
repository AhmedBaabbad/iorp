from types import SimpleNamespace

from app.core.permission import (
    has_any_permission,
    has_any_role,
    has_permission,
    has_role,
)


def make_user(
    *,
    roles: frozenset[str] = frozenset(),
    permissions: frozenset[str] = frozenset(),
) -> SimpleNamespace:
    return SimpleNamespace(roles=roles, permissions=permissions)


def test_has_role_returns_true_when_role_present() -> None:
    user = make_user(roles=frozenset({"admin"}))

    assert has_role(user, "admin") is True


def test_has_role_returns_false_when_role_missing() -> None:
    user = make_user(roles=frozenset({"sales_rep"}))

    assert has_role(user, "admin") is False


def test_has_any_role_returns_true_when_one_matches() -> None:
    user = make_user(roles=frozenset({"sales_rep"}))

    assert has_any_role(user, ["admin", "sales_rep"]) is True


def test_has_permission_returns_true_when_present() -> None:
    user = make_user(permissions=frozenset({"commercial:customers:read"}))

    assert has_permission(user, "commercial:customers:read") is True


def test_has_permission_returns_false_when_missing() -> None:
    user = make_user(permissions=frozenset({"commercial:customers:read"}))

    assert has_permission(user, "foundation:users:write") is False


def test_has_any_permission_returns_true_when_one_matches() -> None:
    user = make_user(permissions=frozenset({"commercial:customers:read"}))

    assert has_any_permission(
        user,
        ["foundation:users:write", "commercial:customers:read"],
    ) is True
