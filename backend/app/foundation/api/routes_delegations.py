"""Approval delegations (PROJECT-GOV-004): who may sign which approval for whom, and until when — governed: each
delegation is in force only once the other side agrees (domain/delegations.py)."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, page_params
from app.dependencies import CurrentUserContext, get_db, require_any_permission
from app.foundation.application.delegation_service import DelegationService
from app.foundation.domain import delegations as D
from app.foundation.domain.delegations import DelegationError

router = APIRouter(prefix="/delegations", tags=["approval-delegations"])
# Whoever holds an approval that can be delegated (their own), reads or manages delegations; the service checks the rest.
ANY = require_any_permission([D.READ, D.MANAGE, *D.DELEGABLE])


class DelegationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delegator_user_id: UUID
    delegate_user_id: UUID
    permission_code: str = Field(min_length=1, max_length=120)
    effective_from: date
    effective_to: date
    reason: str = Field(min_length=1, max_length=2000)


class Reason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="", max_length=2000)


def _service(current: CurrentUserContext, db: Session) -> DelegationService:
    return DelegationService(db, current.tenant, current.auth_user.permissions)


def _run(fn):
    try:
        return fn()
    except DelegationError as exc:
        raise HTTPException(exc.status, detail=exc.code) from exc


@router.get("")
def listing(state: str | None = Query(None, pattern="^(waiting|lapsed|scheduled|active|ended|rejected|revoked)$"),
            search: str | None = Query(None, max_length=120), params: PageParams = Depends(page_params),
            current: CurrentUserContext = Depends(ANY), db: Session = Depends(get_db)):
    """One page of delegations (ARCH-PAGE-001), filtered by state and by a person's name."""
    return _service(current, db).page(params, state, search)


@router.get("/options")
def options(current: CurrentUserContext = Depends(ANY), db: Session = Depends(get_db)):
    return _service(current, db).options()


@router.get("/waiting")
def waiting(current: CurrentUserContext = Depends(ANY), db: Session = Depends(get_db)):
    """What waits for this user's answer: the number on the menu and the list at the top of the page."""
    return _service(current, db).waiting()


@router.post("", status_code=201)
def create(data: DelegationCreate, current: CurrentUserContext = Depends(ANY), db: Session = Depends(get_db)):
    return _run(lambda: _service(current, db).create(data))


@router.post("/{delegation_id}/approve")
def approve(delegation_id: UUID, data: Reason, current: CurrentUserContext = Depends(ANY), db: Session = Depends(get_db)):
    return _run(lambda: _service(current, db).answer(delegation_id, True, data.reason))


@router.post("/{delegation_id}/reject")
def reject(delegation_id: UUID, data: Reason, current: CurrentUserContext = Depends(ANY), db: Session = Depends(get_db)):
    return _run(lambda: _service(current, db).answer(delegation_id, False, data.reason))


@router.post("/{delegation_id}/revoke")
def revoke(delegation_id: UUID, data: Reason, current: CurrentUserContext = Depends(ANY), db: Session = Depends(get_db)):
    if not data.reason.strip():
        raise HTTPException(422, detail="REASON_REQUIRED")
    return _run(lambda: _service(current, db).revoke(delegation_id, data.reason))
