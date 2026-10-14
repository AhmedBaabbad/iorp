"""ORG-AUDIT-003: the activity log keeps 12 months; an older month is downloaded as an archive file (built on request,
never stored), then deleted once its download is confirmed — or deleted automatically 30 days after it is due. Holders of
the archive permission are told and reminded; every download and deletion is in the audit trail. And the log reads by
person and by department."""
import io
import zipfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.core.tenancy import TenantContext
from app.foundation.application import activity_archive as AA
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import (ActivityArchive, Permission, Role, RolePermission, TenantActivityLog, TenantAuditEntry,
                                                  User, UserRole)
from app.notifications.infrastructure.models import NotificationItem

API = "/api/v1/admin/activity-log"


@pytest.fixture
def o(client, db, test_org):
    def permission(code):
        found = db.query(Permission).filter_by(organization_id=test_org.id, code=code).first()
        if found is None:
            module, resource, action = code.split(":")
            found = Permission(organization_id=test_org.id, code=code, name=code, description=code, module_name=module,
                               resource_name=resource, action_name=action)
            db.add(found); db.flush()
        return found

    role = Role(organization_id=test_org.id, name="Archivists", code="archivists")
    db.add(role); db.flush()
    for code in ("foundation:activity_log:read", AA.ARCHIVE):
        db.add(RolePermission(role_id=role.id, permission_id=permission(code).id, scope="organization"))
    admin = User(organization_id=test_org.id, full_name="Archive Keeper", email="keeper@example.com",
                 password_hash=hash_password("Secret12345!"), status=UserStatus.ACTIVE)
    db.add(admin); db.flush()
    db.add(UserRole(user_id=admin.id, role_id=role.id))
    db.commit()
    token = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "Secret12345!"}).json()["access_token"]

    def entry(when, action="customer.created", name="Gulf Pack", actor=admin, details=None):
        db.add(TenantActivityLog(organization_id=test_org.id, action=action, entity_type=action.split(".")[0], entity_name=name,
                                 actor_id=actor.id if actor else None, actor_name=actor.full_name if actor else None, details=details,
                                 created_at=when))
        db.commit()

    return SimpleNamespace(client=client, db=db, org=test_org, admin=admin, entry=entry, headers={"Authorization": f"Bearer {token}"})


