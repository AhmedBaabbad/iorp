from app.core.config import settings
from app.foundation.domain.permission_catalog import PERMISSIONS
from app.core.security import has_usable_password, verify_password
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission, User, UserRole
from app.core.interfaces.organization_queries import ProvisionedOrganization, ProvisionedUser
from app.platform.api.schemas import OrganizationAdminInput, OrganizationInput
from app.platform.application.services import PlatformOrganizationService


def _initialize(client, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "org-provision-token")
    assert client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "org-provision-token",
        "platform_root": {"full_name": "Platform Root", "email": "platform-root@example.com", "password": "PlatformRoot123!", "password_confirmation": "PlatformRoot123!"},
        "organization": {"name": "Initial", "code": "initial", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Initial Root", "email": "initial-root@example.com", "password": "InitialRoot123!", "password_confirmation": "InitialRoot123!"},
    }).status_code == 201
    token = client.post("/api/v1/platform/login", json={"email": "platform-root@example.com", "password": "PlatformRoot123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _payload(email="new-root@example.com", code="new-org"):
    return {
        "organization": {"name": "New Organization", "code": code, "industry_type": "manufacturing", "timezone": "Asia/Riyadh", "default_locale": "ar"},
        "organization_admin": {"full_name": "New Root", "email": email, "phone": "+966500000000"},  # SEC-003: no password
    }


def test_provisioning_response_and_complete_root_setup(client, db, monkeypatch, mailbox, activate):
    headers = _initialize(client, monkeypatch)
    response = client.post("/api/v1/platform/organizations", headers=headers, json=_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["organization"]["code"] == "NEW-ORG"
    assert body["organization"]["status"] == "active"
    assert body["root_user"]["is_organization_root"] is True
    assert "password" not in body and "password_hash" not in body
    root = db.query(User).filter_by(email="new-root@example.com").one()
    # SEC-003: nobody chose the root's password; an activation link went to the root, who chooses it
    assert body["invitation_sent"] is True and "new-root@example.com" in mailbox
    assert not has_usable_password(root.password_hash)
    assert client.post("/api/v1/auth/login", json={"email": "new-root@example.com", "password": "NewOrganization123!"}).status_code == 401
    activate("new-root@example.com", "NewOrganization123!")
    db.refresh(root)
    assert verify_password("NewOrganization123!", root.password_hash)
    assert client.post("/api/v1/auth/login", json={"email": "new-root@example.com", "password": "NewOrganization123!"}).status_code == 200
    role = db.query(Role).filter_by(organization_id=root.organization_id, code="organization_admin").one()
    assert db.query(UserRole).filter_by(user_id=root.id, role_id=role.id).count() == 1
    assert db.query(RolePermission).filter_by(role_id=role.id).count() == len(PERMISSIONS)


def test_provisioning_permissions_are_idempotent(client, db, monkeypatch):
    headers = _initialize(client, monkeypatch)
    initial_count = db.query(Permission).count()
    assert client.post("/api/v1/platform/organizations", headers=headers, json=_payload()).status_code == 201
    assert client.post("/api/v1/platform/organizations", headers=headers, json=_payload("another-root@example.com", "another-org")).status_code == 201
    assert db.query(Permission).count() == len(PERMISSIONS) * 3


def test_duplicate_code_and_cross_identity_email_are_rejected(client, db, monkeypatch):
    headers = _initialize(client, monkeypatch)
    assert client.post("/api/v1/platform/organizations", headers=headers, json=_payload()).status_code == 201
    before = (db.query(Organization).count(), db.query(User).count(), db.query(Role).count())
    duplicate_code = client.post("/api/v1/platform/organizations", headers=headers, json=_payload("other@example.com"))
    assert duplicate_code.status_code == 409 and duplicate_code.json()["code"] == "ORG_CODE_EXISTS"
    duplicate_platform = client.post("/api/v1/platform/organizations", headers=headers, json=_payload("platform-root@example.com", "other-org"))
    assert duplicate_platform.status_code == 409 and duplicate_platform.json()["code"] == "EMAIL_ALREADY_EXISTS"
    assert (db.query(Organization).count(), db.query(User).count(), db.query(Role).count()) == before


def test_detail_contains_root_and_roles(client, monkeypatch):
    headers = _initialize(client, monkeypatch)
    created = client.post("/api/v1/platform/organizations", headers=headers, json=_payload()).json()
    response = client.get(f"/api/v1/platform/organizations/{created['organization']['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["root_user"]["email"] == "new-root@example.com"
    assert any(role["code"] == "organization_admin" and role["user_count"] == 1 for role in response.json()["roles"])


def test_the_platform_cannot_choose_the_roots_password(client, db, monkeypatch, mailbox):
    """SEC-003: a password sent with the organization is ignored; the root activates the account through the link."""
    headers = _initialize(client, monkeypatch)
    payload = _payload()
    payload["organization_admin"].update(password="Chosen12345678!", password_confirmation="Chosen12345678!")
    assert client.post("/api/v1/platform/organizations", headers=headers, json=payload).status_code == 201
    assert client.post("/api/v1/auth/login", json={"email": "new-root@example.com", "password": "Chosen12345678!"}).status_code == 401
    assert mailbox["new-root@example.com"]  # the activation link went out


def test_an_activation_password_still_needs_twelve_characters(client, monkeypatch, mailbox):
    headers = _initialize(client, monkeypatch)
    assert client.post("/api/v1/platform/organizations", headers=headers, json=_payload()).status_code == 201
    short = client.post("/api/v1/auth/reset-password", json={"token": mailbox["new-root@example.com"], "new_password": "Short123", "new_password_confirmation": "Short123"})
    assert short.status_code in (400, 422)
