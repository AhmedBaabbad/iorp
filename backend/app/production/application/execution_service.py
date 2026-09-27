from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_

from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.foundation.infrastructure.models import Organization
from app.production.api.execution_schemas import RunMemberInput
from app.production.domain.enums import ProductionOrderStatus
from app.production.infrastructure.execution_models import ProductionRun, ProductionRunMember, ShiftRoster, ShiftRosterMember
from app.production.infrastructure.execution_repository import ExecutionRepository
from app.production.infrastructure.models import ProductionOrder, ShiftDefinition, WorkCenter
from app.workforce.domain.enums import WorkforceMemberStatus
from app.workforce.infrastructure.models import WorkforceMember

RUNNABLE_ORDER_STATUSES = {ProductionOrderStatus.DRAFT, ProductionOrderStatus.RELEASED, ProductionOrderStatus.IN_PROGRESS}
TRANSITION_EVENTS = {"start": "started", "pause": "paused", "complete": "completed", "cancel": "cancelled"}


class ExecutionService:
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant
        self.repo = ExecutionRepository(db, tenant.organization_id)
        self._lookup_cache = {}

    def get(self, model, record_id, lock=False):
        row = self.repo.get(model, record_id, lock=lock)
        if row is None:
            raise HTTPException(404, "Record not found")
        return row

    def lookup(self, model, record_id):
        # Read-only reference data for presentation; avoids one query per member/row.
        key = (model, record_id)
        if key not in self._lookup_cache:
            self._lookup_cache[key] = self.get(model, record_id)
        return self._lookup_cache[key]

    def today(self):
        organization = self.db.get(Organization, self.tenant.organization_id)
        return datetime.now(ZoneInfo(organization.timezone or "UTC")).date()

    def add(self, model, **values):
        row = model(organization_id=self.tenant.organization_id, **values)
        self.db.add(row)
        self.db.flush()
        return row

    def audit(self, action, row, **details):
        entity_type = "shift_roster" if isinstance(row, ShiftRoster) else "production_run"
        get_registered_activity_logger().log_activity(
            self.db, self.tenant.organization_id, f"{entity_type}.{action}", entity_type, row.id,
            getattr(row, "name", None), actor_id=self.tenant.user_id,
            details={key: None if value is None else str(value) for key, value in details.items()} or None,
        )

    def active_worker(self, worker_id):
        worker = self.get(WorkforceMember, worker_id, lock=True)
        if worker.status != WorkforceMemberStatus.ACTIVE:
            raise ValueError("Workforce member is not active")
        return worker

    def members(self, row):
        model, field = (ShiftRosterMember, "shift_roster_id") if isinstance(row, ShiftRoster) else (ProductionRunMember, "production_run_id")
        return self.repo.list(model, **{field: row.id})

    def present(self, row):
        result = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        result["members"] = []
        for member in self.members(row):
            worker = self.lookup(WorkforceMember, member.workforce_member_id)
            result["members"].append({**{c.name: getattr(member, c.name) for c in member.__table__.columns}, "workforce_name": worker.full_name, "employee_code": worker.employee_code})
        result["team_count"] = len(result["members"])
        shift_id = row.shift_definition_id
        result["shift_name"] = self.lookup(ShiftDefinition, shift_id).name if shift_id else None
        if isinstance(row, ProductionRun):
            result["work_center_name"] = self.lookup(WorkCenter, row.work_center_id).name
        else:
            today = self.today()
            result["period_state"] = "upcoming" if row.effective_from > today else "ended" if row.effective_to and row.effective_to < today else "current"
            result["members_editable"] = self.roster_members_editable(row)
        return result

    def rosters(self, shift_definition_id=None, workforce_member_id=None, date_from=None, date_to=None):
        q = self.repo.query(ShiftRoster)
        if shift_definition_id:
            q = q.where(ShiftRoster.shift_definition_id == shift_definition_id)
        if date_from:
            q = q.where(or_(ShiftRoster.effective_to.is_(None), ShiftRoster.effective_to >= date_from))
        if date_to:
            q = q.where(ShiftRoster.effective_from <= date_to)
        if workforce_member_id:
            ids = self.repo.query(ShiftRosterMember).with_only_columns(ShiftRosterMember.shift_roster_id).where(ShiftRosterMember.workforce_member_id == workforce_member_id)
            q = q.where(ShiftRoster.id.in_(ids))
        return list(self.db.scalars(q.order_by(ShiftRoster.effective_from, ShiftRoster.id)))

    def check_worker_rosters(self, worker_id, effective_from, effective_to, exclude_roster_id=None):
        # A worker belongs to one planned team at a time; moving shifts means closing or replacing the old roster.
        overlapping = [r for r in self.rosters(workforce_member_id=worker_id, date_from=effective_from, date_to=effective_to) if r.id != exclude_roster_id]
        if overlapping:
            raise ValueError("Worker is already on an overlapping roster; close or replace that roster first")

    def _create_roster(self, data):
        self.get(ShiftDefinition, data.shift_definition_id, lock=True)
        overlaps = self.rosters(data.shift_definition_id, date_from=data.effective_from, date_to=data.effective_to)
        if overlaps:
            raise ValueError("Roster periods for a shift cannot overlap; replace the existing roster")
        ids = [m.workforce_member_id for m in data.members]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate roster member")
        for worker_id in ids:
            self.active_worker(worker_id)
            self.check_worker_rosters(worker_id, data.effective_from, data.effective_to)
        roster = self.add(ShiftRoster, **data.model_dump(exclude={"members"}))
        for member in data.members:
            self.add(ShiftRosterMember, shift_roster_id=roster.id, **member.model_dump())
        return roster

    def create_roster(self, data):
        roster = self._create_roster(data)
        self.audit("created", roster, effective_from=roster.effective_from, effective_to=roster.effective_to, members=len(data.members))
        return roster

    def replace_roster(self, roster_id, data):
        old = self.get(ShiftRoster, roster_id, lock=True)
        self.get(ShiftDefinition, old.shift_definition_id, lock=True)
        if data.shift_definition_id != old.shift_definition_id:
            raise ValueError("Replacement must use the same shift; create a roster on the destination shift separately")
        if old.status != "active" or data.effective_from <= old.effective_from or data.effective_from < self.today():
            raise ValueError("Replacement must start today or later and after the previous roster start")
        if old.effective_to and data.effective_from > old.effective_to + timedelta(days=1):
            raise ValueError("Replacement cannot extend a closed historical period")
        cutoff = data.effective_from - timedelta(days=1)
        self.check_roster_runs(old, cutoff)
        old.effective_to = cutoff
        old.status = "closed"
        self.db.flush()
        new = self._create_roster(data)
        self.audit("replaced", old, effective_to=cutoff, replacement_roster_id=new.id)
        self.audit("created", new, effective_from=new.effective_from, effective_to=new.effective_to, members=len(data.members), replaces_roster_id=old.id)
        return new

    def check_roster_runs(self, roster, cutoff):
        runs = self.repo.query(ProductionRun).where(ProductionRun.shift_roster_id == roster.id, ProductionRun.run_date > cutoff)
        if self.db.scalar(runs.limit(1)):
            raise ValueError("Roster period is referenced by a later run")

    def close_roster(self, roster_id, end):
        row = self.get(ShiftRoster, roster_id, lock=True)
        if row.status != "active" or end < row.effective_from or end < self.today() - timedelta(days=1):
            raise ValueError("Cannot rewrite a historical roster period")
        if row.effective_to and end > row.effective_to:
            raise ValueError("Cannot extend a roster using close")
        self.check_roster_runs(row, end)
        row.effective_to, row.status = end, "closed"
        self.db.flush()
        self.audit("closed", row, effective_to=end)
        return row

    def roster_members_editable(self, row):
        # The team stays editable until a run uses it; runs copy members, so their history is never rewritten.
        return row.status == "active" and self.db.scalar(self.repo.query(ProductionRun).where(ProductionRun.shift_roster_id == row.id).limit(1)) is None

    def set_roster_member(self, roster_id, data=None, member_id=None):
        row = self.get(ShiftRoster, roster_id, lock=True)
        if not self.roster_members_editable(row):
            raise ValueError("This team is already used by a production run or is closed; create a replacement roster to change it")
        if member_id:
            member = self.get(ShiftRosterMember, member_id)
            if member.shift_roster_id != row.id:
                raise HTTPException(404, "Member not found")
            self.db.delete(member)
            self.audit("member_removed", row, workforce_member_id=member.workforce_member_id)
        else:
            self.active_worker(data.workforce_member_id)
            if any(m.workforce_member_id == data.workforce_member_id for m in self.members(row)):
                raise ValueError("Duplicate roster member")
            self.check_worker_rosters(data.workforce_member_id, row.effective_from, row.effective_to, exclude_roster_id=row.id)
            self.add(ShiftRosterMember, shift_roster_id=row.id, **data.model_dump())
            self.audit("member_added", row, workforce_member_id=data.workforce_member_id)
        self.db.flush()
        return row

    def runs(self, production_order_id=None, workforce_member_id=None):
        q = self.repo.query(ProductionRun)
        if production_order_id:
            q = q.where(ProductionRun.production_order_id == production_order_id)
        if workforce_member_id:
            ids = self.repo.query(ProductionRunMember).with_only_columns(ProductionRunMember.production_run_id).where(ProductionRunMember.workforce_member_id == workforce_member_id)
            q = q.where(ProductionRun.id.in_(ids))
        return list(self.db.scalars(q.order_by(ProductionRun.run_date, ProductionRun.id)))

    def runnable_order(self, order_id):
        # Locked: order cancellation holds this row lock while it checks execution evidence.
        order = self.get(ProductionOrder, order_id, lock=True)
        if order.status not in RUNNABLE_ORDER_STATUSES:
            raise ValueError("Runs are only allowed for draft, released or in-progress production orders")
        return order

    def create_run(self, data):
        self.runnable_order(data.production_order_id)
        self.get(WorkCenter, data.work_center_id)
        shift_id = data.shift_definition_id
        if shift_id:
            self.get(ShiftDefinition, shift_id)
        if data.shift_roster_id:
            roster = self.get(ShiftRoster, data.shift_roster_id, lock=True)
            if shift_id and shift_id != roster.shift_definition_id:
                raise ValueError("Roster and shift do not match")
            if data.run_date < roster.effective_from or (roster.effective_to and data.run_date > roster.effective_to):
                raise ValueError("Roster is not effective on run date")
            shift_id = roster.shift_definition_id
        values = data.model_dump(exclude={"members"})
        values["shift_definition_id"] = shift_id
        row = self.add(ProductionRun, created_by_user_id=self.tenant.user_id, **values)
        for member in data.members:
            self._add_run_member(row, member)
        self.audit("created", row, production_order_id=row.production_order_id, run_date=row.run_date, members=len(data.members))
        return row

    def editable_run(self, run_id):
        row = self.get(ProductionRun, run_id, lock=True)
        if row.status in ("completed", "cancelled"):
            raise ValueError("Terminal run is immutable")
        return row

    def update_run(self, run_id, data):
        row = self.editable_run(run_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(row, field, value)
        self.db.flush()
        self.audit("updated", row, fields=",".join(sorted(changes)))
        return row

    def participation_values(self, run, data, current=None):
        values = data.model_dump()
        if run.status == "planned":
            if values["started_at"] or values["ended_at"]:
                raise ValueError("Participation times are recorded after the run starts")
            return values
        if values["started_at"] is None:
            values["started_at"] = current.started_at if current else utc_now()
        if run.started_at and values["started_at"] < run.started_at:
            raise ValueError("Participation cannot start before the run started")
        if values["ended_at"] and values["ended_at"] < values["started_at"]:
            raise ValueError("Invalid participation time window")
        return values

    def _add_run_member(self, row, data):
        self.active_worker(data.workforce_member_id)
        values = self.participation_values(row, data)
        previous = [m for m in self.members(row) if m.workforce_member_id == data.workforce_member_id]
        if any(m.ended_at is None for m in previous) or (previous and row.status == "planned"):
            raise ValueError("Duplicate run member")
        if any(values["started_at"] < m.ended_at for m in previous):
            raise ValueError("Participation overlaps an earlier participation of this worker")
        return self.add(ProductionRunMember, production_run_id=row.id, **values)

    def set_run_member(self, run_id, data=None, member_id=None):
        row = self.editable_run(run_id)
        if member_id:
            member = self.get(ProductionRunMember, member_id)
            if member.production_run_id != row.id:
                raise HTTPException(404, "Member not found")
            if data:
                if data.workforce_member_id != member.workforce_member_id:
                    raise ValueError("Cannot replace participation identity")
                for field, value in self.participation_values(row, data, member).items():
                    setattr(member, field, value)
                self.audit("member_updated", row, workforce_member_id=member.workforce_member_id, started_at=member.started_at, ended_at=member.ended_at)
            else:
                if row.status != "planned":
                    raise ValueError("After starting, end participation instead of deleting it")
                self.db.delete(member)
                self.audit("member_removed", row, workforce_member_id=member.workforce_member_id)
        else:
            member = self._add_run_member(row, data)
            self.audit("member_added", row, workforce_member_id=member.workforce_member_id, started_at=member.started_at)
        self.db.flush()
        return row

    def load_roster(self, run_id):
        row = self.editable_run(run_id)
        if row.status != "planned" or not row.shift_roster_id:
            raise ValueError("Load a roster only on a planned run with a roster")
        roster = self.get(ShiftRoster, row.shift_roster_id, lock=True)
        existing = {m.workforce_member_id for m in self.members(row)}
        loaded, skipped = 0, 0
        for member in self.members(roster):
            if member.workforce_member_id in existing:
                continue
            # Planned teams may include workers who have since left; the actual team takes only active ones.
            if self.get(WorkforceMember, member.workforce_member_id).status != WorkforceMemberStatus.ACTIVE:
                skipped += 1
                continue
            self._add_run_member(row, RunMemberInput(workforce_member_id=member.workforce_member_id, role_code="operator", is_lead=member.is_shift_lead, notes=member.role_note))
            loaded += 1
        self.audit("roster_loaded", row, shift_roster_id=roster.id, loaded=loaded, skipped_inactive=skipped)
        return row

    def transition(self, run_id, action):
        row = self.get(ProductionRun, run_id, lock=True)
        allowed = {"start": ({"planned", "paused"}, "in_progress"), "pause": ({"in_progress"}, "paused"), "complete": ({"in_progress", "paused"}, "completed"), "cancel": ({"planned", "in_progress", "paused"}, "cancelled")}
        states, target = allowed[action]
        if row.status not in states:
            raise ValueError("Invalid run status transition")
        if action == "start":
            self.runnable_order(row.production_order_id)
        now = utc_now()
        if action == "start" and row.started_at is None:
            row.started_at = now
            for member in self.members(row):
                if member.started_at is None and member.ended_at is None:
                    member.started_at = now
        if target in ("completed", "cancelled") and row.started_at:
            row.ended_at = now
            for member in self.members(row):
                if member.started_at is not None and member.ended_at is None:
                    member.ended_at = now
        previous, row.status = row.status, target
        self.db.flush()
        self.audit(TRANSITION_EVENTS[action], row, from_status=previous, to_status=target)
        return row
