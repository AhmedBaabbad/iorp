"""PROJECT-GOV-004: governed approval delegations and the record of every signed step.

A holder lends one approval they hold through a role, for at most 90 days, to another user of the same organization;
it is in force only once the other side agrees (a manager for a holder's request, the holder for a manager's); the
signer is always the session's user, and the record keeps whose authority it was."""
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.interfaces import approvals
from app.core.interfaces.approvals import ApprovalAuthorityError
from app.core.security import hash_password
from app.core.tenancy import TenantContext
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.delegation_models import ApprovalDelegation, ApprovalRecord
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission, User, UserRole

API = "/api/v1/delegations"
APPROVE, VERIFY = "procurement:purchase_orders:approve", "quality:ncr_reports:verify"
MANAGE = "foundation:delegations:manage"
TODAY = date.today()


@pytest.fixture
def org(client, db, test_org):
    def permission(code):
        found = db.query(Permission).filter_by(organization_id=test_org.id, code=code).first()
        if found is None:
            module, resource, action = code.split(":")
            found = Permission(organization_id=test_org.id, code=code, name=code, description=code, module_name=module,
                               resource_name=resource, action_name=action)
            db.add(found); db.flush()
        return found

    def user(name, *codes, root=False, organization=test_org):
        person = User(organization_id=organization.id, full_name=name, email=f"{name.lower().replace(' ', '.')}@example.com",
                      password_hash=hash_password("Secret12345!"), status=UserStatus.ACTIVE, is_organization_root=root)
        db.add(person); db.flush()
        if codes:
            role = Role(organization_id=organization.id, name=f"{name} role", code=f"r{uuid4().hex[:8]}")
            db.add(role); db.flush()
            for code in codes:
                db.add(RolePermission(role_id=role.id, permission_id=permission(code).id, scope="organization"))
            db.add(UserRole(user_id=person.id, role_id=role.id))
        db.commit()
        return person

    def login(person):
        r = client.post("/api/v1/auth/login", json={"email": person.email, "password": "Secret12345!"})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def delegate(by, delegator, delegate_to, code=APPROVE, start=TODAY, end=TODAY + timedelta(days=30)):
        return client.post(API, headers=login(by), json=dict(delegator_user_id=str(delegator.id), delegate_user_id=str(delegate_to.id),
                                                             permission_code=code, effective_from=str(start), effective_to=str(end),
                                                             reason="Annual leave"))

    def answer(by, made, verb="approve", reason=""):
        return client.post(f"{API}/{made['id']}/{verb}", headers=login(by), json=dict(reason=reason))

    def in_force(by, delegator, delegate_to, code=APPROVE):
        """A holder's request, approved by the manager."""
        made = delegate(by, delegator, delegate_to, code).json()
        assert answer(admin, made).json()["status"] == "active"
        return made

    def tenant(person):
        permissions = client.get("/api/v1/auth/me", headers=login(person)).json()["permissions"]
        return TenantContext(person.id, test_org.id, permissions=frozenset(permissions))

    manager = user("Production Manager", APPROVE, VERIFY)  # a holder: no delegation permission of their own
    deputy = user("Deputy Planner")
    admin = user("Delegation Manager", MANAGE)
    return SimpleNamespace(client=client, db=db, org=test_org, user=user, login=login, delegate=delegate, answer=answer, in_force=in_force,
                           tenant=tenant, manager=manager, deputy=deputy, admin=admin)


def sign(o, person, code=APPROVE, resource=None):
    resource = resource or uuid4()
    result = approvals.record(o.db, o.tenant(person), "purchase_order", resource, "approve", code)
    o.db.commit()
    return resource, result


# ── the governed workflow ────────────────────────────────────────────────────────────────────────

