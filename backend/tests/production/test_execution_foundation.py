"""PROD-EXEC-FOUNDATION-001: actual history and tenant boundary regressions."""
from datetime import date, time, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.tenancy import TenantContext
from app.production.api.schemas import ShiftDefinitionCreate, ShiftDefinitionUpdate
from app.production.api.execution_schemas import RosterCreate, RosterMemberInput, RunCreate, RunMemberInput
from app.production.application.services import ShiftDefinitionService, WorkCenterService
from app.production.application.execution_service import ExecutionService
from app.production.infrastructure.execution_models import ShiftRoster, ProductionRun, ProductionRunMember
from app.production.infrastructure.models import ShiftDefinition, WorkCenter, ProductionOrder
from app.workforce.infrastructure.models import WorkforceMember
from app.foundation.infrastructure.models import Organization


@pytest.fixture
def ctx(db, test_org, test_user):
    tenant = TenantContext(test_user.id, test_org.id)
    svc = ExecutionService(db, tenant)
    today = svc.today()
    shift = ShiftDefinitionService(db).create_shift_definition(tenant, ShiftDefinitionCreate(code="M", name="Morning", start_time=time(7), end_time=time(15)))
    evening = ShiftDefinitionService(db).create_shift_definition(tenant, ShiftDefinitionCreate(code="E", name="Evening", start_time=time(15), end_time=time(23)))
    center = WorkCenter(organization_id=test_org.id, code="WC", name="Line")
    workers = [WorkforceMember(organization_id=test_org.id, employee_code=f"W{i}", full_name=f"Worker {i}", worker_type="operator", employment_type="employee") for i in range(2)]
    db.add_all([center, *workers]); db.flush()
    order = ProductionOrder(organization_id=test_org.id, production_order_number="PO", work_center_id=center.id, product_type="film", planned_quantity=100, unit="kg", planned_start_date=today, planned_end_date=today, created_by_user_id=test_user.id)
    db.add(order); db.commit()
    return SimpleNamespace(svc=svc, tenant=tenant, shift=shift, evening=evening, center=center, workers=workers, order=order, today=today, db=db)


def roster(c, **kw):
    values = dict(shift_definition_id=c.shift.id, effective_from=c.today - timedelta(days=10), members=[RosterMemberInput(workforce_member_id=c.workers[0].id)])
    values.update(kw)
    return c.svc.create_roster(RosterCreate(**values))


def run(c, **kw):
    values = dict(production_order_id=c.order.id, work_center_id=c.center.id, run_date=c.today)
    values.update(kw)
    return c.svc.create_run(RunCreate(**values))


def test_t01_shift_without_work_center(ctx):
    assert ctx.shift.id and "work_center_id" not in ShiftDefinition.__table__.columns


@pytest.mark.parametrize("schema", [ShiftDefinitionCreate, ShiftDefinitionUpdate])
def test_t02_reject_legacy_work_center(schema):
    with pytest.raises(ValidationError):
        schema(code="S", name="Shift", start_time="07:00", end_time="15:00", work_center_id=uuid4())


def test_t03_roster_belongs_to_shift(ctx):
    assert roster(ctx).shift_definition_id == ctx.shift.id


def test_t04_period_validation(ctx):
    with pytest.raises(ValidationError):
        RosterCreate(shift_definition_id=ctx.shift.id, effective_from=ctx.today, effective_to=ctx.today-timedelta(days=1))
    assert roster(ctx).effective_to is None


def test_t05_replacement_preserves_history(ctx):
    old = roster(ctx)
    new = ctx.svc.replace_roster(old.id, RosterCreate(shift_definition_id=ctx.shift.id, effective_from=ctx.today, members=[RosterMemberInput(workforce_member_id=ctx.workers[1].id)]))
    assert old.effective_to == ctx.today-timedelta(days=1)
    assert ctx.svc.members(old)[0].workforce_member_id == ctx.workers[0].id
    assert ctx.svc.members(new)[0].workforce_member_id == ctx.workers[1].id


def test_t06_t07_t28_worker_movement_period_query(ctx):
    old = roster(ctx)
    ctx.svc.close_roster(old.id, ctx.today-timedelta(days=1))
    new = roster(ctx, shift_definition_id=ctx.evening.id, effective_from=ctx.today)
    history = ctx.svc.rosters(workforce_member_id=ctx.workers[0].id)
    assert [r.id for r in history] == [old.id, new.id]
    assert ctx.svc.rosters(workforce_member_id=ctx.workers[0].id, date_from=ctx.today, date_to=ctx.today) == [new]
    assert ctx.svc.rosters(workforce_member_id=ctx.workers[0].id, date_from=old.effective_from, date_to=old.effective_from) == [old]


