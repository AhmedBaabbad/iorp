from uuid import UUID

from app.core.config import settings
from app.core.security import hash_password
from app.foundation.api.schemas import UserUpdateRequest
from app.foundation.application.services import FoundationService, OrganizationRootProtectionError
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Organization, Permission, User


def _bootstrap_payload() -> dict:
    return {
        "bootstrap_token": "root-test-token",
        "platform_root": {
            "full_name": "Platform Root",
            "email": "platform-root@example.com",
            "password": "PlatformRoot123!",
            "password_confirmation": "PlatformRoot123!",
        },
        "organization": {
            "name": "Root Organization",
            "code": "root-org",
            "timezone": "Asia/Riyadh",
            "default_locale": "ar",
        },
        "organization_admin": {
            "full_name": "Organization Root",
            "email": "org-root@example.com",
            "phone": "+966500000000",
            "password": "OrganizationRoot123!",
            "password_confirmation": "OrganizationRoot123!",
        },
    }


def _initialize(client, monkeypatch) -> tuple[dict[str, str], dict[str, str]]:
    monkeypatch.setattr(settings, "bootstrap_token", "root-test-token")
    assert client.post("/api/v1/system/bootstrap/initialize", json=_bootstrap_payload()).status_code == 201
    tenant_login = client.post(
        "/api/v1/auth/login",
        json={"email": "org-root@example.com", "password": "OrganizationRoot123!"},
    )
    platform_login = client.post(
        "/api/v1/platform/login",
        json={"email": "platform-root@example.com", "password": "PlatformRoot123!"},
    )
    return (
        {"Authorization": f"Bearer {tenant_login.json()['access_token']}"},
        {"Authorization": f"Bearer {platform_login.json()['access_token']}"},
    )


def _root(db) -> User:
    return db.query(User).filter(User.is_organization_root.is_(True)).one()


def _normal_user(client, headers, email="normal@example.com") -> dict:
    response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={"full_name": "Normal User", "email": email, "password": "NormalUser123!"},
    )
    assert response.status_code == 201
    return response.json()