def test_a_holder_asks_and_a_manager_approves_before_it_is_in_force(org):
    made = org.delegate(org.manager, org.manager, org.deputy).json()  # no extra permission: holding the approval is enough
    assert made["status"] == "awaiting_manager" and not made["usable"]
    assert APPROVE not in org.client.get("/api/v1/auth/me", headers=org.login(org.deputy)).json()["permissions"]
    with pytest.raises(ApprovalAuthorityError):
        sign(org, org.deputy)
    assert org.client.get(f"{API}/waiting", headers=org.login(org.admin)).json()["count"] == 1
    assert org.client.get(f"{API}/waiting", headers=org.login(org.manager)).json()["count"] == 0
    r = org.answer(org.manager, made)  # the holder cannot approve their own request
    assert r.status_code == 403 and r.json()["detail"] == "DELEGATION_NOT_YOURS_TO_ANSWER"
    done = org.answer(org.admin, made).json()
    assert done["status"] == "active" and done["decided_by_name"] == "Delegation Manager"
    _, signed = sign(org, org.deputy)
    assert signed == dict(step="approve", authority_name="Production Manager", signer_name="Deputy Planner", delegated=True)


def test_a_manager_delegates_on_a_holders_behalf_and_the_holder_agrees_or_refuses(org):
    made = org.delegate(org.admin, org.manager, org.deputy).json()
    assert made["status"] == "awaiting_holder"
    assert org.client.get(f"{API}/waiting", headers=org.login(org.manager)).json()["count"] == 1
    assert org.answer(org.admin, made).status_code == 403  # the manager does not answer their own proposal
    r = org.answer(org.manager, made, "reject")
    assert r.status_code == 422 and r.json()["detail"] == "REASON_REQUIRED"
    refused = org.answer(org.manager, made, "reject", "I will sign before leaving").json()
    assert refused["status"] == "rejected" and refused["decision_reason"] == "I will sign before leaving"
    with pytest.raises(ApprovalAuthorityError):
        sign(org, org.deputy)
    again = org.delegate(org.admin, org.manager, org.deputy).json()
    assert org.answer(org.manager, again).json()["status"] == "active"
    assert sign(org, org.deputy)[1]["delegated"] is True


def test_the_organizations_administrator_delegating_their_own_is_in_force_at_once(org):
    root = org.user("Ahmed Root", root=True)
    made = org.delegate(root, root, org.deputy).json()
    assert made["status"] == "active" and made["decided_by_name"] == "Ahmed Root"


def test_a_delegation_lasts_at_most_90_days(org):
    r = org.delegate(org.manager, org.manager, org.deputy, end=TODAY + timedelta(days=90))
    assert r.status_code == 422 and r.json()["detail"] == "DELEGATION_TOO_LONG"
    assert org.delegate(org.manager, org.manager, org.deputy, end=TODAY + timedelta(days=89)).status_code == 201


def test_an_unanswered_request_lapses_when_its_period_ends(org):
    row = ApprovalDelegation(organization_id=org.org.id, delegator_user_id=org.manager.id, delegate_user_id=org.deputy.id,
                             permission_code=APPROVE, effective_from=TODAY - timedelta(days=10), effective_to=TODAY - timedelta(days=1),
                             reason="Last week", created_by_user_id=org.manager.id, approval="awaiting_manager")
    org.db.add(row); org.db.commit()
    [listed] = org.client.get(API, headers=org.login(org.admin)).json()["items"]
    assert listed["status"] == "lapsed" and not listed["can_answer"]
    r = org.answer(org.admin, listed)
    assert r.status_code == 409 and r.json()["detail"] == "DELEGATION_LAPSED"


# ── what a delegation allows ─────────────────────────────────────────────────────────────────────

def test_a_holder_signs_in_their_own_name(org):
    _, signed = sign(org, org.manager)
    assert signed == dict(step="approve", authority_name="Production Manager", signer_name="Production Manager", delegated=False)
    assert org.db.query(ApprovalRecord).one().delegation_id is None


def test_a_delegation_does_not_work_outside_its_scope(org):
    org.in_force(org.manager, org.manager, org.deputy, APPROVE)
    assert VERIFY not in org.client.get("/api/v1/auth/me", headers=org.login(org.deputy)).json()["permissions"]
    with pytest.raises(ApprovalAuthorityError):
        sign(org, org.deputy, VERIFY)


