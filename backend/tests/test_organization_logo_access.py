"""PROJECT-FIX-002: every user of an organization sees its logo and name; only an authorised user changes the logo; no
user reaches another organization's logo."""
from app.core.security import hash_password
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Organization, User

from tests.test_organization_profile import PNG, JPEG, _upload, env  # noqa: F401  (fixture)


def member(env, email, organization=None):
    """A user of the organization with no role at all (no permission of any kind)."""
    user = User(organization_id=(organization or env["org"]).id, full_name="Plain Member", email=email,
                password_hash=hash_password("Member12345!"), status=UserStatus.ACTIVE)
    env["db"].add(user); env["db"].commit()
    login = env["client"].post("/api/v1/auth/login", json={"email": email, "password": "Member12345!"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_a_member_without_permissions_sees_the_logo_and_name(env):
    assert _upload(env, PNG).status_code == 200
    headers = member(env, "plain@example.com")
    me = env["client"].get("/api/v1/auth/me", headers=headers).json()
    assert me["organization_name"] == "Profile Org" and me["organization_logo_url"] == "/api/v1/organization/logo"
    logo = env["client"].get("/api/v1/organization/logo", headers=headers)
    assert logo.status_code == 200 and logo.headers["content-type"] == "image/png" and logo.content.startswith(PNG[:8])


def test_a_member_cannot_change_the_logo(env):
    _upload(env, PNG)
    headers = member(env, "plain2@example.com")
    assert _upload(env, JPEG, "logo.jpg", headers).status_code == 403
    assert env["client"].delete("/api/v1/organization/logo", headers=headers).status_code == 403
    assert env["client"].put("/api/v1/organization/branding", headers=headers, json={"phone": "1"}).status_code == 403
    assert env["client"].get("/api/v1/organization/logo", headers=headers).content.startswith(PNG[:8])  # still the PNG logo


def test_the_administrator_reads_and_changes_the_logo(env):
    assert _upload(env, PNG).status_code == 200
    first = env["client"].get("/api/v1/organization/logo", headers=env["tenant"]).content
    assert first.startswith(PNG[:8])
    assert _upload(env, JPEG, "logo.jpg").status_code == 200  # a JPEG logo is stored as a small PNG too
    replaced = env["client"].get("/api/v1/organization/logo", headers=env["tenant"])
    assert replaced.headers["content-type"] == "image/png" and replaced.content != first


def test_another_organization_never_reaches_this_logo(env):
    _upload(env, PNG)
    other = Organization(name="Other Org", code="OTHER-LOGO", timezone="UTC")
    env["db"].add(other); env["db"].commit()
    headers = member(env, "outsider@example.com", other)
    assert env["client"].get("/api/v1/organization/logo", headers=headers).status_code == 404  # its own organization has none
    assert env["client"].get("/api/v1/organization/logo").status_code == 401  # no session, no logo
    assert env["client"].get("/api/v1/organization/logo", headers=env["platform"]).status_code in (401, 403)
