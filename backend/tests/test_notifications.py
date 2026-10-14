"""PROJECT-NOTIFY-001: every user's notifications, and announcements written by people.

- A module tells people through core/interfaces/notifications, in the transaction of its change; only active users of the
  organization receive it, the person who did it is left out, and each user reads only their own.
- Work that is done is settled: it stops counting as unread for everyone who was asked.
- An announcement reaches named users, a role's members or everyone; one that requires acknowledgement stays in front
  of its reader until confirmed; its author follows who read and who acknowledged.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.interfaces import notifications as N
from app.core.security import hash_password
from app.core.tenancy import TenantContext
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Permission, Role, RolePermission, User, UserRole
from app.notifications.application.service import purge
from app.notifications.infrastructure.models import NotificationItem
from app.procurement.application import notices as procurement_notices

API, ANN = "/api/v1/notifications", "/api/v1/announcements"
SEND, MANAGE = "notifications:announcements:send", "notifications:announcements:manage"
APPROVE = "procurement:purchase_orders:approve"
ROOT = Path(__file__).parents[2]


@pytest.fixture
def o(client, db, test_org):
    tokens = {}

    def permission(code):
        found = db.query(Permission).filter_by(organization_id=test_org.id, code=code).first()
        if found is None:
            module, resource, action = code.split(":")
            found = Permission(organization_id=test_org.id, code=code, name=code, description=code, module_name=module,
                               resource_name=resource, action_name=action)
            db.add(found); db.flush()
        return found

    def role(name, *codes):
        made = Role(organization_id=test_org.id, name=name, code=f"r{uuid4().hex[:8]}")
        db.add(made); db.flush()
        for code in codes:
            db.add(RolePermission(role_id=made.id, permission_id=permission(code).id, scope="organization"))
        db.commit()
        return made

    def user(name, *roles, status=UserStatus.ACTIVE):
        person = User(organization_id=test_org.id, full_name=name, email=f"{name.lower().replace(' ', '.')}@example.com",
                      password_hash=hash_password("Secret12345!"), status=status)
        db.add(person); db.flush()
        for r in roles:
            db.add(UserRole(user_id=person.id, role_id=r.id))
        db.commit()
        return person

    def login(person):
        if person.id not in tokens:  # once per person: the login rate limit
            r = client.post("/api/v1/auth/login", json={"email": person.email, "password": "Secret12345!"})
            assert r.status_code == 200, r.text
            tokens[person.id] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return tokens[person.id]

    def summary(person):
        r = client.get(f"{API}/summary", headers=login(person))
        assert r.status_code == 200, r.text
        return r.json()

    admins = role("Administrators", "foundation:user_roles:write", "foundation:role_permissions:write", "foundation:users:read",
                  "foundation:roles:read", SEND, MANAGE, APPROVE, "procurement:purchase_orders:read", "procurement:suppliers:read")
    approvers = role("Approvers", APPROVE)
    admin = user("Org Admin", admins)
    return SimpleNamespace(client=client, db=db, org=test_org, role=role, user=user, login=login, summary=summary, admin=admin,
                           admins=admins, approvers=approvers)


def test_a_role_given_tells_its_holder_who_gave_it_and_nobody_else(o):
    planner = o.user("Planner")
    r = o.client.post(f"/api/v1/admin/users/{planner.id}/roles", headers=o.login(o.admin), json={"role_id": str(o.approvers.id)})
    assert r.status_code == 201, r.text
    mine = o.summary(planner)
    assert mine["unread"] == 1
    note = mine["latest"][0]
    assert (note["event"], note["category"], note["actor_name"], note["params"]["role"]) == ("foundation.role.assigned", "access", "Org Admin", "Approvers")
    assert o.summary(o.admin)["unread"] == 0  # the person who did it is not told
    # nobody reads or marks another user's notification
    assert o.client.post(f"{API}/{note['id']}/read", headers=o.login(o.admin)).status_code == 404
    assert o.client.post(f"{API}/{note['id']}/read", headers=o.login(planner)).json()["read"] is True
    assert o.summary(planner)["unread"] == 0


def test_several_permission_changes_make_one_unread_notice_for_the_role_members(o):
    member = o.user("Member", o.approvers)
    for code in ("procurement:purchase_orders:read", "procurement:suppliers:read"):
        r = o.client.post(f"/api/v1/admin/roles/{o.approvers.id}/permissions", headers=o.login(o.admin), json={"permission_code": code})
        assert r.status_code == 201, r.text
    events = [n["event"] for n in o.summary(member)["latest"]]
    assert events == ["foundation.role.permissions_changed"]


def test_work_waits_for_the_holders_and_is_settled_once_done(o):
    approver, other, preparer = o.user("Approver", o.approvers), o.user("Other Approver", o.approvers), o.user("Preparer")
    inactive = o.user("Former Approver", o.approvers, status=UserStatus.INACTIVE)
    tenant = TenantContext(preparer.id, o.org.id, permissions=frozenset())
    order = SimpleNamespace(id=uuid4(), po_number="PO-2026-0001", supplier_name="Gulf Resins", created_by_user_id=preparer.id)
    procurement_notices.order_awaits_approval(o.db, tenant, order)
    procurement_notices.order_awaits_approval(o.db, tenant, order)  # never repeated while unread
    o.db.commit()
    rows = o.db.query(NotificationItem).filter_by(resource_id=order.id).all()
    assert sorted(r.recipient_user_id for r in rows) == sorted([approver.id, other.id, o.admin.id])  # every holder; not the preparer
    assert inactive.id not in {r.recipient_user_id for r in rows}
    note = o.summary(approver)["latest"][0]
    assert (note["severity"], note["link"], note["params"]["number"]) == ("important", f"/purchase-orders/{order.id}", "PO-2026-0001")

    procurement_notices.order_approved(o.db, TenantContext(approver.id, o.org.id, permissions=frozenset()), order)
    o.db.commit()
    assert o.summary(other)["unread"] == 0  # done by someone else: nothing waits any more
    assert o.summary(preparer)["latest"][0]["event"] == "procurement.purchase_order.approved"


def test_a_notification_never_undoes_the_change_it_reports(o, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("down")
    monkeypatch.setattr(N._provider, "send", broken)
    assert N.notify(o.db, o.org.id, N.Audience.to(o.admin.id), N.Notice("x.y.z")) == 0


def test_an_announcement_to_a_role_requires_acknowledgement_and_its_author_follows_it(o):
    first, second, outsider = o.user("First", o.approvers), o.user("Second", o.approvers), o.user("Outsider")
    body = dict(title="New quality policy", body="Read the updated policy before Sunday.", severity="urgent", requires_ack=True,
                audience="role", role_id=str(o.approvers.id))
    r = o.client.post(ANN, headers=o.login(o.admin), json=body)
    assert r.status_code == 201, r.text
    made = r.json()
    assert (made["recipient_count"], made["audience_label"], made["read_count"]) == (2, "Approvers", 0)
    assert o.summary(outsider)["unread"] == 0  # only the people it concerns

    waiting = o.summary(first)["pending_ack"]
    assert [w["announcement"]["title"] for w in waiting] == ["New quality policy"]
    assert o.client.post(f"{API}/{waiting[0]['id']}/acknowledge", headers=o.login(first)).json()["announcement"]["acknowledged"] is True
    assert o.summary(first)["pending_ack"] == []

    detail = o.client.get(f"{ANN}/{made['id']}", headers=o.login(o.admin)).json()
    assert (detail["read_count"], detail["acknowledged_count"]) == (1, 1)
    assert {(x["name"], x["acknowledged_at"] is not None) for x in detail["receipts"]} == {("First", True), ("Second", False)}

    # withdrawn: no longer shown to anyone
    assert o.client.post(f"{ANN}/{made['id']}/withdraw", headers=o.login(o.admin)).json()["state"] == "withdrawn"
    assert o.summary(second)["pending_ack"] == [] and o.summary(second)["unread"] == 0


def test_only_holders_of_the_permission_send_announcements(o):
    person = o.user("Plain User")
    body = dict(title="Hello", body="Hi", audience="everyone")
    assert o.client.post(ANN, headers=o.login(person), json=body).status_code == 403
    assert o.client.get(ANN, headers=o.login(person)).status_code == 403
    assert o.client.post(ANN, headers=o.login(o.admin), json=dict(body, audience="users")).status_code == 400  # nobody named


def test_inbox_pages_and_filters(o):
    person = o.user("Reader")
    tenant = TenantContext(o.admin.id, o.org.id, permissions=frozenset())
    for i in range(3):
        N.notify(o.db, o.org.id, N.Audience.to(person.id), N.Notice("foundation.role.assigned", N.ACCESS, dict(role=f"R{i}")), tenant.user_id)
    N.notify(o.db, o.org.id, N.Audience.to(person.id), N.Notice("foundation.user.password_reset", N.SECURITY, severity=N.IMPORTANT), tenant.user_id)
    o.db.commit()
    page = o.client.get(f"{API}?page=1&page_size=2", headers=o.login(person)).json()
    assert (page["total"], page["pages"], len(page["items"])) == (4, 2, 2)
    assert o.client.get(f"{API}?kind=important", headers=o.login(person)).json()["total"] == 1
    assert o.client.get(f"{API}?kind=security", headers=o.login(person)).json()["total"] == 1
    assert o.client.post(f"{API}/read-all", headers=o.login(person)).json()["read"] == 4
    assert o.client.get(f"{API}?kind=unread", headers=o.login(person)).json()["total"] == 0


def test_purge_keeps_unread_and_recent(o, db):
    from datetime import timedelta
    from app.core.utils import utc_now
    person = o.user("Old Reader")
    old = utc_now() - timedelta(days=100)
    db.add_all([NotificationItem(organization_id=o.org.id, recipient_user_id=person.id, event="a.b.c", category="work", params={},
                                 created_at=old, read_at=old),
                NotificationItem(organization_id=o.org.id, recipient_user_id=person.id, event="a.b.d", category="work", params={},
                                 created_at=old)])
    db.commit()
    assert purge(db) == 1
    assert [r.event for r in db.query(NotificationItem).filter_by(recipient_user_id=person.id)] == ["a.b.d"]


def test_every_event_has_its_words_in_both_languages():
    """An event sent by a module is shown in Arabic and English (frontend notifications.json)."""
    events = {"notifications.announcement.published"}
    for path in [*(ROOT / "backend" / "app").rglob("notices.py"), ROOT / "backend" / "app" / "foundation" / "application" / "activity_archive.py"]:
        events |= set(re.findall(r'"([a-z_]+\.[a-z_]+\.[a-z_]+)"', path.read_text(encoding="utf-8")))
    assert len(events) > 20
    for lang in ("ar", "en"):
        words = json.loads((ROOT / "frontend" / "src" / "i18n" / "locales" / lang / "notifications.json").read_text(encoding="utf-8"))["events"]
        missing = []
        for event in events:
            node = words
            for part in event.split("."):
                node = node.get(part) if isinstance(node, dict) else None
            if not isinstance(node, str):
                missing.append(event)
        assert not missing, (lang, sorted(missing))