def test_t08_cross_org_worker_rejected(ctx):
    org = Organization(code="other", name="Other")
    ctx.db.add(org); ctx.db.flush()
    worker = WorkforceMember(organization_id=org.id, employee_code="X", full_name="Other", worker_type="operator", employment_type="employee")
    ctx.db.add(worker); ctx.db.flush()
    with pytest.raises(HTTPException) as exc:
        roster(ctx, members=[RosterMemberInput(workforce_member_id=worker.id)])
    assert exc.value.status_code == 404


def test_t09_duplicate_roster_member(ctx):
    member = RosterMemberInput(workforce_member_id=ctx.workers[0].id)
    with pytest.raises(ValueError, match="Duplicate"):
        roster(ctx, members=[member, member])


def test_t10_workforce_only_roster(ctx):
    r = roster(ctx)
    assert ctx.workers[0].user_id is None
    assert len(ctx.svc.members(r)) == 1


def test_t11_multiple_runs_per_order(ctx):
    a, b = run(ctx), run(ctx)
    assert {r.id for r in ctx.svc.runs(production_order_id=ctx.order.id)} == {a.id, b.id}


@pytest.mark.parametrize("field", ["production_order_id", "work_center_id"])
def test_t12_t13_required_run_links(ctx, field):
    values = dict(production_order_id=ctx.order.id, work_center_id=ctx.center.id, run_date=ctx.today)
    values.pop(field)
    with pytest.raises(ValidationError):
        RunCreate(**values)


def test_t14_t15_optional_shift_roster(ctx):
    r = run(ctx)
    assert r.shift_definition_id is None and r.shift_roster_id is None


@pytest.mark.parametrize("field", ["shift_definition_id", "shift_roster_id", "work_center_id", "production_order_id"])
def test_t16_t25_foreign_org_run_links(ctx, field):
    # Existing records belonging to the original tenant are invisible to another.
    r = roster(ctx)
    ids = dict(shift_definition_id=ctx.shift.id, shift_roster_id=r.id, work_center_id=ctx.center.id, production_order_id=ctx.order.id)
    other = ExecutionService(ctx.db, TenantContext(uuid4(), uuid4()))
    models = dict(shift_definition_id=ShiftDefinition, shift_roster_id=ShiftRoster, work_center_id=WorkCenter, production_order_id=ProductionOrder)
    with pytest.raises(HTTPException) as exc:
        other.get(models[field], ids[field])
    assert exc.value.status_code == 404


def test_t17_t18_t26_run_worker_identity_extensible_role(ctx):
    r = run(ctx, members=[RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="custom_factory_role")])
    member = ctx.svc.members(r)[0]
    assert member.workforce_member_id == ctx.workers[0].id
    assert member.role_code == "custom_factory_role"
    assert "user_id" not in ProductionRunMember.__table__.columns


def test_t19_duplicate_run_member(ctx):
    r = run(ctx)
    data = RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="operator")
    ctx.svc.set_run_member(r.id, data)
    with pytest.raises(ValueError, match="Duplicate"):
        ctx.svc.set_run_member(r.id, data)


def test_t20_t21_t22_copy_and_actual_adjustment(ctx):
    planned = roster(ctx)
    r = run(ctx, shift_roster_id=planned.id)
    ctx.svc.load_roster(r.id)
    ctx.svc.load_roster(r.id)
    assert len(ctx.svc.members(r)) == 1
    ctx.svc.set_run_member(r.id, member_id=ctx.svc.members(r)[0].id)
    ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=ctx.workers[1].id, role_code="relief_operator"))
    assert ctx.svc.members(planned)[0].workforce_member_id == ctx.workers[0].id
    assert ctx.svc.members(r)[0].workforce_member_id == ctx.workers[1].id


def test_t23_run_team_immutable_from_later_roster(ctx):
    planned = roster(ctx)
    r = run(ctx, shift_roster_id=planned.id, run_date=ctx.today-timedelta(days=1))
    ctx.svc.load_roster(r.id)
    ctx.svc.replace_roster(planned.id, RosterCreate(shift_definition_id=ctx.shift.id, effective_from=ctx.today, members=[]))
    assert ctx.svc.members(r)[0].workforce_member_id == ctx.workers[0].id


