"""Contract tests for the authorization policy architecture.

get_authorization_policy() was unwired (returning DefaultOrganizationPolicy)
in v0.1 (ORG-RBAC-004-PREP) and is now wired to ScopedAuthorizationPolicy as
of v0.2 (ORG-RBAC-004). DefaultOrganizationPolicy itself is unchanged and
still exercised directly below -- only test_t09 pins the composition root.
"""

from pathlib import Path
from uuid import uuid4

from sqlalchemy import event, select

from app.commercial.domain.enums import FollowUpPriority, FollowUpStatus
from app.commercial.infrastructure.models import Customer, FollowUp
from app.core.authorization.default_policy import DefaultOrganizationPolicy
from app.core.authorization.scoped_policy import ScopedAuthorizationPolicy
from app.core.interfaces.authorization_policy import (
    AccessScope,
    AuthorizationContext,
    AuthorizationPolicy,
)
from app.dependencies import get_authorization_policy
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import User
from app.foundation.infrastructure.models import Permission, Role, RolePermission, UserRole
from app.core.security import hash_password
from app.core.utils import utc_now


def _context(**overrides) -> AuthorizationContext:
    values = {
        "user_id": uuid4(),
        "organization_id": uuid4(),
        "is_organization_root": False,
        "permission_code": "commercial:customers:read",
    }
    values.update(overrides)
    return AuthorizationContext(**values)


def _grant_permissions(db, organization_id, user_id, *codes: str) -> None:
    role = Role(
        organization_id=organization_id,
        name="Authorization Architecture Test",
        code=f"authorization_architecture_{uuid4().hex[:8]}",
    )
    db.add(role)
    db.flush()
    for code in codes:
        module, resource, action = code.split(":")
        permission = Permission(
            organization_id=organization_id,
            code=code,
            name=code,
            description=code,
            module_name=module,
            resource_name=resource,
            action_name=action,
        )
        db.add(permission)
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.add(UserRole(user_id=user_id, role_id=role.id))
    db.commit()


def _login(client, email: str = "test@example.com") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Test1234!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_t01_authorization_policy_protocol_is_importable():
    assert AuthorizationPolicy is not None


def test_t02_authorization_context_can_be_instantiated():
    context = _context()
    assert context.effective_scope == AccessScope.ORGANIZATION


def test_t03_access_scope_has_expected_values():
    assert {scope.value for scope in AccessScope} == {"own", "team", "organization"}


def test_t04_default_policy_structurally_implements_protocol():
    assert isinstance(DefaultOrganizationPolicy(), AuthorizationPolicy)


def test_t05_can_access_is_always_true():
    policy = DefaultOrganizationPolicy()
    assert policy.can_access(_context(effective_scope=AccessScope.OWN)) is True


def test_t06_apply_query_filter_returns_same_object():
    policy = DefaultOrganizationPolicy()
    query = object()
    assert policy.apply_query_filter(_context(), query, "sales_owner_user_id") is query


def test_t07_can_access_record_is_always_true_without_owner():
    assert DefaultOrganizationPolicy().can_access_record(_context()) is True


def test_t08_other_record_owner_is_still_accessible():
    context = _context(effective_scope=AccessScope.OWN)
    assert DefaultOrganizationPolicy().can_access_record(context, uuid4()) is True


def test_t09_provider_returns_scoped_policy():
    """As of ORG-RBAC-004, the composition root is wired to the real scoped
    policy rather than the pass-through default (see module docstring)."""
    assert isinstance(get_authorization_policy(), ScopedAuthorizationPolicy)


def test_t10_provided_policy_supports_the_complete_contract():
    policy = get_authorization_policy()
    context = _context()
    query = object()
    assert policy.can_access(context) is True
    assert policy.apply_query_filter(context, query) is query
    assert policy.can_access_record(context, uuid4()) is True


def test_t11_customer_endpoint_returns_all_organization_records(
    client, db, test_org, test_user
):
    owner_a, owner_b = uuid4(), uuid4()
    db.add_all(
        [
            Customer(organization_id=test_org.id, customer_code="CUST-A", name="A", sales_owner_user_id=owner_a),
            Customer(organization_id=test_org.id, customer_code="CUST-B", name="B", sales_owner_user_id=owner_b),
        ]
    )
    db.commit()
    _grant_permissions(db, test_org.id, test_user.id, "commercial:customers:read")
    response = client.get("/api/v1/commercial/customers", headers=_login(client))
    assert response.status_code == 200
    assert {item["customer_code"] for item in response.json()} == {"CUST-A", "CUST-B"}