def test_an_ended_or_future_delegation_does_not_work(org):
    org.db.add(ApprovalDelegation(organization_id=org.org.id, delegator_user_id=org.manager.id, delegate_user_id=org.deputy.id,
                                  permission_code=APPROVE, effective_from=TODAY - timedelta(days=10), effective_to=TODAY - timedelta(days=1),
                                  reason="Last week", created_by_user_id=org.manager.id, approval="approved"))
    org.db.commit()
    with pytest.raises(ApprovalAuthorityError):
        sign(org, org.deputy)
    future = org.delegate(org.manager, org.manager, org.deputy, start=TODAY + timedelta(days=5)).json()
    assert org.answer(org.admin, future).json()["status"] == "scheduled"
    with pytest.raises(ApprovalAuthorityError):
        sign(org, org.deputy)
    r = org.delegate(org.manager, org.manager, org.deputy, start=TODAY - timedelta(days=5), end=TODAY - timedelta(days=1))
    assert r.status_code == 422 and r.json()["detail"] == "DELEGATION_ALREADY_ENDED"


def test_a_revoked_delegation_does_not_work_and_stays_on_record(org):
    made = org.in_force(org.manager, org.manager, org.deputy)
    sign(org, org.deputy)
    r = org.client.post(f"{API}/{made['id']}/revoke", headers=org.login(org.manager), json=dict(reason="Back from leave"))
    assert r.status_code == 200 and r.json()["status"] == "revoked"  # revoking needs no one's agreement
    with pytest.raises(ApprovalAuthorityError):
        sign(org, org.deputy)
    assert org.db.query(ApprovalDelegation).count() == 1
    assert org.db.query(ApprovalRecord).filter(ApprovalRecord.delegation_id.isnot(None)).count() == 1


def test_a_delegation_stops_when_its_delegator_loses_the_permission_and_history_stays(org):
    org.in_force(org.manager, org.manager, org.deputy)
    resource, _ = sign(org, org.deputy)
    org.db.query(UserRole).filter_by(user_id=org.manager.id).delete()
    org.db.commit()
    with pytest.raises(ApprovalAuthorityError):
        sign(org, org.deputy)
    [record] = approvals.signatures(org.db, org.org.id, "purchase_order", [resource])[resource]
    assert record["authority_name"] == "Production Manager" and record["delegated"]


def test_another_organizations_users_cannot_be_delegated_to(org):
    other = Organization(name="Other Delegations", code="OTHER-DEL", timezone="UTC")
    org.db.add(other); org.db.commit()
    outsider = org.user("Outsider", organization=other)
    r = org.delegate(org.admin, org.manager, outsider)
    assert r.status_code == 404 and r.json()["detail"] == "USER_NOT_FOUND"


def test_a_holder_delegates_only_their_own_and_only_what_they_hold(org):
    lead = org.user("Shift Lead", VERIFY)
    r = org.delegate(lead, org.manager, org.deputy)  # on behalf of someone else
    assert r.status_code == 403 and r.json()["detail"] == "DELEGATION_ONLY_OWN"
    r = org.delegate(lead, lead, org.deputy, code=APPROVE)  # an approval they do not hold
    assert r.status_code == 422 and r.json()["detail"] == "DELEGATOR_LACKS_PERMISSION"
    r = org.delegate(org.manager, org.manager, org.manager)
    assert r.status_code == 422 and r.json()["detail"] == "DELEGATION_TO_SELF"
    r = org.delegate(org.manager, org.manager, org.deputy, code="foundation:users:delete")
    assert r.status_code == 422 and r.json()["detail"] == "PERMISSION_NOT_DELEGABLE"


def test_a_delegated_permission_cannot_be_delegated_again(org):
    org.in_force(org.manager, org.manager, org.deputy)
    third = org.user("Third Person")
    r = org.delegate(org.deputy, org.deputy, third)
    assert r.status_code == 422 and r.json()["detail"] == "DELEGATOR_LACKS_PERMISSION"


def test_the_signer_is_always_the_session_user(org):
    stranger = org.user("No Authority")
    with pytest.raises(ApprovalAuthorityError):
        sign(org, stranger)
    assert sign(org, org.manager)[1]["signer_name"] == "Production Manager"
    assert "signed_by_user_id" not in approvals.record.__code__.co_varnames  # the interface takes no signer


def test_a_user_without_any_approval_cannot_use_delegations(org):
    assert org.client.get(API, headers=org.login(org.deputy)).status_code == 403
    assert org.delegate(org.deputy, org.manager, org.deputy).status_code == 403