def test_t24_order_has_no_shift_fk():
    assert not {"shift_definition_id", "shift_roster_id"}.intersection(ProductionOrder.__table__.columns.keys())


def test_t25_tenant_lists_and_mutations(ctx):
    r = run(ctx)
    other = ExecutionService(ctx.db, TenantContext(uuid4(), uuid4()))
    assert other.runs() == [] and other.rosters() == []
    with pytest.raises(HTTPException):
        other.transition(r.id, "start")


def test_t27_transitions_and_terminal_history(ctx):
    r = run(ctx)
    with pytest.raises(ValueError):
        ctx.svc.transition(r.id, "complete")
    for action in ("start", "pause", "start", "complete"):
        ctx.svc.transition(r.id, action)
    assert r.ended_at >= r.started_at
    with pytest.raises(ValueError):
        ctx.svc.transition(r.id, "start")
    with pytest.raises(ValueError):
        ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="operator"))


def test_effective_roster_is_editable_until_a_run_uses_it(ctx):
    r = roster(ctx)  # already in effect
    assert ctx.svc.present(r)["members_editable"]
    ctx.svc.set_roster_member(r.id, RosterMemberInput(workforce_member_id=ctx.workers[1].id))
    ctx.svc.set_roster_member(r.id, member_id=ctx.svc.members(r)[0].id)
    assert [m.workforce_member_id for m in ctx.svc.members(r)] == [ctx.workers[1].id]
    run(ctx, shift_roster_id=r.id)
    assert not ctx.svc.present(r)["members_editable"]
    with pytest.raises(ValueError, match="used by a production run"):
        ctx.svc.set_roster_member(r.id, member_id=ctx.svc.members(r)[0].id)


def test_empty_roster_starting_today_can_receive_several_workers(ctx):
    r = roster(ctx, effective_from=ctx.today, members=[])
    for worker in ctx.workers:
        ctx.svc.set_roster_member(r.id, RosterMemberInput(workforce_member_id=worker.id))
    assert len(ctx.svc.members(r)) == 2


def test_closed_roster_is_not_editable(ctx):
    r = roster(ctx)
    ctx.svc.close_roster(r.id, ctx.today)
    with pytest.raises(ValueError, match="closed"):
        ctx.svc.set_roster_member(r.id, RosterMemberInput(workforce_member_id=ctx.workers[1].id))


def test_future_roster_edit_and_overlap_guard(ctx):
    r = roster(ctx, effective_from=ctx.today+timedelta(days=1))
    ctx.svc.set_roster_member(r.id, member_id=ctx.svc.members(r)[0].id)
    assert not ctx.svc.members(r)
    with pytest.raises(ValueError, match="overlap"):
        roster(ctx, effective_from=ctx.today+timedelta(days=1))


def test_run_roster_date_and_shift_consistency(ctx):
    r = roster(ctx)
    with pytest.raises(ValueError, match="match"):
        run(ctx, shift_roster_id=r.id, shift_definition_id=ctx.evening.id)
    with pytest.raises(ValueError, match="effective"):
        run(ctx, shift_roster_id=r.id, run_date=r.effective_from-timedelta(days=1))


def test_no_run_history_cascade(ctx):
    run(ctx)
    with pytest.raises(ValueError, match="history"):
        WorkCenterService(ctx.db).delete_work_center(ctx.tenant, ctx.center.id)


def test_shift_history_blocks_delete(ctx):
    roster(ctx)
    service = ShiftDefinitionService(ctx.db)
    assert service.get_deletion_impact(ctx.tenant, ctx.shift.id).is_blocked
    with pytest.raises(ValueError):
        service.delete_shift_definition(ctx.tenant, ctx.shift.id)


def test_api_create_history_and_permissions(ctx, client, auth_headers):
    payload = dict(production_order_id=str(ctx.order.id), work_center_id=str(ctx.center.id), run_date=str(ctx.today))
    response = client.post("/api/v1/production/runs", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    assert client.get("/api/v1/production/runs", headers=auth_headers).json()[0]["id"] == response.json()["id"]
    assert client.post("/api/v1/production/runs", json=payload).status_code == 401
    payload["organization_id"] = str(uuid4())
    assert client.post("/api/v1/production/runs", json=payload, headers=auth_headers).status_code == 422


def test_actual_worker_run_history(ctx):
    actual = run(ctx, members=[RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="operator")])
    run(ctx, members=[RunMemberInput(workforce_member_id=ctx.workers[1].id, role_code="helper")])
    assert ctx.svc.runs(workforce_member_id=ctx.workers[0].id) == [actual]