def _month_ago(months: int) -> datetime:
    now = datetime.now(timezone.utc)
    index = now.year * 12 + now.month - 1 - months
    return datetime(index // 12, index % 12 + 1, 15, 10, 0, tzinfo=timezone.utc)


def test_a_month_is_due_twelve_months_after_it_ends(o):
    old, recent = _month_ago(14), _month_ago(6)
    o.entry(old); o.entry(old, action="production_order.status_changed", name="PO-1", details={"action": "release"}); o.entry(recent)
    due = o.client.get(f"{API}/archive", headers=o.headers).json()
    assert [(d["month"], d["rows"]) for d in due] == [(f"{old.year:04d}-{old.month:02d}", 2)]


def test_download_builds_a_readable_file_then_deletion_follows_and_both_are_audited(o):
    old = _month_ago(14)
    month = f"{old.year:04d}-{old.month:02d}"
    o.entry(old, action="production_order.status_changed", name="PO-2026-0007", details={"action": "release", "from_status": "draft"})
    assert o.client.post(f"{API}/archive/{month}/delete", headers=o.headers).status_code == 409  # not downloaded yet

    response = o.client.get(f"{API}/archive/{month}/download?locale=ar", headers=o.headers)
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    text = zipfile.ZipFile(io.BytesIO(response.content)).read(f"activity-{month}.csv").decode("utf-8-sig")
    assert "اعتماد وإطلاق أمر إنتاج" in text and "PO-2026-0007" in text and "مسودة" in text and "production_order" not in text

    assert o.client.post(f"{API}/archive/{month}/delete", headers=o.headers).json()["rows"] == 1
    assert o.db.scalar(select(func.count()).select_from(TenantActivityLog).where(TenantActivityLog.organization_id == o.org.id)) == 0
    actions = set(o.db.scalars(select(TenantAuditEntry.action).where(TenantAuditEntry.organization_id == o.org.id)))
    assert {AA.ARCHIVED, AA.PURGED} <= actions


def test_a_recent_month_cannot_be_archived_nor_deleted(o):
    recent = _month_ago(3)
    o.entry(recent)
    month = f"{recent.year:04d}-{recent.month:02d}"
    assert o.client.get(f"{API}/archive/{month}/download", headers=o.headers).status_code == 409
    assert o.client.post(f"{API}/archive/{month}/delete", headers=o.headers).status_code == 409


def test_the_daily_run_tells_reminds_and_finally_deletes(o):
    old = _month_ago(14)
    month = f"{old.year:04d}-{old.month:02d}"
    o.entry(old)
    due = datetime.combine(AA.due_on(month), datetime.min.time(), tzinfo=timezone.utc)
    assert AA.run_daily(o.db, due + timedelta(hours=1))["told"] == 1
    assert AA.run_daily(o.db, due + timedelta(hours=2))["told"] == 0  # told once
    assert AA.run_daily(o.db, due + timedelta(days=AA.GRACE_DAYS - 3))["reminded"] == 1
    assert AA.run_daily(o.db, due + timedelta(days=AA.GRACE_DAYS))["deleted"] == 1
    events = [n.event for n in o.db.scalars(select(NotificationItem).where(NotificationItem.recipient_user_id == o.admin.id)
                                              .order_by(NotificationItem.created_at))]
    assert events == ["foundation.activity_archive.ready", "foundation.activity_archive.reminder", "foundation.activity_archive.deleted"]
    assert o.db.scalar(select(ActivityArchive.deleted_at).where(ActivityArchive.month == month)) is not None


def test_the_archive_needs_its_permission(client, db, test_org, test_user):
    token = client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"}).json()["access_token"]
    assert client.get(f"{API}/archive", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_the_log_reads_by_person_and_by_department(o):
    now = datetime.now(timezone.utc)
    other = User(organization_id=o.org.id, full_name="Sara", email="sara@example.com", password_hash="x", status=UserStatus.ACTIVE)
    o.db.add(other); o.db.commit()
    o.entry(now); o.entry(now, action="quality_check.closed", name="QI-1", actor=other)
    by_area = o.client.get(f"{API}?area=quality", headers=o.headers).json()
    assert [i["entity_name"] for i in by_area["items"]] == ["QI-1"]
    assert [i["entity_name"] for i in o.client.get(f"{API}?actor_id={other.id}", headers=o.headers).json()["items"]] == ["QI-1"]
    assert {p["name"] for p in o.client.get(f"{API}/actors", headers=o.headers).json()} == {"Archive Keeper", "Sara"}


def test_a_reader_puts_away_notifications_but_not_an_announcement_to_acknowledge(o):
    from app.core.interfaces import notifications as N
    tenant = TenantContext(o.admin.id, o.org.id, permissions=frozenset())
    N.notify(o.db, o.org.id, N.Audience.to(o.admin.id), N.Notice("foundation.role.assigned", N.ACCESS, dict(role="R")), None)
    o.db.commit()
    item = o.db.scalar(select(NotificationItem).where(NotificationItem.recipient_user_id == tenant.user_id))
    assert o.client.post(f"/api/v1/notifications/{item.id}/hide", headers=o.headers).json() == {"hidden": 1}
    assert o.client.get("/api/v1/notifications", headers=o.headers).json()["total"] == 0


def test_every_word_of_the_logs_is_the_same_on_the_screens():
    import json
    from pathlib import Path
    from app.foundation.domain import log_words as W
    root = Path(__file__).parents[2]
    for i, lang in enumerate(("ar", "en")):
        words = json.loads((root / "frontend" / "src" / "i18n" / "locales" / lang / "logs.json").read_text(encoding="utf-8"))
        for name, key in (("ENTITIES", "entities"), ("VERBS", "verbs"), ("FIELDS", "fields"), ("VALUES", "values"), ("LISTS", "lists"),
                          ("EXACT", "exact")):
            assert words[key] == {k: v[i] for k, v in getattr(W, name).items()}, (lang, key)