def test_several_steps_are_signed_separately_and_nothing_is_filled_by_itself(org):
    resource = uuid4()
    approvals.record(org.db, org.tenant(org.manager), "ncr", resource, "verify", VERIFY)
    org.db.commit()
    signed = approvals.signatures(org.db, org.org.id, "ncr", [resource])[resource]
    assert [s["step"] for s in signed] == ["verify"] and approvals.latest(signed, "effectiveness_review") is None
    approvals.record(org.db, org.tenant(org.manager), "ncr", resource, "effectiveness_review", VERIFY)
    org.db.commit()
    assert [s["step"] for s in approvals.signatures(org.db, org.org.id, "ncr", [resource])[resource]] == ["verify", "effectiveness_review"]


def test_documents_name_the_signer_and_on_whose_behalf():
    from app.quality.reporting.ncr_document import _signer
    view = dict(verified_by_name="Deputy Planner", verification_signature=dict(delegated=True, signer_name="Deputy Planner",
                                                                               authority_name="Quality Manager"))
    assert _signer(view, "ar") == "Deputy Planner — بالتفويض عن Quality Manager"
    assert approvals.signed_name(view["verification_signature"], "x", "en") == "Deputy Planner — on behalf of Quality Manager"
    assert approvals.signed_name(None, "Quality Manager", "ar") == "Quality Manager"


def test_options_offer_holders_their_own_and_managers_anyones(org):
    mine = org.client.get(f"{API}/options", headers=org.login(org.manager)).json()
    assert [d["name"] for d in mine["delegators"]] == ["Production Manager"] and set(mine["delegators"][0]["permissions"]) == {APPROVE, VERIFY}
    anyone = org.client.get(f"{API}/options", headers=org.login(org.admin)).json()
    assert "Production Manager" in [d["name"] for d in anyone["delegators"]] and anyone["manages"] is True


# ── the twelve approvals and who may read their signatures ───────────────────────────────────────

def test_every_delegable_approval_is_a_real_permission_and_its_document_is_readable():
    from app.foundation.domain.delegations import DELEGABLE
    from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES
    from app.core.interfaces.approvals import _visibility
    assert len(DELEGABLE) == 12 and set(DELEGABLE) <= set(ALL_PERMISSION_CODES)
    assert {"quote", "sales_order", "complaint", "purchase_order", "supplier", "production_order", "quality_check",
            "quality_rejection", "ncr", "quality_certificate", "shipment_return"} <= set(_visibility)


def test_signatures_are_read_only_by_who_may_read_the_document(org):
    from app.core.db import Base
    table = Base.metadata.tables["quality_certificates"]
    reader = org.user("Certificate Reader", "quality:certificates:read")
    resource = uuid4()
    approvals.record(org.db, TenantContext(org.manager.id, org.org.id, permissions=frozenset({"quality:certificates:issue"})),
                     "quality_certificate", resource, "issue", "quality:certificates:issue")
    org.db.commit()
    url = f"/api/v1/approvals/quality_certificate/{resource}"
    assert org.client.get(url, headers=org.login(reader)).status_code == 404  # no such certificate in this organization
    assert org.client.get(url, headers=org.login(org.deputy)).status_code == 404  # no permission to read certificates
    assert org.client.get(f"/api/v1/approvals/unknown/{resource}", headers=org.login(reader)).status_code == 404
    assert table is not None


def test_the_list_is_paged_and_filtered_by_state_and_name(org):
    made = [org.delegate(org.manager, org.manager, org.deputy).json() for _ in range(3)]
    org.answer(org.admin, made[0])
    admin = org.login(org.admin)
    get = lambda **params: org.client.get(API, headers=admin, params=params).json()  # noqa: E731
    page = get(page=1, page_size=2)
    assert page["total"] == 3 and page["pages"] == 2 and len(page["items"]) == 2
    assert get(state="active")["total"] == 1 and get(state="waiting")["total"] == 2 and get(state="revoked")["total"] == 0
    assert get(search="Deputy")["total"] == 3 and get(search="Nobody")["total"] == 0
    waiting = org.client.get(f"{API}/waiting", headers=admin).json()
    assert waiting["count"] == 2 and {w["id"] for w in waiting["items"]} == {made[1]["id"], made[2]["id"]}