def test_api_replacement_failure_rolls_back_old_period(ctx, client, auth_headers):
    old = roster(ctx)
    ctx.db.commit()
    response = client.post(f"/api/v1/production/shift-rosters/{old.id}/replace", headers=auth_headers, json={
        "shift_definition_id": str(ctx.shift.id), "effective_from": str(ctx.today),
        "members": [{"workforce_member_id": str(uuid4())}],
    })
    assert response.status_code == 404
    ctx.db.refresh(old)
    assert old.status == "active" and old.effective_to is None
    assert len(ctx.svc.rosters()) == 1


def test_api_permission_denied_without_grants(ctx, client, auth_headers):
    from sqlalchemy import delete
    from app.foundation.infrastructure.models import UserRole
    ctx.db.execute(delete(UserRole).where(UserRole.user_id == ctx.tenant.user_id))
    ctx.db.commit()
    assert client.get("/api/v1/production/runs", headers=auth_headers).status_code == 403
    assert client.get("/api/v1/production/shift-rosters", headers=auth_headers).status_code == 403


def test_referenced_roster_cannot_shorten_past_run(ctx):
    old = roster(ctx)
    run(ctx, shift_roster_id=old.id)
    with pytest.raises(ValueError, match="later run"):
        ctx.svc.close_roster(old.id, ctx.today-timedelta(days=1))


def test_participation_history_not_deleted_after_start(ctx):
    row = run(ctx, members=[RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="operator")])
    ctx.svc.transition(row.id, "start")
    with pytest.raises(ValueError, match="end participation"):
        ctx.svc.set_run_member(row.id, member_id=ctx.svc.members(row)[0].id)
    assert str(ctx.order.status.value) == "draft"


# --- Review fixes: H1/H2/M1-M5/L2/L6 ---------------------------------------

from sqlalchemy import select

from app.core.utils import utc_now
from app.foundation.infrastructure.models import TenantActivityLog
from app.production.domain.enums import ProductionOrderStatus
from app.workforce.domain.enums import WorkforceMemberStatus


def deactivate(c, worker, status=WorkforceMemberStatus.TERMINATED):
    worker.status = status
    c.db.flush()


@pytest.mark.parametrize("status", [WorkforceMemberStatus.INACTIVE, WorkforceMemberStatus.SUSPENDED, WorkforceMemberStatus.TERMINATED])
def test_inactive_worker_rejected_everywhere(ctx, status):
    deactivate(ctx, ctx.workers[1], status)
    with pytest.raises(ValueError, match="not active"):
        roster(ctx, members=[RosterMemberInput(workforce_member_id=ctx.workers[1].id)])
    future = roster(ctx, effective_from=ctx.today + timedelta(days=1), members=[])
    with pytest.raises(ValueError, match="not active"):
        ctx.svc.set_roster_member(future.id, RosterMemberInput(workforce_member_id=ctx.workers[1].id))
    with pytest.raises(ValueError, match="not active"):
        run(ctx, members=[RunMemberInput(workforce_member_id=ctx.workers[1].id, role_code="operator")])


def test_load_roster_skips_workers_who_left(ctx):
    planned = roster(ctx, members=[RosterMemberInput(workforce_member_id=w.id) for w in ctx.workers])
    deactivate(ctx, ctx.workers[1])
    r = run(ctx, shift_roster_id=planned.id)
    ctx.svc.load_roster(r.id)
    assert [m.workforce_member_id for m in ctx.svc.members(r)] == [ctx.workers[0].id]
    # The planned roster itself is history and keeps the departed worker.
    assert len(ctx.svc.members(planned)) == 2


@pytest.mark.parametrize("status", [ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED])
def test_runs_blocked_on_finished_orders(ctx, status):
    planned = run(ctx)
    ctx.order.status = status
    ctx.db.flush()
    with pytest.raises(ValueError, match="production orders"):
        run(ctx)
    with pytest.raises(ValueError, match="production orders"):
        ctx.svc.transition(planned.id, "start")
    # Closing out an existing run is still allowed.
    assert ctx.svc.transition(planned.id, "cancel").status == "cancelled"