def test_t01_root_cannot_be_soft_deleted(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    response = client.delete(f"/api/v1/admin/users/{_root(db).id}", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "CANNOT_DEACTIVATE_ORGANIZATION_ROOT"


def test_t02_root_cannot_be_hard_deleted(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    response = client.delete(f"/api/v1/admin/users/{_root(db).id}/hard", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "CANNOT_DEACTIVATE_ORGANIZATION_ROOT"


def test_t03_root_name_is_immutable(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    response = client.patch(f"/api/v1/admin/users/{_root(db).id}", headers=headers, json={"full_name": "Changed"})
    assert response.status_code == 403
    assert response.json()["code"] == "CANNOT_MODIFY_ROOT_IDENTITY"


def test_t04_root_email_is_immutable(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    response = client.patch(f"/api/v1/admin/users/{_root(db).id}", headers=headers, json={"email": "changed@example.com"})
    assert response.status_code == 403


def test_t05_root_can_change_own_password(client, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": "OrganizationRoot123!",
            "new_password": "NewOrganizationRoot123!",
            "new_password_confirmation": "NewOrganizationRoot123!",
        },
    )
    assert response.status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "org-root@example.com", "password": "NewOrganizationRoot123!"}).status_code == 200


def test_t06_root_phone_can_change(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    response = client.patch(f"/api/v1/admin/users/{_root(db).id}", headers=headers, json={"phone": "+966511111111"})
    assert response.status_code == 200
    assert response.json()["phone"] == "+966511111111"


def test_t07_last_root_flag_cannot_be_removed(client, db, monkeypatch):
    _initialize(client, monkeypatch)
    root = _root(db)
    try:
        FoundationService(db).set_organization_root_status(root.organization_id, root.id, False)
        raise AssertionError("last root flag was removed")
    except OrganizationRootProtectionError as exc:
        assert exc.status_code == 409 and exc.code == "LAST_ORGANIZATION_ROOT"


def test_t08_root_flag_can_move_when_another_root_exists(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    root = _root(db)
    other_data = _normal_user(client, headers)
    service = FoundationService(db)
    service.set_organization_root_status(root.organization_id, UUID(other_data["id"]), True)
    updated = service.set_organization_root_status(root.organization_id, root.id, False)
    assert updated.is_organization_root is False


def test_t09_legacy_hard_route_deactivates_without_deleting(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    user = _normal_user(client, headers)
    response = client.delete(f"/api/v1/admin/users/{user['id']}/hard", headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "inactive"
    assert db.get(User, UUID(user["id"])) is not None


def test_t10_normal_user_can_be_deactivated(client, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    user = _normal_user(client, headers)
    response = client.delete(f"/api/v1/admin/users/{user['id']}", headers=headers)
    assert response.status_code == 200 and response.json()["status"] == "inactive"


def test_t11_bootstrap_creates_organization_root(client, db, monkeypatch):
    _initialize(client, monkeypatch)
    assert _root(db).email == "org-root@example.com"


def test_t12_provisioning_creates_root(client, db, monkeypatch):
    _, platform_headers = _initialize(client, monkeypatch)
    response = client.post(
        "/api/v1/platform/organizations",
        headers=platform_headers,
        json={
            "organization": {"name": "Second", "code": "second", "timezone": "UTC", "default_locale": "en"},
            "organization_admin": {"full_name": "Second Root", "email": "second-root@example.com", "password": "SecondRoot123!", "password_confirmation": "SecondRoot123!"},
        },
    )
    assert response.status_code == 201
    assert db.query(User).filter(User.email == "second-root@example.com").one().is_organization_root


def test_t13_provisioned_organizations_have_a_root(client, db, monkeypatch):
    _initialize(client, monkeypatch)
    for organization in db.query(Organization).all():
        assert db.query(User).filter(User.organization_id == organization.id, User.is_organization_root.is_(True)).count() >= 1


def test_t14_create_body_cannot_set_root_flag(client, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    body = {"full_name": "Injected", "email": "injected@example.com", "password": "Injected123!", "is_organization_root": True}
    response = client.post("/api/v1/admin/users", headers=headers, json=body)
    assert response.status_code == 201 and response.json()["is_organization_root"] is False


def test_t15_update_body_cannot_set_root_flag(client, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    user = _normal_user(client, headers)
    response = client.patch(f"/api/v1/admin/users/{user['id']}", headers=headers, json={"phone": "123", "is_organization_root": True})
    assert response.status_code == 200 and response.json()["is_organization_root"] is False


def test_t16_root_has_all_tenant_permissions_without_roles(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    root = _root(db)
    db.query(root.user_roles[0].__class__).filter_by(user_id=root.id).delete()
    db.commit()
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 200


def test_t17_root_does_not_receive_platform_permissions(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    root = _root(db)
    db.add(Permission(organization_id=root.organization_id, code="platform:test:read", name="Platform", description="Platform test", module_name="platform", resource_name="test", action_name="read"))
    db.commit()
    assert "platform:test:read" not in client.get("/api/v1/auth/me", headers=headers).json()["permissions"]


def test_t18_root_can_access_tenant_permission_guarded_endpoint(client, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    assert client.get("/api/v1/admin/permissions", headers=headers).status_code == 200


def test_t19_root_cannot_access_platform_endpoint(client, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    assert client.get("/api/v1/platform/organizations", headers=headers).status_code == 401


def test_t20_list_response_includes_root_flag(client, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    assert client.get("/api/v1/admin/users", headers=headers).json()[0]["is_organization_root"] is True


def test_t21_detail_response_includes_root_flag(client, db, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    assert client.get(f"/api/v1/admin/users/{_root(db).id}", headers=headers).json()["is_organization_root"] is True


def test_t22_root_is_identifiable_in_user_list(client, monkeypatch):
    headers, _ = _initialize(client, monkeypatch)
    roots = [item for item in client.get("/api/v1/admin/users", headers=headers).json() if item["is_organization_root"]]
    assert len(roots) == 1 and roots[0]["email"] == "org-root@example.com"


def test_t23_org_a_root_cannot_read_org_b_user(client, db, monkeypatch):
    headers, platform_headers = _initialize(client, monkeypatch)
    payload = {"organization": {"name": "B", "code": "org-b", "timezone": "UTC", "default_locale": "en"}, "organization_admin": {"full_name": "B Root", "email": "b-root@example.com", "password": "BRootPassword123!", "password_confirmation": "BRootPassword123!"}}
    client.post("/api/v1/platform/organizations", headers=platform_headers, json=payload)
    other = db.query(User).filter(User.email == "b-root@example.com").one()
    assert client.get(f"/api/v1/admin/users/{other.id}", headers=headers).status_code == 404


def test_t24_org_a_root_cannot_modify_org_b_user(client, db, monkeypatch):
    headers, platform_headers = _initialize(client, monkeypatch)
    payload = {"organization": {"name": "B", "code": "org-b", "timezone": "UTC", "default_locale": "en"}, "organization_admin": {"full_name": "B Root", "email": "b-root@example.com", "password": "BRootPassword123!", "password_confirmation": "BRootPassword123!"}}
    client.post("/api/v1/platform/organizations", headers=platform_headers, json=payload)
    other = db.query(User).filter(User.email == "b-root@example.com").one()
    assert client.patch(f"/api/v1/admin/users/{other.id}", headers=headers, json={"phone": "x"}).status_code == 404


def test_t25_each_organization_has_independent_root(client, db, monkeypatch):
    _, platform_headers = _initialize(client, monkeypatch)
    payload = {"organization": {"name": "B", "code": "org-b", "timezone": "UTC", "default_locale": "en"}, "organization_admin": {"full_name": "B Root", "email": "b-root@example.com", "password": "BRootPassword123!", "password_confirmation": "BRootPassword123!"}}
    client.post("/api/v1/platform/organizations", headers=platform_headers, json=payload)
    roots = db.query(User).filter(User.is_organization_root.is_(True)).all()
    assert len(roots) == 2 and len({root.organization_id for root in roots}) == 2
