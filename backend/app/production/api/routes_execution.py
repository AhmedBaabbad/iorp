from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.api.execution_schemas import RosterCreate, RosterClose, RosterMemberInput, RunCreate, RunUpdate, RunMemberInput
from app.production.application.execution_service import ExecutionService
from app.production.infrastructure.execution_models import ShiftRoster, ProductionRun

router = APIRouter(tags=["production-execution"])

def execute(db, tenant, operation):
    service = ExecutionService(db, tenant)
    try:
        result = operation(service)
        response = [service.present(row) for row in result] if isinstance(result, list) else service.present(result)
        db.commit()
        return response
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(400, str(exc) if isinstance(exc, ValueError) else "Conflicting or referenced execution record") from exc
    except Exception:
        db.rollback()
        raise


@router.get("/shift-rosters", dependencies=[Depends(require_permission("production:shift_rosters:read"))])
def list_rosters(shift_definition_id: UUID | None = None, workforce_member_id: UUID | None = None, date_from: date | None = None, date_to: date | None = None, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.rosters(shift_definition_id, workforce_member_id, date_from, date_to))


@router.post("/shift-rosters", dependencies=[Depends(require_permission("production:shift_rosters:create")), Depends(require_permission("production:shift_rosters:manage_members"))], status_code=201)
def create_roster(payload: RosterCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.create_roster(payload))


@router.get("/shift-rosters/{roster_id}", dependencies=[Depends(require_permission("production:shift_rosters:read"))])
def get_roster(roster_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.get(ShiftRoster, roster_id))


@router.post("/shift-rosters/{roster_id}/replace", dependencies=[Depends(require_permission("production:shift_rosters:update")), Depends(require_permission("production:shift_rosters:manage_members"))])
def replace_roster(roster_id: UUID, payload: RosterCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.replace_roster(roster_id, payload))


@router.post("/shift-rosters/{roster_id}/close", dependencies=[Depends(require_permission("production:shift_rosters:update"))])
def close_roster(roster_id: UUID, payload: RosterClose, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.close_roster(roster_id, payload.effective_to))


@router.post("/shift-rosters/{roster_id}/members", dependencies=[Depends(require_permission("production:shift_rosters:manage_members"))])
def add_roster_member(roster_id: UUID, payload: RosterMemberInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.set_roster_member(roster_id, payload))


@router.delete("/shift-rosters/{roster_id}/members/{member_id}", dependencies=[Depends(require_permission("production:shift_rosters:manage_members"))])
def remove_roster_member(roster_id: UUID, member_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.set_roster_member(roster_id, member_id=member_id))


@router.get("/runs", dependencies=[Depends(require_permission("production:runs:read"))])
def list_runs(production_order_id: UUID | None = None, workforce_member_id: UUID | None = None, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.runs(production_order_id, workforce_member_id))


@router.post("/runs", dependencies=[Depends(require_permission("production:runs:create")), Depends(require_permission("production:runs:manage_members"))], status_code=201)
def create_run(payload: RunCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.create_run(payload))


@router.get("/runs/{run_id}", dependencies=[Depends(require_permission("production:runs:read"))])
def get_run(run_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.get(ProductionRun, run_id))


@router.patch("/runs/{run_id}", dependencies=[Depends(require_permission("production:runs:update"))])
def update_run(run_id: UUID, payload: RunUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.update_run(run_id, payload))


@router.post("/runs/{run_id}/load-roster-members", dependencies=[Depends(require_permission("production:runs:manage_members"))])
def load_roster(run_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.load_roster(run_id))


@router.post("/runs/{run_id}/members", dependencies=[Depends(require_permission("production:runs:manage_members"))])
def add_run_member(run_id: UUID, payload: RunMemberInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.set_run_member(run_id, payload))


@router.put("/runs/{run_id}/members/{member_id}", dependencies=[Depends(require_permission("production:runs:manage_members"))])
def update_run_member(run_id: UUID, member_id: UUID, payload: RunMemberInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.set_run_member(run_id, payload, member_id))


@router.delete("/runs/{run_id}/members/{member_id}", dependencies=[Depends(require_permission("production:runs:manage_members"))])
def remove_run_member(run_id: UUID, member_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.set_run_member(run_id, member_id=member_id))


@router.post("/runs/{run_id}/start", dependencies=[Depends(require_permission("production:runs:start"))])
def start_run(run_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.transition(run_id, "start"))


@router.post("/runs/{run_id}/pause", dependencies=[Depends(require_permission("production:runs:pause"))])
def pause_run(run_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.transition(run_id, "pause"))


@router.post("/runs/{run_id}/complete", dependencies=[Depends(require_permission("production:runs:complete"))])
def complete_run(run_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.transition(run_id, "complete"))


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(require_permission("production:runs:cancel"))])
def cancel_run(run_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return execute(db, tenant, lambda s: s.transition(run_id, "cancel"))