def test_mutations_write_audit_with_acting_user(ctx):
    old = roster(ctx)
    ctx.svc.replace_roster(old.id, RosterCreate(shift_definition_id=ctx.shift.id, effective_from=ctx.today, members=[]))
    r = run(ctx, members=[RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="operator")])
    for action in ("start", "pause", "start", "complete"):
        ctx.svc.transition(r.id, action)
    logs = ctx.db.scalars(select(TenantActivityLog).where(TenantActivityLog.organization_id == ctx.tenant.organization_id, TenantActivityLog.entity_type.in_(["shift_roster", "production_run"]))).all()
    actions = [log.action for log in logs]
    for expected in ("shift_roster.created", "shift_roster.replaced", "production_run.created", "production_run.started", "production_run.paused", "production_run.completed"):
        assert expected in actions
    assert {log.actor_id for log in logs} == {ctx.tenant.user_id}
    replaced = next(log for log in logs if log.action == "shift_roster.replaced")
    assert replaced.entity_id == old.id


def test_replacement_after_start_and_rejoin(ctx):
    a, b = ctx.workers
    r = run(ctx, members=[RunMemberInput(workforce_member_id=a.id, role_code="operator")])
    ctx.svc.transition(r.id, "start")
    first = ctx.svc.members(r)[0]
    assert first.started_at == r.started_at
    # A leaves, B replaces A.
    left = utc_now()
    ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=a.id, role_code="operator", started_at=first.started_at, ended_at=left), first.id)
    ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=b.id, role_code="relief_operator"))
    # A cannot come back into a window overlapping the first stint, or while still open.
    with pytest.raises(ValueError, match="overlaps"):
        ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=a.id, role_code="operator", started_at=first.started_at))
    ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=a.id, role_code="operator", started_at=left))
    with pytest.raises(ValueError, match="Duplicate"):
        ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=a.id, role_code="operator"))
    stints = [m for m in ctx.svc.members(r) if m.workforce_member_id == a.id]
    assert len(stints) == 2 and stints[0].ended_at == left and stints[1].ended_at is None


def test_complete_closes_open_participation(ctx):
    r = run(ctx, members=[RunMemberInput(workforce_member_id=w.id, role_code="operator") for w in ctx.workers])
    ctx.svc.transition(r.id, "start")
    ctx.svc.transition(r.id, "complete")
    assert all(m.started_at == r.started_at and m.ended_at == r.ended_at for m in ctx.svc.members(r))


def test_participation_bounded_by_run(ctx):
    r = run(ctx)
    with pytest.raises(ValueError, match="after the run starts"):
        ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="operator", started_at=utc_now()))
    ctx.svc.transition(r.id, "start")
    with pytest.raises(ValueError, match="before the run started"):
        ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="operator", started_at=r.started_at - timedelta(hours=1)))


def test_participation_identity_cannot_change(ctx):
    r = run(ctx, members=[RunMemberInput(workforce_member_id=ctx.workers[0].id, role_code="operator")])
    member = ctx.svc.members(r)[0]
    with pytest.raises(ValueError, match="identity"):
        ctx.svc.set_run_member(r.id, RunMemberInput(workforce_member_id=ctx.workers[1].id, role_code="operator"), member.id)


def test_worker_cannot_be_on_overlapping_rosters(ctx):
    roster(ctx)
    with pytest.raises(ValueError, match="overlapping roster"):
        roster(ctx, shift_definition_id=ctx.evening.id, effective_from=ctx.today)
    future = roster(ctx, shift_definition_id=ctx.evening.id, effective_from=ctx.today + timedelta(days=1), members=[])
    with pytest.raises(ValueError, match="overlapping roster"):
        ctx.svc.set_roster_member(future.id, RosterMemberInput(workforce_member_id=ctx.workers[0].id))


def test_roster_period_state(ctx):
    past = roster(ctx, effective_to=ctx.today - timedelta(days=5))
    current = roster(ctx, effective_from=ctx.today - timedelta(days=4), effective_to=ctx.today, members=[])
    upcoming = roster(ctx, effective_from=ctx.today + timedelta(days=1), members=[])
    assert [ctx.svc.present(r)["period_state"] for r in (past, current, upcoming)] == ["ended", "current", "upcoming"]


def test_shift_history_delete_message(ctx):
    roster(ctx)
    with pytest.raises(ValueError, match="roster or production run history"):
        ShiftDefinitionService(ctx.db).delete_shift_definition(ctx.tenant, ctx.shift.id)