def test_t12_follow_up_endpoint_returns_all_organization_records(
    client, db, test_org, test_user
):
    customer = Customer(organization_id=test_org.id, customer_code="CUST-F", name="Follow-ups")
    db.add(customer)
    db.flush()
    db.add_all(
        [
            FollowUp(customer_id=customer.id, assigned_user_id=uuid4(), due_date=utc_now(), priority=FollowUpPriority.MEDIUM, status=FollowUpStatus.PENDING, reason="A"),
            FollowUp(customer_id=customer.id, assigned_user_id=uuid4(), due_date=utc_now(), priority=FollowUpPriority.MEDIUM, status=FollowUpStatus.PENDING, reason="B"),
        ]
    )
    db.commit()
    _grant_permissions(db, test_org.id, test_user.id, "commercial:follow_ups:read")
    response = client.get(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        headers=_login(client),
    )
    assert response.status_code == 200
    assert {item["reason"] for item in response.json()} == {"A", "B"}


def test_t13_user_endpoint_returns_all_organization_users(client, db, test_org, test_user):
    other = User(
        organization_id=test_org.id,
        full_name="Other User",
        email="other-authorization@example.com",
        password_hash=hash_password("Test1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(other)
    db.commit()
    _grant_permissions(db, test_org.id, test_user.id, "foundation:users:read")
    response = client.get("/api/v1/admin/users", headers=_login(client))
    assert response.status_code == 200
    assert {item["email"] for item in response.json()} == {
        "test@example.com",
        "other-authorization@example.com",
    }


def test_t14_organization_root_still_has_full_endpoint_access(client, db, test_org, test_user):
    db.add(Customer(organization_id=test_org.id, customer_code="CUST-ROOT", name="Root Visible"))
    test_user.is_organization_root = True
    db.commit()
    response = client.get("/api/v1/commercial/customers", headers=_login(client))
    assert response.status_code == 200
    assert [item["customer_code"] for item in response.json()] == ["CUST-ROOT"]


def test_t15_non_root_with_read_permission_still_sees_all_endpoint_records(
    client, db, test_org, test_user
):
    db.add_all(
        [
            Customer(organization_id=test_org.id, customer_code="CUST-ONE", name="One", sales_owner_user_id=test_user.id),
            Customer(organization_id=test_org.id, customer_code="CUST-OTHER", name="Other", sales_owner_user_id=uuid4()),
        ]
    )
    _grant_permissions(db, test_org.id, test_user.id, "commercial:customers:read")
    response = client.get("/api/v1/commercial/customers", headers=_login(client))
    assert response.status_code == 200
    assert {item["customer_code"] for item in response.json()} == {"CUST-ONE", "CUST-OTHER"}


def test_t16_example_policy_is_not_imported_by_production_code():
    app_root = Path(__file__).parents[1] / "app"
    example_root = app_root / "core" / "authorization" / "examples"
    offenders = []
    for path in app_root.rglob("*.py"):
        if example_root in path.parents:
            continue
        source = path.read_text(encoding="utf-8")
        if "own_records_policy" in source or "OwnRecordsPolicy" in source:
            offenders.append(path)
    assert offenders == []


def test_t17_default_policy_executes_zero_database_queries(db):
    query_count = 0

    def count_query(*_args, **_kwargs):
        nonlocal query_count
        query_count += 1

    event.listen(db.bind, "before_cursor_execute", count_query)
    try:
        policy = DefaultOrganizationPolicy()
        context = _context()
        statement = select(User)
        assert policy.can_access(context) is True
        assert policy.apply_query_filter(context, statement) is statement
        assert policy.can_access_record(context, uuid4()) is True
        assert query_count == 0
    finally:
        event.remove(db.bind, "before_cursor_execute", count_query)


def test_t18_interface_resides_at_the_core_boundary():
    interface_path = Path(__file__).parents[1] / "app" / "core" / "interfaces" / "authorization_policy.py"
    assert interface_path.is_file()
